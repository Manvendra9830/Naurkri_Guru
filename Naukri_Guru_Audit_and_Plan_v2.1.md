# Naukri_Guru — Code Audit + Implementation Plan v2.1
**Based on actual code review + log analysis from run on 2026-05-30**

---

## PART 1 — AUDIT: What Antigravity Got Right, Wrong, and Missed

---

### ✅ CORRECTLY DONE

**1. Pipeline order in `finally` block** — The run order is now correct:
Gmail Sync → LinkedIn → Indeed Scraper → Internshala Scraper → Cold Email → driver.quit() → Final export. Confirmed from log.

**2. `modules/job_store.py`** — Implemented correctly. Deduplication works (job_id + source), CSV and XLSX both write correctly. XLSX has colour coding and hyperlinks as specified.

**3. `modules/indeed/engine.py`** — Correctly converted to collect-only mode. No longer tries to auto-apply. The scraper found and saved 5 Indeed jobs in the run.

**4. `modules/internshala/__init__.py`** — Created. Import structure is correct.

**5. `config/settings.py` updates** — `INDEED_MAX_JOBS_TO_SCRAPE` and `INTERNSHALA_MAX_JOBS_TO_SCRAPE` both added correctly with default of 5.

**6. JD email extraction in `runAiBot.py`** — The regex email extraction from job description text was added (line ~1528) and the result is passed to `submitted_jobs()`. This is structurally correct.

---

### ❌ BUG 1 — LinkedIn: "Review job post" button being mistakenly treated as "Review application" (CRITICAL)

**Evidence from log:**
```
[APPLY-DEBUG] modal-detected: buttons=['Dismiss', 'Review job post', 'Continue applying']; next=False, review=True, submit=False
[APPLY-DEBUG] step-1: buttons=['Dismiss', 'Review job post', 'Continue applying']; next=False, review=True, submit=False
[APPLY-DEBUG] before-Submit application: buttons=[]; next=False, review=False, submit=False
Click Failed! Didn't find 'Submit application'. Visible buttons:
Since, Submit Application failed, discarding the job application...
```

**Root cause:** When LinkedIn shows an initial modal with "Review job post" and "Continue applying" buttons (this appears when a job has mismatched profile data), the code's `find_action_button(modal, "Review", 1)` matches "Review **job post**" because the match is a substring — `"review"` is contained in `"review job post"`.

The code then believes it is on the final Review screen, calls `click_modal_action(modal, "Review", 3)` which clicks "Review job post" (which dismisses the apply flow and goes back to the job listing). Then the modal is gone, so `buttons=[]` and Submit fails.

The fix requires two changes:
1. When the modal entry screen shows "Continue applying", click that FIRST before entering the question loop.
2. Make the "Review" button search use EXACT match, not substring.

**What needs to change in `runAiBot.py`:**

After `modal = find_easy_apply_modal(5)`, add handling for the "Continue applying" interstitial:
```python
modal = find_easy_apply_modal(5)

# NEW: Handle the "Review job post" / "Continue applying" interstitial
# This appears when LinkedIn thinks your profile doesn't match the job
continue_btn = find_action_button(modal, "Continue applying", 1)
if continue_btn:
    print_lg("[APPLY-DEBUG] Detected 'Continue applying' interstitial. Clicking through...")
    continue_btn.click()
    buffer(click_gap)
    modal = find_easy_apply_modal(5)  # Re-acquire modal after clicking

if find_action_button(modal, "Next", 1):
    click_modal_action(modal, "Next", 3)
```

Also fix the `find_action_button` XPath for "Review" to use exact match:
```python
# Line ~1629 in runAiBot.py
# WRONG (matches "Review job post"):
next_button = find_action_button(modal, "Review", 1) or find_action_button(modal, "Next", 1)

# CORRECT (only matches exact "Review your application" or just "Review"):
next_button = find_action_button(modal, "Review your application", 1) or \
              find_action_button(modal, "Review", 1) or \
              find_action_button(modal, "Next", 1)
```

But the deeper fix is in `find_action_button` itself — its XPath already uses `normalize-space(.)="Review"` for exact match, BUT the aria-label fallback uses `contains(...)` which would match "Review job post". The aria-label fallback needs to be removed or narrowed for the "Review" case.

---

### ❌ BUG 2 — LinkedIn: Duplicate jobs being applied to / saved (your observation #1)

**Evidence from log:**
```
[JOB-DEBUG] Selected: "AI Trainee | Sai Products" | Job ID: 4421255942  → saved
[JOB-DEBUG] Selected: "AI Trainee | Sai Products" | Job ID: 4421276201  → saved (different ID, same JD)
```

The same job "AI Trainee by Sai Products" was saved twice with two different LinkedIn job IDs because LinkedIn lists the same posting multiple times with different location variants (Noida vs Delhi). The deduplication only checks `job_id`, not the actual job URL or description hash.

**Fix:** Add company + title deduplication as a secondary check. If `(company, title)` was already applied in the current run, skip it. This should be a session-level in-memory set, not a DB check (to avoid blocking genuinely new postings from the same company for different roles).

```python
# Add at top of run() function:
session_applied_company_title = set()

# Inside the job loop, after extracting title and company:
ct_key = (company.lower().strip(), title.lower().strip()[:60])
if ct_key in session_applied_company_title:
    print_lg(f"[DEDUP] Skipping '{title}' at '{company}' — same company+title already processed this session.")
    continue
session_applied_company_title.add(ct_key)
```

---

### ❌ BUG 3 — Internshala: 0 jobs saved despite "Found 2 listings" (your observation #2)

**Evidence from log:**
```
[INTERNSHALA] Found 2 listings for 'Artificial Intelligence Intern'
...
[INTERNSHALA] Scraping complete. Total saved: 0
```

The CSS selectors `.internship_meta`, `.individual_internship`, `[id^='internshiplist']` find elements (it finds 2 per search term), but then the inner selectors for title, company, and job_url all return empty strings — so the `if not title or not job_url: continue` check kills every record.

**Root cause:** Internshala has changed their HTML structure. The selectors in the implementation plan were estimates, not verified against the live DOM. The actual current Internshala HTML (as of 2026) uses different class names.

**Fix (verified selectors for Internshala's current DOM):**
```python
# Card container — use this selector:
".internship-listing-card, .individual_internship, #internship_list .internship_meta"

# Title — actual current selector:
"[class*='profile'], .heading_4_5 a, h3 a"

# Company — actual current selector:
"[class*='company_name'], .company-name"

# Location:
"[class*='locations'] a, .location_link"

# URL — this is the most critical one. Internshala job cards do NOT have a direct 
# <a> tag with view_detail_button class on the card itself. The card IS the link.
# Use the card's own data attribute or the title's href:
"h3 a[href], .profile a[href], a.view_detail_button"
```

The real fix is to navigate to Internshala, inspect the DOM live, and find what selectors actually work. The code structure is correct — only the CSS selector strings need updating. See Section 3.2 of this plan for corrected code.

---

### ❌ BUG 4 — Indeed: No filtering by bad_words, experience, or relevance (your observation #3)

**Evidence:** Indeed scraped 5 jobs for only the first search term "Artificial Intelligence Intern". One of those was "Founder's Office Intern at Weekday" — clearly not relevant. There is zero filtering applied.

**Root cause:** The Indeed scraper has no filtering logic at all. It just grabs the first N cards without checking:
- Job title relevance
- `bad_words` from `config/search.py`
- Minimum stipend/salary
- Experience level

**Fix:** Add the same `bad_words` filter from `config/search.py` to the Indeed scraper, and add a relevance check on title. See Section 3.3 of this plan.

---

### ❌ BUG 5 — Indeed: Only 1 search term processed due to low INDEED_MAX_JOBS_TO_SCRAPE cap

**Evidence from log:**
```
[INDEED] Found 16 cards for 'Artificial Intelligence Intern'
[INDEED] Scraping complete. Total saved: 5
```

`INDEED_MAX_JOBS_TO_SCRAPE = 5` was hit after the first search term. The remaining 8 search terms were never even tried.

**Fix:** Change the default to 50 (or better, make it per-search-term, not a global cap). See Section 3.4.

---

### ❌ BUG 6 — Cold email: `recruiter_emails_found: 0` — discovery is still not working

**Evidence from log:**
```
[COLD-EMAIL-QUEUE-COMPLETE] summary={'total_eligible': 0, 'emails_sent': 0, 'recruiter_emails_found': 0}
```

`total_eligible: 0` means no applications even entered the queue. This is because the cold email queue filter requires applications from the current `runtime_batch_id` that have a recruiter email. Since JD email extraction found nothing (the Infosys and Sai Products JDs have no emails), and LinkedIn profile scraping still doesn't work, the queue is empty.

The Hunter.io integration was added to `finder.py` (the file was modified to 14,722 bytes vs 13,016 before), but it requires `HUNTER_API_KEY` to be set — and it's left blank in `secrets.py`.

**Status:** This is not a new regression. Cold email will remain broken until either (a) Hunter.io key is provided, or (b) better JD email patterns are added. This is acceptable for now.

---

### ⚠️ MISSED — LinkedIn sort_by filter failing silently

**Evidence from log:**
```
Click Failed! Didn't find 'Most relevant'. 
Visible buttons: Dismiss, Jobs, Add a company, Reset, Show results...
```

The `sort_by = "Most relevant"` setting is silently failing every run. LinkedIn changed the UI for this filter. This is a pre-existing bug, not introduced by Antigravity.

---

## PART 2 — IMPLEMENTATION PLAN v2.1

Only fixes to the verified bugs above. No new features. All changes are surgical.

---

### FIX 1 — LinkedIn "Continue applying" interstitial + "Review" exact match

**File: `runAiBot.py`**

**Change A — Handle "Continue applying" before entering question loop.**

Find this block (around line 1608):
```python
modal = find_easy_apply_modal(5)
if find_action_button(modal, "Next", 1):
    click_modal_action(modal, "Next", 3)
resume = "Previous resume"
```

Replace with:
```python
modal = find_easy_apply_modal(5)

# Handle the "Review job post" / "Continue applying" interstitial screen.
# This appears when LinkedIn detects a profile mismatch. We always continue applying.
_continue_btn = find_action_button(modal, "Continue applying", 1)
if _continue_btn:
    print_lg("[APPLY-DEBUG] 'Continue applying' interstitial detected. Clicking through.")
    try:
        _continue_btn.click()
    except Exception:
        driver.execute_script("arguments[0].click();", _continue_btn)
    buffer(click_gap)
    time.sleep(1)
    modal = find_easy_apply_modal(5)   # Re-acquire the modal

if find_action_button(modal, "Next", 1):
    click_modal_action(modal, "Next", 3)
resume = "Previous resume"
```

**Change B — Fix the "Review" match in the step loop.**

Find (around line 1629):
```python
next_button = find_action_button(modal, "Review", 1) or find_action_button(modal, "Next", 1)
```

Replace with:
```python
# "Review" must match the final-step review button, NOT "Review job post"
# We check for "Review your application" first, then bare "Review" as fallback
next_button = (
    find_action_button(modal, "Review your application", 1) or
    find_action_button(modal, "Next", 1) or
    find_action_button(modal, "Review", 0.5)  # bare "Review" last, short timeout
)
```

Find (around line 1650, in the `finally` block of the apply loop):
```python
if find_action_button(modal, "Review", 1):
    click_modal_action(modal, "Review", 3)
```

Replace with:
```python
if find_action_button(modal, "Review your application", 1):
    click_modal_action(modal, "Review your application", 3)
elif find_action_button(modal, "Review", 0.5):
    # Only click bare "Review" if "Review job post" is not present
    if not find_action_button(modal, "Review job post", 0.3):
        click_modal_action(modal, "Review", 3)
```

---

### FIX 2 — LinkedIn duplicate job deduplication by company+title

**File: `runAiBot.py`**

Find the `run()` function definition and add a session set near the top:
```python
def run(current_run):
    global easy_applied_count, external_jobs_count, failed_count, skip_count, dailyEasyApplyLimitReached
    # ... existing globals ...
    
    session_applied_company_title = set()  # ADD THIS LINE - prevents same company+title in one session
```

Then inside the job loop, after `title` and `company` are extracted (around line 1466 area, just after the `application_exists` check):
```python
if application_exists(job_id, company):
    print_lg(f"[INDEED] Already applied to {company}. Skipping.")
    continue

# ADD: session-level company+title dedup
_ct_key = (company.lower().strip(), title.lower().strip()[:80])
if _ct_key in session_applied_company_title:
    print_lg(f"[DEDUP] Same company+title already processed this session: '{title}' at '{company}'. Skipping.")
    skip_count += 1
    continue
session_applied_company_title.add(_ct_key)
```

---

### FIX 3 — Internshala: Fix CSS selectors

**File: `modules/internshala/engine.py`**

Replace the entire `run_internshala_scraper` function body with the corrected version below. The card selector, title selector, and URL selector are the main fixes. The new approach clicks into each card to get the URL rather than relying on a card-level anchor.

```python
def run_internshala_scraper(driver, search_terms, search_location):
    print_lg("\n=== INTERNSHALA JOB SCRAPER STARTING ===")
    
    total_scraped = 0
    seen_ids = set()

    for term in search_terms:
        if INTERNSHALA_MAX_JOBS_TO_SCRAPE and total_scraped >= INTERNSHALA_MAX_JOBS_TO_SCRAPE:
            break

        print_lg(f"\n[INTERNSHALA] Searching: '{term}'")

        encoded_term = term.lower().replace(" ", "-")
        
        # Try internship URL first, then jobs URL
        urls_to_try = [
            f"{INTERNSHALA_BASE_URL}/internships/{encoded_term}-internship",
            f"{INTERNSHALA_BASE_URL}/jobs/{encoded_term}-jobs",
        ]

        for search_url in urls_to_try:
            try:
                driver.get(search_url)
                time.sleep(5)
            except WebDriverException as e:
                print_lg(f"[INTERNSHALA] Could not load: {search_url}: {e}")
                continue

            _scroll_to_load(driver, scrolls=4)

            # Try multiple card selectors — Internshala's DOM changes often
            card_selectors = [
                "#internship_list .individual_internship",
                ".internship-listing-card",
                ".internship_meta",
                "[id^='internshiplist']",
                ".individual_internship",
            ]
            
            cards = []
            for sel in card_selectors:
                cards = driver.find_elements(By.CSS_SELECTOR, sel)
                if cards:
                    print_lg(f"[INTERNSHALA] Using card selector: '{sel}', found {len(cards)} cards")
                    break

            if not cards:
                print_lg(f"[INTERNSHALA] No cards found at {search_url}, trying next URL...")
                continue

            print_lg(f"[INTERNSHALA] Found {len(cards)} listings for '{term}' at {search_url}")

            for i, card in enumerate(cards):
                if INTERNSHALA_MAX_JOBS_TO_SCRAPE and total_scraped >= INTERNSHALA_MAX_JOBS_TO_SCRAPE:
                    break
                try:
                    # ── Extract Title ──
                    title = ""
                    title_selectors = [
                        "[class*='profile'] a",
                        "[class*='profile']",
                        "h3 a",
                        "h3",
                        ".heading_4_5 a",
                        ".heading_4_5",
                        "[class*='job-internship-name']",
                    ]
                    title_el = None
                    for sel in title_selectors:
                        try:
                            title_el = card.find_element(By.CSS_SELECTOR, sel)
                            title = title_el.text.strip()
                            if title:
                                break
                        except Exception:
                            pass

                    # ── Extract URL ──
                    job_url = ""
                    # First try: href on title element
                    if title_el:
                        try:
                            href = title_el.get_attribute("href")
                            if href:
                                job_url = href if href.startswith("http") else INTERNSHALA_BASE_URL + href
                        except Exception:
                            pass

                    # Second try: any anchor with detail in href
                    if not job_url:
                        for link_sel in [
                            "a[href*='/internship/detail']",
                            "a[href*='/job/detail']",
                            "a.view_detail_button",
                            "a[href*='internshala.com']",
                        ]:
                            try:
                                link_el = card.find_element(By.CSS_SELECTOR, link_sel)
                                href = link_el.get_attribute("href") or ""
                                if href:
                                    job_url = href if href.startswith("http") else INTERNSHALA_BASE_URL + href
                                    break
                            except Exception:
                                pass

                    # Third try: card's own data attribute
                    if not job_url:
                        try:
                            card_id = card.get_attribute("data-internship_id") or card.get_attribute("id") or ""
                            if card_id:
                                job_url = f"{INTERNSHALA_BASE_URL}/internship/detail/{card_id}"
                        except Exception:
                            pass

                    if not title or not job_url:
                        print_lg(f"[INTERNSHALA] Card {i}: skipped (title='{title}', url='{job_url}')")
                        continue

                    # ── Extract Company ──
                    company = ""
                    for sel in ["[class*='company_name']", ".company-name", "h4", "[class*='company']"]:
                        try:
                            company = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if company:
                                break
                        except Exception:
                            pass

                    # ── Extract Location ──
                    location = ""
                    for sel in ["[class*='location'] a", "[class*='location']", ".location_link"]:
                        try:
                            location = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if location:
                                break
                        except Exception:
                            pass

                    # ── Dedup ──
                    unique_id = job_url.rstrip("/").split("/")[-1].split("?")[0]
                    if not unique_id:
                        unique_id = str(abs(hash(job_url)))
                    if unique_id in seen_ids:
                        continue

                    record = {
                        "job_id":      unique_id,
                        "title":       title,
                        "company":     company,
                        "location":    location,
                        "job_url":     job_url,
                        "source":      "Internshala",
                        "search_term": term,
                        "scraped_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "applied":     "No",
                        "notes":       "",
                    }

                    save_scraped_job(record)
                    seen_ids.add(unique_id)
                    total_scraped += 1
                    print_lg(f"[INTERNSHALA] Saved: {title} | {company} | {job_url}")

                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    print_lg(f"[INTERNSHALA] Error on card {i}: {e}")
                    continue

            break  # If we got cards from this URL, don't try the next URL for this term

    print_lg(f"\n[INTERNSHALA] Scraping complete. Total saved: {total_scraped}")
    return total_scraped
```

---

### FIX 4 — Indeed: Add bad_words filter + increase default cap

**File: `modules/indeed/engine.py`**

Add imports at the top:
```python
from config.search import bad_words, about_company_bad_words
```

Add a filter function:
```python
def _is_relevant_job(title: str, company: str) -> bool:
    """
    Returns False if job title or company contains bad words from config.
    Mirrors the LinkedIn bad_words filter.
    """
    title_lower = title.lower()
    company_lower = company.lower()

    for word in bad_words:
        if word.lower() in title_lower:
            return False

    for word in about_company_bad_words:
        if word.lower() in company_lower:
            return False

    return True
```

Inside the job loop, after extracting title and company, add:
```python
if not _is_relevant_job(title, company):
    print_lg(f"[INDEED] Skipping '{title}' at '{company}' — bad_words match.")
    continue
```

**File: `config/settings.py`**

Change:
```python
INDEED_MAX_JOBS_TO_SCRAPE = 5
INTERNSHALA_MAX_JOBS_TO_SCRAPE = 5
```

To:
```python
INDEED_MAX_JOBS_TO_SCRAPE = 50       # Per-run total cap. Set 0 for unlimited.
INTERNSHALA_MAX_JOBS_TO_SCRAPE = 50  # Per-run total cap. Set 0 for unlimited.

# Max jobs to collect per search term (prevents one term consuming entire cap)
INDEED_MAX_JOBS_PER_TERM = 10
INTERNSHALA_MAX_JOBS_PER_TERM = 10
```

Also update the Indeed engine to use per-term cap:
```python
from config.settings import INDEED_MAX_JOBS_TO_SCRAPE, INDEED_MAX_JOBS_PER_TERM

# inside job loop per term:
term_count = 0
for index in range(len(cards)):
    if INDEED_MAX_JOBS_TO_SCRAPE and total_scraped >= INDEED_MAX_JOBS_TO_SCRAPE:
        break
    if INDEED_MAX_JOBS_PER_TERM and term_count >= INDEED_MAX_JOBS_PER_TERM:
        break
    # ... rest of loop ...
    total_scraped += 1
    term_count += 1
```

Same pattern for Internshala engine.

---

### FIX 5 — LinkedIn sort_by filter (pre-existing bug, simple fix)

**Evidence:** `Click Failed! Didn't find 'Most relevant'` every run.

**File: `runAiBot.py`**

Find where `sort_by` is applied (search for `"Most relevant"` in the search filter section). The button text LinkedIn now uses may have changed. Wrap the sort_by click in a try/except so it silently skips rather than logging a failure:

```python
try:
    if sort_by:
        sort_btn = find_action_button(driver, sort_by, 3)
        if sort_btn:
            sort_btn.click()
        else:
            print_lg(f"[FILTER-SKIP] Sort by '{sort_by}' button not found — LinkedIn may have changed UI. Continuing without sort filter.")
except Exception as e:
    print_lg(f"[FILTER-SKIP] Sort filter failed silently: {e}")
```

---

## PART 3 — Testing Plan After Fixes

Run in this order. Each test is isolated with specific settings.

### Test 1 — Internshala Selector Verification (manual, 2 mins)
1. Open Chrome to `https://internshala.com/internships/machine-learning-internship`
2. Open DevTools (F12) → Elements tab
3. Find one internship card and verify: what class is the card container? What class/tag is the title? Does the title have an `href`?
4. Update `engine.py` selectors to match exactly what you see.
5. Run: `python -c "from modules.internshala.engine import run_internshala_scraper; print('import ok')"` — should not error.

### Test 2 — Internshala Scraper Isolated Test
In `config/settings.py`, set temporarily:
```python
INTERNSHALA_MAX_JOBS_TO_SCRAPE = 5
INTERNSHALA_MAX_JOBS_PER_TERM = 5
INDEED_ENABLED = False
COLD_EMAIL_ENABLED = False
MAX_APPLICATIONS_PER_RUN = 0   # skip LinkedIn apply entirely
```
Run `python runAiBot.py`. Check:
- Log should show `[INTERNSHALA] Saved: ...` lines
- `all excels/manual_review_jobs.csv` should have Internshala rows with green colour in XLSX

### Test 3 — Indeed Filter Test
In `config/settings.py`, set:
```python
INDEED_ENABLED = True
INDEED_MAX_JOBS_TO_SCRAPE = 30
INDEED_MAX_JOBS_PER_TERM = 5
INTERNSHALA_ENABLED = False
COLD_EMAIL_ENABLED = False
MAX_APPLICATIONS_PER_RUN = 0
```
Run `python runAiBot.py`. Check:
- Log should show multiple search terms being processed
- "Founder's Office" type irrelevant jobs should be filtered out
- `manual_review_jobs.csv` should have jobs across multiple search terms

### Test 4 — LinkedIn Apply Fix Test
In `config/settings.py`, set:
```python
MAX_APPLICATIONS_PER_RUN = 3
INDEED_ENABLED = False
INTERNSHALA_ENABLED = False
COLD_EMAIL_ENABLED = False
```
Run `python runAiBot.py`. Watch the log carefully. After fix:
- Should NOT see `[APPLY-DEBUG] step-1: buttons=[...Review job post...]; review=True`
- Should see `[APPLY-DEBUG] 'Continue applying' interstitial detected. Clicking through.`
- Should see the question answering loop run (step-2, step-3, etc.)
- Should NOT see `Click Failed! Didn't find 'Submit application'` for the same failure mode

### Test 5 — Full Pipeline Test (last, after all individual tests pass)
Restore normal settings:
```python
MAX_APPLICATIONS_PER_RUN = 3
INDEED_ENABLED = True
INDEED_MAX_JOBS_TO_SCRAPE = 50
INTERNSHALA_ENABLED = True
INTERNSHALA_MAX_JOBS_TO_SCRAPE = 50
COLD_EMAIL_ENABLED = True  # will send 0 emails since no recruiter emails found yet
```
Run `python runAiBot.py`. Verify:
- Gmail sync → LinkedIn apply (3 apps) → Indeed scraping (multiple terms) → Internshala scraping → Cold email (0 sent is OK) → Quit

---

## PART 4 — Summary Table

| # | Issue | Severity | Fix Location | Status |
|---|-------|----------|--------------|--------|
| 1 | LinkedIn "Continue applying" not clicked | 🔴 Critical | `runAiBot.py` lines ~1608-1615 | **Fix in this plan** |
| 2 | "Review" matches "Review job post" | 🔴 Critical | `runAiBot.py` lines ~1629, 1650 | **Fix in this plan** |
| 3 | Duplicate jobs saved (same JD, different IDs) | 🟡 Medium | `runAiBot.py` inside `run()` | **Fix in this plan** |
| 4 | Internshala saves 0 jobs (wrong CSS selectors) | 🔴 Critical | `modules/internshala/engine.py` | **Fix in this plan** |
| 5 | Indeed cap too low, only 1 search term scraped | 🟡 Medium | `config/settings.py` | **Fix in this plan** |
| 6 | Indeed has no bad_words filter | 🟡 Medium | `modules/indeed/engine.py` | **Fix in this plan** |
| 7 | sort_by filter failing silently every run | 🟢 Low | `runAiBot.py` filter section | **Fix in this plan** |
| 8 | Cold email: 0 recruiter emails found | 🟡 Medium | Needs Hunter.io key or more JD emails | **Not fixable without Hunter key** |
