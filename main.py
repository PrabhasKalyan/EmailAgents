"""APScheduler entry point. Wires daily_send, followup, reply_check."""
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cron.daily_send import run as daily_send
from cron.followup import run as followup
from cron.reply_check import run_once as reply_check_once
from db.database import init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)


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
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()
