# Config Cleanup Report

Date: 2026-06-15

Scope: `config/search.py` and `config/settings.py`

Findings before cleanup:
- `search_terms` included `"Data Analyst"` and `"Data Analyst Intern"`.
- `bad_words` included `"Analyst"`.
- This was contradictory because LinkedIn/Indeed title filtering could search for analyst roles and then reject them by title.

Cleanup performed:
- Removed `"Data Analyst"` and `"Data Analyst Intern"` from `search_terms`.
- Removed `"Analyst"` from `bad_words`.

Settings added:
- `MIN_MONTHLY_SALARY_INR = 30000`
- `MIN_ANNUAL_CTC_LPA = 4`
- `ALLOW_UNDISCLOSED_SALARY = False`

Forbidden areas intentionally not changed:
- LinkedIn Easy Apply workflow
- Gmail lifecycle tracking
- SQLite schema
- Cold email queue architecture
- Export architecture
- Application storage logic
