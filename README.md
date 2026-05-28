# Naukri_Guru - AI-Powered Job Automation Platform

Naukri_Guru automates LinkedIn job search and Easy Apply flows, syncs recruiter email outcomes from Gmail IMAP, stores normalized application data in SQLite, and exports clean CSV/XLSX reports.

## Production Setup

Windows:

```powershell
.\setup.ps1
```

Linux/macOS:

```bash
chmod +x setup.sh
./setup.sh
```

The setup scripts:

- create `venv`
- install pinned dependencies from `requirements.txt`
- verify Python 3.10+
- verify package imports
- detect Google Chrome and print its installed version/path

Run environment validation any time:

```powershell
.\venv\Scripts\python.exe tools\validate_environment.py
```

## Why These Dependencies Exist

- `selenium`: browser automation and Selenium Manager fallback driver resolution.
- `undetected-chromedriver`: stealth Chrome startup for LinkedIn automation.
- `webdriver-manager`: explicit driver-management utility for future startup recovery paths.
- `pandas` and `openpyxl`: cleaned CSV/XLSX export generation.
- `beautifulsoup4` and `requests`: HTML parsing and HTTP helpers used by automation/export extensions.
- `fake-useragent`: optional user-agent rotation support.
- `pyautogui`: user prompts and manual-intervention dialogs.
- `openai`, `google-generativeai`, `flask`, `flask-cors`: existing AI and local dashboard integrations.

## Browser Architecture

The bot never uses your personal Chrome profile. Startup is:

1. validate Chrome installation
2. detect Chrome executable and version
3. use the detected Chrome major version for `undetected-chromedriver`
4. fall back to Selenium Manager if stealth startup fails
5. prepare `C:\Naukri_Guru_Profile` on Windows
6. remove stale automation-profile locks
7. kill only Chrome processes tied to the automation profile
8. launch isolated Chrome
9. log Chrome version, ChromeDriver version, executable path, and profile path

This fixes the ChromeDriver 149 vs Chrome 148 failure without downgrading Chrome.

## Data Architecture

Primary storage:

- `data/naukri_guru.sqlite3`
- tables: `applications`, `recruiters`, `lifecycle_events`, `notes`
- long job descriptions are stored under `data/job_descriptions/`

Compatibility storage:

- existing CSV files in `all excels/` are still written so the current bot flow remains stable.

Canonical analytics exports:

- `all excels/all_applied_applications_history.csv`
- `all excels/all_applied_applications_history.xlsx`
- `all excels/all_failed_applications_history.csv`
- `all excels/all_failed_applications_history.xlsx`

Applied-history lifecycle columns include:

- `current_status`
- `last_status_update`
- `status_source`
- `response_received`
- `recruiter_email`

## Gmail Lifecycle Sync

Gmail sync runs before Chrome launch. It classifies recruiter/application emails, filters low-trust senders, matches messages to applications using exact URL/job ID, recruiter email/domain, normalized company/title, fuzzy fallback, and timing evidence, then writes lifecycle events to SQLite and updates CSV compatibility fields.

Supported statuses:

- Applied
- OA Received
- Interview Scheduled
- Rejected
- Offer
- Ghosted
- Withdrawn

## Running

```powershell
.\venv\Scripts\python.exe runAiBot.py
```

Run validation:

```powershell
.\venv\Scripts\python.exe -m tests.validate_pipeline
```

If live Gmail IMAP is blocked by your shell or sandbox, run validation from a normal terminal with network access.

## Migration Plan

1. Run `setup.ps1`.
2. Run validation.
3. Start the bot once. Existing CSV rows are migrated into SQLite automatically.
4. Log into LinkedIn inside the automation Chrome profile once if needed.
5. Use `all_applied_applications_history.xlsx` and `all_failed_applications_history.xlsx` for tracking.

## Notes

This project is for educational and academic use. Automated browsing must comply with website terms and account safety requirements.
