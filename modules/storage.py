from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from config.settings import file_name
from modules.helpers import APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA, LEGACY_COLUMN_ALIASES, normalize_row, print_lg


DB_PATH = os.path.join("data", "naukri_guru.sqlite3")
DETAILS_DIR = os.path.join("data", "job_descriptions")


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def serialize_value(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (set, tuple, list)):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    return value


def dumps_json(data) -> str:
    return json.dumps(serialize_value(data), ensure_ascii=False)


def application_id_for(row: dict[str, str]) -> str:
    existing = str(row.get("application_id", "")).strip()
    if existing:
        return existing
    seed = "|".join(
        normalize_text(row.get(key, ""))
        for key in ("job_id", "job_url", "title", "company", "application_date")
    )
    return "app_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    close = conn is None
    conn = conn or connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                application_id TEXT PRIMARY KEY,
                job_id TEXT,
                job_title TEXT,
                company_name TEXT,
                location TEXT,
                work_style TEXT,
                experience_required TEXT,
                skills_required TEXT,
                application_date TEXT,
                current_status TEXT NOT NULL DEFAULT 'Applied',
                status_updated_at TEXT,
                recruiter_name TEXT,
                recruiter_email TEXT,
                linkedin_job_url TEXT,
                external_apply_url TEXT,
                source_platform TEXT,
                confidence_score REAL DEFAULT 0,
                cold_email_sent TEXT DEFAULT 'False',
                cold_email_sent_at TEXT,
                cold_email_status TEXT DEFAULT 'pending',
                cold_email_subject TEXT,
                cold_email_recipient TEXT,
                cold_email_source TEXT,
                cold_email_error TEXT,
                cold_email_attempts INTEGER DEFAULT 0,
                recruiter_email_confidence REAL,
                recruiter_email_source TEXT,
                recruiter_email_found_at TEXT,
                runtime_segment TEXT DEFAULT 'production',
                runtime_batch_id TEXT,
                data_quality_flags TEXT,
                raw_json TEXT,
                description_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recruiters (
                recruiter_email TEXT PRIMARY KEY,
                recruiter_name TEXT,
                company_name TEXT,
                profile_url TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT NOT NULL,
                status TEXT NOT NULL,
                event_time TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL DEFAULT 0,
                message_id TEXT,
                runtime_batch_id TEXT,
                details_json TEXT,
                UNIQUE(application_id, status, source, message_id),
                FOREIGN KEY(application_id) REFERENCES applications(application_id)
            );
            CREATE TABLE IF NOT EXISTS notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(application_id) REFERENCES applications(application_id)
            );
            CREATE TABLE IF NOT EXISTS cold_emails (
                cold_email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                subject TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                sent_at TEXT,
                error TEXT,
                generated_by TEXT,
                recruiter_email_source TEXT DEFAULT 'linkedin_field',
                recruiter_email_confidence REAL DEFAULT 1.0,
                runtime_batch_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(application_id, recipient_email),
                FOREIGN KEY(application_id) REFERENCES applications(application_id)
            );
            CREATE TABLE IF NOT EXISTS failed_applications (
                failure_id TEXT PRIMARY KEY,
                job_id TEXT,
                job_url TEXT,
                resume_tried TEXT,
                date_listed TEXT,
                date_tried TEXT,
                assumed_reason TEXT,
                stack_trace TEXT,
                external_job_url TEXT,
                screenshot_name TEXT,
                portal_type TEXT,
                source_platform TEXT,
                confidence_score REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # Migration existing applications table if columns are missing
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(applications)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add missing cold email columns to applications table if they don't exist
        missing_cols = [
            ('confidence_score', 'REAL DEFAULT 0'),
            ('cold_email_sent', 'TEXT DEFAULT "False"'),
            ('cold_email_sent_at', 'TEXT'),
            ('cold_email_status', 'TEXT DEFAULT "pending"'),
            ('cold_email_subject', 'TEXT'),
            ('cold_email_recipient', 'TEXT'),
            ('cold_email_source', 'TEXT'),
            ('cold_email_error', 'TEXT'),
            ('cold_email_attempts', 'INTEGER DEFAULT 0'),
            ('recruiter_email_confidence', 'REAL'),
            ('recruiter_email_source', 'TEXT'),
            ('recruiter_email_found_at', 'TEXT'),
            ('runtime_segment', 'TEXT DEFAULT "production"'),
            ('runtime_batch_id', 'TEXT'),
            ('data_quality_flags', 'TEXT')
        ]
        
        for col_name, col_type in missing_cols:
            if col_name not in columns:
                try:
                    conn.execute(f"ALTER TABLE applications ADD COLUMN {col_name} {col_type}")
                except Exception as e:
                    print_lg(f"Migration: Could not add column {col_name}: {e}")

        child_runtime_columns = {
            "cold_emails": "TEXT",
            "lifecycle_events": "TEXT",
        }
        for table, col_type in child_runtime_columns.items():
            cursor.execute(f"PRAGMA table_info({table})")
            table_columns = [row[1] for row in cursor.fetchall()]
            if "runtime_batch_id" not in table_columns:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN runtime_batch_id {col_type}")
                except Exception as e:
                    print_lg(f"Migration: Could not add runtime_batch_id to {table}: {e}")
        
        conn.commit()
    finally:
        if close:
            conn.close()


def _write_description(application_id: str, description: str) -> str:
    if not description:
        return ""
    Path(DETAILS_DIR).mkdir(parents=True, exist_ok=True)
    path = os.path.join(DETAILS_DIR, f"{application_id}.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(description)
    return path


def application_exists(job_id: str, company_name: str = None, conn: sqlite3.Connection | None = None) -> bool:
    """Checks if an application already exists in the database by job_id or company+title."""
    close = conn is None
    conn = conn or connect()
    try:
        cursor = conn.cursor()
        if job_id and job_id != "":
            cursor.execute("SELECT 1 FROM applications WHERE job_id = ?", (job_id,))
        elif company_name:
            cursor.execute("SELECT 1 FROM applications WHERE company_name = ?", (company_name,))
        else:
            return False
        return cursor.fetchone() is not None
    except Exception as e:
        print_lg(f"Error checking application existence in SQLite: {e}")
        return False
    finally:
        if close:
            conn.close()


def get_all_applications(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Retrieves all applications from the database as a list of dictionaries."""
    close = conn is None
    conn = conn or connect()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM applications
            ORDER BY
                CASE COALESCE(runtime_segment, 'production')
                    WHEN 'production' THEN 0
                    WHEN 'quarantined_recruiter' THEN 1
                    WHEN 'validation' THEN 2
                    WHEN 'dummy' THEN 3
                    ELSE 4
                END,
                application_date DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print_lg(f"Error fetching applications from SQLite: {e}")
        return []
    finally:
        if close:
            conn.close()


def get_applications_by_runtime_batch(runtime_batch_id: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Retrieves applications created during one runtime batch only."""
    if not runtime_batch_id:
        return []
    close = conn is None
    conn = conn or connect()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM applications
            WHERE runtime_batch_id = ?
            ORDER BY application_date DESC, created_at DESC
            """,
            (runtime_batch_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print_lg(f"Error fetching runtime-scoped applications from SQLite: {e}")
        return []
    finally:
        if close:
            conn.close()


def get_outreach_queue_applications(
    *,
    limit: int,
    confidence_threshold: float | None = None,
    validation_mode: bool = False,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Returns the next cold-email outreach queue rows, independent of runtime batch."""
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM applications
            WHERE recruiter_email IS NOT NULL
              AND TRIM(recruiter_email) != ''
              AND (
                    cold_email_sent IS NULL
                    OR cold_email_sent IN ('False', 'false', '0', 0)
                  )
              AND COALESCE(cold_email_status, 'pending') IN ('pending', 'validation_only')
            ORDER BY
                CASE WHEN application_date IS NULL OR application_date = '' THEN 1 ELSE 0 END,
                application_date ASC,
                created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print_lg(f"Error fetching outreach queue applications from SQLite: {e}")
        return []
    finally:
        if close:
            conn.close()


def reset_validation_cold_email_rows(conn: sqlite3.Connection | None = None) -> int:
    """Resets only the five validation cold-email rows for repeatable SMTP demos."""
    validation_ids = (
        "test_cold_email1",
        "test_cold_email2",
        "test_cold_email3",
        "test_cold_email4",
        "test_cold_email5",
    )
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    try:
        placeholders = ",".join("?" for _ in validation_ids)
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE applications
            SET cold_email_sent='False',
                cold_email_status='validation_only',
                cold_email_sent_at=NULL,
                cold_email_attempts=0,
                cold_email_error='',
                cold_email_recipient='',
                cold_email_subject='',
                cold_email_source=''
            WHERE application_id IN ({placeholders})
            """,
            validation_ids,
        )
        reset_count = cursor.rowcount
        cursor.execute(
            f"""
            UPDATE cold_emails
            SET status='validation_reset',
                sent_at=NULL,
                error=NULL
            WHERE application_id IN ({placeholders})
              AND status='sent'
            """,
            validation_ids,
        )
        conn.commit()
        return reset_count
    finally:
        if close:
            conn.close()


def get_recruiter_enrichment_candidates(
    *,
    limit: int,
    validation_mode: bool = False,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Returns rows that need recruiter email enrichment before queue selection."""
    if validation_mode:
        return []
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM applications
            WHERE COALESCE(runtime_segment, 'production') = 'production'
              AND (recruiter_email IS NULL OR TRIM(recruiter_email) = '')
              AND COALESCE(cold_email_sent, 'False') NOT IN ('1', 'True', 'true')
              AND COALESCE(cold_email_status, '') NOT IN ('sent')
            ORDER BY
                CASE WHEN application_date IS NULL OR application_date = '' THEN 1 ELSE 0 END,
                application_date DESC,
                created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print_lg(f"Error fetching recruiter enrichment candidates from SQLite: {e}")
        return []
    finally:
        if close:
            conn.close()


def db_row_to_schema_dict(row: dict) -> dict:
    """Reconstructs a dictionary matching APPLIED_EXPORT_SCHEMA from an SQLite database row."""
    import json
    res = {}
    if row.get("raw_json"):
        try:
            res = json.loads(row["raw_json"])
        except Exception:
            pass
            
    # Normalize starting dict to match schema structure
    res = normalize_row(res, APPLIED_EXPORT_SCHEMA, default_val="")
    res['application_id'] = row.get('application_id') or res.get('application_id') or ""
    
    # Overwrite/backfill with database columns to ensure we have the absolute latest state
    res['job_id'] = row.get('job_id') or res.get('job_id') or ""
    res['title'] = row.get('job_title') or res.get('title') or ""
    res['company'] = row.get('company_name') or res.get('company') or ""
    res['work_location'] = row.get('location') or res.get('work_location') or ""
    res['work_style'] = row.get('work_style') or res.get('work_style') or ""
    res['experience_required'] = row.get('experience_required') or res.get('experience_required') or ""
    res['skills_required'] = row.get('skills_required') or res.get('skills_required') or ""
    res['application_date'] = row.get('application_date') or res.get('application_date') or ""
    
    res['current_status'] = row.get('current_status') or res.get('current_status') or "Applied"
    res['last_status_update'] = row.get('status_updated_at') or res.get('last_status_update') or ""
    
    res['recruiter_name'] = row.get('recruiter_name') or res.get('recruiter_name') or ""
    res['recruiter_email'] = row.get('recruiter_email') or res.get('recruiter_email') or ""
    res['job_url'] = row.get('linkedin_job_url') or res.get('job_url') or ""
    res['external_job_url'] = row.get('external_apply_url') or res.get('external_job_url') or ""
    res['source_platform'] = row.get('source_platform') or res.get('source_platform') or "LinkedIn"
    
    if row.get('confidence_score') is not None:
        res['confidence_score'] = str(row['confidence_score'])
        
    res['cold_email_sent'] = row.get('cold_email_sent') or res.get('cold_email_sent') or "False"
    res['cold_email_sent_at'] = row.get('cold_email_sent_at') or res.get('cold_email_sent_at') or ""
    res['cold_email_status'] = row.get('cold_email_status') or res.get('cold_email_status') or "pending"
    res['cold_email_subject'] = row.get('cold_email_subject') or res.get('cold_email_subject') or ""
    res['cold_email_recipient'] = row.get('cold_email_recipient') or res.get('cold_email_recipient') or ""
    res['cold_email_source'] = row.get('cold_email_source') or res.get('cold_email_source') or ""
    res['cold_email_error'] = row.get('cold_email_error') or res.get('cold_email_error') or ""
    res['cold_email_attempts'] = str(row.get('cold_email_attempts') if row.get('cold_email_attempts') is not None else (res.get('cold_email_attempts') or "0"))
    
    if row.get('recruiter_email_confidence') is not None:
        res['recruiter_email_confidence'] = str(row['recruiter_email_confidence'])
    res['recruiter_email_source'] = row.get('recruiter_email_source') or res.get('recruiter_email_source') or ""
    res['recruiter_email_found_at'] = row.get('recruiter_email_found_at') or res.get('recruiter_email_found_at') or ""
    res['runtime_segment'] = row.get('runtime_segment') or res.get('runtime_segment') or "production"
    res['runtime_batch_id'] = row.get('runtime_batch_id') or res.get('runtime_batch_id') or ""
    res['data_quality_flags'] = row.get('data_quality_flags') or res.get('data_quality_flags') or ""

    # Backfill job description text from raw text files if available
    if row.get('description_path') and os.path.exists(row['description_path']):
        try:
            with open(row['description_path'], 'r', encoding='utf-8') as desc_file:
                res['job_description'] = desc_file.read()
        except Exception:
            pass
            
    return res


def db_row_to_failed_schema_dict(row: dict) -> dict:
    """Reconstructs a dictionary matching FAILED_EXPORT_SCHEMA from an SQLite database row."""
    res = normalize_row(dict(row), FAILED_EXPORT_SCHEMA, default_val="")
    return res


def get_all_failed_applications(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Retrieves all failed applications from the database as a list of dictionaries."""
    close = conn is None
    conn = conn or connect()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM failed_applications ORDER BY date_tried DESC")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print_lg(f"Error fetching failed applications from SQLite: {e}")
        return []
    finally:
        if close:
            conn.close()


def upsert_failed_application(row: dict[str, str], conn: sqlite3.Connection | None = None) -> str:
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = normalize_row(row, FAILED_EXPORT_SCHEMA, default_val="")
    
    # Calculate failure_id using job_id, job_url, and date_tried to ensure uniqueness
    seed = "|".join(
        normalize_text(normalized.get(key, ""))
        for key in ("job_id", "job_url", "date_tried")
    )
    failure_id = "fail_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    
    conn.execute(
        """
        INSERT INTO failed_applications (
            failure_id, job_id, job_url, resume_tried, date_listed, date_tried,
            assumed_reason, stack_trace, external_job_url, screenshot_name,
            portal_type, source_platform, confidence_score,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(failure_id) DO UPDATE SET
            resume_tried=excluded.resume_tried,
            date_listed=excluded.date_listed,
            date_tried=excluded.date_tried,
            assumed_reason=excluded.assumed_reason,
            stack_trace=excluded.stack_trace,
            external_job_url=excluded.external_job_url,
            screenshot_name=excluded.screenshot_name,
            portal_type=excluded.portal_type,
            source_platform=excluded.source_platform,
            confidence_score=excluded.confidence_score,
            updated_at=excluded.updated_at
        """,
        (
            failure_id,
            normalized.get("job_id", ""),
            normalized.get("job_url", ""),
            normalized.get("resume_tried", ""),
            normalized.get("date_listed", ""),
            normalized.get("date_tried", ""),
            normalized.get("assumed_reason", ""),
            normalized.get("stack_trace", ""),
            normalized.get("external_job_url", ""),
            normalized.get("screenshot_name", ""),
            normalized.get("portal_type", ""),
            normalized.get("source_platform", "LinkedIn") or "LinkedIn",
            float(normalized.get("confidence_score") or 0),
            now,
            now,
        ),
    )
    conn.commit()
    if close:
        conn.close()
    return failure_id


def export_db_to_csv(csv_path: str = file_name, failed_csv_path: str | None = None) -> None:
    """Exports SQLite application and failed application database records to target CSV files atomically."""
    from modules.helpers import safe_write_csv
    from config.settings import failed_file_name
    if failed_csv_path is None:
        failed_csv_path = failed_file_name

    # 1. Export successful applications
    apps = get_all_applications()
    schema_rows = [db_row_to_schema_dict(app) for app in apps]
    success = safe_write_csv(csv_path, APPLIED_EXPORT_SCHEMA, schema_rows)
    if success:
        print_lg(f"[SYNC-SUCCESS] Synchronized SQLite applications to CSV: rows={len(schema_rows)}, path={csv_path}")
    else:
        print_lg(f"[SYNC-FAILURE] Failed to write SQLite applications to CSV: {csv_path}")

    # 2. Export failed applications
    failed_apps = get_all_failed_applications()
    failed_schema_rows = [db_row_to_failed_schema_dict(fa) for fa in failed_apps]
    success_failed = safe_write_csv(failed_csv_path, FAILED_EXPORT_SCHEMA, failed_schema_rows)
    if success_failed:
        print_lg(f"[SYNC-SUCCESS] Synchronized SQLite failed applications to CSV: rows={len(failed_schema_rows)}, path={failed_csv_path}")
    else:
        print_lg(f"[SYNC-FAILURE] Failed to write SQLite failed applications to CSV: {failed_csv_path}")


def run_db_maintenance(conn: sqlite3.Connection | None = None) -> None:
    """Performs database cleanup by tagging risky rows instead of deleting history."""
    close = conn is None
    conn = conn or connect()
    try:
        cursor = conn.cursor()
        
        # 1. Tag dummy/validation rows. Keep the rows for auditability.
        cursor.execute(
            """
            UPDATE applications
            SET runtime_segment='dummy',
                data_quality_flags=COALESCE(NULLIF(data_quality_flags, ''), 'dummy_or_validation_candidate'),
                cold_email_status='archived_runtime'
            WHERE application_id LIKE 'DUMMY%' 
               OR company_name LIKE '%Dummy%' 
               OR company_name = 'Infosys' 
               OR company_name = 'Goldman Sachs' 
               OR company_name = 'Deloitte'
            """
        )
        tagged_dummies = cursor.rowcount
        if tagged_dummies > 0:
            print_lg(f"DB Maintenance: Tagged {tagged_dummies} dummy/validation applications.")

        quarantined_emails = (
            "riya.kumari@nilasu.com",
            "rosysmita.jena@atyeti.com",
        )
        cursor.execute(
            f"""
            UPDATE applications
            SET runtime_segment='quarantined_recruiter',
                data_quality_flags=TRIM(COALESCE(data_quality_flags, '') || ';historical_recruiter_contamination'),
                cold_email_status='skipped_quarantined_recruiter',
                cold_email_sent='False'
            WHERE LOWER(COALESCE(recruiter_email, '')) IN ({','.join('?' for _ in quarantined_emails)})
            """,
            quarantined_emails,
        )
        quarantined_count = cursor.rowcount
        if quarantined_count > 0:
            print_lg(f"DB Maintenance: Permanently quarantined {quarantined_count} historical recruiter-contaminated row(s).")

        validation_rows = [
            ("test_cold_email1", "FutureAI", "Validation Cold Email 1", "cs22b1054@iiitr.ac.in"),
            ("test_cold_email2", "Darwix Validation", "Validation Cold Email 2", "manvendra.singh@darwix.ai"),
            ("test_cold_email3", "Gmail Validation A", "Validation Cold Email 3", "manomegle9830@gmail.com"),
            ("test_cold_email4", "Gmail Validation B", "Validation Cold Email 4", "manusingh9830@gmail.com"),
            ("test_cold_email5", "Akarsh Validation", "Validation Cold Email 5", "akarsh7376@gmail.com"),
        ]
        validation_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for app_id, company, title, email in validation_rows:
            upsert_application(
                {
                    "application_id": app_id,
                    "job_id": app_id,
                    "title": title,
                    "company": company,
                    "application_date": validation_now,
                    "current_status": "Applied",
                    "last_status_update": validation_now,
                    "status_source": "Validation Seed",
                    "response_received": "False",
                    "recruiter_name": "Validation Recipient",
                    "recruiter_email": email,
                    "recruiter_email_source": "validation_seed",
                    "recruiter_email_confidence": "1.0",
                    "cold_email_sent": "False",
                    "cold_email_status": "validation_only",
                    "runtime_segment": "validation",
                    "runtime_batch_id": "validation_seed",
                    "data_quality_flags": "validation_only;exclude_from_production_analytics",
                    "source_platform": "Validation",
                    "confidence_score": "100",
                },
                conn,
            )
            
        # 2. Mark duplicates for review. Do not remove historical rows.
        cursor.execute(
            """
            UPDATE applications
            SET runtime_segment='review',
                data_quality_flags=TRIM(COALESCE(data_quality_flags, '') || ';duplicate_company_title')
            WHERE application_id NOT IN (
                SELECT application_id FROM (
                    SELECT application_id, 
                           ROW_NUMBER() OVER (
                               PARTITION BY company_name, job_title 
                               ORDER BY application_date DESC, created_at DESC
                           ) as rn
                    FROM applications
                    WHERE COALESCE(runtime_segment, 'production') = 'production'
                ) WHERE rn = 1
            )
            AND COALESCE(runtime_segment, 'production') = 'production'
            """
        )
        tagged_dups = cursor.rowcount
        if tagged_dups > 0:
            print_lg(f"DB Maintenance: Tagged {tagged_dups} duplicate application rows for review.")
            
        # 3. Report orphaned child rows instead of deleting them.
        for child_table in ("lifecycle_events", "cold_emails", "notes"):
            cursor.execute(
                f"SELECT COUNT(*) FROM {child_table} WHERE application_id NOT IN (SELECT application_id FROM applications)"
            )
            orphan_count = cursor.fetchone()[0]
            if orphan_count:
                print_lg(f"DB Maintenance: {child_table} has {orphan_count} orphaned row(s) requiring manual review.")
        
        conn.commit()
    except Exception as e:
        print_lg(f"DB Maintenance failed: {e}")
    finally:
        if close:
            conn.close()


def upsert_application(row: dict[str, str], conn: sqlite3.Connection | None = None) -> str:
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = normalize_row(row, APPLIED_EXPORT_SCHEMA, default_val="")
    application_id = application_id_for({**normalized, **row})
    description_path = _write_description(application_id, normalized.get("job_description", ""))

    conn.execute(
        """
        INSERT INTO applications (
            application_id, job_id, job_title, company_name, location, work_style,
            experience_required, skills_required, application_date, current_status,
            status_updated_at, recruiter_name, recruiter_email, linkedin_job_url,
            external_apply_url, source_platform, confidence_score,
            cold_email_sent, cold_email_sent_at, cold_email_status,
            cold_email_subject, cold_email_recipient, cold_email_source,
            cold_email_error, cold_email_attempts, recruiter_email_confidence, recruiter_email_source,
            recruiter_email_found_at, runtime_segment, runtime_batch_id, data_quality_flags, raw_json, description_path,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(application_id) DO UPDATE SET
            current_status=excluded.current_status,
            status_updated_at=excluded.status_updated_at,
            recruiter_email=COALESCE(NULLIF(excluded.recruiter_email, ''), applications.recruiter_email),
            confidence_score=excluded.confidence_score,
            cold_email_sent=excluded.cold_email_sent,
            cold_email_sent_at=excluded.cold_email_sent_at,
            cold_email_status=excluded.cold_email_status,
            cold_email_subject=excluded.cold_email_subject,
            cold_email_recipient=excluded.cold_email_recipient,
            cold_email_source=excluded.cold_email_source,
            cold_email_error=excluded.cold_email_error,
            cold_email_attempts=excluded.cold_email_attempts,
            recruiter_email_confidence=excluded.recruiter_email_confidence,
            recruiter_email_source=excluded.recruiter_email_source,
            recruiter_email_found_at=excluded.recruiter_email_found_at,
            runtime_segment=COALESCE(NULLIF(excluded.runtime_segment, ''), applications.runtime_segment),
            runtime_batch_id=COALESCE(NULLIF(excluded.runtime_batch_id, ''), applications.runtime_batch_id),
            data_quality_flags=COALESCE(NULLIF(excluded.data_quality_flags, ''), applications.data_quality_flags),
            raw_json=excluded.raw_json,
            description_path=COALESCE(NULLIF(excluded.description_path, ''), applications.description_path),
            updated_at=excluded.updated_at
        """,
        (
            application_id,
            normalized.get("job_id", ""),
            normalized.get("title", ""),
            normalized.get("company", ""),
            normalized.get("work_location", ""),
            normalized.get("work_style", ""),
            normalized.get("experience_required", ""),
            normalized.get("skills_required", ""),
            normalized.get("application_date", ""),
            normalized.get("current_status", "Applied") or "Applied",
            normalized.get("last_status_update", "") or normalized.get("application_date", ""),
            normalized.get("recruiter_name", ""),
            normalized.get("recruiter_email", ""),
            normalized.get("job_url", ""),
            normalized.get("external_job_url", ""),
            normalized.get("source_platform", "LinkedIn") or "LinkedIn",
            float(normalized.get("confidence_score") or 0),
            normalized.get("cold_email_sent") or "False",
            normalized.get("cold_email_sent_at") or "",
            normalized.get("cold_email_status") or "pending",
            normalized.get("cold_email_subject") or "",
            normalized.get("cold_email_recipient") or "",
            normalized.get("cold_email_source") or "",
            normalized.get("cold_email_error") or "",
            int(normalized.get("cold_email_attempts") or 0),
            float(normalized.get("recruiter_email_confidence") or 0) if normalized.get("recruiter_email_confidence") else None,
            normalized.get("recruiter_email_source") or "",
            normalized.get("recruiter_email_found_at") or "",
            normalized.get("runtime_segment") or "production",
            normalized.get("runtime_batch_id") or "",
            normalized.get("data_quality_flags") or "",
            dumps_json(normalized),
            description_path,
            now,
            now,
        ),
    )
    
    if normalized.get("recruiter_email") and (normalized.get("runtime_segment") or "production") == "production":
        conn.execute(
            """
            INSERT INTO recruiters (recruiter_email, recruiter_name, company_name, profile_url, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(recruiter_email) DO UPDATE SET
                recruiter_name=COALESCE(NULLIF(excluded.recruiter_name, ''), recruiters.recruiter_name),
                company_name=COALESCE(NULLIF(excluded.company_name, ''), recruiters.company_name),
                profile_url=COALESCE(NULLIF(excluded.profile_url, ''), recruiters.profile_url),
                updated_at=excluded.updated_at
            """,
            (
                normalized.get("recruiter_email", ""),
                normalized.get("recruiter_name", ""),
                normalized.get("company", ""),
                normalized.get("recruiter_profile_url", ""),
                now,
            ),
        )
    conn.commit()
    if close:
        conn.close()
    return application_id


def add_lifecycle_event(
    application_id: str,
    status: str,
    *,
    event_time: str,
    source: str,
    confidence: float = 0,
    message_id: str = "",
    runtime_batch_id: str = "",
    details: dict | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    close = conn is None
    conn = conn or connect()
    init_db(conn)
    conn.execute(
        """
        INSERT OR IGNORE INTO lifecycle_events
            (application_id, status, event_time, source, confidence, message_id, runtime_batch_id, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (application_id, status, event_time, source, confidence, message_id, runtime_batch_id, dumps_json(details or {})),
    )
    conn.execute(
        """
        UPDATE applications
        SET current_status=?, status_updated_at=?, updated_at=?
        WHERE application_id=?
        """,
        (status, event_time, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), application_id),
    )
    conn.commit()
    if close:
        conn.close()


def migrate_csv_to_db(csv_path: str = file_name) -> int:
    if not os.path.exists(csv_path):
        return 0
    conn = connect()
    init_db(conn)
    count = 0
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                row = {LEGACY_COLUMN_ALIASES.get(key, key): value for key, value in raw.items()}
                upsert_application(row, conn)
                count += 1
        print_lg(f"SQLite migration complete: {count} application row(s) in {DB_PATH}")
        return count
    finally:
        conn.close()
