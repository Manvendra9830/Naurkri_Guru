# Naukri_Guru Manual QA Stabilization Checklist

Use this checklist for controlled production-hardening checks. Do not run it as a bulk automation session. The goal is to observe one controlled path at a time and confirm that SQLite, logs, and exports agree.

## Safety Rules

- Do not send real cold emails during QA unless you intentionally enable outreach and verify the recipient.
- Do not use unreviewed recruiter emails for outreach.
- Keep Excel files closed while the bot writes exports.
- Keep `MAX_APPLICATIONS_PER_RUN` low during QA, ideally `1`.
- Preserve `data/runtime_backups/` and do not delete historical rows manually.

## Pre-Run Checklist

Codex-side expectations already in place:

- SQLite is the runtime source of truth.
- CSV/XLSX are export layers.
- `runtime_segment` separates production, quarantined recruiter rows, and validation rows.
- Known contaminated recruiter emails are quarantined.
- Easy Apply persistence requires LinkedIn confirmation.

Manual user checks before a controlled run:

- Open `config/settings.py`.
- Confirm `MAX_APPLICATIONS_PER_RUN = 1`.
- For apply QA only, keep cold email sending disabled or test-safe.
- Close `all excels/*.xlsx`.
- Open `logs/log.txt` in a viewer that does not lock the file, or close it before running.
- Confirm the automation Chrome profile is logged into LinkedIn.

## Controlled Dry-Run QA Flow

This is the safest sequence for one controlled application attempt.

1. Start from a normal terminal, not from inside Codex.
2. Run:

```powershell
.\venv\Scripts\python.exe runAiBot.py
```

3. Watch for Chrome launch and LinkedIn login state.
4. Let the bot process only one candidate job.
5. If the Easy Apply final review modal appears, manually inspect the answers.
6. Do not click LinkedIn buttons yourself unless the bot explicitly pauses for you.
7. After the run ends, close Chrome only after logs stop updating.
8. Open SQLite, CSV, XLSX, and logs for verification.

## Expected Runtime Signals

### Confirmed Apply

Expected log sequence:

- `[EASY-APPLY-MODAL-OPEN]`
- `[APPLY-DEBUG]`
- `[APPLY-CONFIRMED]`
- `[APPLY-SUCCESS] Confirmed application`
- `[APPLICATION-SAVED]`
- `[SYNC-SUCCESS]`
- `[EXPORT-SUCCESS]`

Expected persistence:

- New or updated row in `applications`.
- `application_date` is a real timestamp, not `Pending`.
- `current_status = Applied`.
- `status_source = LinkedIn Automation`.
- `runtime_segment = production`.
- CSV and XLSX row counts match SQLite after export.

### Failed Apply

Expected log sequence:

- `[APPLY-FAILURE]`
- `Failed to Easy apply!`
- failure reason in log

Expected persistence:

- No clean production applied row for that job.
- Row should appear in `failed_applications`.
- Failure export should include the row after export.
- Screenshot may exist under `logs/screenshots/` if the failure path captured one.

### Unverified Apply

Expected log sequence:

- `[APPLY-UNVERIFIED]`
- failure message containing missing LinkedIn confirmation
- `[APPLY-FAILURE]`

Expected persistence:

- No clean applied row should be written.
- No success counter should be trusted for that job.
- Failure record should be present or the job should be skipped/recovered.
- If `submitted_jobs()` is reached with `Pending`, it must emit `[PERSISTENCE-BLOCKED]`.

### Cold Email Sent

Only validate this in explicit email QA mode.

Expected log sequence:

- `Starting Smart Recruiter Outreach System`
- recruiter trust/enrichment logs
- `Cold email sent successfully`
- `Smart Cold Emailing Pipeline completed`

Expected persistence:

- `cold_emails.status = sent`.
- `applications.cold_email_sent = True`.
- `applications.cold_email_status = sent`.
- `cold_email_recipient` stores the original intended recruiter email.
- In test mode, manually verify whether SMTP sent to the whitelisted target.

### Recruiter Enrichment Skipped

Expected log sequence:

- `[ENRICHMENT-SAFE]` for blind domain guessing skipped
- `[ENRICHMENT-QUARANTINE]` for unsafe/test/contaminated emails
- `[COLD-EMAIL-SKIP]` for non-production or untrusted recruiter rows

Expected persistence:

- No guessed recruiter email should be inserted.
- Quarantined recruiter rows remain `runtime_segment = quarantined_recruiter`.
- Production rows with no trusted email remain blank rather than filled with noisy data.

## Runtime Recovery Expectations

Browser or Selenium failure:

- Log should include browser health or WebDriver exception context.
- The run should fail safely instead of writing a false applied row.
- Existing SQLite rows should remain intact.

LinkedIn modal changed:

- Log should show `[APPLY-DEBUG]` visible buttons.
- If confirmation cannot be detected, the row must not be persisted as applied.
- Add the observed button/modal text to the QA notes before changing selectors.

Excel file locked:

- CSV/XLSX export should log a write failure.
- SQLite should remain the source of truth.
- Close Excel and rerun export only, not the live bot.

Recruiter email contamination:

- Known contaminated emails must not return to production rows.
- Any repeated recruiter email across unrelated companies should be manually quarantined before outreach.

## Export Verification Checklist

After a controlled run:

1. Open SQLite Browser.
2. Run:

```sql
SELECT COALESCE(runtime_segment, 'production') AS segment, COUNT(*) AS rows
FROM applications
GROUP BY segment
ORDER BY rows DESC;
```

3. Run:

```sql
SELECT COUNT(*) AS active_contaminated_rows
FROM applications
WHERE COALESCE(runtime_segment, 'production') = 'production'
  AND lower(recruiter_email) IN (
    'riya.kumari@nilasu.com',
    'rosysmita.jena@atyeti.com'
  );
```

4. Confirm `active_contaminated_rows = 0`.
5. Open `all excels/all_applied_applications_history.xlsx`.
6. Confirm `runtime_history` has production rows first.
7. Confirm `summary` counts match SQLite segment counts.
8. Open `all excels/all_failed_applications_history.xlsx`.
9. Confirm failed rows are understandable and not mixed into applied history.

## Manual QA Stop Points

Pause and review manually when any of these occur:

- `[APPLY-UNVERIFIED]`
- `[PERSISTENCE-BLOCKED]`
- repeated recruiter email across unrelated companies
- `cold_email_status = failed`
- Excel export permission failure
- CAPTCHA/checkpoint/login-wall detection
- any new LinkedIn modal text that prevents confirmation detection

## QA Outcome Template

Record one outcome per controlled run:

```text
Date/time:
Run type: Easy Apply / Export only / Gmail sync / Cold email test
MAX_APPLICATIONS_PER_RUN:
Cold email enabled:
Observed result:
Expected signals present:
Unexpected signals:
SQLite row count before:
SQLite row count after:
CSV/XLSX verified:
Manual notes:
Decision: pass / needs fix / quarantine data
```
