# Naukri_Guru - Comprehensive Technical Interview Preparation Guide

This guide is designed to provide you with in-depth answers, design rationales, and technical justifications for all aspects of the **Naukri_Guru AI-Powered Job Automation Platform**. It covers everything from the core architecture to the PPT presentation slides, ensuring you are fully prepared for any technical interview questions.

---

## 1. Project Overview & Scope
**What is Naukri_Guru?**
Naukri_Guru is an autonomous, AI-driven local desktop application designed to streamline the job search process. It automatically discovers jobs, evaluates candidate fit using heuristic scoring, applies on LinkedIn using stealth browser automation, tracks application lifecycles via Gmail IMAP sync, and proactively engages recruiters using an AI-generated cold email pipeline. 

**Why a Local Desktop App instead of a Cloud SaaS?**
The current scope is a single-user, local, academic project execution. It was designed to run directly from a user's laptop to utilize their existing, trusted IP address and local Chrome session cookies. Hosting browser automation on a centralized cloud server (like AWS/GCP) often triggers immediate bot detection and CAPTCHAs from LinkedIn.

---

## 2. Core Architecture & Tech Stack Selection
**Current Tech Stack Used:** Python, Selenium, SQLite, Pandas/OpenPyXL, Gemini/OpenAI, IMAP/SMTP, BeautifulSoup, PyAutoGUI, Flask.

* **Why Python?** Python is the industry standard for AI integration, web scraping, and automation. Its rich ecosystem allows seamless integration between the browser (Selenium), local database (SQLite3), and AI APIs.
* **Why Selenium (DOM manipulation) instead of API requests?** LinkedIn does not provide a public API for job applications. Using undocumented, private backend APIs is highly risky, requires reverse-engineering complex authentication tokens, and triggers immediate account bans. Selenium interacts with the DOM just like a real human user. Paired with `undetected-chromedriver` and randomized delays, it significantly reduces the risk of bot detection.
* **Why SQLite?** The tool requires reliable storage without the setup overhead of PostgreSQL or MySQL. SQLite stores normalized application, recruiter, lifecycle, and notes data locally. It is lightweight, serverless, and provides ACID compliance (atomic writes), making it perfect for a standalone desktop automation tool.
* **Why Pandas and OpenPyXL?** To export the SQLite data into clean, presentation-ready CSV and XLSX reports for the user.
* **Why Flask and Flask-CORS?** Flask is included to serve as the backend for a local interactive analytics dashboard and API integration (currently in development).
* **Why PyAutoGUI?** Used as a fallback for handling unexpected manual-intervention dialogs or local prompts that Selenium cannot natively intercept.

---

## 3. Job Filtering Configuration & Candidate Fit
To prevent wasting the user's daily application limit on irrelevant jobs, the bot uses highly specific filters.

* **Target Profiles:** AI Engineer, ML Engineer, Python Developer (including Intern roles), and Software Developer.
* **Location:** India.
* **Candidate Fit Parameters:** Internship, Entry level, and Associate roles. Full-time and Internship job types. On-site, Remote, and Hybrid modes.
* **Quality / Negative Filters:** The system actively skips senior or irrelevant roles by checking the DOM text for "bad words" such as: *Senior, Lead, Architect, Manager, Principal, Director, SAP, ERP, Salesforce, Workday*, and similar terms.
* **LinkedIn Search Strategy:** Ranks by "Most relevant", rotating through Past month, Past week, and Past 24 hours.
* **Scope Control:** It switches search queries after 5 applications and caps each run at 20 applications total. This mimics human pacing and prevents LinkedIn from flagging the account for spam.
* **Indeed Specific Filters:** It scrapes up to 15 jobs at a time. It requires a minimum monthly salary of INR 30,000 (or annual CTC 4 LPA) and outright rejects postings with undisclosed salaries.

---

## 4. Heuristic Confidence Scoring & AI Integrations
**How does the system decide to apply?**
Before clicking "Apply", the engine uses AI (Gemini, OpenAI, or DeepSeek) to evaluate the job description against the user's profile.
* **Criteria:** It checks keyword relevance, seniority indicators, degree requirements, and experience thresholds.
* **Experience Thresholding:** If the job requires 5 years of experience, and the candidate profile only has 1, the AI assigns a low "Confidence Score" and rejects the job, saving the application quota for better matches.
* **Form Answering:** It uses these AI integrations to read custom LinkedIn application questions, extract relevant skills from the user's resume, and generate context-aware answers to inject into the text boxes.

---

## 5. Job Deduplication & Persistence
**How does it ensure the same job is not saved twice?**
The system maintains a deduplicated record of all application attempts using the `applications` table in SQLite. When a job is discovered, its unique `job_id` or URL is checked against the database. If it exists, it is skipped entirely. To prevent data corruption during exports to Excel, it uses atomic writes (`tempfile` and `shutil.move`) and implements database locks, avoiding race conditions if a background process (like Gmail sync) tries to update the database simultaneously.

---

## 6. Gmail Lifecycle Synchronization
**How does it track application status?**
The tool connects to the user's Gmail via built-in IMAP (`imaplib`). It fetches recent emails (default 20 days lookback) and passes them through an AI classification pipeline.
* **Match Threshold (`0.75`):** The AI must be at least 75% confident that the recruiter's email matches a specific job/company stored in the local database.
* **Classification Threshold (`0.65`):** The AI must be at least 65% confident about the status (e.g., Rejected, Interview Scheduled, Offer, OA Received).
* **Why IMAP and not the official Gmail API?** Setting up the official Gmail API requires creating a Google Cloud Project, configuring OAuth2 consent screens, and managing tokens. IMAP only requires a standard Google App Password, drastically reducing friction for a local open-source tool while achieving the exact same result.

---

## 7. Cold Email Outreach Pipeline
**How does it automatically cold email recruiters?**
After the LinkedIn applications are finished, the system runs a separate queue-based cold email pipeline. 
* **Process:** It attempts to extract the recruiter's email from the job posting. It validates the email's trustworthiness using multi-signal scoring. Finally, it uses AI to generate a highly personalized cold email and sends it via authenticated SMTP.
* **Why Queue-Based?** Decoupling applying from emailing ensures idempotency. If the bot crashes, it resumes emailing exactly where it left off.
* **Sender Reputation Protection:** It strictly limits the number of emails sent (`MAX_COLD_EMAILS_PER_RUN = 5`), implements random delays (3 to 5 seconds) between sends to mimic human typing, and ensures no duplicate emails are sent to the same recruiter.
* **Test Mode:** Includes a `COLD_EMAIL_TEST_MODE` to allow testing the SMTP pipeline safely using whitelisted recipients.

---

## 8. Safety Guards & Anti-Bot Evasion
**How does the bot prevent account bans?**
* **Humanized Interaction:** Uses `time.sleep(randint(...))` and custom `buffer()` functions to randomize the milliseconds between clicks and keystrokes, completely evading basic bot heuristics that look for perfectly timed actions.
* **Stealth Profiles:** Uses `undetected-chromedriver` to hide standard Selenium automation flags from the browser.
* **AI Safety Guards:** Enforces strict formatting on AI outputs to prevent the bot from attempting to type hallucinations or malformed JSON into LinkedIn text boxes.

---

## 9. Limitations: Why scrape Instead of Apply for Indeed/Internshala?
**Why not fully automate everything everywhere?**
* **Aggressive Anti-Bot Mechanisms:** Platforms like Indeed employ aggressive Cloudflare CAPTCHAs and behavioral tracking that actively detect and block headless browsers far faster than LinkedIn.
* **Dynamic DOM Structures:** Unlike LinkedIn's relatively stable and unified "Easy Apply" modal, Indeed and Internshala have highly variable application flows. They frequently redirect users to third-party Applicant Tracking Systems (ATS) like Workday, Lever, or Greenhouse, all of which have completely different HTML structures that are nearly impossible to reliably parse.
* **Current Approach:** The tool acts as a highly efficient scraper for Indeed, aggregating relevant jobs into the local database for the user to review manually, keeping the fragile autonomous AI engine focused exclusively on LinkedIn's predictable ecosystem.

---

## 10. Scaling & Optimization Strategies (For Future Versions)
*Interviewers often ask: "This is great locally, but how would you scale this for an enterprise or multiple users?" Be prepared to discuss these tools.*

* **LangChain or LlamaIndex:** Could be used to structure multi-step AI workflows, prompt chains, retrieval (RAG), and tool calling. *Why not used now?* Current AI usage is narrow (Q&A, skill extraction, email generation) and direct API calls are lighter, cheaper, and easier to debug.
* **Celery with Redis/RabbitMQ:** Could move scraping, email sync, and outreach into background worker queues.
* **PostgreSQL:** Would replace local SQLite to allow concurrent database writes from multiple workers or users.
* **Docker:** Would make deployment repeatable across different OS environments.
* **FastAPI:** Could expose the automation as a service with standard REST API endpoints.
* **Playwright:** Could replace Selenium to improve browser automation stability, network interception, and execution tracing for complex sites.
* **Vector Databases (Pinecone/Chroma):** Could store resumes, job descriptions, and recruiter emails for semantic matching instead of simple keyword heuristics.
* **Monitoring (Prometheus, Grafana, Sentry):** Could track system failures, network latency, and job application success rates across a fleet of bots.
* **Why were these avoided in the current version?** The current scope is a single-user, local prototype. Adding queues, containers, cloud databases, and orchestration would drastically increase setup complexity for a user just trying to run the tool on their laptop. Local SQLite and CSV files are perfect for presentation-ready reporting without the cloud overhead.
