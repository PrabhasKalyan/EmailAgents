"""
Reply detector. Polls every Gmail inbox, finds inbound messages whose
threadId matches an outbound email we logged, classifies the reply with
Gemini, and writes to the replies table. Updates company status so
follow-ups stop.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import (
    find_email_by_thread,
    reply_exists_for_thread,
    save_reply,
    update_company_status,
)
from modules.gmail_auth import all_services
from modules.gemini_client import complete_text


def _header(headers, name):
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def classify(reply_subject, snippet):
    prompt = f"""Classify this email reply as one of: Positive, Negative, Neutral.

Positive = interested, wants to meet, asks questions, asks for resume/portfolio.
Negative = not hiring, not interested, asks to stop emailing, complaint.
Neutral = auto-reply, out of office, vacation, autoresponder, generic acknowledgement.

Subject: {reply_subject or ""}
Body snippet: {snippet or ""}

Return only one word: Positive, Negative, or Neutral."""
    try:
        out = complete_text(prompt).strip().split()[0].rstrip(".,!").capitalize()
        return out if out in ("Positive", "Negative", "Neutral") else "Neutral"
    except Exception:
        return "Neutral"


def _process_message(service, account_address, msg_meta):
    msg_id = msg_meta["id"]
    thread_id = msg_meta.get("threadId")
    if not thread_id:
        return False

    outbound = find_email_by_thread(thread_id)
    if not outbound:
        return False
    if reply_exists_for_thread(thread_id):
        return False

    full = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["From", "Subject", "To"],
    ).execute()

    headers = full.get("payload", {}).get("headers", [])
    sender_addr = _header(headers, "From") or ""
    if account_address.lower() in sender_addr.lower():
        return False  # our own outbound, not a reply

    subject = _header(headers, "Subject") or ""
    snippet = full.get("snippet", "")

    classification = classify(subject, snippet)
    thread_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"

    save_reply(
        company_id=outbound["company_id"],
        email_sent_id=outbound["id"],
        reply_from=sender_addr,
        reply_subject=subject,
        reply_snippet=snippet,
        classification=classification,
        gmail_thread_url=thread_url,
    )

    if classification == "Negative":
        update_company_status(outbound["company_id"], "dead")
    else:
        update_company_status(outbound["company_id"], "replied")

    print(f"reply[{classification}] {sender_addr} :: {subject}")
    return True


def check_all_inboxes(lookback_hours=72):
    """Scan inboxes for inbound messages newer than lookback_hours."""
    since = int((datetime.now(timezone.utc).timestamp()) - lookback_hours * 3600)
    query = f"in:inbox newer_than:{max(1, lookback_hours // 24)}d"
    found = 0
    for address, service in all_services():
        try:
            resp = service.users().messages().list(
                userId="me", q=query, maxResults=100
            ).execute()
        except Exception as e:
            print(f"list failed for {address}: {e}")
            continue
        for m in resp.get("messages", []):
            try:
                if _process_message(service, address, m):
                    found += 1
            except Exception as e:
                print(f"process_message error for {address}: {e}")
    if found:
        print(f"Reply check complete: {found} new replies")
    return found


if __name__ == "__main__":
    check_all_inboxes()
