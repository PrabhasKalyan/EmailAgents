"""15-min reply poll loop (used standalone or by APScheduler interval job)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.tracker import check_all_inboxes


def run_once():
    check_all_inboxes()


def run_forever(interval_seconds=900):
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"reply check error: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_forever()
