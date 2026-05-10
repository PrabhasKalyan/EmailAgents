"""Morning batch: enrich, score, generate, send.

The pipeline is self-sufficient — each morning it tops up enrichment and
scoring before pulling eligible companies. Volumes are capped to keep
Gemini and web-fetch usage bounded per day.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import companies_ready_to_send, get_generated_emails
from modules.enricher import enrich_batch
from modules.scorer import score_batch
from modules.generator import generate_for_company
from modules.sender import send_batch
from config import GMAIL_ACCOUNTS, PER_ACCOUNT_DAILY_LIMIT


# Daily refill caps. Keep these comfortably above the send cap so the
# eligible pool stays full, but bounded so Gemini quota and web-fetch
# load are predictable.
ENRICH_PER_DAY = int(os.environ.get("ENRICH_PER_DAY", "300"))
SCORE_PER_DAY = int(os.environ.get("SCORE_PER_DAY", "300"))


def run():
    daily_cap = max(1, len(GMAIL_ACCOUNTS)) * PER_ACCOUNT_DAILY_LIMIT

    print(f"=== enrichment (cap={ENRICH_PER_DAY}) ===")
    try:
        enrich_batch(limit=ENRICH_PER_DAY)
    except Exception as e:
        print(f"enrich_batch failed: {e}")

    print(f"=== scoring (cap={SCORE_PER_DAY}) ===")
    try:
        score_batch(limit=SCORE_PER_DAY)
    except Exception as e:
        print(f"score_batch failed: {e}")

    candidates = companies_ready_to_send(limit=daily_cap)
    print(f"=== send: eligible today {len(candidates)} (cap={daily_cap}) ===")

    for c in candidates:
        gen = get_generated_emails(c["id"])
        if not gen or not gen.get("initial_body"):
            try:
                generate_for_company(c["id"])
            except Exception as e:
                print(f"generate failed for {c['name']}: {e}")

    send_batch([c["id"] for c in candidates])


if __name__ == "__main__":
    run()
