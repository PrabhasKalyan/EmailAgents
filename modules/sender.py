"""
Gmail-API sender with 4-account rotation, plain-text only, EST send window,
domain-per-day dedupe, per-account daily cap, randomised inter-send delays.
"""
import base64
import os
import random
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GMAIL_ACCOUNTS,
    PER_ACCOUNT_DAILY_LIMIT,
    SEND_DELAY_MIN,
    SEND_DELAY_MAX,
    SEND_WINDOW_START_HOUR_EST,
    SEND_WINDOW_END_HOUR_EST,
)
from db.database import (
    log_email_sent,
    update_company_status,
    get_account_count,
    increment_account_count,
    domain_emailed_today,
    get_company,
    get_generated_emails,
    mark_followup_sent,
    first_email_for_company,
)
from modules.gmail_auth import gmail_service


EST = ZoneInfo("America/New_York")


def _in_send_window():
    now = datetime.now(EST)
    return SEND_WINDOW_START_HOUR_EST <= now.hour < SEND_WINDOW_END_HOUR_EST


def _pick_account():
    """Account with fewest sends today and under the cap. None if all are full."""
    best = None
    best_count = None
    for acc in GMAIL_ACCOUNTS:
        count = get_account_count(acc["address"])
        if count >= PER_ACCOUNT_DAILY_LIMIT:
            continue
        if best is None or count < best_count:
            best = acc
            best_count = count
    return best


def _build_message(sender, to, subject, body, thread_id=None):
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return payload


def _send_via(account, to, subject, body, thread_id=None):
    service = gmail_service(account["credentials_b64"])
    msg = _build_message(account["address"], to, subject, body, thread_id=thread_id)
    sent = service.users().messages().send(userId="me", body=msg).execute()
    return sent.get("id"), sent.get("threadId")


# --------- public API ----------

_domains_claimed_today = set()


def _send_initial_with(company_id, account):
    """Send an initial email using a specific account. Returns msg_id or None."""
    company = get_company(company_id)
    if not company:
        return None
    if company.get("status") in ("dead", "replied"):
        return None

    domain = (company.get("domain") or "").lower()
    if domain and (domain in _domains_claimed_today or domain_emailed_today(domain)):
        return None
    if domain:
        _domains_claimed_today.add(domain)

    gen = get_generated_emails(company_id)
    if not gen or not gen.get("initial_subject"):
        return None

    if get_account_count(account["address"]) >= PER_ACCOUNT_DAILY_LIMIT:
        return None

    msg_id, thread_id = _send_via(
        account, company["ceo_email"], gen["initial_subject"], gen["initial_body"]
    )
    log_email_sent(
        company_id, account["address"], gen["initial_subject"], gen["initial_body"],
        thread_id, msg_id, day_number=1,
    )
    increment_account_count(account["address"])
    update_company_status(company_id, "active")
    print(f"sent[{account['address']}] -> {company['ceo_email']} ({company['name']})")
    return msg_id


def send_initial(company_id):
    account = _pick_account()
    if account is None:
        return None
    return _send_initial_with(company_id, account)


def send_followup(company_id, day_number):
    """day_number is one of 1, 3, 5, 7, 9, 10."""
    company = get_company(company_id)
    if not company or company.get("status") in ("dead", "replied"):
        return None

    gen = get_generated_emails(company_id)
    if not gen:
        return None
    body = gen.get(f"f{day_number}_body")
    if not body:
        return None
    initial_subj = gen.get("initial_subject") or ""
    subj = initial_subj if initial_subj.lower().startswith("re:") else f"Re: {initial_subj}"

    first = first_email_for_company(company_id)
    if not first:
        return None

    account = next(
        (a for a in GMAIL_ACCOUNTS if a["address"] == first["gmail_account"]),
        None,
    )
    if account is None or get_account_count(account["address"]) >= PER_ACCOUNT_DAILY_LIMIT:
        return None

    msg_id, thread_id = _send_via(
        account, company["ceo_email"], subj, body, thread_id=first["thread_id"]
    )
    log_email_sent(
        company_id, account["address"], subj, body, thread_id, msg_id,
        day_number=day_number,
    )
    increment_account_count(account["address"])
    mark_followup_sent(company_id, day_number)
    print(f"day{day_number}[{account['address']}] -> {company['ceo_email']}")
    return msg_id


def send_batch(company_ids):
    """Burst-mode sender: every round, each Gmail account fires one email
    back-to-back (no inter-account delay — the HTTP calls take ~500ms each,
    so all N sends finish within ~N seconds). Then a single long sleep
    (SEND_DELAY_MIN..MAX) before the next round.

    Effect: from a recipient's perspective the 3 accounts send "at the same
    time", then everyone waits, then another burst. Done in a single process
    with no threads."""
    accounts = [a for a in GMAIL_ACCOUNTS if get_account_count(a["address"]) < PER_ACCOUNT_DAILY_LIMIT]
    if not accounts:
        print("All accounts at daily cap; nothing to send.")
        return 0
    if not company_ids:
        return 0

    _domains_claimed_today.clear()

    # Round-robin partition into per-account queues.
    buckets = {a["address"]: [] for a in accounts}
    for i, cid in enumerate(company_ids):
        acc = accounts[i % len(accounts)]
        buckets[acc["address"]].append(cid)

    counts = {a["address"]: 0 for a in accounts}
    total = 0
    round_num = 0

    while True:
        if not _in_send_window():
            print("Outside EST send window; stopping.")
            break

        live = [
            a for a in accounts
            if buckets[a["address"]]
            and get_account_count(a["address"]) < PER_ACCOUNT_DAILY_LIMIT
        ]
        if not live:
            break

        round_num += 1
        round_sent = 0
        for acc in live:
            addr = acc["address"]
            cid = buckets[addr].pop(0)
            try:
                r = _send_initial_with(cid, acc)
            except Exception as e:
                print(f"[{addr}] send_initial({cid}) failed: {e}")
                r = None
            if r:
                round_sent += 1
                counts[addr] += 1
                total += 1

        if round_sent == 0:
            continue
        delay = random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX)
        print(f"round {round_num}: burst of {round_sent}; sleeping {delay:.0f}s")
        time.sleep(delay)

    for addr, c in counts.items():
        print(f"[{addr}] sent {c}")
    print(f"Batch complete. Sent: {total}")
    return total
