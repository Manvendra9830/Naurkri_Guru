# Naukri_Guru - AI-Powered Job Automation Platform

Naukri_Guru is an autonomous, AI-driven local desktop application designed to streamline the job search process. It automatically discovers jobs, evaluates candidate fit using heuristic scoring, applies on LinkedIn using stealth browser automation, tracks application lifecycles via Gmail IMAP sync, and proactively engages recruiters using an AI-generated cold email pipeline. 

This project is currently scoped as a single-user, local, academic execution to maximize success rates and avoid cloud-based bot detection flags.

---

## 1. Core Features & Capabilities

- **Automated LinkedIn Applying:** Seamlessly automates LinkedIn job search and Easy Apply flows.
- **Smart Filtering & Scoring:** Uses AI to evaluate job descriptions against your resume to determine fit and reject unsuitable roles.
- **Gmail Lifecycle Sync:** Automatically syncs recruiter emails via IMAP to track statuses (e.g., Interview Scheduled, Rejected).
- **Cold Email Outreach:** Extracts recruiter emails and uses AI to send highly personalized, rate-limited cold emails via SMTP.
- **Deduplication & Persistence:** Stores normalized application data safely in local SQLite and exports clean CSV/XLSX reports without duplicates.
- **Safety First:** Employs stealth Chrome profiles and humanized interaction delays to prevent account bans.

---

## 2. Architecture & Tech Stack

**Current Tech Stack Used:**
- **Python:** The core language tying together automation, database, and AI integrations.
- **Selenium (`undetected-chromedriver`):** Drives browser automation. Interacts directly with the DOM like a human to bypass LinkedIn API restrictions and avoid account bans.
- **SQLite:** A lightweight, serverless database storing normalized applications, recruiters, lifecycle events, and notes. Selected over PostgreSQL to keep local setup simple.
- **Pandas & OpenPyXL:** Generates clean, presentation-ready CSV and XLSX exports for the user.
- **Gemini / OpenAI / DeepSeek:** Provides AI capabilities for question answering, skill extraction, and generating personalized cold emails.
- **IMAP / SMTP (`imaplib`, `smtplib`):** Standard email protocols used to sync application statuses and send cold emails. (Chosen over the official Gmail API to avoid complex Google Cloud Project OAuth2 setups).
- **BeautifulSoup & Requests:** HTML parsing and HTTP helpers used by automation/export extensions.
- **PyAutoGUI:** Handles fallback local user prompts and manual-intervention dialogs.
- **Flask & Flask-CORS:** Backend framework reserved for local interactive dashboard and API integration (in active development).

---

## 3. Job Filtering & Candidate Fit

To prevent wasting the user's daily application limit on irrelevant jobs, the bot uses highly specific filters:
* **Target Profiles:** AI Engineer, ML Engineer, Python Developer, Software Developer (including Intern roles).
* **Location:** India.
* **Fit Parameters:** Internship, Entry level, Associate roles. Full-time, Internship job types. On-site, Remote, Hybrid modes.
* **Quality / Negative Filters:** Actively skips senior or irrelevant roles by checking the DOM text for "bad words" such as: *Senior, Lead, Architect, Manager, Principal, Director, SAP, ERP, Salesforce, Workday*.
* **Pacing & Limits:** Searches rank by "Most relevant" over recent date cycles. It switches search queries after 5 applications and caps each run at 20 applications total to mimic human pacing.
* **Indeed Filters:** Scrapes up to 15 jobs, requires a minimum monthly salary of INR 30,000 (or annual CTC 4 LPA), and rejects undisclosed salaries.

---

## 4. Heuristic Confidence Scoring

Before clicking "Apply", the engine uses AI to evaluate the job description against the user's profile.
* **Experience Thresholding:** If the job requires 5 years of experience, and the candidate profile only has 1, the AI assigns a low "Confidence Score" and rejects the job.
* **Form Answering:** It uses AI to read custom LinkedIn questions, extract skills from your resume, and inject context-aware answers directly into the application text boxes.

---

## 5. Gmail Lifecycle Synchronization

The tool connects to the user's Gmail via IMAP before the Chrome launch.
* **Lookback:** Fetches emails from the last 20 days.
* **Thresholds:** The AI must be at least **75% confident** (`GMAIL_MATCH_THRESHOLD`) that the email matches a specific job stored in the database, and **65% confident** (`GMAIL_CLASSIFICATION_THRESHOLD`) about the status.
* **Supported Statuses:** Applied, OA Received, Interview Scheduled, Rejected, Offer, Ghosted, Withdrawn.

---

## 6. Cold Email Outreach Pipeline

After LinkedIn applications are finished, a queue-based cold email pipeline activates:
* **Process:** Extracts the recruiter's email, validates trustworthiness via multi-signal scoring, and generates a personalized cold email using AI.
* **Queue-Based Idempotency:** If the bot crashes, it resumes emailing exactly where it left off.
* **Sender Reputation Protection:** Strictly limits emails (`MAX_COLD_EMAILS_PER_RUN = 5`), implements random 3-5 second delays between sends, and ensures no duplicate emails are sent to the same recruiter.
* **Test Mode:** Includes a `COLD_EMAIL_TEST_MODE` to safely test the SMTP pipeline using whitelisted recipients.

---

## 7. Safety Guards & Anti-Bot Evasion

* **Humanized Interaction:** Uses `time.sleep(randint(...))` to randomize the milliseconds between clicks and keystrokes, completely evading basic bot heuristics.
* **Stealth Profiles:** Removes stale locks and uses undetected-chromedriver.
* **AI Safety Guards:** Enforces strict formatting on AI outputs to prevent the bot from attempting to type hallucinations or malformed JSON.

---

## 8. Indeed & Internshala Limitations

**Why Scrape Instead of Apply for Indeed/Internshala?**
* **Aggressive Anti-Bot:** Indeed heavily relies on Cloudflare CAPTCHAs and behavioral tracking.
* **Dynamic DOMs:** Unlike LinkedIn's relatively stable "Easy Apply", these platforms frequently redirect to third-party ATS portals (Workday, Lever, Greenhouse) with vastly different structures.
* **Current Approach:** The tool efficiently scrapes Indeed to aggregate relevant jobs into the local database for manual review, keeping the fragile autonomous AI engine focused on LinkedIn's predictable ecosystem.

---

## 9. Production Setup

**Windows:**
```powershell
.\setup.ps1
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

The setup scripts:
- Create `venv` and install pinned dependencies from `requirements.txt`
- Verify Python 3.10+ and package imports
- Detect Google Chrome and print its installed version/path

Run environment validation any time:
```powershell
.\venv\Scripts\python.exe tools\validate_environment.py
```

---

## 10. Running the Platform

To start the bot:
```powershell
.\venv\Scripts\python.exe runAiBot.py
```

Run validation pipeline:
```powershell
.\venv\Scripts\python.exe -m tests.validate_pipeline
```
*(If live Gmail IMAP is blocked by your shell or sandbox, run validation from a normal terminal with network access.)*

---

## 11. Migration Plan (For Existing Users)

1. Run `setup.ps1`.
2. Run validation.
3. Start the bot once. Existing CSV rows (`all excels/`) are migrated into SQLite automatically.
4. Log into LinkedIn inside the automation Chrome profile once if needed.
5. Use `all_applied_applications_history.xlsx` and `all_failed_applications_history.xlsx` for future tracking.

---

## Notes

This project is for educational and academic use. Automated browsing must comply with website terms and account safety requirements.
