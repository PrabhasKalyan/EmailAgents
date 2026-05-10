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

HARD RULES (every single email must obey):
1. INTENT — Prabhas is asking for a remote SDE or AI engineer role
   (full-time or internship). The initial email MUST contain a clear,
   one-line ask for that role. Every follow-up must keep the same intent
   visible (don't pivot to "consulting" or "feedback").
2. IDENTITY — Sign every email "Prabhas" (just the first name) on its
   own line at the bottom. No --, no titles, no contact block.
3. BACKGROUND — Mention "IIT Kharagpur" or his year ONLY when it
   strengthens the hook (technical recipient, research-heavy company,
   academic angle). Do not paste a CV. Do not list multiple roles.
   Pick ONE concrete piece of evidence per email and weave it in.
4. METRICS — When you cite past work, use a concrete number from the
   context (latency, throughput, user count, etc.). Do not write vague
   phrases like "significantly reduced latency" without a number.
5. ROTATION — Across the 7 emails for one prospect, do NOT reuse the
   same project / metric / opener twice. Pull from different items in
   the context.
6. LENGTH — initial: 3 sentences max before the signoff. Each
   follow-up: 2 sentences max before the signoff. Subjects: 4-6 words,
   no emoji, no clickbait.
7. SPAM HYGIENE — no "RE:" tricks in subjects, no "URGENT", no all-caps,
   no link unless asked, no attachments mentioned.

Return a JSON object with EXACTLY these keys:
{{
  "initial_subject": "...",   "initial_body": "...",
  "f1_subject":  "...",       "f1_body":  "...",
  "f3_subject":  "...",       "f3_body":  "...",
  "f5_subject":  "...",       "f5_body":  "...",
  "f7_subject":  "...",       "f7_body":  "...",
  "f9_subject":  "...",       "f9_body":  "...",
  "f10_subject": "...",       "f10_body": "..."
}}

f1 = Day-1 bump (light, "wanted to make sure this didn't get lost").
f3 = Day-3 metric-led nudge with a different project than the initial.
f5 = Day-5 angle shift — focus on a problem the company is likely
     solving and how Prabhas can help.
f7 = Day-7 short and direct: "Is there a better person on your team to
     point me to for SDE / AI engineer hiring?"
f9 = Day-9 last-value email — share a concrete observation or idea
     about their product, no ask.
f10 = Day-10 breakup — "I'll stop here, best of luck", but keep the
      door open ("happy to reconnect later").

Return only the JSON. No explanation. No markdown fences."""


def build_prompt(company):
    return f"""{SYSTEM_PROMPT}

Company: {company['name']}
Domain: {company.get('domain') or 'unknown'}
Role of recipient: {company.get('role') or 'CEO'}
Description: {company.get('description') or 'unknown'}
Recent news: {company.get('news_headline') or 'none'}
Fit score: {company.get('fit_score') or 'unknown'}
"""


FOLLOWUP_DAYS = (1, 3, 5, 7, 9, 10)
REQUIRED_KEYS = ("initial_subject", "initial_body") + tuple(
    f"f{d}_{k}" for d in FOLLOWUP_DAYS for k in ("subject", "body")
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
