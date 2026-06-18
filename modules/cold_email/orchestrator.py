import csv
import os
import time
from datetime import datetime
from config.settings import (
    file_name,
    COLD_EMAIL_ENABLED,
    MAX_COLD_EMAILS_PER_RUN,
    COLD_EMAIL_DRY_RUN,
    EMAIL_SEND_DELAY_SECONDS,
)
from modules.helpers import print_lg, APPLIED_EXPORT_SCHEMA, LEGACY_COLUMN_ALIASES, normalize_row, ensure_csv_header, safe_write_csv
from modules.storage import (
    upsert_application,
    application_id_for,
    get_recruiter_enrichment_candidates,
    get_outreach_queue_applications,
    db_row_to_schema_dict,
    export_db_to_csv,
)
from modules.runtime_context import get_current_runtime_batch_id
from modules.cold_email import finder, generator, sender, tracker

# >>>>>>>>>>> COLD EMAIL TEST SETTINGS <<<<<<<<<<<
# When True, emails are ONLY sent to COLD_EMAIL_WHITELIST recipients.
COLD_EMAIL_TEST_MODE = True 
COLD_EMAIL_WHITELIST = [
    "cs22b1054@iiitr.ac.in",
    "manvendra.singh@darwix.ai",
    "manomegle9830@gmail.com",
    "manusingh9830@gmail.com",
    "akarsh7376@gmail.com",
]
# <<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>

def load_resume_text() -> str:
    try:
        from config.settings import COLD_EMAIL_RESUME_TEXT
        path = COLD_EMAIL_RESUME_TEXT
    except ImportError:
        path = "resume_text.txt"
        
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print_lg(f"Error reading resume text file: {e}")
    return ""

def load_applications(csv_path: str) -> list[dict]:
    if not os.path.exists(csv_path):
        return []
        
    # Ensure header is synchronized before reading
    ensure_csv_header(csv_path, APPLIED_EXPORT_SCHEMA)
    
    rows = []
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = {LEGACY_COLUMN_ALIASES.get(k, k): v for k, v in raw.items()}
                # Ensure all APPLIED_EXPORT_SCHEMA fields are initialized
                normalized = normalize_row(row, APPLIED_EXPORT_SCHEMA, default_val="")
                rows.append(normalized)
    except Exception as e:
        print_lg(f"Error loading CSV in orchestrator: {e}")
    return rows

def save_applications(csv_path: str, rows: list[dict]) -> None:
    # Atomic write using centralized helper
    safe_write_csv(csv_path, APPLIED_EXPORT_SCHEMA, rows)

def run_cold_email_pipeline(driver=None, runtime_batch_id: str | None = None, dry_run: bool | None = None, include_validation: bool = False) -> dict:
    """Orchestrates queue-based recruiter cold emailing independent of the apply runtime."""
    runtime_batch_id = runtime_batch_id or get_current_runtime_batch_id()
    dry_run = COLD_EMAIL_DRY_RUN if dry_run is None else dry_run
    summary = {
        "total_eligible": 0,
        "emails_sent": 0,
        "emails_failed": 0,
        "emails_skipped": 0,
        "emails_already_sent": 0,
        "recruiter_emails_found": 0,
        "test_mode_redirects": 0
    }
    
    browser_enrichment_enabled = driver is not None

    if not COLD_EMAIL_ENABLED:
        print_lg("Cold email system is disabled globally.")
        return summary
        
    print_lg(
        f"[COLD-EMAIL-QUEUE] Starting queue-based outreach. "
        f"runtime_batch_id={runtime_batch_id or 'none'}, dry_run={dry_run}, "
        f"include_validation={include_validation}, TEST_MODE={COLD_EMAIL_TEST_MODE}, "
        f"BROWSER_ENRICHMENT={browser_enrichment_enabled}"
    )
    if not browser_enrichment_enabled:
        print_lg("[COLD-EMAIL-QUEUE] Browser enrichment unavailable because driver=None; stored/job-description enrichment only.")

    csv_updated = False
    profile_visit_counter = 0
    enrichment_candidates = get_recruiter_enrichment_candidates(limit=max(MAX_COLD_EMAILS_PER_RUN * 3, 10))
    print_lg(f"[COLD-EMAIL-ENRICHMENT] Candidate rows needing recruiter email: {len(enrichment_candidates)}")
    for candidate in enrichment_candidates:
        row = db_row_to_schema_dict(candidate)
        email, source, confidence, profile_visit_counter = finder.find_recruiter_email(
            driver,
            row,
            profile_visit_counter,
        )
        if not email:
            continue
        row["recruiter_email"] = email
        row["recruiter_email_source"] = source or ""
        row["recruiter_email_confidence"] = str(confidence or 0.0)
        row["recruiter_email_found_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        upsert_application(row)
        summary["recruiter_emails_found"] += 1
        csv_updated = True
    
    # Load settings — .env override takes priority over settings.py
    max_emails = MAX_COLD_EMAILS_PER_RUN
    try:
        from modules.cold_email.generator import _read_env_file
        env_values = _read_env_file("config/email/.env")
        max_runs_str = env_values.get("MAX_COLD_EMAILS_PER_RUN")
        if max_runs_str:
            max_emails = min(int(max_runs_str), MAX_COLD_EMAILS_PER_RUN)
    except Exception:
        pass
        
    resume_text = load_resume_text()

    queue_load_limit = max_emails * 20 if COLD_EMAIL_TEST_MODE else max_emails
    apps = get_outreach_queue_applications(
        limit=queue_load_limit,
    )
    applications = [db_row_to_schema_dict(app) for app in apps]
    print_lg(
        f"[COLD-EMAIL-QUEUE-LOAD] Loaded {len(applications)} pending row(s) from SQLite. "
        f"send_limit={max_emails}; load_limit={queue_load_limit}"
    )
    
    if not applications:
        print_lg("[COLD-EMAIL-QUEUE] No eligible pending outreach rows found.")
        if csv_updated:
            export_db_to_csv(file_name)
        return summary
        
    sent_this_run = 0
    
    planned_outreach = []
    for row in applications:
        runtime_segment = (row.get("runtime_segment") or "production").strip().lower()

        # Determine application ID
        app_id = application_id_for(row)
        row["application_id"] = app_id # ensure populated
        
        # Check if email is already sent
        email_sent_field = row.get("cold_email_sent")
        email_status_field = row.get("cold_email_status")
        
        # We also query SQLite for double-checking duplicate prevention
        recipient = row.get("recruiter_email") or ""
        print_lg(
            f"[COLD-EMAIL-PENDING] application_id={app_id}; segment={runtime_segment}; "
            f"recipient={recipient}; status={email_status_field}; sent={email_sent_field}; "
            f"application_date={row.get('application_date')}"
        )

        is_validation_row = runtime_segment == "validation"
        if is_validation_row and row.get("recruiter_email_source") == "validation_seed":
            trusted, trust_reason, adjusted_confidence = True, "validation_seed", float(row.get("recruiter_email_confidence") or 1.0)
        else:
            trusted, trust_reason, adjusted_confidence = finder.trust_recruiter_email(
                recipient,
                row.get("recruiter_email_source"),
                row.get("recruiter_email_confidence"),
                row.get("company"),
            )
        if not trusted:
            print_lg(f"[COLD-EMAIL-SKIP] Recruiter email not trusted for {row.get('company')}: {recipient} ({trust_reason})")
            if dry_run:
                summary["emails_skipped"] += 1
                continue
            row["runtime_segment"] = "quarantined_recruiter"
            row["data_quality_flags"] = f"recruiter_email_quarantined:{trust_reason}"
            row["cold_email_sent"] = "False"
            row["cold_email_status"] = "skipped_quarantined_recruiter"
            row["cold_email_error"] = f"Recruiter email trust failure: {trust_reason}"
            row["cold_email_recipient"] = recipient
            row["recruiter_email_confidence"] = str(adjusted_confidence)
            upsert_application(row)
            summary["emails_skipped"] += 1
            csv_updated = True
            continue
            
        # SQLite double check
        if tracker.has_cold_email_been_sent(app_id, recipient) or str(email_sent_field).lower() in ("true", "1") or email_status_field == "sent":
            print_lg(f"[COLD-EMAIL-SKIP-SENT] application_id={app_id}; recipient={recipient}")
            summary["emails_already_sent"] += 1
            # Ensure SQLite is updated with sent status if csv has it
            if (email_sent_field == "True" or email_status_field == "sent") and not tracker.has_cold_email_been_sent(app_id, recipient):
                tracker.record_cold_email(
                    application_id=app_id,
                    recipient_email=recipient,
                    subject=row.get("cold_email_subject"),
                    status="sent",
                    sent_at=row.get("cold_email_sent_at"),
                    error=None,
                    generated_by=row.get("cold_email_source"),
                    recruiter_email_source=row.get("recruiter_email_source"),
                    recruiter_email_confidence=float(row.get("recruiter_email_confidence") or 1.0),
                    runtime_batch_id=runtime_batch_id
                )
            continue
            
        # Check execution limits
        if len(planned_outreach) >= max_emails:
            print_lg(f"Reached MAX_COLD_EMAILS_PER_RUN ({max_emails}). Stopping outreach.")
            break
            
        confidence = float(row.get("recruiter_email_confidence") or 0.0)
            
        # Test Mode Logic
        target_email = recipient
        if COLD_EMAIL_TEST_MODE:
            if recipient not in COLD_EMAIL_WHITELIST:
                print_lg(f"[COLD-EMAIL-QUEUE-SKIP] TEST_MODE blocks non-whitelisted recipient: {recipient}")
                summary["emails_skipped"] += 1
                continue

        planned_outreach.append((row, app_id, recipient, target_email, confidence, runtime_segment))

    summary["total_eligible"] = len(planned_outreach)

    for row, app_id, recipient, target_email, confidence, runtime_segment in planned_outreach:
        print_lg(
            "[COLD-EMAIL-PENDING] "
            f"to={target_email}; original_recipient={recipient}; "
            f"source={row.get('recruiter_email_source')}; confidence={confidence}; "
            f"company={row.get('company')}; title={row.get('title')}"
        )

    if dry_run:
        print_lg(f"[COLD-EMAIL-QUEUE-COMPLETE] Dry run complete. No SMTP sends executed. summary={summary}")
        if csv_updated:
            export_db_to_csv(file_name)
        return summary

    for row, app_id, recipient, target_email, confidence, runtime_segment in planned_outreach:
        if sent_this_run >= max_emails:
            print_lg(f"Reached MAX_COLD_EMAILS_PER_RUN ({max_emails}). Stopping outreach.")
            break

        # Generate personalized email
        content = generator.generate_cold_email(row, resume_text)

        if runtime_segment == "validation":
            print_lg(f"[COLD-EMAIL-VALIDATION-RECIPIENT] SMTP send target: {target_email}")

        # Send email
        result = sender.send_cold_email(target_email, content)
        csv_updated = True
        
        # Update records
        if result.success:
            sent_this_run += 1
            row["cold_email_sent"] = "True"
            row["cold_email_status"] = "sent"
            row["cold_email_sent_at"] = result.timestamp
            row["cold_email_subject"] = content.subject
            row["cold_email_recipient"] = recipient # Store original recipient
            row["cold_email_source"] = content.generated_by
            row["cold_email_error"] = ""
            
            tracker.record_cold_email(
                application_id=app_id,
                recipient_email=recipient,
                subject=content.subject,
                status="sent",
                sent_at=result.timestamp,
                error=None,
                generated_by=content.generated_by,
                recruiter_email_source=row.get("recruiter_email_source"),
                recruiter_email_confidence=confidence,
                runtime_batch_id=runtime_batch_id
            )
            
            # Upsert application to DB
            upsert_application(row)
            summary["emails_sent"] += 1
            print_lg(f"[COLD-EMAIL-SENT] application_id={app_id}; recipient={recipient}; sent_at={result.timestamp}")
            
            print_lg(f"[EMAIL-THROTTLE] Sleeping {EMAIL_SEND_DELAY_SECONDS}s before next email.")
            time.sleep(EMAIL_SEND_DELAY_SECONDS)
        else:
            row["cold_email_sent"] = "False"
            row["cold_email_status"] = "failed"
            row["cold_email_error"] = result.error or "Unknown SMTP error"
            row["cold_email_recipient"] = recipient
            row["cold_email_subject"] = content.subject
            row["cold_email_source"] = content.generated_by
            row["cold_email_attempts"] = str(int(row.get("cold_email_attempts") or 0) + 1)
            
            tracker.record_cold_email(
                application_id=app_id,
                recipient_email=recipient,
                subject=content.subject,
                status="failed",
                sent_at=None,
                error=result.error,
                generated_by=content.generated_by,
                recruiter_email_source=row.get("recruiter_email_source"),
                recruiter_email_confidence=confidence,
                runtime_batch_id=runtime_batch_id
            )
            upsert_application(row)
            summary["emails_failed"] += 1
            print_lg(f"[COLD-EMAIL-FAILED] application_id={app_id}; recipient={recipient}; error={row['cold_email_error']}")
            
    if csv_updated:
        print_lg("Saving updated application records back to CSV from SQLite...")
        export_db_to_csv(file_name)
        
    print_lg(f"[COLD-EMAIL-QUEUE-COMPLETE] Smart Cold Emailing Pipeline completed. runtime_batch_id={runtime_batch_id or 'none'} summary={summary}")
    return summary
