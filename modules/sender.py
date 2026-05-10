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

def send_initial(company_id):
    company = get_company(company_id)
    if not company:
        return None
    if company.get("status") in ("dead", "replied"):
        return None
    if domain_emailed_today(company.get("domain")):
        return None

    gen = get_generated_emails(company_id)
    if not gen or not gen.get("initial_subject"):
        return None

    account = _pick_account()
    if account is None:
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


def send_followup(company_id, day_number):
    """day_number = 3 or 6"""
    company = get_company(company_id)
    if not company or company.get("status") in ("dead", "replied"):
        return None

    gen = get_generated_emails(company_id)
    if not gen:
        return None
    subj = gen.get(f"day{day_number}_subject")
    body = gen.get(f"day{day_number}_body")
    if not subj or not body:
        return None

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
    """Walk a list of company IDs, sending initials with random delays.
    Stops when the EST window closes or all accounts are full."""
    sent = 0
    for cid in company_ids:
        if not _in_send_window():
            print("Outside EST send window; stopping.")
            break
        if _pick_account() is None:
            print("All accounts at daily cap; stopping.")
            break
        try:
            r = send_initial(cid)
        except Exception as e:
            print(f"send_initial({cid}) failed: {e}")
            r = None
        if r:
            sent += 1
            time.sleep(random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX))
    print(f"Batch complete. Sent: {sent}")
    return sent
