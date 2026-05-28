import sqlite3
from datetime import datetime
from modules.storage import connect, init_db
from modules.helpers import print_lg

def has_cold_email_been_sent(application_id: str, recipient_email: str, conn: sqlite3.Connection | None = None) -> bool:
    """Returns True if a cold email has already been successfully sent to this recipient for this application."""
    close = conn is None
    conn = conn or connect()
    init_db(conn) # Use centralized init
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM cold_emails WHERE application_id = ? AND recipient_email = ? AND status = 'sent'",
            (application_id, recipient_email)
        )
        row = cursor.fetchone()
        return row is not None
    except Exception as e:
        print_lg(f"Error checking cold email status: {e}")
        return False
    finally:
        if close:
            conn.close()

def record_cold_email(
    application_id: str,
    recipient_email: str,
    subject: str | None,
    status: str,
    sent_at: str | None,
    error: str | None,
    generated_by: str | None,
    recruiter_email_source: str | None,
    recruiter_email_confidence: float | None,
    conn: sqlite3.Connection | None = None,
    runtime_batch_id: str | None = None
) -> None:
    """Inserts or updates the status of a cold email outreach in the database."""
    close = conn is None
    conn = conn or connect()
    init_db(conn) # Use centralized init
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            """
            INSERT INTO cold_emails (
                application_id, recipient_email, subject, status, sent_at, error,
                generated_by, recruiter_email_source, recruiter_email_confidence, runtime_batch_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(application_id, recipient_email) DO UPDATE SET
                status = excluded.status,
                sent_at = excluded.sent_at,
                error = excluded.error,
                subject = COALESCE(excluded.subject, cold_emails.subject),
                generated_by = COALESCE(excluded.generated_by, cold_emails.generated_by),
                recruiter_email_source = COALESCE(excluded.recruiter_email_source, cold_emails.recruiter_email_source),
                recruiter_email_confidence = COALESCE(excluded.recruiter_email_confidence, cold_emails.recruiter_email_confidence),
                runtime_batch_id = COALESCE(excluded.runtime_batch_id, cold_emails.runtime_batch_id)
            """,
            (
                application_id, recipient_email, subject, status, sent_at, error,
                generated_by, recruiter_email_source, recruiter_email_confidence, runtime_batch_id, now
            )
        )
        conn.commit()
    except Exception as e:
        print_lg(f"Error recording cold email in SQLite: {e}")
    finally:
        if close:
            conn.close()

def get_cold_email_stats(conn: sqlite3.Connection | None = None) -> dict:
    """Returns summary statistics of cold email outreach."""
    close = conn is None
    conn = conn or connect()
    init_db(conn) # Use centralized init
    stats = {"total": 0, "sent": 0, "failed": 0, "pending": 0, "skipped": 0}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM cold_emails GROUP BY status")
        rows = cursor.fetchall()
        for row in rows:
            status = row[0]
            count = row[1]
            stats["total"] += count
            if status in stats:
                stats[status] = count
    except Exception as e:
        print_lg(f"Error getting cold email stats: {e}")
    finally:
        if close:
            conn.close()
    return stats
