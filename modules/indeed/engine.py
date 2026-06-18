"""
Indeed Job Scraper — Collect-Only Mode
Does NOT apply to any job. Only scrapes job cards and saves URLs.
"""

import time
import os
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException
from modules.helpers import print_lg
from config.settings import (
    ALLOW_UNDISCLOSED_SALARY,
    INDEED_MAX_JOBS_TO_SCRAPE,
    INDEED_MAX_JOBS_PER_TERM,
    MIN_ANNUAL_CTC_LPA,
    MIN_MONTHLY_SALARY_INR,
)
from config.search import bad_words, about_company_bad_words, current_experience
from modules.indeed.selectors import CARD_SELECTORS
from modules.job_store import save_scraped_job           # new shared module (see Section 3.3)

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


def _salary_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _normalize_salary_amount(amount: float, suffix: str) -> float:
    suffix = (suffix or "").lower()
    if suffix in {"k", "thousand"}:
        return amount * 1000
    if suffix in {"l", "lac", "lakh", "lakhs"}:
        return amount * 100000
    return amount


def _parse_salary(text: str) -> dict | None:
    """Parse salary snippets and return minimum monthly/annual INR values."""
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text.lower())
    if not any(marker in normalized for marker in ("₹", "rs", "inr", "lpa", "ctc", "per month", "/month", "monthly", "per annum", "per year", "/year", "pa")):
        return None

    monthly_values = []
    annual_lpa_values = []
    pattern = re.compile(
        r"(?:₹|rs\.?|inr)?\s*"
        r"(\d+(?:,\d+)*(?:\.\d+)?)\s*"
        r"(k|thousand|l|lac|lakh|lakhs)?"
        r"(?:\s*(?:-|to)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|thousand|l|lac|lakh|lakhs)?)?"
        r"\s*(per month|/month|a month|monthly|per annum|per year|/year|annually|pa|lpa|ctc)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(normalized):
        trailing = normalized[match.end(): match.end() + 12]
        if re.match(r"\s*(?:years?|yrs?)\b", trailing):
            continue
        amount = _normalize_salary_amount(_salary_number(match.group(1)), match.group(2) or match.group(4) or "")
        if match.group(3):
            amount = min(amount, _normalize_salary_amount(_salary_number(match.group(3)), match.group(4) or match.group(2) or ""))
        context = (match.group(5) or "").lower()
        window = normalized[max(0, match.start() - 20): match.end() + 30]
        if context in {"lpa", "ctc"} or "lpa" in window or "ctc" in window:
            annual_lpa_values.append(amount / 100000 if amount >= 100000 else amount)
        elif any(token in context for token in ("month", "monthly")) or "per month" in window or "/month" in window:
            monthly_values.append(amount)
        elif any(token in context for token in ("annum", "year", "annually", "pa")) or any(token in window for token in ("per annum", "per year", "/year", " pa")):
            annual_lpa_values.append(amount / 100000)

    if not monthly_values and not annual_lpa_values:
        return None
    return {
        "monthly_min": min(monthly_values) if monthly_values else None,
        "annual_lpa_min": min(annual_lpa_values) if annual_lpa_values else None,
    }


def _parse_required_experience(text: str) -> float | None:
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text.lower())
    if any(word in normalized for word in ("fresher", "freshers", "entry level", "internship")):
        return 0.0
    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)",
        r"minimum\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"at least\s+(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*\d+(?:\.\d+)?\s*(?:years?|yrs?)",
        r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
    ]
    values = []
    for pattern in patterns:
        values.extend(float(match.group(1)) for match in re.finditer(pattern, normalized))
    return min(values) if values else None


def _passes_quality_filters(title: str, company: str, text: str) -> bool:
    salary = _parse_salary(text)
    if not salary:
        if not ALLOW_UNDISCLOSED_SALARY:
            print_lg(f"[INDEED-SALARY-REJECT] {title} | {company} | salary=unparsed/undisclosed")
            return False
    else:
        monthly_min = salary.get("monthly_min")
        annual_lpa_min = salary.get("annual_lpa_min")
        if monthly_min is not None and monthly_min < MIN_MONTHLY_SALARY_INR:
            print_lg(f"[INDEED-SALARY-REJECT] {title} | {company} | monthly_min={monthly_min:.0f} < {MIN_MONTHLY_SALARY_INR}")
            return False
        if annual_lpa_min is not None and annual_lpa_min < MIN_ANNUAL_CTC_LPA:
            print_lg(f"[INDEED-SALARY-REJECT] {title} | {company} | annual_lpa_min={annual_lpa_min:.2f} < {MIN_ANNUAL_CTC_LPA}")
            return False

    required_exp = _parse_required_experience(text)
    if current_experience >= 0 and required_exp is not None and required_exp > current_experience:
        print_lg(f"[INDEED-EXP-REJECT] {title} | {company} | required_exp={required_exp:g} > current_experience={current_experience}")
        return False
    return True


def run_indeed_scraper(driver, search_terms, search_location):
    """
    Scrapes Indeed for relevant jobs and stores them for manual review.
    Returns: (int) total jobs scraped this run
    """
    print_lg("\n=== INDEED JOB SCRAPER STARTING ===")
    
    search_tab = driver.current_window_handle
    driver.get("https://www.indeed.com/")
    time.sleep(3)
    
    # Detect redirected domain (in.indeed.com for India, etc.)
    current_domain = driver.current_url.split("/")[2]
    print_lg(f"[INDEED] Domain: {current_domain}")

    total_scraped = 0
    seen_job_ids = set()

    for term in search_terms:
        if INDEED_MAX_JOBS_TO_SCRAPE and total_scraped >= INDEED_MAX_JOBS_TO_SCRAPE:
            break

        print_lg(f"\n[INDEED] Searching: '{term}' in '{search_location}'")
        
        q = term.replace(" ", "+")
        loc = search_location.replace(" ", "+").replace(",", "%2C")
        search_url = f"https://{current_domain}/jobs?q={q}&l={loc}&fromage=7"
        # fromage=7 = last 7 days, adjust as needed
        
        driver.get(search_url)
        time.sleep(4)

        # Scroll to load more cards
        _scroll_to_load(driver, scrolls=3)

        cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTORS["job_card"])
        print_lg(f"[INDEED] Found {len(cards)} cards for '{term}'")

        term_count = 0
        for index in range(len(cards)):
            if INDEED_MAX_JOBS_TO_SCRAPE and total_scraped >= INDEED_MAX_JOBS_TO_SCRAPE:
                break
            if INDEED_MAX_JOBS_PER_TERM and term_count >= INDEED_MAX_JOBS_PER_TERM:
                break
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTORS["job_card"])
                if index >= len(cards):
                    break
                card = cards[index]

                job_id = _extract_job_id(card)
                if not job_id or job_id in seen_job_ids:
                    continue

                title   = _safe_text(card, CARD_SELECTORS["job_title"])
                company = _safe_text(card, CARD_SELECTORS["company_name"])
                location = _safe_text(card, CARD_SELECTORS["location"])
                
                if not title:
                    continue

                if not _is_relevant_job(title, company):
                    print_lg(f"[INDEED] Skipping '{title}' at '{company}' — bad_words match.")
                    continue

                try:
                    card_text = card.text or ""
                except Exception:
                    card_text = " ".join([title, company, location])
                if not _passes_quality_filters(title, company, card_text):
                    continue

                job_url = f"https://{current_domain}/viewjob?jk={job_id}"

                record = {
                    "job_id":       job_id,
                    "title":        title,
                    "company":      company,
                    "location":     location,
                    "job_url":      job_url,
                    "source":       "Indeed",
                    "search_term":  term,
                    "scraped_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "applied":      "No",   # user manually marks this
                    "notes":        "",
                }

                save_scraped_job(record)  # writes to shared manual_review_jobs Excel
                seen_job_ids.add(job_id)
                total_scraped += 1
                term_count += 1
                print_lg(f"[INDEED] Saved: {title} | {company} | {job_url}")

            except StaleElementReferenceException:
                continue
            except Exception as e:
                print_lg(f"[INDEED] Error on card {index}: {e}")
                continue

    print_lg(f"\n[INDEED] Scraping complete. Total saved: {total_scraped}")
    return total_scraped


def _scroll_to_load(driver, scrolls=3):
    for _ in range(scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)


def _safe_text(parent, css_selector):
    try:
        return parent.find_element(By.CSS_SELECTOR, css_selector).text.strip()
    except Exception:
        return ""


def _extract_job_id(card):
    try:
        link = card.find_element(By.CSS_SELECTOR, "a[data-jk]")
        return link.get_attribute("data-jk")
    except Exception:
        pass
    try:
        link = card.find_element(By.CSS_SELECTOR, "a[href*='jk=']")
        href = link.get_attribute("href") or ""
        if "jk=" in href:
            return href.split("jk=")[1].split("&")[0]
    except Exception:
        pass
    return None
