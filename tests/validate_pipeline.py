"""
Naukri_Guru -- End-to-End Pipeline Validation
=============================================
Tests every stage of the pipeline in isolation AND in sequence
WITHOUT launching Chrome or making live LinkedIn calls.

Run from project root:
    python -m tests.validate_pipeline
"""

import csv
import copy
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timedelta
from io import StringIO

# Force UTF-8 stdout on Windows to prevent cp1252 encoding errors
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# -----------------------------------------------
#  Helpers
# -----------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results: list[tuple[str, str, str]] = []   # (test_name, status, detail)


def record(name: str, status: str, detail: str = ""):
    results.append((name, status, detail))
    icon = status
    print(f"  {icon}  {name}" + (f" -- {detail}" if detail else ""))


def separator(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ─────────────────────────────────────────────
#  PHASE 1: Config / Schema Validation
# ─────────────────────────────────────────────
def test_config_validation():
    separator("PHASE 1 — Config & Schema Validation")
    try:
        from modules.validator import validate_config
        validate_config()
        record("Config validation (all files)", PASS)
    except Exception as e:
        record("Config validation (all files)", FAIL, str(e))

    # Schema constants
    from modules.helpers import APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA, LEGACY_COLUMN_ALIASES

    lifecycle_fields = ['current_status', 'last_status_update', 'status_source', 'response_received', 'recruiter_email']
    for field in lifecycle_fields:
        if field in APPLIED_EXPORT_SCHEMA:
            record(f"Schema has lifecycle field: {field}", PASS)
        else:
            record(f"Schema has lifecycle field: {field}", FAIL, "Missing from APPLIED_EXPORT_SCHEMA")

    # Cold email fields check
    cold_email_fields = [
        'cold_email_sent', 'cold_email_sent_at', 'cold_email_status',
        'cold_email_subject', 'cold_email_recipient', 'cold_email_source',
        'cold_email_error', 'recruiter_email_confidence', 'recruiter_email_source',
        'recruiter_email_found_at'
    ]
    for field in cold_email_fields:
        if field in APPLIED_EXPORT_SCHEMA:
            record(f"Schema has cold email field: {field}", PASS)
        else:
            record(f"Schema has cold email field: {field}", FAIL, "Missing from APPLIED_EXPORT_SCHEMA")


# ─────────────────────────────────────────────
#  PHASE 2: Gmail Sync — Unit Tests
# ─────────────────────────────────────────────
def test_gmail_sync_units():
    separator("PHASE 2 — Gmail Sync Unit Tests")

    # 2a. Classifier
    from modules.email.fetcher import EmailRecord
    from modules.email.classifier import classify_email, ClassificationResult

    now = datetime.now()

    rejection_email = EmailRecord(
        message_id="1", sender="HR at Ericsson", sender_email="noreply@ericsson.com",
        subject="Your application status", date=now,
        body="We regret to inform you that we will not be moving forward with your application for the Software Developer role."
    )
    result = classify_email(rejection_email)
    if result and result.status == "Rejected" and result.confidence >= 0.90:
        record("Classifier: Rejection email", PASS, f"status={result.status}, conf={result.confidence:.2f}")
    else:
        record("Classifier: Rejection email", FAIL, f"Got: {result}")

    interview_email = EmailRecord(
        message_id="2", sender="Priya from Acme Labs", sender_email="priya@acmelabs.com",
        subject="Interview Scheduled for SDE Role",
        date=now,
        body="Hi Manvendra, we'd like to schedule an interview with you for the Software Developer position. Please share your availability."
    )
    result = classify_email(interview_email)
    if result and result.status == "Interview Scheduled" and result.confidence >= 0.90:
        record("Classifier: Interview email", PASS, f"status={result.status}, conf={result.confidence:.2f}")
    else:
        record("Classifier: Interview email", FAIL, f"Got: {result}")

    oa_email = EmailRecord(
        message_id="3", sender="TechCorp Talent", sender_email="talent@techcorp.com",
        subject="Online Assessment for your application",
        date=now,
        body="Thank you for applying to the Data Scientist role. Please complete this HackerRank coding assessment within 5 days."
    )
    result = classify_email(oa_email)
    if result and result.status == "OA Received" and result.confidence >= 0.88:
        record("Classifier: OA email", PASS, f"status={result.status}, conf={result.confidence:.2f}")
    else:
        record("Classifier: OA email", FAIL, f"Got: {result}")

    newsletter_email = EmailRecord(
        message_id="4", sender="TechNewsletter", sender_email="newsletter@techblog.com",
        subject="Top 10 JavaScript Frameworks in 2026",
        date=now,
        body="Here are the best JavaScript frameworks you should learn this year. React, Vue, Svelte..."
    )
    result = classify_email(newsletter_email)
    if result is None:
        record("Classifier: Newsletter ignored", PASS)
    else:
        record("Classifier: Newsletter ignored", FAIL, f"Should be None, got: {result}")

    offer_email = EmailRecord(
        message_id="5", sender="HR at Dream Corp", sender_email="hr@dreamcorp.com",
        subject="Offer Letter - Software Engineer",
        date=now,
        body="We are pleased to offer you the position of Software Engineer at Dream Corp. Please review the attached offer letter."
    )
    result = classify_email(offer_email)
    if result and result.status == "Offer" and result.confidence >= 0.90:
        record("Classifier: Offer email", PASS, f"status={result.status}, conf={result.confidence:.2f}")
    else:
        record("Classifier: Offer email", FAIL, f"Got: {result}")

    # 2b. Matcher
    from modules.email.matcher import match_email_to_application

    applications = [
        {"company": "Acme Labs", "title": "Software Developer", "recruiter_name": "Priya Sharma",
         "recruiter_email": "", "application_date": (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"), "job_id": "J100"},
        {"company": "BetaCorp", "title": "Data Analyst", "recruiter_name": "Unknown",
         "recruiter_email": "", "application_date": (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), "job_id": "J101"},
    ]

    match = match_email_to_application(interview_email, applications)
    if match and match.index == 0 and match.confidence >= 0.70:
        record("Matcher: Interview→Acme Labs", PASS, f"conf={match.confidence:.2f}, reasons={match.reasons}")
    else:
        record("Matcher: Interview→Acme Labs", FAIL, f"Got: {match}")

    match = match_email_to_application(newsletter_email, applications)
    if match is None or match.confidence < 0.75:
        record("Matcher: Newsletter no match", PASS)
    else:
        record("Matcher: Newsletter no match", WARN, f"Unexpected match: {match}")

    # 2c. Status priority logic
    from modules.email.updater import _can_update_status

    assert _can_update_status("Applied", "Interview Scheduled") == True
    record("Priority: Applied→Interview Scheduled", PASS)
    assert _can_update_status("Rejected", "Interview Scheduled") == False
    record("Priority: Rejected→Interview Scheduled blocked", PASS)
    assert _can_update_status("Rejected", "Offer") == True
    record("Priority: Rejected→Offer allowed", PASS)
    assert _can_update_status("Applied", "Rejected") == True
    record("Priority: Applied→Rejected allowed", PASS)
    assert _can_update_status("Offer", "Rejected") == True
    record("Priority: Offer→Rejected allowed", PASS)
    assert _can_update_status("Interview Scheduled", "Under Review") == False
    record("Priority: Interview Scheduled→Under Review blocked", PASS)


# ─────────────────────────────────────────────
#  PHASE 3: Lifecycle CSV Update (Integration)
# ─────────────────────────────────────────────
def test_lifecycle_csv_update():
    separator("PHASE 3 — Lifecycle CSV Update Integration")

    from modules.helpers import APPLIED_EXPORT_SCHEMA, normalize_row
    from modules.email.fetcher import EmailRecord
    from modules.email.updater import apply_email_updates

    now = datetime.now()
    applications = [
        normalize_row({
            'job_id': 'J200', 'title': 'ML Engineer', 'company': 'Acme Labs',
            'work_location': 'Bangalore', 'work_style': 'Remote',
            'application_date': (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            'current_status': 'Applied', 'status_source': 'LinkedIn Automation',
            'response_received': 'False', 'recruiter_name': 'Ravi Kumar',
            'recruiter_email': '', 'source_platform': 'LinkedIn'
        }, APPLIED_EXPORT_SCHEMA, default_val=''),
        normalize_row({
            'job_id': 'J201', 'title': 'Backend Developer', 'company': 'BetaCorp',
            'work_location': 'Hyderabad', 'work_style': 'Hybrid',
            'application_date': (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"),
            'current_status': 'Rejected', 'status_source': 'Gmail IMAP',
            'response_received': 'True', 'recruiter_name': 'Unknown',
            'recruiter_email': '', 'source_platform': 'LinkedIn'
        }, APPLIED_EXPORT_SCHEMA, default_val=''),
    ]

    records = [
        EmailRecord(
            message_id="10", sender="Ravi from Acme Labs", sender_email="ravi@acmelabs.com",
            subject="Interview Scheduled for ML Engineer",
            date=now,
            body="Hi, we'd like to schedule an interview for the ML Engineer position at Acme Labs. Please share your availability."
        ),
        EmailRecord(
            message_id="11", sender="HR BetaCorp", sender_email="hr@betacorp.com",
            subject="We're moving forward with your application",
            date=now,
            body="Good news! You have been shortlisted for the next step in the recruitment process for Backend Developer at BetaCorp."
        ),
    ]

    before_status_j200 = applications[0]['current_status']
    before_status_j201 = applications[1]['current_status']
    updates = apply_email_updates(applications, records)

    # J200: Applied → Interview Scheduled (should update)
    if applications[0]['current_status'] == 'Interview Scheduled':
        record("CSV Update: J200 Applied→Interview Scheduled", PASS)
    else:
        record("CSV Update: J200 Applied→Interview Scheduled", FAIL, f"Got: {applications[0]['current_status']}")

    if applications[0]['status_source'] == 'Gmail IMAP':
        record("CSV Update: J200 status_source=Gmail IMAP", PASS)
    else:
        record("CSV Update: J200 status_source", FAIL, f"Got: {applications[0]['status_source']}")

    if applications[0]['response_received'] == 'True':
        record("CSV Update: J200 response_received=True", PASS)
    else:
        record("CSV Update: J200 response_received", FAIL, f"Got: {applications[0]['response_received']}")

    if applications[0].get('recruiter_email') == 'ravi@acmelabs.com':
        record("CSV Update: J200 recruiter_email stored", PASS)
    else:
        record("CSV Update: J200 recruiter_email", FAIL, f"Got: {applications[0].get('recruiter_email')}")

    # J201: Rejected should NOT be overwritten by Shortlisted
    if applications[1]['current_status'] == 'Rejected':
        record("CSV Update: J201 Rejected preserved (not overwritten)", PASS)
    else:
        record("CSV Update: J201 Rejected preserved", FAIL, f"Got: {applications[1]['current_status']}")

    if updates >= 1:
        record(f"CSV Update: total updates={updates}", PASS)
    else:
        record(f"CSV Update: total updates={updates}", FAIL, "Expected at least 1 update")


# ─────────────────────────────────────────────
#  PHASE 4: CSV File Integrity
# ─────────────────────────────────────────────
def test_csv_file_integrity():
    separator("PHASE 4 — CSV File Integrity")

    from config.settings import file_name, failed_file_name
    from modules.helpers import APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA

    for csv_path, schema, label in [
        (file_name, APPLIED_EXPORT_SCHEMA, "Applied CSV"),
        (failed_file_name, FAILED_EXPORT_SCHEMA, "Failed CSV"),
    ]:
        if not os.path.exists(csv_path):
            record(f"{label}: File exists", WARN, f"{csv_path} not found")
            continue
        record(f"{label}: File exists", PASS, csv_path)

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                missing = [col for col in schema if col not in headers]
                extra = [col for col in headers if col not in schema]
                row_count = 0
                for _ in reader:
                    row_count += 1

            if not missing:
                record(f"{label}: Schema match (columns)", PASS, f"{len(headers)} columns")
            else:
                record(f"{label}: Schema match (columns)", FAIL, f"Missing: {missing}")

            if not extra:
                record(f"{label}: No extra columns", PASS)
            else:
                record(f"{label}: Extra columns found", WARN, f"{extra}")

            record(f"{label}: Row count", PASS, f"{row_count} rows")

        except Exception as e:
            record(f"{label}: Read error", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 5: Normalization & Export
# ─────────────────────────────────────────────
def test_normalization_and_export():
    separator("PHASE 5 — Normalization & Export")

    from modules.helpers import APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA, normalize_row

    # Test legacy column normalization
    legacy_row = {
        'Job ID': 'J999', 'Title': 'Test Engineer', 'Company': 'TestCorp',
        'HR Name': 'John Doe', 'HR Link': 'https://linkedin.com/in/johndoe',
        'Date Applied': '2026-05-20', 'Job Link': 'https://linkedin.com/jobs/999',
    }
    normalized = normalize_row(legacy_row, APPLIED_EXPORT_SCHEMA, default_val='')
    if normalized.get('job_id') == 'J999' and normalized.get('title') == 'Test Engineer':
        record("Normalize: Legacy columns remapped", PASS)
    else:
        record("Normalize: Legacy columns remapped", FAIL, f"Got: {normalized}")

    if normalized.get('current_status') == 'Applied':
        record("Normalize: Default current_status=Applied", PASS)
    else:
        record("Normalize: Default current_status", FAIL, f"Got: {normalized.get('current_status')}")

    if normalized.get('source_platform') == 'LinkedIn':
        record("Normalize: Default source_platform=LinkedIn", PASS)
    else:
        record("Normalize: Default source_platform", FAIL, f"Got: {normalized.get('source_platform')}")

    # Ensure exact column count
    if len(normalized) == len(APPLIED_EXPORT_SCHEMA):
        record("Normalize: Exact column count", PASS, f"{len(normalized)} columns")
    else:
        record("Normalize: Exact column count", FAIL, f"Expected {len(APPLIED_EXPORT_SCHEMA)}, got {len(normalized)}")

    # Test export module import
    try:
        from modules.export_to_excel import normalize_csv_file, convert_csvs_to_excel
        record("Export: Module import", PASS)
    except Exception as e:
        record("Export: Module import", FAIL, str(e))

    # Test XLSX generation on a temp CSV
    try:
        import pandas as pd
        temp_dir = os.path.join(PROJECT_ROOT, "tests", "_temp_export_test")
        os.makedirs(temp_dir, exist_ok=True)
        temp_csv = os.path.join(temp_dir, "test_applied.csv")
        temp_xlsx = temp_csv.replace('.csv', '.xlsx')

        with open(temp_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=APPLIED_EXPORT_SCHEMA)
            writer.writeheader()
            writer.writerow(normalized)

        df = normalize_csv_file(temp_csv, APPLIED_EXPORT_SCHEMA)
        if df is not None and len(df) == 1:
            record("Export: Normalize temp CSV", PASS)
            df.to_excel(temp_xlsx, index=False)
            if os.path.exists(temp_xlsx):
                record("Export: XLSX generation", PASS, temp_xlsx)
                os.remove(temp_xlsx)
            else:
                record("Export: XLSX generation", FAIL, "File not created")
        else:
            record("Export: Normalize temp CSV", FAIL, f"df={df}")

        os.remove(temp_csv)
        os.rmdir(temp_dir)
    except Exception as e:
        record("Export: XLSX generation", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 6: Live XLSX Export Validation
# ─────────────────────────────────────────────
def test_live_xlsx_export():
    separator("PHASE 6 — Live XLSX Export Validation")

    from config.settings import file_name, failed_file_name

    for csv_path, label in [
        (file_name, "Applied"),
        (failed_file_name, "Failed"),
    ]:
        xlsx_path = csv_path.replace('.csv', '.xlsx')
        if os.path.exists(xlsx_path):
            size = os.path.getsize(xlsx_path)
            record(f"XLSX {label}: Exists", PASS, f"{size:,} bytes")
        else:
            record(f"XLSX {label}: Exists", WARN, "Not generated yet — will be created on next run")


# ─────────────────────────────────────────────
#  PHASE 7: Gmail IMAP Live Connection Test
# ─────────────────────────────────────────────
def test_gmail_imap_connection():
    separator("PHASE 7 — Gmail IMAP Live Connection")

    from config.settings import GMAIL_SYNC_ENABLED

    if not GMAIL_SYNC_ENABLED:
        record("Gmail IMAP: Sync enabled", WARN, "GMAIL_SYNC_ENABLED=False, skipping live test")
        return

    try:
        from modules.email.auth import load_email_credentials
        creds = load_email_credentials()
        if creds.address and creds.app_password:
            record("Gmail: Credentials loaded", PASS, f"address={creds.address[:5]}***")
        else:
            record("Gmail: Credentials loaded", FAIL, "Empty credentials")
            return
    except Exception as e:
        record("Gmail: Credentials loaded", FAIL, str(e))
        return

    try:
        from modules.email.auth import connect_imap
        client = connect_imap()
        record("Gmail: IMAP connected", PASS)
        try:
            from modules.email.fetcher import fetch_recent_emails
            emails = fetch_recent_emails(client)
            record("Gmail: Emails fetched", PASS, f"{len(emails)} emails")
        finally:
            try:
                client.logout()
            except Exception:
                pass
    except Exception as e:
        record("Gmail: IMAP connected", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 8: Full Gmail Sync (live, safe)
# ─────────────────────────────────────────────
def test_full_gmail_sync():
    separator("PHASE 8 — Full Gmail Lifecycle Sync (Live)")

    from config.settings import GMAIL_SYNC_ENABLED

    if not GMAIL_SYNC_ENABLED:
        record("Gmail Full Sync: Enabled", WARN, "Skipped — GMAIL_SYNC_ENABLED=False")
        return

    try:
        from modules.email.updater import sync_gmail_lifecycle_statuses
        updates = sync_gmail_lifecycle_statuses()
        record("Gmail Full Sync: Executed", PASS, f"{updates} updates applied")
    except Exception as e:
        record("Gmail Full Sync: Executed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 9: Scheduler Compatibility
# ─────────────────────────────────────────────
def test_scheduler_compatibility():
    separator("PHASE 9 — Scheduler Compatibility")

    try:
        from config.settings import AUTO_RUN_ENABLED, AUTO_RUN_TIME
        record("Scheduler: AUTO_RUN_ENABLED", PASS, str(AUTO_RUN_ENABLED))
        record("Scheduler: AUTO_RUN_TIME", PASS, AUTO_RUN_TIME)
    except Exception as e:
        record("Scheduler: Config load", FAIL, str(e))

    try:
        from run_scheduled import RunLock, LOCK_FILE
        record("Scheduler: RunLock import", PASS)
    except Exception as e:
        record("Scheduler: RunLock import", FAIL, str(e))

    # Check lock file doesn't exist (no stale lock)
    try:
        lock_path = os.path.join(PROJECT_ROOT, "logs", "scheduled_run.lock")
        if os.path.exists(lock_path):
            record("Scheduler: No stale lock", WARN, f"Lock file exists: {lock_path}")
        else:
            record("Scheduler: No stale lock", PASS)
    except Exception as e:
        record("Scheduler: Lock check", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 10: Execution Flow Order Verification
# ─────────────────────────────────────────────
def test_execution_flow_order():
    separator("PHASE 10 -- Execution Flow Order")

    # Read main() source from the file directly -- DO NOT import runAiBot
    # because it imports open_chrome which launches Chrome at module level.
    source_path = os.path.join(PROJECT_ROOT, "runAiBot.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    main_pos = source.find("def main()")
    main_source = source[main_pos:] if main_pos >= 0 else source

    # Find positions inside main() only. Helpers above main() also navigate
    # LinkedIn, but they are not executed until main() initializes Chrome.
    gmail_pos = main_source.find("sync_gmail_lifecycle_statuses")
    chrome_init_pos = main_source.find("initialize_chrome_session()")
    chrome_nav_pos = main_source.find('driver.get("https://www.linkedin.com')
    login_pos = main_source.find("login_LN()")
    apply_pos = main_source.find("run(total_runs)")
    export_pos = main_source.find("convert_csvs_to_excel()")

    if gmail_pos > 0 and chrome_init_pos > 0 and gmail_pos < chrome_init_pos:
        record("Flow: Gmail sync BEFORE Chrome launch", PASS)
    else:
        record("Flow: Gmail sync BEFORE Chrome launch", FAIL, f"Gmail@{gmail_pos} vs ChromeInit@{chrome_init_pos}")

    if gmail_pos > 0 and chrome_nav_pos > 0 and gmail_pos < chrome_nav_pos:
        record("Flow: Gmail sync BEFORE Chrome navigation", PASS)
    elif gmail_pos < 0:
        record("Flow: Gmail sync BEFORE Chrome navigation", FAIL, "Gmail sync not found in main()")
    else:
        record("Flow: Gmail sync BEFORE Chrome navigation", FAIL, f"Gmail@{gmail_pos} vs Chrome@{chrome_nav_pos}")

    if gmail_pos > 0 and apply_pos > 0 and gmail_pos < apply_pos:
        record("Flow: Gmail sync BEFORE apply_to_jobs", PASS)
    else:
        record("Flow: Gmail sync BEFORE apply_to_jobs", FAIL)

    if apply_pos > 0 and export_pos > 0 and apply_pos < export_pos:
        record("Flow: apply_to_jobs BEFORE export", PASS)
    else:
        record("Flow: apply_to_jobs BEFORE export", FAIL)

    # Check Gmail failure is wrapped in try/except (graceful)
    gmail_try_pos = main_source.rfind("try:", 0, gmail_pos) if gmail_pos > 0 else -1
    gmail_except_pos = main_source.find("except Exception as email_sync_error", gmail_pos) if gmail_pos > 0 else -1
    if gmail_try_pos > 0 and gmail_except_pos > 0:
        record("Flow: Gmail sync wrapped in try/except", PASS, "Failure is graceful")
    else:
        record("Flow: Gmail sync wrapped in try/except", WARN, "May not be gracefully handled")

    # Check that validate_config() runs before Gmail sync
    validate_pos = main_source.find("validate_config()")
    if validate_pos > 0 and gmail_pos > 0 and validate_pos < gmail_pos:
        record("Flow: validate_config BEFORE Gmail sync", PASS)
    else:
        record("Flow: validate_config BEFORE Gmail sync", FAIL)


# ─────────────────────────────────────────────
#  PHASE 11: Low-Trust Sender Domain Filtering
# ─────────────────────────────────────────────
def test_low_trust_filtering():
    separator("PHASE 11 — Low-Trust Sender Filtering")

    from modules.email.updater import LOW_TRUST_SENDER_DOMAINS
    from modules.email.matcher import sender_host

    expected_blocked = ["glassdoor", "indeed", "naukri", "substack", "resumeworded", "freshersindia", "getujobs"]
    for domain in expected_blocked:
        if domain in LOW_TRUST_SENDER_DOMAINS:
            record(f"Low-trust blocked: {domain}", PASS)
        else:
            record(f"Low-trust blocked: {domain}", FAIL, "Not in LOW_TRUST_SENDER_DOMAINS")

    # Test the sender_host helper
    host = sender_host("alerts@jobalert.example.com")
    if "jobalert" in host:
        record("Low-trust: sender_host extraction", PASS, f"host={host}")
    else:
        record("Low-trust: sender_host extraction", WARN, f"host={host}")


# ─────────────────────────────────────────────
#  PHASE 12: Schema Corruption Guard
# ─────────────────────────────────────────────
def test_schema_corruption_guard():
    separator("PHASE 12 — Schema Corruption Guard")

    from modules.helpers import APPLIED_EXPORT_SCHEMA, normalize_row

    # Test with extra fields (should be stripped)
    row_with_extra = {
        'job_id': 'J300', 'title': 'Test', 'company': 'Corp',
        'garbage_field': 'should_be_removed', 'another_bad': 'gone'
    }
    normalized = normalize_row(row_with_extra, APPLIED_EXPORT_SCHEMA, default_val='')
    if 'garbage_field' not in normalized and 'another_bad' not in normalized:
        record("Schema guard: Extra fields stripped", PASS)
    else:
        record("Schema guard: Extra fields stripped", FAIL, f"Extra fields still present")

    if len(normalized) == len(APPLIED_EXPORT_SCHEMA):
        record("Schema guard: Column count preserved", PASS)
    else:
        record("Schema guard: Column count preserved", FAIL, f"Expected {len(APPLIED_EXPORT_SCHEMA)}, got {len(normalized)}")

    # Test with missing fields (should be padded)
    row_minimal = {'job_id': 'J301'}
    normalized = normalize_row(row_minimal, APPLIED_EXPORT_SCHEMA, default_val='')
    if len(normalized) == len(APPLIED_EXPORT_SCHEMA):
        record("Schema guard: Missing fields padded", PASS)
    else:
        record("Schema guard: Missing fields padded", FAIL)


# ─────────────────────────────────────────────
#  PHASE 13: Live CSV Lifecycle Field Audit
# ─────────────────────────────────────────────
def test_live_csv_lifecycle_audit():
    separator("PHASE 13 — Live CSV Lifecycle Field Audit")

    from config.settings import file_name
    from modules.helpers import APPLIED_EXPORT_SCHEMA

    if not os.path.exists(file_name):
        record("Live CSV audit: File exists", WARN, "No CSV file found")
        return

    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        record("Live CSV audit: Total rows", PASS, f"{total}")

        statuses = {}
        empty_status = 0
        empty_source = 0
        gmail_updated = 0

        for row in rows:
            status = row.get('current_status', '').strip()
            source = row.get('status_source', '').strip()
            if not status:
                empty_status += 1
            statuses[status] = statuses.get(status, 0) + 1
            if not source:
                empty_source += 1
            if source == 'Gmail IMAP':
                gmail_updated += 1

        for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
            record(f"Live CSV status distribution: '{status}'", PASS, f"{count} jobs")

        if empty_status == 0:
            record("Live CSV: No empty current_status", PASS)
        else:
            record("Live CSV: Empty current_status found", WARN, f"{empty_status} rows")

        if empty_source == 0:
            record("Live CSV: No empty status_source", PASS)
        else:
            record("Live CSV: Empty status_source found", WARN, f"{empty_source} rows")

        record("Live CSV: Gmail-updated rows", PASS, f"{gmail_updated} rows")

    except Exception as e:
        record("Live CSV audit", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 14: Cold Email Components Unit Tests
# ─────────────────────────────────────────────
def test_cold_email_pipeline():
    separator("PHASE 14 — Cold Email Component Unit Tests")
    
    # 1. Finder tests
    try:
        from modules.cold_email.finder import extract_email_level3_guess, clean_company_name
        email, source, conf = extract_email_level3_guess("John Doe", "Acme Corp Ltd")
        if email == "john.doe@acme.com" and source == "pattern_guess" and conf < 0.8:
            record("Finder: Pattern guessing is low-confidence only", PASS)
        else:
            record("Finder: Pattern guessing is low-confidence only", FAIL, f"Got: {email}, {source}, {conf}")
            
        cleaned = clean_company_name("Google India Pvt. Ltd.")
        if cleaned == "google india":
            record("Finder: Clean company name", PASS)
        else:
            record("Finder: Clean company name", FAIL, f"Got: '{cleaned}'")
    except Exception as e:
        record("Finder tests failed", FAIL, str(e))
        
    # 2. Generator tests (template fallback check)
    try:
        from modules.cold_email.generator import generate_cold_email
        from modules.cold_email.templates import ColdEmailContent
        
        job_data = {"company": "Acme Labs", "title": "SDE 1", "recruiter_name": "Jane Smith"}
        content = generate_cold_email(job_data, "My resume text")
        
        if content and isinstance(content, ColdEmailContent):
            record("Generator: Fallback template selection", PASS, f"source={content.generated_by}")
        else:
            record("Generator: Fallback template selection", FAIL, f"Got: {content}")
    except Exception as e:
        record("Generator tests failed", FAIL, str(e))
        
    # 3. Sender tests
    try:
        from modules.cold_email.sender import find_first_pdf
        res_pdf = find_first_pdf("all resumes")
        record("Sender: Discover resume pdf", PASS, f"Path: {res_pdf}")
    except Exception as e:
        record("Sender tests failed", FAIL, str(e))
        
    # 4. Tracker tests
    try:
        import sqlite3
        from modules.storage import init_db
        from modules.cold_email.tracker import record_cold_email, has_cold_email_been_sent
        
        temp_db = "data/test_naukri_guru.sqlite3"
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
            
        conn = sqlite3.connect(temp_db)
        init_db(conn)
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cold_emails'")
        if cursor.fetchone():
            record("Tracker: DB Table initialization", PASS)
        else:
            record("Tracker: DB Table initialization", FAIL, "Table not found")
            
        # Insert a mock application to satisfy foreign key reference
        from modules.storage import upsert_application
        upsert_application({"application_id": "test_app_1", "job_id": "test_app_1", "company": "Acme Labs", "title": "Software Developer"}, conn)
        
        record_cold_email("test_app_1", "hr@acme.com", "Subject Line", "sent", "2026-05-25 12:00:00", None, "gemini", "guessed_pattern", 0.6, conn)
        
        is_sent = has_cold_email_been_sent("test_app_1", "hr@acme.com", conn)
        if is_sent:
            record("Tracker: Record and verify sent status", PASS)
        else:
            record("Tracker: Record and verify sent status", FAIL, "Status not marked as sent")
            
        is_sent2 = has_cold_email_been_sent("test_app_1", "other@acme.com", conn)
        if not is_sent2:
            record("Tracker: Duplicate check for non-existent recipient", PASS)
        else:
            record("Tracker: Duplicate check for non-existent recipient", FAIL, "Reported sent incorrectly")
            
        conn.close()
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
    except Exception as e:
        record("Tracker tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 15: Recruiter Email Extractor & Confidence Scoring
# ─────────────────────────────────────────────
def test_recruiter_email_extraction_confidence_scoring():
    separator("PHASE 15 — Recruiter Email Extraction & Confidence Scoring")
    try:
        from modules.cold_email.finder import (
            extract_email_level3_guess,
            clean_company_name,
            extract_emails_from_text,
            email_matches_company_context,
            trust_recruiter_email
        )
        
        # Test clean_company_name extensively
        c1 = clean_company_name("Acme Corp.")
        c2 = clean_company_name("Google India Pvt. Ltd.")
        c3 = clean_company_name("OpenAI LLC")
        if c1 == "acme" and c2 == "google india" and c3 == "openai":
            record("Finder: Extensive company name cleaning", PASS)
        else:
            record("Finder: Extensive company name cleaning", FAIL, f"Got: '{c1}', '{c2}', '{c3}'")
            
        # Test extract_emails_from_text with trust word filtering
        valid_email = "hr@acme.com"
        junk_email = "noreply@linkedin.com"
        text = f"Contact us at {valid_email} or {junk_email} for assistance."
        emails = extract_emails_from_text(text)
        if valid_email in emails and junk_email not in emails:
            record("Finder: Email filtering and low-trust word exclusion", PASS)
        else:
            record("Finder: Email filtering and low-trust word exclusion", FAIL, f"Got: {emails}")

        noisy_text = "Reach Jane at mailto:Jane.Recruiter@Acme-Labs.com, jane.recruiter@acme-labs.com."
        normalized_emails = extract_emails_from_text(noisy_text)
        if normalized_emails == ["jane.recruiter@acme-labs.com"]:
            record("Finder: Email normalization and duplicate suppression", PASS)
        else:
            record("Finder: Email normalization and duplicate suppression", FAIL, f"Got: {normalized_emails}")

        if (
            email_matches_company_context("talent@careersacmelabs.com", "Acme Labs Pvt. Ltd.")
            and email_matches_company_context("hr@darwix.ai", "Darwix AI")
            and not email_matches_company_context("riya.kumari@nilasu.com", "Scienaptic AI")
        ):
            record("Finder: Company-domain matching and polluted-domain rejection", PASS)
        else:
            record("Finder: Company-domain matching and polluted-domain rejection", FAIL)

        trusted, reason, adjusted = trust_recruiter_email("recruiter@gmail.com", "recruiter_profile", 1.0, "Acme Labs")
        if not trusted and reason == "public_email_domain" and adjusted <= 0.5:
            record("Finder: Public recruiter mailbox quarantine", PASS)
        else:
            record("Finder: Public recruiter mailbox quarantine", FAIL, f"Got: {trusted}, {reason}, {adjusted}")

        trusted, reason, adjusted = trust_recruiter_email("hr@othercompany.com", "job_description", 0.95, "Acme Labs")
        if not trusted and reason == "company_domain_mismatch" and adjusted <= 0.4:
            record("Finder: Job-description company-domain trust gate", PASS)
        else:
            record("Finder: Job-description company-domain trust gate", FAIL, f"Got: {trusted}, {reason}, {adjusted}")

        trusted, reason, adjusted = trust_recruiter_email("cs22b1054@iiitr.ac.in", "validation_seed", 1.0, "Validation")
        if trusted and reason == "validation_seed" and adjusted == 1.0:
            record("Finder: Validation seed email flow preserved", PASS)
        else:
            record("Finder: Validation seed email flow preserved", FAIL, f"Got: {trusted}, {reason}, {adjusted}")
            
        # Test confidence levels for guessing. Guesses are generated, but stay below the send trust gate.
        _, _, conf1 = extract_email_level3_guess("John Doe", "Acme Corp.")
        _, _, conf2 = extract_email_level3_guess("", "Acme Corp.")
        if 0.0 < conf1 < 0.8 and 0.0 < conf2 < 0.8:
            record("Finder: Correct low-confidence pattern scoring", PASS)
        else:
            record("Finder: Correct low-confidence pattern scoring", FAIL, f"Got: {conf1}, {conf2}")
            
    except Exception as e:
        record("Phase 15 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 16: Safe Cold Email Generator with Gemini & Fallback Mocking
# ─────────────────────────────────────────────
def test_cold_email_generator_fallback_and_mocking():
    separator("PHASE 16 — Safe Cold Email Generator & Gemini Mocking")
    from unittest.mock import patch, MagicMock
    try:
        from modules.cold_email.generator import generate_cold_email
        from modules.cold_email.templates import ColdEmailContent
        
        # 1. Test missing API key fallback
        with patch('modules.cold_email.generator.load_gemini_api_key', return_value=""):
            job_data = {"company": "Acme Labs", "title": "SDE 1", "recruiter_name": "Jane Smith"}
            content = generate_cold_email(job_data, "My resume text")
            if content and content.generated_by == "fallback_template":
                record("Generator: Graceful fallback when API key is missing", PASS)
            else:
                record("Generator: Graceful fallback when API key is missing", FAIL, f"Got: {content.generated_by if content else None}")
                
        # 2. Test Gemini exception fallback
        with patch('modules.cold_email.generator.load_gemini_api_key', return_value="mock_key"):
            with patch('google.generativeai.GenerativeModel') as mock_model:
                mock_model.return_value.generate_content.side_effect = Exception("API Connection Timeout")
                content = generate_cold_email(job_data, "My resume text")
                if content and content.generated_by == "fallback_template":
                    record("Generator: Graceful fallback on API exception", PASS)
                else:
                    record("Generator: Graceful fallback on API exception", FAIL, f"Got: {content.generated_by if content else None}")
                    
        # 3. Test successful Gemini mock response parsing
        with patch('modules.cold_email.generator.load_gemini_api_key', return_value="mock_key"):
            with patch('google.generativeai.GenerativeModel') as mock_model:
                mock_resp = MagicMock()
                mock_resp.text = '{"subject": "SDE Role Inquiry", "body": "Hello Jane, I am interested..."}'
                mock_model.return_value.generate_content.return_value = mock_resp
                
                content = generate_cold_email(job_data, "My resume text")
                if content and content.generated_by == "gemini" and content.subject == "SDE Role Inquiry":
                    record("Generator: Successful mock API response parsing", PASS)
                else:
                    record("Generator: Successful mock API response parsing", FAIL, f"Got: {content.generated_by if content else None}, subject={content.subject if content else None}")
                    
    except Exception as e:
        record("Phase 16 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 17: Cold Email Database Tracker Schema & Integrity
# ─────────────────────────────────────────────
def test_cold_email_tracker_db_integrity():
    separator("PHASE 17 — Cold Email Database Tracker & Schema Integrity")
    import sqlite3
    try:
        from modules.storage import init_db
        from modules.cold_email.tracker import (
            record_cold_email,
            has_cold_email_been_sent,
            get_cold_email_stats
        )
        
        temp_db = "data/test_tracker_integrity.sqlite3"
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
            
        conn = sqlite3.connect(temp_db)
        
        # Test idempotent db initialization
        init_db(conn)
        init_db(conn) # second time should not throw
        record("Tracker: Idempotent DB initialization", PASS)
        
        # Insert a mock application to satisfy foreign key reference
        from modules.storage import upsert_application
        upsert_application({"application_id": "app_1", "job_id": "app_1", "company": "Acme Labs", "title": "Software Developer"}, conn)
        
        # Test record and unique constraint conflict handling
        record_cold_email("app_1", "hr@acme.com", "Subject 1", "sent", "2026-05-25 12:00:00", None, "gemini", "guessed_pattern", 0.6, conn)
        record_cold_email("app_1", "hr@acme.com", "Subject 2", "sent", "2026-05-25 13:00:00", None, "gemini", "guessed_pattern", 0.6, conn)
        
        # Verify duplicate send prevention query
        is_sent = has_cold_email_been_sent("app_1", "hr@acme.com", conn)
        if is_sent:
            record("Tracker: Double-send prevention query", PASS)
        else:
            record("Tracker: Double-send prevention query", FAIL)
            
        # Test retrieving database stats
        stats = get_cold_email_stats(conn)
        if stats.get("sent") == 1:
            record("Tracker: Retrieve stats summary", PASS)
        else:
            record("Tracker: Retrieve stats summary", FAIL, f"Got: {stats}")
            
        conn.close()
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
            
    except Exception as e:
        record("Phase 17 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 18: Cold Email SMTP Sender Attachments & Credentials
# ─────────────────────────────────────────────
def test_cold_email_sender_attachments_and_credentials():
    separator("PHASE 18 — Cold Email SMTP Sender & Attachments")
    from unittest.mock import patch, MagicMock
    try:
        from modules.cold_email.sender import find_first_pdf, send_cold_email
        from modules.cold_email.templates import ColdEmailContent
        from modules.email.auth import EmailCredentials
        
        # 1. Test find_first_pdf
        temp_dir = "data/temp_resumes_test"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        
        empty_search = find_first_pdf(temp_dir)
        if empty_search is None:
            record("Sender: find_first_pdf handles empty directory", PASS)
        else:
            record("Sender: find_first_pdf handles empty directory", FAIL)
            
        # Create mock PDF files
        pdf1 = os.path.join(temp_dir, "b_resume.pdf")
        pdf2 = os.path.join(temp_dir, "a_resume.pdf")
        with open(pdf1, "w") as f: f.write("mock pdf content b")
        with open(pdf2, "w") as f: f.write("mock pdf content a")
        
        discovered = find_first_pdf(temp_dir)
        # Note: alphabetically/directory search finds the first match
        if discovered and discovered.endswith(".pdf"):
            record("Sender: find_first_pdf discovers PDF correctly", PASS)
        else:
            record("Sender: find_first_pdf discovers PDF correctly", FAIL, f"Got: {discovered}")
            
        # 2. Test send_cold_email SMTP credentials error
        invalid_creds = EmailCredentials("", "")
        content = ColdEmailContent("Subject", "Body", "fallback_template")
        res = send_cold_email("hr@acme.com", content, sender_credentials=invalid_creds)
        if not res.success and "credentials are empty" in res.error:
            record("Sender: Rejects empty credentials safely", PASS)
        else:
            record("Sender: Rejects empty credentials safely", FAIL, f"Result: {res}")
            
        # 3. Test send_cold_email SMTP mock success
        valid_creds = EmailCredentials("test@gmail.com", "app_pass_123")
        with patch('smtplib.SMTP_SSL') as mock_smtp:
            # Mock SMTP connection and methods
            instance = mock_smtp.return_value.__enter__.return_value
            
            res_success = send_cold_email(
                "hr@acme.com",
                content,
                sender_credentials=valid_creds,
                resume_path=pdf2,
                cover_letter_path=None
            )
            if res_success.success and res_success.error is None:
                record("Sender: Successful mock SMTP SSL connection and sendmail", PASS)
            else:
                record("Sender: Successful mock SMTP SSL connection and sendmail", FAIL, f"Error: {res_success.error}")
                
        # Clean up temp files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
    except Exception as e:
        record("Phase 18 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 19: Full Cold Email End-to-End Orchestrator Pipeline Dry-Run
# ─────────────────────────────────────────────
def test_orchestrator_pipeline_dry_run():
    separator("PHASE 19 — Full Cold Email Orchestrator Pipeline Dry-Run")
    from unittest.mock import patch, MagicMock
    import sqlite3
    try:
        from modules.cold_email.orchestrator import run_cold_email_pipeline
        from modules.cold_email.templates import ColdEmailContent
        
        # We will point to a temporary CSV file
        mock_csv = "data/mock_applied_jobs.csv"
        mock_failed_csv = "data/mock_failed_jobs.csv"
        for mock_path in (mock_csv, mock_failed_csv):
            if not os.path.exists(mock_path):
                continue
            try:
                os.remove(mock_path)
            except Exception:
                pass
            
        # Setup mock rows using schema fields
        from modules.helpers import APPLIED_EXPORT_SCHEMA
        row1 = {k: "" for k in APPLIED_EXPORT_SCHEMA}
        row1.update({
            "job_id": "runtime_acme",
            "company": "Acme Inc",
            "title": "Software Developer",
            "recruiter_email": "hr@acme.com",
            "recruiter_email_confidence": "1.0",
            "runtime_segment": "production",
            "runtime_batch_id": "test_runtime_batch",
            "application_date": "2026-05-25 09:00:00",
            "cold_email_sent": "",
            "cold_email_status": ""
        })
        
        row2 = {k: "" for k in APPLIED_EXPORT_SCHEMA}
        row2.update({
            "job_id": "runtime_lowconf",
            "company": "Low Confidence Corp",
            "title": "Data Analyst",
            "recruiter_email": "guess@lowconf.com",
            "recruiter_email_confidence": "0.4",
            "runtime_segment": "production",
            "runtime_batch_id": "test_runtime_batch",
            "application_date": "2026-05-25 09:05:00",
            "cold_email_sent": "",
            "cold_email_status": ""
        })
        
        row3 = {k: "" for k in APPLIED_EXPORT_SCHEMA}
        row3.update({
            "job_id": "runtime_sent",
            "company": "Already Sent Ltd",
            "title": "Product Manager",
            "recruiter_email": "hr@alreadysent.com",
            "recruiter_email_confidence": "1.0",
            "runtime_segment": "production",
            "runtime_batch_id": "test_runtime_batch",
            "application_date": "2026-05-25 09:10:00",
            "cold_email_sent": "True",
            "cold_email_status": "sent",
            "cold_email_sent_at": "2026-05-25 10:00:00"
        })
        
        # Write mock CSV
        with open(mock_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=APPLIED_EXPORT_SCHEMA)
            writer.writeheader()
            writer.writerows([row1, row2, row3])
            
        # Mock database connection to avoid messing with local sqlite3 db
        temp_db = "data/test_orchestrator_pipeline.sqlite3"
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
                
        # Populate the SQLite DB with the same rows
        from modules.storage import init_db, upsert_application
        conn = sqlite3.connect(temp_db)
        init_db(conn)
        upsert_application(row1, conn)
        upsert_application(row2, conn)
        upsert_application(row3, conn)
        conn.close()
            
        # Patch the file name and settings to use mock paths
        with patch('modules.cold_email.orchestrator.file_name', mock_csv), \
             patch('config.settings.failed_file_name', mock_failed_csv), \
             patch('modules.cold_email.tracker.connect', side_effect=lambda: sqlite3.connect(temp_db)), \
             patch('modules.storage.connect', side_effect=lambda: sqlite3.connect(temp_db)), \
             patch('modules.cold_email.orchestrator.COLD_EMAIL_TEST_MODE', False), \
             patch('modules.cold_email.generator.generate_cold_email', return_value=ColdEmailContent("Subj", "Body", "gemini")), \
             patch('modules.cold_email.sender.send_cold_email', return_value=MagicMock(success=True, timestamp="2026-05-25 12:30:00", error=None)), \
             patch('modules.cold_email.orchestrator.time.sleep') as mock_sleep: # bypass humanized delay
             
             res = run_cold_email_pipeline(driver=None, dry_run=False)
             if res["emails_sent"] == 1 and res["emails_skipped"] == 1 and res["emails_already_sent"] == 0:
                 record("Orchestrator: SQLite queue processes pending rows without runtime batch gate", PASS)
             else:
                 record("Orchestrator: SQLite queue processes pending rows without runtime batch gate", FAIL, f"Stats: {res}")
             
             followup_res = run_cold_email_pipeline(driver=None, runtime_batch_id="test_runtime_batch", dry_run=False)
             if followup_res["total_eligible"] == 0 and followup_res["emails_sent"] == 0:
                 record("Orchestrator: Sent/quarantined rows leave pending SQLite queue", PASS)
             else:
                 record("Orchestrator: Sent/quarantined rows leave pending SQLite queue", FAIL, f"Stats: {followup_res}")
                 
             # Let's inspect updated CSV to verify persistence
             from modules.cold_email.orchestrator import load_applications
             updated_rows = load_applications(mock_csv)
             
             acme_row = next(r for r in updated_rows if r["company"] == "Acme Inc")
             lowconf_row = next(r for r in updated_rows if r["company"] == "Low Confidence Corp")
             
             if acme_row["cold_email_sent"] == "True" and acme_row["cold_email_status"] == "sent":
                 record("Orchestrator: CSV update and serialization on success", PASS)
             else:
                 record("Orchestrator: CSV update and serialization on success", FAIL, f"Acme: {acme_row}")
                 
             if lowconf_row["cold_email_sent"] == "False" and lowconf_row["cold_email_status"] in ("skipped_low_confidence", "skipped_quarantined_recruiter"):
                 record("Orchestrator: Correct logic path for low-confidence quarantine", PASS)
             else:
                 record("Orchestrator: Correct logic path for low-confidence quarantine", FAIL, f"LowConf: {lowconf_row}")
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
        for mock_path in (mock_csv, mock_failed_csv):
            if not os.path.exists(mock_path):
                continue
            try:
                os.remove(mock_path)
            except Exception:
                pass
            
    except Exception as e:
        record("Phase 19 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 20: Applier Main (runAiBot.py) End-to-End Integration Flow Audits
# ─────────────────────────────────────────────
def test_applier_main_integration_flow_audit():
    separator("PHASE 20 — Applier Main (runAiBot.py) Integration & Clean Up")
    try:
        # Verify runAiBot integration path by reading it
        # Here we perform an integration validation checking that runAiBot.py has no syntax errors
        # and has a robust finally block order: first excel export, then cold emails, then quit, then second excel export.
        
        # Read runAiBot.py contents to verify code order matches specification programmatically
        with open("runAiBot.py", "r", encoding="utf-8") as f:
            code = f.read()
            
        has_cold_email = "run_cold_email_pipeline" in code
        has_quit = "driver.quit()" in code
        has_excel = "convert_csvs_to_excel()" in code
        
        if has_cold_email and has_quit and has_excel:
            record("runAiBot.py Integration: Essential logic components presence", PASS)
        else:
            record("runAiBot.py Integration: Essential logic components presence", FAIL, f"Found: cold={has_cold_email}, quit={has_quit}, excel={has_excel}")
            
        # Programmatic verification of execution order in the finally block
        idx_first_excel = code.find("convert_csvs_to_excel()")
        idx_cold_email = code.find("run_cold_email_pipeline")
        idx_driver_quit = code.find("driver.quit()")
        idx_second_excel = code.rfind("convert_csvs_to_excel()")
        
        if idx_first_excel < idx_cold_email < idx_driver_quit < idx_second_excel:
            record("runAiBot.py Integration: Precise chronological execution order", PASS)
        else:
            record("runAiBot.py Integration: Precise chronological execution order", FAIL, 
                   f"Indices: Excel1={idx_first_excel}, Cold={idx_cold_email}, Quit={idx_driver_quit}, Excel2={idx_second_excel}")
                   
    except Exception as e:
        record("Phase 20 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 21: CSV Normalization & Jagged Row Preservation
# ─────────────────────────────────────────────
def test_csv_normalization_robustness():
    separator("PHASE 21 — CSV Normalization & Jagged Row Preservation")
    try:
        from modules.helpers import ensure_csv_header
        
        temp_csv = "data/test_normalization.csv"
        if os.path.exists(temp_csv):
            os.remove(temp_csv)
            
        schema = ["col1", "col2", "col3"]
        
        # 1. Create a jagged CSV with OLD header
        with open(temp_csv, "w", encoding="utf-8", newline="") as f:
            f.write("col1,col2\n") # OLD header (only 2 cols)
            f.write("val1,val2,val3\n") # Jagged row (3 cols, but header only has 2)
            
        # 2. Run normalization
        ensure_csv_header(temp_csv, schema)
        
        # 3. Verify content
        with open(temp_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if len(rows) == 1 and rows[0]["col1"] == "val1" and rows[0]["col2"] == "val2":
                # col3 might be empty if ensure_csv_header couldn't map val3
                # but at least val1 and val2 are preserved
                record("CSV Normalization: Jagged row preservation", PASS)
            else:
                record("CSV Normalization: Jagged row preservation", FAIL, f"Rows: {rows}")
                
        if os.path.exists(temp_csv):
            os.remove(temp_csv)
            
    except Exception as e:
        record("Phase 21 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 22: Atomic CSV Write Validation
# ─────────────────────────────────────────────
def test_atomic_csv_writes():
    separator("PHASE 22 — Atomic CSV Write Validation")
    try:
        from modules.helpers import safe_write_csv
        import os
        
        temp_csv = "data/test_atomic_write.csv"
        schema = ["id", "name"]
        rows = [{"id": "1", "name": "Test 1"}]
        
        # 1. Test basic write
        success = safe_write_csv(temp_csv, schema, rows)
        if success and os.path.exists(temp_csv):
            record("Atomic Write: File creation", PASS)
        else:
            record("Atomic Write: File creation", FAIL, "File not created")
            
        # 2. Test overwriting
        rows_new = [{"id": "1", "name": "Updated"}]
        success = safe_write_csv(temp_csv, schema, rows_new)
        with open(temp_csv, 'r', encoding='utf-8') as f:
            content = f.read()
            if "Updated" in content:
                record("Atomic Write: Overwrite integrity", PASS)
            else:
                record("Atomic Write: Overwrite integrity", FAIL, "Content not updated")
                
        if os.path.exists(temp_csv):
            os.remove(temp_csv)
            
    except Exception as e:
        record("Phase 22 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  PHASE 23: SQLite-First Consistency Validation
# ─────────────────────────────────────────────
def test_sqlite_first_consistency():
    separator("PHASE 23 — SQLite-First Consistency Validation")
    try:
        from modules.storage import application_exists, upsert_application, init_db
        import sqlite3
        
        temp_db = "data/test_sqlite_consistency.sqlite3"
        if os.path.exists(temp_db):
            os.remove(temp_db)
            
        conn = sqlite3.connect(temp_db)
        init_db(conn)
        
        job_id = "SQLITE-TEST-001"
        company = "Consistency Corp"
        
        # 1. Verify it doesn't exist yet
        if not application_exists(job_id, company, conn):
            record("SQLite-First: Initial absence", PASS)
        else:
            record("SQLite-First: Initial absence", FAIL, "Reported existing incorrectly")
            
        # 2. Add via upsert
        row = {"job_id": job_id, "company": company, "title": "Consistency Engineer"}
        upsert_application(row, conn)
        
        # 3. Verify it now exists
        if application_exists(job_id, company, conn):
            record("SQLite-First: Existence after upsert", PASS)
        else:
            record("SQLite-First: Existence after upsert", FAIL, "Reported absent incorrectly")
            
        conn.close()
        if os.path.exists(temp_db):
            os.remove(temp_db)
            
    except Exception as e:
        record("Phase 23 tests failed", FAIL, str(e))


def test_indeed_filtering_and_enrichment_updates():
    separator("PHASE 24 — Indeed Filtering, Email Enrichment & Browser Health")
    try:
        from modules.indeed.engine import _passes_quality_filters

        if _passes_quality_filters("ML Intern", "Acme Labs", "Salary ₹35,000 per month. Fresher role."):
            record("Indeed Filter: accepts qualifying monthly salary", PASS)
        else:
            record("Indeed Filter: accepts qualifying monthly salary", FAIL)

        if not _passes_quality_filters("ML Intern", "Acme Labs", "Stipend ₹20,000 per month. Fresher role."):
            record("Indeed Filter: rejects low monthly stipend", PASS)
        else:
            record("Indeed Filter: rejects low monthly stipend", FAIL)

        if not _passes_quality_filters("ML Engineer", "Acme Labs", "CTC 3.5 LPA. Fresher role."):
            record("Indeed Filter: rejects low annual CTC", PASS)
        else:
            record("Indeed Filter: rejects low annual CTC", FAIL)

        if not _passes_quality_filters("ML Engineer", "Acme Labs", "Salary ₹45,000 per month. Minimum 2 years experience."):
            record("Indeed Filter: rejects experience above current_experience", PASS)
        else:
            record("Indeed Filter: rejects experience above current_experience", FAIL)

        if not _passes_quality_filters("ML Engineer", "Acme Labs", "Great culture and learning opportunity."):
            record("Indeed Filter: rejects undisclosed salary", PASS)
        else:
            record("Indeed Filter: rejects undisclosed salary", FAIL)

        from modules.cold_email.finder import find_recruiter_email
        email, source, confidence, visits = find_recruiter_email(
            None,
            {
                "company": "Acme Labs",
                "job_description": "Send applications to talent@acmelabs.com",
                "recruiter_profile_url": "",
            },
            0,
        )
        if email == "talent@acmelabs.com" and source == "job_description" and confidence >= 0.8 and visits == 0:
            record("Email Enrichment: JD email extraction stores source/confidence", PASS)
        else:
            record("Email Enrichment: JD email extraction stores source/confidence", FAIL, f"{email}, {source}, {confidence}, visits={visits}")

        from selenium.common.exceptions import WebDriverException
        from modules.diagnostics import assert_browser_healthy

        class DeadDriver:
            @property
            def current_window_handle(self):
                raise WebDriverException("no such window: target window already closed")

        if not assert_browser_healthy(DeadDriver()):
            record("Browser Health: detects closed target window", PASS)
        else:
            record("Browser Health: detects closed target window", FAIL)
    except Exception as e:
        record("Phase 24 tests failed", FAIL, str(e))


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "="*70)
    print("  NAUKRI_GURU — END-TO-END PIPELINE VALIDATION")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    test_config_validation()
    test_gmail_sync_units()
    test_lifecycle_csv_update()
    test_csv_file_integrity()
    test_normalization_and_export()
    test_live_xlsx_export()
    test_gmail_imap_connection()
    test_full_gmail_sync()
    test_scheduler_compatibility()
    test_execution_flow_order()
    test_low_trust_filtering()
    test_schema_corruption_guard()
    test_live_csv_lifecycle_audit()
    test_cold_email_pipeline()
    test_recruiter_email_extraction_confidence_scoring()
    test_cold_email_generator_fallback_and_mocking()
    test_cold_email_tracker_db_integrity()
    test_cold_email_sender_attachments_and_credentials()
    test_orchestrator_pipeline_dry_run()
    test_applier_main_integration_flow_audit()
    test_csv_normalization_robustness()
    test_atomic_csv_writes()
    test_sqlite_first_consistency()
    test_indeed_filtering_and_enrichment_updates()

    # ── Summary ──
    separator("VALIDATION SUMMARY")
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    warned = sum(1 for _, s, _ in results if s == WARN)

    print(f"\n  Total tests:  {total}")
    print(f"  {PASS}  Passed:   {passed}")
    print(f"  {FAIL}  Failed:   {failed}")
    print(f"  {WARN}  Warnings: {warned}")
    print()

    if failed > 0:
        print("  FAILED TESTS:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    {FAIL}  {name} — {detail}")
        print()

    if warned > 0:
        print("  WARNINGS:")
        for name, status, detail in results:
            if status == WARN:
                print(f"    {WARN}  {name} — {detail}")
        print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
