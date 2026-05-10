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


CONTEXT_PATH = os.environ.get(
    "PRABHAS_CONTEXT_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "prabhas_context.md"),
)

with open(CONTEXT_PATH, encoding="utf-8") as _f:
    PRABHAS_CONTEXT = _f.read()


SYSTEM_PROMPT = f"""You are writing cold emails on behalf of Prabhas Kalyan.
Below is his complete background, projects, skills, and the outreach style
guide he wants you to follow. Treat it as authoritative; never invent
projects or claims that aren't in it.

================ PRABHAS CONTEXT (source of truth) ================
{PRABHAS_CONTEXT}
================ END CONTEXT ================

Return a JSON object with exactly these keys:
{{
  "initial_subject": "...",
  "initial_body": "...",
  "day3_subject": "...",
  "day3_body": "...",
  "day6_subject": "...",
  "day6_body": "..."
}}
The day3_* slot holds the Day-1 follow-up. The day6_* slot holds the
Day-2 breakup. Names are kept for backward compatibility with the DB
schema. Return only the JSON. No explanation. No markdown."""


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
