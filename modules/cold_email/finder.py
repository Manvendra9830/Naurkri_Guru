import re
import time
import random
import os
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from modules.helpers import print_lg

# Safety Setting
MIN_RECRUITER_EMAIL_CONFIDENCE = 0.8
MAX_RECRUITER_PROFILE_VISITS_PER_RUN = 10
OWN_OR_TEST_EMAILS = {
    "manvendras606@gmail.com",
    "cs22b1054@iiitr.ac.in",
    "manvendra.singh@darwix.ai",
    "manomegle9830@gmail.com",
    "manusingh9830@gmail.com",
    "akarsh7376@gmail.com",
}
QUARANTINED_RECRUITER_EMAILS = {
    "riya.kumari@nilasu.com",
    "rosysmita.jena@atyeti.com",
}
PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
}
COMPANY_TOKEN_STOPWORDS = {
    "and",
    "the",
    "india",
    "global",
    "international",
    "careers",
    "jobs",
}
DOMAIN_PREFIX_NOISE = (
    "careers",
    "jobs",
    "hiring",
    "talent",
    "people",
    "mail",
    "email",
    "recruiting",
    "recruitment",
    "hr",
)


def is_driver_alive(driver) -> bool:
    """Check if the Selenium driver session is still valid.
    Returns False if driver is None or session is dead/stale."""
    if driver is None:
        return False
    try:
        _ = driver.current_window_handle
        return True
    except (WebDriverException, Exception) as e:
        print_lg(f"[BROWSER-HEALTH] enrichment_driver=dead; error={type(e).__name__}: {e}")
        return False


def _log_email_result(email: str, source: str, confidence: float) -> None:
    print_lg(f"[EMAIL-FOUND] email={email}")
    print_lg(f"[EMAIL-SOURCE] source={source}")
    print_lg(f"[EMAIL-CONFIDENCE] confidence={confidence:.2f}")

def clean_company_name(company_name: str) -> str:
    if not company_name:
        return ""
    name = company_name.lower().strip()
    # Remove common corporate suffixes
    suffixes = [
        r'\binc\b', r'\bcorp\b', r'\bcorporation\b', r'\bco\b', r'\bltd\b',
        r'\bllc\b', r'\btechnologies\b', r'\blabs\b', r'\bgroup\b',
        r'\bsolutions\b', r'\bpvt\b', r'\bprivate\b', r'\blimited\b'
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name)
    name = re.sub(r'[^a-z0-9 ]', '', name)
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    return name


def normalize_email_candidate(candidate: str) -> str:
    """Normalize a raw email candidate captured from visible page/profile text."""
    if not candidate:
        return ""
    candidate = candidate.strip().lower()
    candidate = re.sub(r"^mailto:", "", candidate)
    match = re.search(r'[a-z0-9_.+-]+@(?:[a-z0-9-]+\.)+[a-z]{2,}', candidate)
    if not match:
        return ""
    return match.group(0).strip(".,;:)]}>\"'")


def email_domain(email: str) -> str:
    email = normalize_email_candidate(email)
    if "@" not in email:
        return ""
    return email.split("@", 1)[1]


def domain_root(domain: str) -> str:
    if not domain:
        return ""
    root = domain.split(".", 1)[0].lower()
    root = re.sub(r"[^a-z0-9]", "", root)
    for prefix in DOMAIN_PREFIX_NOISE:
        if root.startswith(prefix) and len(root) > len(prefix) + 3:
            root = root[len(prefix):]
            break
    return root


def company_domain_signals(company_name: str) -> set[str]:
    tokens = [
        token
        for token in clean_company_name(company_name).split()
        if len(token) >= 3 and token not in COMPANY_TOKEN_STOPWORDS
    ]
    signals = set(tokens)
    if tokens:
        compact = "".join(tokens)
        if len(compact) >= 4:
            signals.add(compact)
        acronym = "".join(token[0] for token in tokens if token)
        if len(acronym) >= 2:
            signals.add(acronym)
    return signals


def extract_emails_from_text(text: str) -> list[str]:
    if not text:
        return []
    pattern = r'[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    found = re.findall(pattern, text)
    filtered = []
    seen = set()
    low_trust_words = [
        'glassdoor', 'indeed', 'naukri', 'substack', 'resumeworded',
        'freshersindia', 'getujobs', 'linkedin', 'support', 'noreply',
        'no-reply', 'donotreply', 'example.com', 'w3.org', 'reply',
        'feedback', 'privacy', 'security', 'help', 'jobs-listings',
        'alert', 'notification', 'info@linkedin.com', 'members@linkedin.com'
    ]
    for email in found:
        email_lower = normalize_email_candidate(email)
        if not email_lower:
            continue
        if email_lower in seen:
            continue
        seen.add(email_lower)
        if email_lower in OWN_OR_TEST_EMAILS or email_lower in QUARANTINED_RECRUITER_EMAILS:
            print_lg(f"[ENRICHMENT-QUARANTINE] Ignoring known unsafe/test recruiter email: {email_lower}")
            continue
        if any(word in email_lower for word in low_trust_words):
            continue
        filtered.append(email_lower)
    if found and len(filtered) != len(found):
        print_lg(f"[ENRICHMENT-DIAGNOSTIC] Email extraction filtered {len(found) - len(filtered)} of {len(found)} candidate(s).")
    return filtered


def email_matches_company_context(email: str, company_name: str) -> bool:
    """Conservative check: visible-page emails must share a meaningful company token."""
    if not email or "@" not in email or not company_name:
        return False
    root = domain_root(email_domain(email))
    if not root:
        return False
    signals = company_domain_signals(company_name)
    if not signals:
        return False
    return any(signal in root or root in signal for signal in signals)


def trust_recruiter_email(email: str, source: str | None, confidence: float | None, company_name: str = "") -> tuple[bool, str, float]:
    """Central recruiter-email trust gate used before storing or sending outreach."""
    email_lower = normalize_email_candidate(email)
    source = source or ""
    confidence = float(confidence or 0.0)
    if not email_lower:
        return False, "missing_email", 0.0
    domain = email_domain(email_lower)
    if source == "validation_seed":
        return True, "validation_seed", max(confidence, 1.0)
    if email_lower in OWN_OR_TEST_EMAILS:
        return False, "own_or_manual_test_email", 0.0
    if email_lower in QUARANTINED_RECRUITER_EMAILS:
        return False, "known_cross_company_contamination", 0.0
    if domain in PUBLIC_EMAIL_DOMAINS:
        return False, "public_email_domain", min(confidence, 0.5)
    if source in {"linkedin_visible", "job_description"} and not email_matches_company_context(email_lower, company_name):
        return False, "company_domain_mismatch", min(confidence, 0.4)
    if confidence < MIN_RECRUITER_EMAIL_CONFIDENCE:
        return False, "low_confidence", confidence
    return True, "trusted", confidence

def extract_email_level1_direct(driver) -> tuple[str | None, str | None, float | None]:
    """Level 1: Direct extraction from current job page body/elements."""
    if not is_driver_alive(driver):
        print_lg("[ENRICHMENT-SKIP] Level 1: Driver session is not alive. Skipping direct extraction.")
        return None, None, None
    try:
        # Search visible body text
        body_element = driver.find_element(By.TAG_NAME, "body")
        body_text = body_element.text
        emails = extract_emails_from_text(body_text)
        if emails:
            print_lg(f"[ENRICHMENT-SUCCESS] Level 1: Direct job description page email found: {emails[0]}")
            return emails[0], "linkedin_visible", 1.0
        print_lg("[ENRICHMENT-DEBUG] Level 1: direct page email scan finished. No email found.")
    except Exception as e:
        print_lg(f"Level 1 email extraction error: {e}")
    return None, None, None

def extract_email_level2_profile(driver, profile_url: str) -> tuple[str | None, str | None, float | None]:
    """Level 2: Open recruiter profile safely and scan contact overlay & visible text."""
    if not is_driver_alive(driver):
        print_lg("[ENRICHMENT-SKIP] Level 2: Driver session is not alive. Skipping profile extraction.")
        return None, None, None
    if not profile_url or profile_url == "Unknown":
        return None, None, None
    try:
        print_lg(f"[ENRICHMENT-DEBUG] Level 2: Visiting recruiter profile contact info: {profile_url}")
        
        # Navigate to profile contact info directly
        base_url = profile_url.split('?')[0].rstrip('/')
        contact_url = f"{base_url}/overlay/contact-info/"
        
        driver.get(contact_url)
        # Random sleep to mimic human behavior
        time.sleep(random.uniform(3, 5))
        
        # Scan page text
        body_text = driver.find_element(By.TAG_NAME, "body").text
        emails = extract_emails_from_text(body_text)
        if emails:
            print_lg(f"[ENRICHMENT-SUCCESS] Level 2: Email found on recruiter contact overlay: {emails[0]}")
            return emails[0], "recruiter_profile", 0.9
            
        # Fallback to main profile page if overlay fails
        driver.get(base_url)
        time.sleep(random.uniform(2, 4))
        body_text = driver.find_element(By.TAG_NAME, "body").text
        emails = extract_emails_from_text(body_text)
        if emails:
            print_lg(f"[ENRICHMENT-SUCCESS] Level 2: Email found on recruiter profile main page: {emails[0]}")
            return emails[0], "recruiter_profile", 0.9
        print_lg("[ENRICHMENT-DEBUG] Level 2: Finished scanning recruiter profile. No email found.")
            
    except Exception as e:
        print_lg(f"Level 2 email extraction error for {profile_url}: {e}")
    return None, None, None

def extract_email_level3_job_description(job_description: str, company_name: str) -> tuple[str | None, str | None, float | None]:
    """Level 3: Conservative email extraction from the stored job description."""
    emails = extract_emails_from_text(job_description or "")
    for email in emails:
        if email_matches_company_context(email, company_name):
            print_lg(f"[ENRICHMENT-SUCCESS] Level 3: Job description email found: {email}")
            return email, "job_description", 0.85
        print_lg(f"[ENRICHMENT-QUARANTINE] Job description email rejected for company mismatch: {email}")
    return None, None, None

def extract_email_company_careers(driver, company_name: str) -> tuple[str | None, str | None, float | None]:
    """Scan a guessed company careers/jobs page for visible recruiter emails."""
    if not is_driver_alive(driver):
        print_lg("[ENRICHMENT-SKIP] Careers page extraction skipped because driver is unavailable.")
        return None, None, None
    domain = _guess_company_domain(company_name)
    if not domain:
        return None, None, None
    urls = [f"https://{domain}/careers", f"https://{domain}/jobs"]
    for url in urls:
        try:
            print_lg(f"[ENRICHMENT-DEBUG] Careers email scan: {url}")
            driver.get(url)
            time.sleep(random.uniform(2, 3))
            body_text = driver.find_element(By.TAG_NAME, "body").text
            for email in extract_emails_from_text(body_text):
                if email_matches_company_context(email, company_name):
                    print_lg(f"[ENRICHMENT-SUCCESS] Careers page email found: {email}")
                    return email, "company_careers_page", 0.88
                print_lg(f"[ENRICHMENT-QUARANTINE] Careers page email rejected for company mismatch: {email}")
        except Exception as e:
            print_lg(f"[ENRICHMENT-DEBUG] Careers page scan failed for {url}: {type(e).__name__}: {e}")
    return None, None, None


def extract_email_hunter(company_name: str) -> tuple[str | None, str | None, float | None]:
    try:
        from config.secrets import HUNTER_API_KEY
    except Exception:
        HUNTER_API_KEY = ""
    email = hunter_find_email(company_name, HUNTER_API_KEY)
    if email:
        return email, "hunter_io", 0.9
    return None, None, None


def extract_email_apify(company_name: str) -> tuple[str | None, str | None, float | None]:
    """Optional Apify enrichment hook controlled by env vars, disabled if not configured."""
    token = os.environ.get("APIFY_API_TOKEN", "").strip()
    endpoint = os.environ.get("APIFY_ENRICHMENT_URL", "").strip()
    if not token or not endpoint:
        print_lg("[ENRICHMENT-SKIP] Apify enrichment skipped; APIFY_API_TOKEN/APIFY_ENRICHMENT_URL not configured.")
        return None, None, None
    try:
        import requests
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            json={"company": company_name},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload if isinstance(payload, list) else payload.get("emails", [])
        for candidate in candidates:
            email = candidate.get("email") if isinstance(candidate, dict) else str(candidate)
            email = normalize_email_candidate(email)
            if email:
                confidence = float(candidate.get("confidence", 0.9)) if isinstance(candidate, dict) else 0.85
                return email, "apify", confidence
    except Exception as e:
        print_lg(f"[APIFY] Enrichment failed: {type(e).__name__}: {e}")
    return None, None, None


def extract_email_pattern_guess(recruiter_name: str, company_name: str) -> tuple[str | None, str | None, float | None]:
    """Generate conservative pattern guesses; trust gate keeps them out of sending unless policy changes."""
    domain = _guess_company_domain(company_name)
    if not domain:
        return None, "pattern_guess", 0.0
    names = [part for part in re.split(r"\s+", recruiter_name or "") if part and part.lower() != "unknown"]
    if len(names) >= 2:
        guesses = guess_email_from_name_domain(names[0], names[-1], domain)
    else:
        guesses = [f"hr@{domain}", f"careers@{domain}", f"recruit@{domain}"]
    guess = normalize_email_candidate(guesses[0])
    if guess:
        print_lg(f"[ENRICHMENT-SAFE] Pattern guess generated but low confidence: {guess}")
        return guess, "pattern_guess", 0.35
    return None, "pattern_guess", 0.0


def extract_email_level3_guess(recruiter_name: str, company_name: str) -> tuple[str | None, str | None, float | None]:
    """Backward-compatible alias for validation/tests using the old helper name."""
    return extract_email_pattern_guess(recruiter_name, company_name)

def find_recruiter_email(driver, job_data: dict, profile_visit_counter: int) -> tuple[str | None, str | None, float | None, int]:
    """Find/enrich recruiter email in the requested priority order."""
    recruiter_profile_url = job_data.get("recruiter_profile_url") or ""
    company = job_data.get("company") or ""
    new_visits = profile_visit_counter

    # A. Stored job description email extraction.
    email, source, conf = extract_email_level3_job_description(job_data.get("job_description") or "", company)
    if email:
        trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
        if trusted:
            _log_email_result(email, source or "", adjusted_conf)
            return email, source, adjusted_conf, new_visits
        print_lg(f"[ENRICHMENT-QUARANTINE] Job description email rejected for {company}: {email} ({reason})")

    # B. Company website careers page extraction.
    email, source, conf = extract_email_company_careers(driver, company)
    if email:
        trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
        if trusted:
            _log_email_result(email, source or "", adjusted_conf)
            return email, source, adjusted_conf, new_visits
        print_lg(f"[ENRICHMENT-QUARANTINE] Careers page email rejected for {company}: {email} ({reason})")

    # C. Hunter.io.
    email, source, conf = extract_email_hunter(company)
    if email:
        trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
        if trusted:
            _log_email_result(email, source or "", adjusted_conf)
            return email, source, adjusted_conf, new_visits
        print_lg(f"[ENRICHMENT-QUARANTINE] Hunter email rejected for {company}: {email} ({reason})")

    # D. Apify enrichment.
    email, source, conf = extract_email_apify(company)
    if email:
        trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
        if trusted:
            _log_email_result(email, source or "", adjusted_conf)
            return email, source, adjusted_conf, new_visits
        print_lg(f"[ENRICHMENT-QUARANTINE] Apify email rejected for {company}: {email} ({reason})")

    # Existing LinkedIn recruiter profile fallback, kept after requested sources.
    if recruiter_profile_url and recruiter_profile_url != "Unknown" and recruiter_profile_url.startswith("http"):
        if profile_visit_counter < MAX_RECRUITER_PROFILE_VISITS_PER_RUN:
            new_visits += 1
            email, source, conf = extract_email_level2_profile(driver, recruiter_profile_url)
            if email:
                trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
                if trusted:
                    _log_email_result(email, source or "", adjusted_conf)
                    return email, source, adjusted_conf, new_visits
                print_lg(f"[ENRICHMENT-QUARANTINE] Level 2 email rejected for {company}: {email} ({reason})")
        else:
            print_lg("Max recruiter profile visits reached. Skipping Level 2.")

    # Visible current-page email fallback.
    email, source, conf = extract_email_level1_direct(driver)
    if email:
        trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
        if trusted:
            _log_email_result(email, source or "", adjusted_conf)
            return email, source, adjusted_conf, new_visits
        print_lg(f"[ENRICHMENT-QUARANTINE] Level 1 email rejected for {company}: {email} ({reason})")

    # E. Pattern guessing, intentionally low confidence unless verified elsewhere.
    email, source, conf = extract_email_pattern_guess(job_data.get("recruiter_name") or "", company)
    if email:
        trusted, reason, adjusted_conf = trust_recruiter_email(email, source, conf, company)
        if trusted:
            _log_email_result(email, source or "", adjusted_conf)
            return email, source, adjusted_conf, new_visits
        print_lg(f"[ENRICHMENT-SAFE] Pattern guess rejected by trust gate for {company}: {email} ({reason})")

    print_lg(f"[ENRICHMENT-SAFE] No trusted recruiter email found for '{company}'.")
    return None, None, None, new_visits

def _guess_company_domain(company_name: str) -> str:
    """Simple heuristic to guess domain from company name."""
    cleaned = clean_company_name(company_name).replace(" ", "")
    if not cleaned:
        return ""
    return f"{cleaned}.com"

def hunter_find_email(company_name: str, hunter_api_key: str) -> str:
    """
    Uses Hunter.io domain search to find recruiter email pattern.
    Returns best guess email or empty string.
    """
    import requests
    if not hunter_api_key:
        return ""
    try:
        domain = _guess_company_domain(company_name)
        if not domain:
            return ""
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": hunter_api_key, "limit": 3},
            timeout=8
        )
        data = resp.json()
        emails = data.get("data", {}).get("emails", [])
        # Prefer HR/Recruiter roles
        for e in emails:
            role = (e.get("position") or "").lower()
            if any(kw in role for kw in ["hr", "recruit", "talent", "people"]):
                return e.get("value", "")
        if emails:
            return emails[0].get("value", "")
    except Exception as e:
        print_lg(f"[HUNTER] API call failed: {e}")
    return ""

def guess_email_from_name_domain(first: str, last: str, domain: str) -> list[str]:
    """Generate common email patterns for a name + domain."""
    f, l = first.lower(), last.lower()
    return [
        f"{f}.{l}@{domain}",
        f"{f}@{domain}",
        f"{f[0]}{l}@{domain}",
        f"hr@{domain}",
        f"careers@{domain}",
        f"recruit@{domain}",
    ]
