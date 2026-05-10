"""Daily follow-up cron. Sends f1/f3/f5/f7/f9/f10 once each, then marks dead."""
import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import (
    FOLLOWUP_DAYS,
    companies_active_for_followup,
    first_email_for_company,
    get_generated_emails,
    update_company_status,
)
from modules.sender import send_followup
from config import SEND_DELAY_MIN, SEND_DELAY_MAX


DEAD_AFTER_DAYS = max(FOLLOWUP_DAYS) + 1  # 11: one day after the breakup


def _days_since(ts_str):
    if not ts_str:
        return None
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def _due_day(days, gen):
    """Largest scheduled follow-up day that's due now and not yet sent."""
    for d in sorted(FOLLOWUP_DAYS, reverse=True):
        if days >= d and not gen.get(f"f{d}_sent_at"):
            return d
    return None


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
        if not gen:
            continue

        if days >= DEAD_AFTER_DAYS:
            update_company_status(c["id"], "dead")
            print(f"dead: {c['name']} ({days}d, no reply)")
            continue

        d = _due_day(days, gen)
        if d is None:
            continue
        try:
            if send_followup(c["id"], d):
                time.sleep(random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX))
        except Exception as e:
            print(f"f{d} failed for {c['name']}: {e}")


if __name__ == "__main__":
    run()
