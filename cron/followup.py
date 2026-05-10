"""Day 3 / Day 6 follow-ups + Day 7 dead-marker."""
import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import (
    companies_active_for_followup,
    first_email_for_company,
    get_generated_emails,
    update_company_status,
)
from modules.sender import send_followup
from config import SEND_DELAY_MIN, SEND_DELAY_MAX


def _days_since(ts_str):
    if not ts_str:
        return None
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def run():
    rows = companies_active_for_followup()
    print(f"Active threads: {len(rows)}")
    for c in rows:
        first = first_email_for_company(c["id"])
        if not first:
            continue
        days = _days_since(first["sent_at"])
        if days is None:
            continue

        gen = get_generated_emails(c["id"])
        if days >= 3:
            update_company_status(c["id"], "dead")
            print(f"dead: {c['name']} ({days}d, no reply)")
            continue
        if days >= 2 and gen and not gen.get("day6_sent_at"):
            try:
                if send_followup(c["id"], 6):
                    time.sleep(random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX))
            except Exception as e:
                print(f"breakup failed for {c['name']}: {e}")
            continue
        if days >= 1 and gen and not gen.get("day3_sent_at"):
            try:
                if send_followup(c["id"], 3):
                    time.sleep(random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX))
            except Exception as e:
                print(f"followup failed for {c['name']}: {e}")


if __name__ == "__main__":
    run()
