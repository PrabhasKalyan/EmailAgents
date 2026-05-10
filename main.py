"""APScheduler entry point. Wires daily_send, followup, reply_check."""
import logging
import sys
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cron.daily_send import run as daily_send
from cron.followup import run as followup
from cron.reply_check import run_once as reply_check_once
from config import SEND_WINDOW_START_HOUR_EST, SEND_WINDOW_END_HOUR_EST
from db.database import init_db, sent_count_today


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
# Silence chatty third-party loggers — every HTTP response and every
# search-engine fallback was leaking through at INFO.
for noisy in ("primp", "ddgs", "ddgs.ddgs", "urllib3", "httpx"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

EST = ZoneInfo("America/New_York")


def _catchup():
    """Run daily_send + followup once on startup IF inside send window and nothing sent today."""
    now = datetime.now(EST)
    if not (SEND_WINDOW_START_HOUR_EST <= now.hour < SEND_WINDOW_END_HOUR_EST):
        print(f"Catch-up skipped: {now.strftime('%H:%M')} EST is outside send window.")
        return
    if sent_count_today() > 0:
        print(f"Catch-up skipped: {sent_count_today()} sends already logged for today.")
        return
    print(f"Catch-up: starting at {now.strftime('%H:%M')} EST, running daily_send + followup now.")
    try:
        daily_send()
    except Exception as e:
        print(f"catch-up daily_send failed: {e}")
    try:
        followup()
    except Exception as e:
        print(f"catch-up followup failed: {e}")


def main():
    init_db()
    sched = BlockingScheduler(timezone="America/New_York")
    sched.add_job(daily_send, CronTrigger(hour=9, minute=0), id="daily_send",
                  max_instances=1, coalesce=True)
    sched.add_job(followup, CronTrigger(hour=9, minute=15), id="followup",
                  max_instances=1, coalesce=True)
    sched.add_job(reply_check_once, IntervalTrigger(minutes=15), id="reply_check",
                  max_instances=1, coalesce=True)
    print("Scheduler started. Jobs: daily_send (9:00 EST), followup (9:15 EST), reply_check (15m)")
    threading.Thread(target=_catchup, daemon=True, name="catchup").start()
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()
