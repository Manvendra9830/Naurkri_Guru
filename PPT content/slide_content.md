# PPT Content - Naukri_Guru

## Slide: Current Job Filtering Configuration

Suggested title:
Current Job Filtering Configuration

Main message:
Naukri_Guru filters jobs using explicit search preferences, platform filters, safety rules, salary rules, and per-run limits before applying or saving results.

Use image:
`current_filter_configuration.svg`

Key points to say:
- Search focus: AI Engineer, ML Engineer, Python Developer Intern, AI Intern, ML Intern, Software Developer, Software Developer Intern.
- Location focus: India.
- LinkedIn ranking: Most relevant, with date cycle across Past month, Past week, and Past 24 hours.
- Candidate fit: Internship, Entry level, and Associate roles; Full-time and Internship job types; On-site, Remote, and Hybrid modes.
- Scope control: switch search after 5 applications and cap each run at 20 applications.
- Quality filters: skip senior or irrelevant roles using bad words such as Senior, Lead, Architect, Manager, Principal, Director, SAP, ERP, Salesforce, Workday, and similar terms.
- Indeed filters: scrape up to 15 jobs, require minimum monthly salary INR 30,000 or annual CTC 4 LPA, and reject undisclosed salary.

Speaker note:
The project is not applying blindly. It narrows the search to early-career AI, ML, Python, and software roles in India, then uses experience, job type, work mode, salary, and keyword-based rejection rules to avoid unsuitable postings.

## Slide: Current Tech Stack

Suggested title:
Current Tech Stack Used

Use image:
`current_tech_stack.svg`

Key points to say:
- Python is the main programming language.
- Selenium and undetected-chromedriver automate Chrome and LinkedIn job flows.
- SQLite stores normalized application, recruiter, lifecycle, and notes data.
- Pandas and OpenPyXL export clean CSV/XLSX reports.
- Gmail IMAP and SMTP support lifecycle sync and cold outreach.
- Gemini, OpenAI, and DeepSeek integrations support AI question answering and skill extraction.
- BeautifulSoup and Requests help with parsing and HTTP-based enrichment.
- PyAutoGUI supports local prompts and manual-intervention dialogs.
- Flask and Flask-CORS are present for local dashboard/API integration.

Speaker note:
This stack was chosen because the project is a local automation system. It needs reliable browser control, file exports, lightweight storage, email sync, and optional AI support without requiring a large cloud backend.

## Slide: Scaling And Optimization Tools

Suggested title:
Tools For Scaling And Optimization

Use image:
`scaling_optimization_tools.svg`

Key points to say:
- LangChain or LlamaIndex could structure multi-step AI workflows, prompt chains, retrieval, and tool calling.
- Celery with Redis/RabbitMQ could move scraping, email sync, and outreach into background queues.
- PostgreSQL could replace local SQLite when multiple users or concurrent workers are needed.
- Docker could make deployment repeatable across machines.
- FastAPI could expose the automation as a service with API endpoints.
- Playwright could improve browser automation stability and tracing for complex sites.
- Vector databases could store resumes, job descriptions, and recruiter emails for semantic matching.
- Monitoring tools such as Prometheus, Grafana, or Sentry could track failures, latency, and job success rate.

Why not used in the current version:
- Current scope is single-user, local, academic project execution.
- SQLite and CSV/XLSX are enough for local storage and presentation-ready reporting.
- Adding queues, containers, cloud databases, and orchestration would increase setup complexity.
- Direct Selenium logic is easier to debug for a prototype where UI behavior changes often.
- LangChain-style orchestration is useful at larger AI workflow scale, but the current AI usage is narrow: question answering, skill extraction, and email generation.

Speaker note:
These tools are valuable for the next phase, especially if the project becomes multi-user or cloud-hosted. They were avoided here to keep the prototype lightweight, understandable, and easier to run on a normal laptop.
