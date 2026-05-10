"""
Generates initial + day3 + day6 emails per company via Gemini, stores in
follow_ups (initial subject/body live there too so the sender can read it
back without re-calling the LLM).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import save_generated_emails, get_generated_emails, get_company
from modules.gemini_client import complete_json


SYSTEM_PROMPT = """You are writing cold emails on behalf of Prabhas Kalyan, a final-year
Physics student at IIT Kharagpur (CGPA 8.4) looking for a remote SDE or AI Engineer role
at US companies.

His background:
- Built RAG systems with Pinecone, Text-to-SQL models, LLM agents at 4 internships
- Built AI video generation pipeline (Manim, MoviePy, OpenAI TTS)
- Built macOS Electron app with on-device LLMs, Ethereum AI agents on AWS
- Built fault tolerant mechanisms for financial agentic chatbot by finetuning transformer
  and bringing latency to 10ms and added a hybrid approach of inline memory and memzero
  + pg vector database for agent session persistence
- Stack: Python, Go, Node.js, React, Kafka, Docker, Kubernetes, PostgreSQL

Rules for the initial email:
- Plain text ONLY. No HTML. No bullet points. No formatting.
- Exactly 3 sentences. Not 2. Not 4.
- Sentence 1: One specific, genuine observation about their product or company (use the
  description and news headline provided). This must feel like you actually looked at
  their site.
- Sentence 2: One sentence connecting a specific project Prabhas built to their exact work.
- Sentence 3: Ask for a 15-minute call. Not "any openings". Not "I'd love to join".
- Never mention CGPA or college unless it's directly relevant.
- Subject line: 4-6 words, specific to the company, no generic phrases like
  "exciting opportunity".

Rules for the next-day follow-up (sent 1 day after the initial):
- 2 sentences only. Plain text.
- Completely different angle from email 1. Lead with a metric or result from his work.
- End with the same 15-min call ask.

Rules for the breakup email (sent 1 day after the follow-up):
- 2 sentences only.
- Sentence 1: acknowledge this is the last email.
- Sentence 2: wish them well with something specific they are building.
- No ask. Just leave the door open.

Return a JSON object with exactly these keys:
{
  "initial_subject": "...",
  "initial_body": "...",
  "day3_subject": "...",
  "day3_body": "...",
  "day6_subject": "...",
  "day6_body": "..."
}
Return only the JSON. No explanation. No markdown."""


def build_prompt(company):
    return f"""{SYSTEM_PROMPT}

Company: {company['name']}
Domain: {company.get('domain') or 'unknown'}
Role of recipient: {company.get('role') or 'CEO'}
Description: {company.get('description') or 'unknown'}
Recent news: {company.get('news_headline') or 'none'}
Fit score: {company.get('fit_score') or 'unknown'}
"""


REQUIRED_KEYS = (
    "initial_subject", "initial_body",
    "day3_subject", "day3_body",
    "day6_subject", "day6_body",
)


def generate_for_company(company_id, force=False):
    if not force:
        existing = get_generated_emails(company_id)
        if existing and existing.get("initial_body"):
            return existing
    company = get_company(company_id)
    if not company:
        raise ValueError(f"company {company_id} not found")
    prompt = build_prompt(company)
    payload = complete_json(prompt)
    missing = [k for k in REQUIRED_KEYS if not payload.get(k)]
    if missing:
        raise ValueError(f"Gemini response missing keys: {missing}")
    save_generated_emails(company_id, payload)
    print(f"Generated emails for {company['name']}")
    return payload


if __name__ == "__main__":
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out = generate_for_company(cid, force=True)
    for k, v in out.items():
        print(f"--- {k} ---")
        print(v)
