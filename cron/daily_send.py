"""Morning batch: pick eligible companies, generate emails if missing, send."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import companies_ready_to_send, get_generated_emails
from modules.generator import generate_for_company
from modules.sender import send_batch
from config import GMAIL_ACCOUNTS, PER_ACCOUNT_DAILY_LIMIT


def run():
    daily_cap = max(1, len(GMAIL_ACCOUNTS)) * PER_ACCOUNT_DAILY_LIMIT
    candidates = companies_ready_to_send(limit=daily_cap)
    print(f"Eligible today: {len(candidates)} (cap={daily_cap})")

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
