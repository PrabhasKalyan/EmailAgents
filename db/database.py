import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_PATH = os.environ.get("OUTREACH_DB_PATH", os.path.join(os.path.dirname(__file__), "outreach.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    with open(SCHEMA_PATH) as f:
        schema = f.read()
    with get_conn() as conn:
        conn.executescript(schema)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- companies ----------

def insert_company(name, domain, ceo_email, role=None, description=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO companies (name, domain, ceo_email, role, description)
               VALUES (?, ?, ?, ?, ?)""",
            (name, domain, ceo_email, role, description),
        )
        return cur.lastrowid


def get_company(company_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return dict(row) if row else None


def update_company_enrichment(company_id, description, news_headline):
    with get_conn() as conn:
        conn.execute(
            "UPDATE companies SET description = ?, news_headline = ? WHERE id = ?",
            (description, news_headline, company_id),
        )


def update_company_score(company_id, fit_score):
    with get_conn() as conn:
        conn.execute("UPDATE companies SET fit_score = ? WHERE id = ?", (fit_score, company_id))


def update_company_status(company_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE companies SET status = ? WHERE id = ?", (status, company_id))


def companies_needing_enrichment(limit=None):
    q = "SELECT * FROM companies WHERE (news_headline IS NULL OR description IS NULL OR description = '')"
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def companies_needing_scoring(limit=None):
    q = "SELECT * FROM companies WHERE fit_score = 'Unscored'"
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q).fetchall()]


def companies_ready_to_send(limit=None):
    """High/Medium fit, status pending, no email sent today, no email yet at all."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    q = """
        SELECT c.* FROM companies c
        WHERE c.fit_score IN ('High', 'Medium')
          AND c.status = 'pending'
          AND NOT EXISTS (
              SELECT 1 FROM emails_sent e
              WHERE e.company_id = c.id AND DATE(e.sent_at) = ?
          )
        ORDER BY CASE c.fit_score WHEN 'High' THEN 0 ELSE 1 END, c.id
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, (today,)).fetchall()]


def companies_active_for_followup():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM companies WHERE status = 'active'"
        ).fetchall()]


def domain_emailed_today(domain):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute(
            """SELECT 1 FROM emails_sent e
               JOIN companies c ON c.id = e.company_id
               WHERE c.domain = ? AND DATE(e.sent_at) = ? LIMIT 1""",
            (domain, today),
        ).fetchone()
        return row is not None


# ---------- follow_ups (the generator's storage) ----------

def save_generated_emails(company_id, payload):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO follow_ups
               (company_id, initial_subject, initial_body,
                day3_subject, day3_body, day6_subject, day6_body, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                company_id,
                payload["initial_subject"], payload["initial_body"],
                payload["day3_subject"], payload["day3_body"],
                payload["day6_subject"], payload["day6_body"],
            ),
        )


def get_generated_emails(company_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM follow_ups WHERE company_id = ?", (company_id,)
        ).fetchone()
        return dict(row) if row else None


def mark_followup_sent(company_id, day_number):
    col = "day3_sent_at" if day_number == 3 else "day6_sent_at"
    with get_conn() as conn:
        conn.execute(
            f"UPDATE follow_ups SET {col} = CURRENT_TIMESTAMP WHERE company_id = ?",
            (company_id,),
        )


# ---------- emails_sent ----------

def log_email_sent(company_id, gmail_account, subject, body, thread_id, message_id, day_number=1):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO emails_sent
               (company_id, gmail_account, subject, body, sent_at, thread_id, message_id, day_number)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)""",
            (company_id, gmail_account, subject, body, thread_id, message_id, day_number),
        )
        return cur.lastrowid


def find_email_by_thread(thread_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM emails_sent WHERE thread_id = ? ORDER BY sent_at DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None


def first_email_for_company(company_id):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM emails_sent WHERE company_id = ? AND day_number = 1
               ORDER BY sent_at ASC LIMIT 1""",
            (company_id,),
        ).fetchone()
        return dict(row) if row else None


# ---------- account daily counts ----------

def get_account_count(gmail_account, send_date=None):
    send_date = send_date or _today_est()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT count FROM account_daily_counts WHERE gmail_account = ? AND send_date = ?",
            (gmail_account, send_date),
        ).fetchone()
        return row["count"] if row else 0


def increment_account_count(gmail_account, send_date=None):
    send_date = send_date or _today_est()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO account_daily_counts (gmail_account, send_date, count)
               VALUES (?, ?, 1)
               ON CONFLICT(gmail_account, send_date) DO UPDATE SET count = count + 1""",
            (gmail_account, send_date),
        )


def _today_est():
    # APScheduler runs in EST per main.py — match that for the daily counter
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


# ---------- replies ----------

def save_reply(company_id, email_sent_id, reply_from, reply_subject, reply_snippet,
               classification, gmail_thread_url):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO replies
               (company_id, email_sent_id, reply_from, reply_subject, reply_snippet,
                classification, gmail_thread_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (company_id, email_sent_id, reply_from, reply_subject, reply_snippet,
             classification, gmail_thread_url),
        )
        return cur.lastrowid


def reply_exists_for_thread(thread_id):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT 1 FROM replies r
               JOIN emails_sent e ON e.id = r.email_sent_id
               WHERE e.thread_id = ? LIMIT 1""",
            (thread_id,),
        ).fetchone()
        return row is not None


def mark_reply_notified(reply_id):
    with get_conn() as conn:
        conn.execute("UPDATE replies SET notified = 1 WHERE id = ?", (reply_id,))


def unnotified_replies():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM replies WHERE notified = 0"
        ).fetchall()]


# ---------- dashboard stats ----------

def dashboard_stats():
    with get_conn() as conn:
        sent = conn.execute(
            "SELECT COUNT(*) AS c FROM emails_sent WHERE day_number = 1"
        ).fetchone()["c"]
        replied = conn.execute(
            "SELECT COUNT(DISTINCT company_id) AS c FROM replies"
        ).fetchone()["c"]
        positive = conn.execute(
            "SELECT COUNT(*) AS c FROM replies WHERE classification = 'Positive'"
        ).fetchone()["c"]
        negative = conn.execute(
            "SELECT COUNT(*) AS c FROM replies WHERE classification = 'Negative'"
        ).fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM companies WHERE status = 'active'"
        ).fetchone()["c"]
        positives = [dict(r) for r in conn.execute(
            """SELECT c.name AS company, r.gmail_thread_url AS url, r.received_at AS at
               FROM replies r JOIN companies c ON c.id = r.company_id
               WHERE r.classification = 'Positive' ORDER BY r.received_at DESC"""
        ).fetchall()]
    return {
        "sent": sent, "replied": replied,
        "positive": positive, "negative": negative, "pending": pending,
        "positives": positives,
    }
