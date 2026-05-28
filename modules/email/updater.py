import csv
from datetime import datetime
import os

from config.settings import (
    GMAIL_CLASSIFICATION_THRESHOLD,
    GMAIL_MATCH_THRESHOLD,
    GMAIL_SYNC_ENABLED,
    file_name,
)
from modules.email.auth import connect_imap
from modules.email.classifier import classify_email
from modules.email.fetcher import EmailRecord, fetch_recent_emails
from modules.email.matcher import match_email_to_application, sender_domain, sender_host
from modules.helpers import APPLIED_EXPORT_SCHEMA, normalize_row, print_lg, safe_write_csv
from modules.storage import add_lifecycle_event, application_id_for, migrate_csv_to_db, upsert_application, get_all_applications, db_row_to_schema_dict, export_db_to_csv


STATUS_PRIORITY = {
    "Applied": 10,
    "Viewed": 20,
    "Under Review": 30,
    "Shortlisted": 40,
    "OA Received": 50,
    "Interview Scheduled": 60,
    "On Hold": 65,
    "Rejected": 90,
    "Offer": 100,
    "Ghosted": 35,
    "Withdrawn": 95,
}

LOW_TRUST_SENDER_DOMAINS = {
    "glassdoor",
    "indeed",
    "jobalert",
    "monsterindia",
    "naukri",
    "substack",
    "resumeworded",
    "freshersindia",
    "getujobs",
    "interviewkickstart",
}


def _load_applications() -> list[dict[str, str]]:
    if not os.path.exists(file_name):
        return []

    with open(file_name, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [normalize_row(row, APPLIED_EXPORT_SCHEMA, default_val="") for row in reader]


def _write_applications(applications: list[dict[str, str]]) -> None:
    safe_write_csv(file_name, APPLIED_EXPORT_SCHEMA, applications)


def _email_timestamp(record: EmailRecord) -> str:
    return (record.date or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _can_update_status(current_status: str, new_status: str) -> bool:
    current_priority = STATUS_PRIORITY.get(current_status or "Applied", 10)
    new_priority = STATUS_PRIORITY.get(new_status, 10)
    if current_status in {"Rejected", "Offer"} and new_status not in {"Rejected", "Offer"}:
        return False
    return new_priority >= current_priority or new_status in {"Rejected", "Offer"}


def _safe_sender(sender_email: str) -> str:
    if "@" not in sender_email:
        return "unknown sender"
    local, domain = sender_email.split("@", 1)
    return f"{local[:2]}***@{domain}"


def apply_email_updates(applications: list[dict[str, str]], records: list[EmailRecord]) -> int:
    updates = 0
    for record in records:
        domain = sender_domain(record.sender_email)
        host = sender_host(record.sender_email)
        low_trust_match = next((blocked for blocked in LOW_TRUST_SENDER_DOMAINS if blocked in host), "")
        if low_trust_match:
            print_lg(f"Gmail email skipped from low-trust sender domain: {low_trust_match}")
            continue

        classification = classify_email(record)
        if classification is None:
            continue
        print_lg(
            f"Gmail classification result: {classification.status} "
            f"(confidence={classification.confidence:.2f}) from {_safe_sender(record.sender_email)}"
        )

        if classification.confidence < GMAIL_CLASSIFICATION_THRESHOLD:
            print_lg(
                f"Gmail classification skipped below threshold: status={classification.status}, "
                f"confidence={classification.confidence:.2f}, threshold={GMAIL_CLASSIFICATION_THRESHOLD:.2f}"
            )
            continue

        match = match_email_to_application(record, applications)
        if match is None or match.confidence < GMAIL_MATCH_THRESHOLD:
            detail = "none" if match is None else f"{match.confidence:.2f}/{match.reasons}"
            print_lg(f"No matching application found for Gmail status '{classification.status}' (best={detail}).")
            continue

        application = applications[match.index]
        print_lg(
            f"Gmail match confidence: job_id={application.get('job_id', '')}, "
            f"company={application.get('company', '')}, confidence={match.confidence:.2f}, "
            f"threshold={GMAIL_MATCH_THRESHOLD:.2f}, reasons={','.join(match.reasons)}"
        )
        current_status = application.get("current_status", "Applied")
        if not _can_update_status(current_status, classification.status):
            print_lg(
                f"Gmail match skipped for job_id={application.get('job_id', '')}: "
                f"current_status={current_status}, detected_status={classification.status}"
            )
            continue

        application["current_status"] = classification.status
        application["last_status_update"] = _email_timestamp(record)
        application["status_source"] = "Gmail IMAP"
        application["response_received"] = "True"
        if record.sender_email and not application.get("recruiter_email"):
            application["recruiter_email"] = record.sender_email
            print_lg(f"Matched recruiter email for job_id={application.get('job_id', '')}: {_safe_sender(record.sender_email)}")
        print_lg(
            f"Lifecycle update prepared: job_id={application.get('job_id', '')}, "
            f"current_status={application['current_status']}, "
            f"last_status_update={application['last_status_update']}, "
            f"response_received={application['response_received']}, "
            f"status_source={application['status_source']}"
        )

        application_id = application_id_for(application)
        upsert_application(application)
        add_lifecycle_event(
            application_id,
            classification.status,
            event_time=application["last_status_update"],
            source="Gmail IMAP",
            confidence=match.confidence,
            message_id=record.message_id,
            details={
                "sender": _safe_sender(record.sender_email),
                "classification_confidence": classification.confidence,
                "match_reasons": match.reasons,
                "matched_keywords": classification.matched_keywords,
            },
        )

        updates += 1
        print_lg(
            f"Status updated from Gmail: application_id={application_id}, job_id={application.get('job_id', '')}, "
            f"company={application.get('company', '')}, status={classification.status}, "
            f"match_confidence={match.confidence:.2f}, reasons={','.join(match.reasons)}"
        )
    return updates


def sync_gmail_lifecycle_statuses() -> int:
    if not GMAIL_SYNC_ENABLED:
        print_lg("Gmail sync skipped because GMAIL_SYNC_ENABLED is False.")
        return 0

    try:
        apps = get_all_applications()
        if not apps:
            print_lg("Gmail sync skipped because no applications were found in SQLite.")
            return 0
        applications = [db_row_to_schema_dict(app) for app in apps]

        client = connect_imap()
        try:
            print_lg("Gmail connected via IMAP.")
            records = fetch_recent_emails(client)
            print_lg(f"Emails fetched from Gmail inbox: {len(records)}")
        finally:
            try:
                client.logout()
            except Exception:
                pass

        updates = apply_email_updates(applications, records)
        if updates:
            export_db_to_csv(file_name)
            print_lg(f"Gmail lifecycle sync completed with {updates} status update(s) and synced to CSV.")
        else:
            print_lg("Gmail lifecycle sync completed with no status updates.")
        return updates
    except Exception as exc:
        print_lg(f"Gmail lifecycle sync failed safely: {type(exc).__name__}: {exc}")
        return 0
