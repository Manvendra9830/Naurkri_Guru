# Imports
import os
import csv
import re
import time


# Set CSV field size limit to prevent field size errors
csv.field_size_limit(1000000)  # Set to 1MB instead of default 131KB

from random import choice, shuffle, randint
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException, WebDriverException

from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password, ai_provider
from config.settings import *

from modules.open_chrome import *
from modules.helpers import ensure_csv_header, detect_external_portal, safe_alert, safe_confirm, safe_write_csv, is_automation_context, normalize_row, normalize_date_posted_value, calculate_date_posted, APPLIED_EXPORT_SCHEMA, FAILED_EXPORT_SCHEMA
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.diagnostics import assert_browser_healthy, detect_captcha, is_linkedin_logged_out
from modules.storage import upsert_application, application_exists
from modules.runtime_context import set_current_runtime_batch_id, get_current_runtime_batch_id

if use_AI:
    from modules.ai.openaiConnections import ai_create_openai_client, ai_extract_skills, ai_answer_question, ai_close_openai_client
    from modules.ai.deepseekConnections import deepseek_create_client, deepseek_extract_skills, deepseek_answer_question
    from modules.ai.geminiConnections import gemini_create_client, gemini_extract_skills, gemini_answer_question

from modules.memory import load_memory, get_answer_from_memory, prompt_user_for_answer, get_or_prompt_skill_experience_answer, is_skill_specific_experience_question, UserCancelledException
global_memory = load_memory()

from typing import Literal



# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
randomly_answered_questions = set()

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False
RUNTIME_BATCH_ID = None

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)
WORK_STYLE_VALUES = {"remote": "Remote", "hybrid": "Hybrid", "on-site": "On-site", "onsite": "On-site", "on site": "On-site"}

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
about_company_for_ai = None # TODO extract about company for AI

#>


def clean_card_text(value: str, fallback: str = "Unknown") -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value if value else fallback


def split_location_and_style(value: str) -> tuple[str, str]:
    value = clean_card_text(value, "")
    if not value:
        return "Unknown", "Unknown"
    style = "Unknown"
    location = value
    match = re.search(r"\(([^()]*)\)\s*$", value)
    if match:
        candidate = clean_card_text(match.group(1), "").lower()
        if candidate in WORK_STYLE_VALUES:
            style = WORK_STYLE_VALUES[candidate]
            location = value[:match.start()].strip()
    return clean_card_text(location), style


def first_text_by_selectors(root: WebElement, selectors: list[str], fallback: str = "") -> str:
    for selector in selectors:
        try:
            text = clean_card_text(root.find_element(By.CSS_SELECTOR, selector).text, "")
            if text:
                return text
        except Exception:
            continue
    return fallback


def find_easy_apply_modal(timeout: float = 10, retries: int = 3) -> WebElement:
    selectors = [
        "[data-view-name='jobs-easy-apply-detail-modal']",
        ".jobs-easy-apply-modal",
        "div.artdeco-modal[role='dialog']",
        "div[role='dialog']",
        ".artdeco-modal"
    ]
    
    print_lg(f"[DRIVER-HEALTH-CHECK] Looking for Easy Apply modal. Timeout={timeout}, Retries={retries}")
    
    for attempt in range(1, retries + 1):
        if attempt > 1:
            print_lg(f"[EASY-APPLY-RETRY] Attempt {attempt}/{retries} to locate modal...")
        
        try:
            driver.switch_to.default_content()
        except Exception as switch_err:
            print_lg(f"[EASY-APPLY-DEBUG] Failed to switch to default content: {switch_err}")
            
        for selector in selectors:
            try:
                elements = WebDriverWait(driver, timeout / retries, poll_frequency=0.2).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, selector)
                )
                for element in elements:
                    try:
                        if element.is_displayed():
                            print_lg(f"[EASY-APPLY-MODAL-OPEN] Easy Apply modal detected via CSS={selector} on attempt {attempt}")
                            debug_modal_state(element, "modal-detected")
                            return element
                    except Exception:
                        continue
            except Exception:
                continue
                
        time.sleep(0.5)
        
    print_lg("[EASY-APPLY-FAILURE] Failed to find Easy Apply modal after all retries and selectors.")
    raise NoSuchElementException("Easy Apply modal was not available")


def debug_modal_state(modal: WebElement | None, stage: str) -> None:
    if not modal:
        print_lg(f"[APPLY-DEBUG] {stage}: modal=None")
        return
    try:
        buttons = describe_action_buttons(modal)
        normalized_buttons = " | ".join(button.lower() for button in buttons)
        has_next = "next" in normalized_buttons
        has_review = "review" in normalized_buttons
        has_submit = "submit application" in normalized_buttons
        has_done = "done" in normalized_buttons
        print_lg(
            f"[APPLY-DEBUG] {stage}: buttons={buttons}; "
            f"next={has_next}, review={has_review}, submit={has_submit}, done={has_done}"
        )
    except Exception as e:
        print_lg(f"[APPLY-DEBUG] {stage}: failed to inspect modal: {e}")


def click_modal_action(modal: WebElement, text: str, timeout: float = 3) -> WebElement | bool:
    debug_modal_state(modal, f"before-{text}")
    button = wait_span_click(modal, text, timeout)
    debug_modal_state(modal, f"after-{text}")
    return button


def verify_easy_apply_submission(modal: WebElement | None, job_id: str, title: str, company: str) -> tuple[bool, str]:
    """Confirm LinkedIn acknowledged submission before writing an applied row."""
    markers = (
        "application submitted",
        "application sent",
        "your application was sent",
        "your application has been sent",
        "application was submitted",
    )
    try:
        if modal:
            modal_text = " ".join((modal.text or "").lower().split())
            if any(marker in modal_text for marker in markers):
                print_lg(f"[APPLY-CONFIRMED] Completion text detected for job_id={job_id}, company={company}")
                return True, "completion_text"
            if find_action_button(modal, "Done", 1) and not find_action_button(modal, "Submit application", 0.5):
                print_lg(f"[APPLY-CONFIRMED] Completion modal Done button detected for job_id={job_id}, company={company}")
                return True, "done_button_without_submit"
    except Exception as e:
        print_lg(f"[APPLY-CONFIRMATION-DEBUG] Modal confirmation check failed for job_id={job_id}: {type(e).__name__}: {e}")

    try:
        page_text = " ".join((driver.find_element(By.TAG_NAME, "body").text or "").lower().split())
        if any(marker in page_text for marker in markers):
            print_lg(f"[APPLY-CONFIRMED] Page-level completion text detected for job_id={job_id}, company={company}")
            return True, "page_completion_text"
    except Exception as e:
        print_lg(f"[APPLY-CONFIRMATION-DEBUG] Page confirmation check failed for job_id={job_id}: {type(e).__name__}: {e}")

    print_lg(f"[APPLY-UNVERIFIED] Submit click was not followed by LinkedIn confirmation for job_id={job_id}, title={title}, company={company}")
    return False, "missing_linkedin_confirmation"


#< Login Functions
def is_logged_in_LN() -> bool:
    '''
    Function to check if user is logged-in in LinkedIn
    * Returns: `True` if user is logged-in or `False` if not
    '''
    if driver.current_url == "https://www.linkedin.com/feed/": return True
    if try_linkText(driver, "Sign in"): return False
    if try_xp(driver, '//button[@type="submit" and contains(text(), "Sign in")]'):  return False
    if try_linkText(driver, "Join now"): return False
    print_lg("Didn't find Sign in link, so assuming user is logged in!")
    return True


def login_LN() -> None:
    '''
    Function to login for LinkedIn
    * Tries to login using given `username` and `password` from `secrets.py`
    * If failed, tries to login using saved LinkedIn profile button if available
    * If both failed, asks user to login manually
    '''
    # Find the username and password fields and fill them with user credentials
    driver.get("https://www.linkedin.com/login")
    if username == "username@example.com" and password == "example_password":
        safe_alert("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!", "Login Manually","Okay")
        print_lg("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!")
        manual_login_retry(is_logged_in_LN, 2)
        return
    try:
        wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Forgot password?")))
        try:
            text_input_by_ID(driver, "username", username, 1)
        except Exception as e:
            print_lg("Couldn't find username field.")
            # print_lg(e)
        try:
            text_input_by_ID(driver, "password", password, 1)
        except Exception as e:
            print_lg("Couldn't find password field.")
            # print_lg(e)
        # Find the login submit button and click it
        driver.find_element(By.XPATH, '//button[@type="submit" and contains(text(), "Sign in")]').click()
    except Exception as e1:
        try:
            profile_button = find_by_class(driver, "profile__details")
            profile_button.click()
        except Exception as e2:
            # print_lg(e1, e2)
            print_lg("Couldn't Login!")

    try:
        # Wait until successful redirect, indicating successful login
        wait.until(EC.url_to_be("https://www.linkedin.com/feed/")) # wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space(.)="Start a post"]')))
        return print_lg("Login successful!")
    except Exception as e:
        print_lg("Seems like login attempt failed! Possibly due to wrong credentials or already logged in! Try logging in manually!")
        # print_lg(e)
        manual_login_retry(is_logged_in_LN, 2)
#>



def get_applied_job_ids() -> set[str]:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from SQLite applications database
    '''
    from modules.storage import get_all_applications
    job_ids: set[str] = set()
    try:
        apps = get_all_applications()
        for row in apps:
            job_id = row.get('job_id')
            if job_id:
                job_ids.add(job_id)
    except Exception as e:
        print_lg(f"Error querying applied job IDs from SQLite: {e}")
    return job_ids



def set_search_location() -> None:
    '''
    Function to set search location
    '''
    if search_location.strip():
        try:
            print_lg(f'Setting search location as: "{search_location.strip()}"')
            search_location_ele = try_xp(driver, ".//input[@aria-label='City, state, or zip code'and not(@disabled)]", False) #  and not(@aria-hidden='true')]")
            text_input(actions, search_location_ele, search_location, "Search Location")
        except ElementNotInteractableException:
            try_xp(driver, ".//label[@class='jobs-search-box__input-icon jobs-search-box__keywords-label']")
            actions.send_keys(Keys.TAB, Keys.TAB).perform()
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            actions.send_keys(search_location.strip()).perform()
            sleep(2)
            actions.send_keys(Keys.ENTER).perform()
            try_xp(driver, ".//button[@aria-label='Cancel']")
        except Exception as e:
            try_xp(driver, ".//button[@aria-label='Cancel']")
            print_lg("Failed to update search location, continuing with default location!", e)


def click_first_visible_xpath(root: WebElement, xpaths: list[str], timeout: float = 1.5) -> WebElement | bool:
    def _find(_driver):
        for xpath in xpaths:
            for element in root.find_elements(By.XPATH, xpath):
                try:
                    if element.is_displayed() and element.is_enabled():
                        return element
                except Exception:
                    continue
        return False

    try:
        element = WebDriverWait(driver, timeout, poll_frequency=0.25).until(_find)
        scroll_to_view(driver, element)
        try:
            element.click()
        except Exception:
            driver.execute_script("arguments[0].click();", element)
        buffer(0 if click_gap < 1 else 1)
        return element
    except Exception:
        return False


def click_date_posted_filter(label: str) -> bool:
    label = clean_card_text(label, "")
    if not label:
        return True
    label_lower = label.lower()
    label_xpaths = [
        f'.//button[.//*[normalize-space()="{label}"] or normalize-space()="{label}"]',
        f'.//*[@role="button" and (.//*[normalize-space()="{label}"] or normalize-space()="{label}")]',
        f'.//label[.//*[normalize-space()="{label}"] or normalize-space()="{label}"]',
        f'.//*[@role="radio" and contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label_lower}")]',
        f'.//input[@type="radio" and contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{label_lower}")]/ancestor::label',
        f'.//*[self::span or self::div][normalize-space()="{label}"]/ancestor::*[self::button or self::label or @role="button" or @role="radio"][1]',
    ]
    if click_first_visible_xpath(driver, label_xpaths):
        print_lg(f"[FILTER-DEBUG] Date posted filter selected: {label}")
        return True

    dropdown_xpaths = [
        './/button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "date posted")]',
        './/button[.//*[contains(translate(normalize-space(.), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "date posted")]]',
        './/*[@role="button" and contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "date posted")]',
    ]
    if not click_first_visible_xpath(driver, dropdown_xpaths):
        return False

    if click_first_visible_xpath(driver, label_xpaths):
        print_lg(f"[FILTER-DEBUG] Date posted dropdown filter selected: {label}")
        return True
    return False


def apply_filters() -> None:
    '''
    Function to apply job search filters
    '''
    set_search_location()

    try:
        recommended_wait = 1 if click_gap < 1 else 0

        wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="All filters"]'))).click()
        buffer(recommended_wait)

        wait_span_click(driver, sort_by)
        if date_posted and not click_date_posted_filter(date_posted):
            print_lg(f"[FILTER-FALLBACK] {date_posted} filter unavailable, continuing without date filter.")
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level) 
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only: boolean_button_click(driver, actions, "Easy Apply")
        
        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)
        
        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

        show_results_button: WebElement = driver.find_element(By.XPATH, '//button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "apply current filters to show")]')
        show_results_button.click()

        global pause_after_filters
        if pause_after_filters and "Turn off Pause after search" == safe_confirm("These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", "Please check your results", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg(f"Setting the preferences failed safely; continuing without blocking execution. ERROR: {type(e).__name__}: {e}")
        # print_lg(e)



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    try:
        pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
    except Exception as e:
        print_lg("Failed to find Pagination element, hence couldn't scroll till end!")
        pagination_element = None
        current_page = None
        print_lg(e)
    return pagination_element, current_page



def get_job_main_details(job: WebElement, blacklisted_companies: set, rejected_jobs: set) -> tuple[str, str, str, str, str, bool]:
    '''
    # Function to get job main details.
    Returns a tuple of (job_id, title, company, work_location, work_style, skip)
    * job_id: Job ID
    * title: Job title
    * company: Company name
    * work_location: Work location of this job
    * work_style: Work style of this job (Remote, On-site, Hybrid)
    * skip: A boolean flag to skip this job
    '''
    skip = False
    try:
        job_details_button = job.find_element(By.CSS_SELECTOR, "a.job-card-container__link")
    except Exception:
        job_details_button = job.find_element(By.TAG_NAME, 'a')  # fallback for older LinkedIn cards
    scroll_to_view(driver, job_details_button, True)
    job_id = job.get_dom_attribute('data-occludable-job-id')
    title = job_details_button.text.strip() or job_details_button.get_attribute("aria-label") or "Unknown Title"
    title = clean_card_text(title.split("\n")[0].replace(" with verification", ""), "Unknown Title")
    subtitle = first_text_by_selectors(job, [
        ".job-card-container__primary-description",
        ".artdeco-entity-lockup__subtitle",
    ], "Unknown")
    company = subtitle.split(" · ", 1)[0].split(" Â· ", 1)[0].strip() or "Unknown"
    work_location, work_style = "Unknown", "Unknown"
    try:
        company = job.find_element(By.CLASS_NAME, "job-card-container__primary-description").text.strip() or company
    except Exception:
        pass
    card_location = first_text_by_selectors(job, [
        ".job-card-container__metadata-item",
        ".artdeco-entity-lockup__caption",
        ".job-card-container__metadata-wrapper li",
    ], "")
    if card_location:
        work_location, work_style = split_location_and_style(card_location)
    
    # Skip if previously rejected due to blacklist or already applied
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        skip = True
    elif job_id in rejected_jobs: 
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}!')
        skip = True
    try:
        if job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state").text == "Applied":
            skip = True
            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
    except: pass
    try: 
        if not skip: job_details_button.click()
    except Exception as e:
        print_lg(f'Failed to click "{title} | {company}" job on details button. Job ID: {job_id}!') 
        # print_lg(e)
        discard_job()
        job_details_button.click() # To pass the error outside
    print_lg(f'[JOB-DEBUG] Selected job card: "{title} | {company}" | Location: {work_location} | Style: {work_style} | Job ID: {job_id}')
    buffer(click_gap)
    return (job_id,title,company,work_location,work_style,skip)


# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
    about_company_org = find_by_class(driver, "jobs-company__box")
    scroll_to_view(driver, about_company_org)
    about_company_org = about_company_org.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words: 
            if word.lower() in about_company: 
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # Extract all patterns like '10+ years', '5 years', '3-5 years', etc.
    matches = re.findall(re_experience, text)
    if len(matches) == 0: 
        print_lg(f'\n{text}\n\nCouldn\'t find experience requirement in About the Job!')
        return 0
    valid_years = [int(match) for match in matches if int(match) <= 12]
    if not valid_years:
        print_lg("[FILTER-DEBUG] Found year-like values, but none looked like experience requirements:", matches)
        return 0
    return max(valid_years)


def contains_filter_word(text: str, word: str) -> bool:
    """
    Match configured filter terms without turning short role words into broad
    substring matches. Phrases still match naturally, single words use boundaries.
    """
    word = word.strip()
    if not word:
        return False
    if re.search(r"\s", word):
        return word.lower() in text.lower()
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


def extract_degree_and_seniority(text: str, title: str = "") -> tuple[bool, str]:
    """
    Checks the job description for advanced degree requirements or high seniority
    that would make it unsuitable for a junior/bachelor candidate.
    Returns (skip, reason).
    """
    text_lower = text.lower()
    title_lower = title.lower()
    
    # Check for advanced degrees
    if re.search(r'\b(phd|ph\.d|doctorate)\b', text_lower):
        return True, "Requires PhD/Doctorate"
        
    # Check high seniority in the role/title first. Company descriptions often
    # contain words like "senior" or "enterprise" that are not role requirements.
    title_seniority_patterns = [
        r'\b(principal|staff|lead|director|architect)\b',
        r'\b(vp|vice president)\b',
        r'\b(senior researcher|research scientist|research fellow|applied scientist)\b',
        r'\b(manager)\b',
    ]
    for pattern in title_seniority_patterns:
        if re.search(pattern, title_lower):
            return True, f"High seniority role detected in title: {pattern.replace(r'\\b', '').replace('(', '').replace(')', '')}"

    # Check explicit high-experience requirements in the JD.
    seniority_patterns = [
        r'\b(5\+\s*years)\b',
        r'\b(6\+\s*years)\b',
        r'\b(7\+\s*years)\b',
        r'\b(10\+\s*years)\b'
    ]
    for pattern in seniority_patterns:
        if re.search(pattern, text_lower):
            return True, f"High seniority/Irrelevant role detected: {pattern.replace(r'\\b', '').replace('(', '').replace(')', '')}"
            
    return False, ""

def calculate_confidence_score(text: str) -> int:
    """
    Calculates a heuristic Apply Confidence Score (0-100) based on JD text.
    """
    score = 60 # Base score
    text_lower = text.lower()
    
    # Positive keywords
    if 'intern' in text_lower or 'internship' in text_lower: score += 20
    if 'fresher' in text_lower or 'entry level' in text_lower: score += 15
    if 'python' in text_lower or 'react' in text_lower or 'machine learning' in text_lower: score += 10
    
    # Negative keywords
    if 'consulting' in text_lower or 'b2b' in text_lower: score -= 15
    if 'clearance' in text_lower or 'secret' in text_lower: score -= 20
    if re.search(r'\b(manager|senior manager|principal|staff engineer)\b', text_lower): score -= 20
    
    return min(100, max(0, score))


ROLE_CONTEXT_FILTER_WORDS = {"Senior", "Lead", "Manager", "Architect", "Analyst", "Consultant", "Enterprise", "B2B"}


def get_job_description(
    title: str = "",
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None,
    int
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    - `confidence_score: int`
    '''
    confidence_score = 0
    jobDescription = "Unknown"
    experience_required = "Unknown"
    skip = False
    skipReason = None
    skipMessage = None
    try:
        ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
        ##<
        found_masters = 0
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        confidence_score = calculate_confidence_score(jobDescription)
        print_lg(f"[SCORE] Apply Confidence Score: {confidence_score}%")
        
        # Advanced Filtering
        adv_skip, adv_reason = extract_degree_and_seniority(jobDescription, title)
        if adv_skip:
            skipMessage = f'\n{jobDescription}\n\n[FILTER-REJECT] {adv_reason}. Skipping this job!\n'
            skipReason = adv_reason
            skip = True
            
        if not skip:
            for word in bad_words:
                if word in ROLE_CONTEXT_FILTER_WORDS:
                    if contains_filter_word(title, word):
                        skipMessage = f'\n{jobDescription}\n\n[FILTER-REJECT] Role title contains filtered seniority/context word "{word}". Skipping this job!\n'
                        skipReason = "Found a filtered role word in title"
                        skip = True
                        break
                    continue
                if contains_filter_word(jobDescription, word):
                    skipMessage = f'\n{jobDescription}\n\n[FILTER-REJECT] Contains bad word "{word}". Skipping this job!\n'
                    skipReason = "Found a Bad Word in About Job"
                    skip = True
                    break
        if not skip and security_clearance == False and ('polygraph' in jobDescriptionLow or 'clearance' in jobDescriptionLow or 'secret' in jobDescriptionLow):
            skipMessage = f'\n{jobDescription}\n\n[FILTER-REJECT] Found "Clearance" or "Polygraph". Skipping this job!\n'
            skipReason = "Asking for Security clearance"
            skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'[FILTER-INFO] Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\n[FILTER-REJECT] Experience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            print_lg("[FILTER-DEBUG] JD extraction exception:", e)
    finally:
        if skip:
            print_lg(f"[FILTER-DEBUG] Skipping job from JD filter. Reason: {skipReason or 'Unknown'} | Experience: {experience_required} | Score: {confidence_score}")
        return jobDescription, experience_required, skip, skipReason, skipMessage, confidence_score
        


# Function to upload resume
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    try:
        modal.find_element(By.NAME, "file").send_keys(os.path.abspath(resume))
        return True, os.path.basename(default_resume_path)
    except: return False, "Previous resume"

def guard_ai_answer(label_org: str, ai_answer: str) -> str:
    global desired_salary, desired_salary_lakhs, desired_salary_monthly
    global current_ctc, current_ctc_lakhs, current_ctc_monthly
    global notice_period, notice_period_months, notice_period_weeks
    global years_of_experience, phone_number, current_city

    label = label_org.lower().strip()
    
    # 1. Graduation year
    if ('graduation' in label or 'graduate' in label) and 'year' in label:
        print_lg(f"[AI-GUARD] Overriding graduation year for '{label_org}' with '2026'")
        return "2026"

    # 2. Overall Experience (avoiding specific skill experience questions)
    if is_skill_specific_experience_question(label_org):
        print_lg(f"[AI-GUARD] Blocking AI fallback for skill-specific experience question '{label_org}'.")
        return get_or_prompt_skill_experience_answer(label_org, global_memory)

    if ('experience' in label or 'years' in label) and not any(skill in label for skill in [
        'python', 'java', 'c++', 'c#', 'sql', 'react', 'aws', 'docker', 'kubernetes', 'javascript', 
        'go', 'ruby', 'rust', 'angular', 'vue', 'swift', 'kotlin', 'flutter', 'typescript', 'php', 
        'node', 'django', 'flask', 'git', 'linux', 'azure', 'gcp', 'cloud', 'ml', 'ai', 
        'machine learning', 'deep learning', 'nlp', 'data science', 'analytics', 'tableau', 
        'powerbi', 'salesforce', 'sap', 'oracle', 'html', 'css', 'testing', 'qa', 'automation', 
        'selenium', 'devops', 'scrum', 'agile', 'frontend', 'backend', 'fullstack', 'full-stack',
        'design', 'product', 'marketing', 'sales', 'management'
    ]):
        print_lg(f"[AI-GUARD] Overriding experience for '{label_org}' with years_of_experience='{years_of_experience}'")
        return str(years_of_experience)

    # 3. Current CTC / Present Salary
    if any(kw in label for kw in ['salary', 'ctc', 'compensation', 'pay', 'package']) and any(kw in label for kw in ['current', 'present', 'now', 'earn', 'existing']):
        if 'lakh' in label or 'lakhs' in label:
            print_lg(f"[AI-GUARD] Overriding current CTC (in lakhs) for '{label_org}' with '{current_ctc_lakhs}'")
            return current_ctc_lakhs
        elif 'month' in label or 'monthly' in label:
            print_lg(f"[AI-GUARD] Overriding current CTC (monthly) for '{label_org}' with '{current_ctc_monthly}'")
            return current_ctc_monthly
        else:
            print_lg(f"[AI-GUARD] Overriding current CTC for '{label_org}' with '{current_ctc}'")
            return current_ctc

    # 4. Desired Salary / Expected CTC
    if any(kw in label for kw in ['salary', 'ctc', 'compensation', 'pay', 'package']) and any(kw in label for kw in ['desired', 'expected', 'expect', 'target', 'requirement', 'require', 'seeking', 'want', 'looking for']):
        if 'lakh' in label or 'lakhs' in label:
            print_lg(f"[AI-GUARD] Overriding desired salary (in lakhs) for '{label_org}' with '{desired_salary_lakhs}'")
            return desired_salary_lakhs
        elif 'month' in label or 'monthly' in label:
            print_lg(f"[AI-GUARD] Overriding desired salary (monthly) for '{label_org}' with '{desired_salary_monthly}'")
            return desired_salary_monthly
        else:
            print_lg(f"[AI-GUARD] Overriding desired salary for '{label_org}' with '{desired_salary}'")
            return desired_salary

    # 5. Notice Period
    if 'notice' in label:
        if 'month' in label or 'months' in label:
            print_lg(f"[AI-GUARD] Overriding notice period (months) for '{label_org}' with '{notice_period_months}'")
            return notice_period_months
        elif 'week' in label or 'weeks' in label:
            print_lg(f"[AI-GUARD] Overriding notice period (weeks) for '{label_org}' with '{notice_period_weeks}'")
            return notice_period_weeks
        else:
            print_lg(f"[AI-GUARD] Overriding notice period for '{label_org}' with '{notice_period}'")
            return notice_period

    # 6. Phone Number
    if 'phone' in label or 'mobile' in label or 'contact number' in label:
        print_lg(f"[AI-GUARD] Overriding phone number for '{label_org}' with '{phone_number}'")
        return str(phone_number)

    # 7. City / Current Location (excluding relocation/travel questions)
    if ('city' in label or 'location' in label or 'live in' in label) and not any(kw in label for kw in [
        'relocate', 'relocation', 'travel', 'open to', 'remote', 'hybrid', 'onsite', 'on-site', 'preference'
    ]):
        print_lg(f"[AI-GUARD] Overriding location/city for '{label_org}' with '{current_city}'")
        return str(current_city)

    # 8. Age
    if label == 'age' or label == 'your age' or label.startswith('age ') or label.endswith(' age'):
        print_lg(f"[AI-GUARD] Overriding age for '{label_org}' with empty string to trigger skip/fallback")
        return ""

    return ai_answer

# Function to answer common questions for Easy Apply
def answer_common_questions(label: str, answer: str) -> str:
    if 'sponsorship' in label or 'visa' in label: answer = require_visa
    return answer


def is_experience_select_question(label: str, options: list[str]) -> bool:
    label = (label or "").lower()
    option_blob = " ".join(options).lower()
    experience_terms = ("experience", "professional", "work", "years", "months")
    unit_terms = ("year", "years", "month", "months")
    return any(term in label for term in experience_terms) and any(term in option_blob for term in unit_terms)


def normalize_select_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def find_matching_select_option(answer: str, options: list[str]) -> str | None:
    normalized_answer = normalize_select_value(answer)
    if not normalized_answer:
        return None
    for option in options:
        if normalize_select_value(option) == normalized_answer:
            return option
    digits = re.findall(r"\d+", normalized_answer)
    if digits:
        wanted = digits[0]
        wants_month = "month" in normalized_answer
        wants_year = "year" in normalized_answer or not wants_month
        for option in options:
            normalized_option = normalize_select_value(option)
            option_digits = re.findall(r"\d+", normalized_option)
            if not option_digits or option_digits[0] != wanted:
                continue
            if wants_month and "month" in normalized_option:
                return option
            if wants_year and "year" in normalized_option:
                return option
    return None


def resolve_experience_select_answer(label_org: str, options_text: list[str]) -> str | None:
    label = (label_org or "").lower()
    usable_options = [option for option in options_text if option and option.strip().lower() != "select an option"]
    print_lg(f"[SAFE-SELECT-GUARD] Experience dropdown detected: '{label_org}' options={usable_options}")

    if "month" in label:
        configured_answer = f"{months_of_experience} month"
    else:
        configured_answer = f"{years_of_experience} year"

    matched = find_matching_select_option(configured_answer, usable_options)
    if matched:
        print_lg(f"[SAFE-SELECT-MATCH] Config matched '{matched}' for '{label_org}'")
        return matched

    memory_answer = get_answer_from_memory(label_org, global_memory)
    matched = find_matching_select_option(memory_answer or "", usable_options)
    if matched:
        print_lg(f"[SAFE-SELECT-MATCH] memory.json matched '{matched}' for '{label_org}'")
        return matched

    try:
        prompted_answer = prompt_user_for_answer(label_org, global_memory)
        matched = find_matching_select_option(prompted_answer, usable_options)
        if matched:
            print_lg(f"[SAFE-SELECT-MATCH] User answer matched '{matched}' for '{label_org}'")
            return matched
    except UserCancelledException:
        print_lg(f"[SAFE-SELECT-GUARD] No safe answer available for '{label_org}'. Leaving dropdown unchanged.")
        return None

    print_lg(f"[SAFE-SELECT-GUARD] Answer did not match available options for '{label_org}'. Leaving dropdown unchanged.")
    return None


# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:
    # Get all questions from the page
     
    all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
    # all_questions = modal.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-element")
    # all_list_questions = modal.find_elements(By.XPATH, ".//div[@data-test-text-entity-list-form-component]")
    # all_single_line_questions = modal.find_elements(By.XPATH, ".//div[@data-test-single-line-text-form-component]")
    # all_questions = all_questions + all_list_questions + all_single_line_questions

    for Question in all_questions:
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            label_org = "Unknown"
            try:
                label = Question.find_element(By.TAG_NAME, "label")
                label_org = label.find_element(By.TAG_NAME, "span").text
            except: pass
            answer = 'Yes'
            label = label_org.lower()
            select = Select(select)
            selected_option = select.first_selected_option.text
            optionsText = []
            options = '"List of phone country codes"'
            if label != "phone country code":
                optionsText = [option.text for option in select.options]
                options = "".join([f' "{option}",' for option in optionsText])
            prev_answer = selected_option
            if overwrite_previous_answers or selected_option == "Select an option":
                ##> ------ WINDY_WINDWARD Email:karthik.sarode23@gmail.com - Added fuzzy logic to answer location based questions ------
                experience_select_guarded = is_experience_select_question(label_org, optionsText)
                safe_select_answer = None
                if experience_select_guarded:
                    safe_select_answer = resolve_experience_select_answer(label_org, optionsText)
                    if safe_select_answer:
                        answer = safe_select_answer
                    else:
                        questions_list.add((f'{label_org} [ {options} ]', selected_option, "select", prev_answer))
                        continue
                elif 'email' in label or 'phone' in label: 
                    answer = prev_answer
                elif 'gender' in label or 'sex' in label: 
                    answer = gender
                elif 'disability' in label: 
                    answer = disability_status
                elif 'proficiency' in label: 
                    answer = 'Professional'
                # Add location handling
                elif any(loc_word in label for loc_word in ['location', 'city', 'state', 'country']):
                    if 'country' in label:
                        answer = country 
                    elif 'state' in label:
                        answer = state
                    elif 'city' in label:
                        answer = current_city if current_city else work_location
                    else:
                        answer = work_location
                else: 
                    answer = answer_common_questions(label,answer)
                try: 
                    select.select_by_visible_text(answer)
                except NoSuchElementException as e:
                    # Define similar phrases for common answers
                    possible_answer_phrases = []
                    if answer == 'Decline':
                        possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"]
                    elif 'yes' in answer.lower():
                        possible_answer_phrases = ["Yes", "Agree", "I do", "I have"]
                    elif 'no' in answer.lower():
                        possible_answer_phrases = ["No", "Disagree", "I don't", "I do not"]
                    else:
                        # Try partial matching for any answer
                        possible_answer_phrases = [answer]
                        # Add lowercase and uppercase variants
                        possible_answer_phrases.append(answer.lower())
                        possible_answer_phrases.append(answer.upper())
                        # Try without special characters
                        possible_answer_phrases.append(''.join(c for c in answer if c.isalnum()))
                    ##<
                    foundOption = False
                    for phrase in possible_answer_phrases:
                        for option in optionsText:
                            # Check if phrase is in option or option is in phrase (bidirectional matching)
                            if phrase.lower() in option.lower() or option.lower() in phrase.lower():
                                select.select_by_visible_text(option)
                                answer = option
                                foundOption = True
                                break
                        if foundOption:
                            break
                    if not foundOption:
                        if experience_select_guarded:
                            print_lg(f"[SAFE-SELECT-GUARD] Refusing random experience dropdown answer for '{label_org}'.")
                            questions_list.add((f'{label_org} [ {options} ]', selected_option, "select", prev_answer))
                            continue
                        #TODO: Use AI to answer the question need to be implemented logic to extract the options for the question
                        print_lg(f'Failed to find an option with text "{answer}" for question labelled "{label_org}", answering randomly!')
                        select.select_by_index(randint(1, len(select.options)-1))
                        answer = select.first_selected_option.text
                        randomly_answered_questions.add((f'{label_org} [ {options} ]',"select"))
            questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label = find_by_class(label, "visually-hidden", 2.0)
            except: pass
            label_org = label.text if label else "Unknown"
            answer = 'Yes'
            label = label_org.lower()

            label_org += ' [ '
            options = radio.find_elements(By.TAG_NAME, 'input')
            options_labels = []
            
            for option in options:
                id = option.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{id}"]', False)
                options_labels.append( f'"{option_label.text if option_label else "Unknown"}"<{option.get_attribute("value")}>' ) # Saving option as "label <value>"
                if option.is_selected(): prev_answer = options_labels[-1]
                label_org += f' {options_labels[-1]},'

            if overwrite_previous_answers or prev_answer is None:
                if 'citizenship' in label or 'employment eligibility' in label: answer = us_citizenship
                elif 'veteran' in label or 'protected' in label: answer = veteran_status
                elif 'disability' in label or 'handicapped' in label: 
                    answer = disability_status
                else: answer = answer_common_questions(label,answer)
                foundOption = try_xp(radio, f".//label[normalize-space()='{answer}']", False)
                if foundOption: 
                    actions.move_to_element(foundOption).click().perform()
                else:    
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    ele = options[0]
                    answer = options_labels[0]
                    for phrase in possible_answer_phrases:
                        for i, option_label in enumerate(options_labels):
                            if phrase in option_label:
                                foundOption = options[i]
                                ele = foundOption
                                answer = f'Decline ({option_label})' if len(possible_answer_phrases) > 1 else option_label
                                break
                        if foundOption: break
                    # if answer == 'Decline':
                    #     answer = options_labels[0]
                    #     for phrase in ["Prefer not", "not want", "not wish"]:
                    #         foundOption = try_xp(radio, f".//label[normalize-space()='{phrase}']", False)
                    #         if foundOption:
                    #             answer = f'Decline ({phrase})'
                    #             ele = foundOption
                    #             break
                    actions.move_to_element(ele).click().perform()
                    if not foundOption: randomly_answered_questions.add((f'{label_org} ]',"radio"))
            else: answer = prev_answer
            questions_list.add((label_org+" ]", answer, "radio", prev_answer))
            continue
        
        # Check if it's a text question
        text = try_xp(Question, ".//input[@type='text']", False)
        if text: 
            do_actions = False
            label = try_xp(Question, ".//label[@for]", False)
            try: label = label.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label.text if label else "Unknown"
            answer = "" # years_of_experience
            label = label_org.lower()

            prev_answer = text.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                if is_skill_specific_experience_question(label_org):
                    answer = get_or_prompt_skill_experience_answer(label_org, global_memory)
                    print_lg(f'[MEMORY-SKILL-EXPERIENCE] Used cached/user answer for "{label_org}": "{answer}"')
                elif 'experience' in label or 'years' in label: answer = years_of_experience
                elif 'phone' in label or 'mobile' in label: answer = phone_number
                elif 'street' in label: answer = street
                elif 'city' in label or 'location' in label or 'address' in label:
                    answer = current_city if current_city else work_location
                    do_actions = True
                elif 'signature' in label: answer = full_name # 'signature' in label or 'legal name' in label or 'your name' in label or 'full name' in label: answer = full_name     # What if question is 'name of the city or university you attend, name of referral etc?'
                elif 'name' in label:
                    if 'full' in label: answer = full_name
                    elif 'first' in label and 'last' not in label: answer = first_name
                    elif 'middle' in label and 'last' not in label: answer = middle_name
                    elif 'last' in label and 'first' not in label: answer = last_name
                    elif 'employer' in label: answer = recent_employer
                    else: answer = full_name
                elif 'notice' in label:
                    if 'month' in label:
                        answer = notice_period_months
                    elif 'week' in label:
                        answer = notice_period_weeks
                    else: answer = notice_period
                elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label: 
                    if 'current' in label or 'present' in label:
                        if 'month' in label:
                            answer = current_ctc_monthly
                        elif 'lakh' in label:
                            answer = current_ctc_lakhs
                        else:
                            answer = current_ctc
                    else:
                        if 'month' in label:
                            answer = desired_salary_monthly
                        elif 'lakh' in label:
                            answer = desired_salary_lakhs
                        else:
                            answer = desired_salary
                elif 'linkedin' in label: answer = linkedIn
                elif 'website' in label or 'blog' in label or 'portfolio' in label or 'link' in label: answer = website
                elif 'scale of 1-10' in label: answer = confidence_level
                elif 'headline' in label: answer = linkedin_headline
                elif ('hear' in label or 'come across' in label) and 'this' in label and ('job' in label or 'position' in label): answer = "LinkedIn Job Search"
                elif 'state' in label or 'province' in label: answer = state
                elif 'zip' in label or 'postal' in label or 'code' in label: answer = zipcode
                elif 'country' in label: answer = country
                else: answer = answer_common_questions(label,answer)
                ##> ------ Yang Li : MARKYangL - Feature ------
                if answer == "":
                    # Check Memory first
                    mem_ans = get_answer_from_memory(label_org, global_memory)
                    if mem_ans:
                        answer = mem_ans
                        print_lg(f'Memory used for question "{label_org}": "{answer}"')
                    elif use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                answer = prompt_user_for_answer(label_org, global_memory)
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                answer = guard_ai_answer(label_org, answer)
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                answer = prompt_user_for_answer(label_org, global_memory)
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            answer = prompt_user_for_answer(label_org, global_memory)
                    else:
                        answer = prompt_user_for_answer(label_org, global_memory)
                ##<
                text.clear()
                text.send_keys(answer)
                if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((label, text.get_attribute("value"), "text", prev_answer))
            continue

        # Check if it's a textarea question
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            label = try_xp(Question, ".//label[@for]", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = ""
            prev_answer = text_area.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                if 'summary' in label: answer = linkedin_summary
                elif 'cover' in label: answer = cover_letter
                if answer == "":
                ##> ------ Yang Li : MARKYangL - Feature ------
                    # Check Memory first
                    mem_ans = get_answer_from_memory(label_org, global_memory)
                    if mem_ans:
                        answer = mem_ans
                        print_lg(f'Memory used for question "{label_org}": "{answer}"')
                    elif use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                answer = prompt_user_for_answer(label_org, global_memory)
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                answer = guard_ai_answer(label_org, answer)
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                answer = prompt_user_for_answer(label_org, global_memory)
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            answer = prompt_user_for_answer(label_org, global_memory)
                    else:
                        answer = prompt_user_for_answer(label_org, global_memory)
                ##<
            text_area.clear()
            text_area.send_keys(answer)
            if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((label, text_area.get_attribute("value"), "textarea", prev_answer))
            ##<
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer
            if not prev_answer:
                try:
                    actions.move_to_element(checkbox).click().perform()
                    checked = True
                except Exception as e: 
                    print_lg("Checkbox click failed!", e)
                    pass
            questions_list.add((f'{label} ([X] {answer})', checked, "checkbox", prev_answer))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    return questions_list




def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str) -> tuple[bool, str, int]:
    '''
    Function to open new tab and save external job application links
    '''
    global tabs_count, dailyEasyApplyLimitReached
    if easy_apply_only:
        try:
            if "exceeded the daily application limit" in driver.find_element(By.CLASS_NAME, "artdeco-inline-feedback__message").text: dailyEasyApplyLimitReached = True
        except: pass
        print_lg("Easy apply failed I guess!")
        if pagination_element != None: return True, application_link, tabs_count
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3')]"))).click() # './/button[contains(span, "Apply") and not(span[contains(@class, "disabled")])]'
        wait_span_click(driver, "Continue", 1, True, False)
        windows = driver.window_handles
        tabs_count = len(windows)
        driver.switch_to.window(windows[-1])
        application_link = driver.current_url
        print_lg('Got the external application link "{}"'.format(application_link))
        if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
        driver.switch_to.window(linkedIn_tab)
        return False, application_link, tabs_count
    except Exception as e:
        # print_lg(e)
        print_lg("Failed to apply!")
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        global failed_count
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str, confidence_score: int = 0) -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        portal_type = detect_external_portal(application_link)
        
        row_data = {
            'job_id': job_id, 'job_url': job_link, 'resume_tried': resume,
            'date_listed': date_listed, 'date_tried': datetime.now(),
            'assumed_reason': error, 'stack_trace': str(exception),
            'external_job_url': application_link, 'screenshot_name': screenshot_name,
            'portal_type': portal_type, 'source_platform': 'LinkedIn',
            'confidence_score': confidence_score
        }
        
        normalized_row = normalize_row(row_data, FAILED_EXPORT_SCHEMA)
        
        # Save to SQLite (single source of truth)
        from modules.storage import upsert_failed_application, export_db_to_csv
        upsert_failed_application(normalized_row)
        print_lg(f"[FAILED-JOB-PERSISTED] Failed job saved to SQLite. Job ID: {job_id}")
        
        # Sync SQLite to CSVs atomically
        export_db_to_csv(file_name)
        
        # Convert CSVs to Excel
        from modules.export_to_excel import convert_csvs_to_excel
        convert_csvs_to_excel()

    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        safe_alert("Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")


def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied:  datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development'], confidence_score: int = 0) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        if application_link == "Easy Applied" and str(date_applied).strip().lower() == "pending":
            print_lg(f"[PERSISTENCE-BLOCKED] Refusing to save unconfirmed Easy Apply row for job_id={job_id}, title={title}, company={company}")
            raise ValueError("Easy Apply row cannot be saved without confirmed LinkedIn submission timestamp")

        portal_type = detect_external_portal(application_link)
        
        # Ensure header is synchronized
        ensure_csv_header(file_name, APPLIED_EXPORT_SCHEMA)
        
        row_data = {
            'job_id': job_id, 'title': title, 'company': company,
            'work_location': work_location, 'work_style': work_style,
            'job_description': description, 'experience_required': experience_required,
            'skills_required': skills, 'resume': resume, 'reposted': reposted,
            'date_posted': date_listed, 'application_date': date_applied,
            'current_status': 'Applied', 'last_status_update': date_applied,
            'status_source': 'LinkedIn Automation', 'response_received': 'False',
            'recruiter_name': hr_name, 'recruiter_email': '',
            'recruiter_profile_url': hr_link, 'job_url': job_link,
            'external_job_url': application_link, 'questions_found': str(questions_list),
            'connect_request': connect_request, 'portal_type': portal_type,
            'source_platform': 'LinkedIn', 'confidence_score': confidence_score,
            'runtime_segment': 'production',
            'runtime_batch_id': get_current_runtime_batch_id() or RUNTIME_BATCH_ID or ''
        }
        
        normalized_row = normalize_row(row_data, APPLIED_EXPORT_SCHEMA)
        upsert_application(normalized_row) # Primary Source update
        
        # Atomic append-like write: read all, append, write all
        rows = []
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        
        rows.append(normalized_row)
        safe_write_csv(file_name, APPLIED_EXPORT_SCHEMA, rows)

    except Exception as e:
        print_lg("Failed to update submitted jobs list!", e)
        safe_alert("Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")
        raise



# Function to discard the job application
def discard_job() -> None:
    actions.send_keys(Keys.ESCAPE).perform()
    wait_span_click(driver, 'Discard', 2)






# Function to apply to jobs
def apply_to_jobs(search_terms: list[str]) -> None:
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume
    current_city = current_city.strip()
    max_applications_this_run = globals().get("MAX_APPLICATIONS_PER_RUN", 0) or 0

    if randomize_search_order:  shuffle(search_terms)
    for searchTerm in search_terms:
        if max_applications_this_run and easy_applied_count + external_jobs_count >= max_applications_this_run:
            print_lg(f"Reached MAX_APPLICATIONS_PER_RUN={max_applications_this_run}. Stopping this run.")
            return
        driver.get(f"https://www.linkedin.com/jobs/search/?keywords={searchTerm}")
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" <<<<\n\n')

        apply_filters()

        current_count = 0
        try:
            while current_count < switch_number:
                # Wait until job listings are loaded
                wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))

                pagination_element, current_page = get_page_info()

                # Find all job listings in current page
                buffer(3)
                job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")  

            
                job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")  
                num_jobs = len(job_listings)
                
                for job_index in range(num_jobs):
                    if max_applications_this_run and easy_applied_count + external_jobs_count >= max_applications_this_run:
                        print_lg(f"Reached MAX_APPLICATIONS_PER_RUN={max_applications_this_run}. Stopping this run.")
                        return
                    if keep_screen_awake:
                        try:
                            import ctypes
                            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
                        except Exception:
                            pass
                    if current_count >= switch_number: break

                    # Re-fetch visible cards fresh from DOM to prevent stale element reference crashes
                    try:
                        job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
                    except Exception as e:
                        print_lg(f"[STALE-RECOVERY] Error re-fetching job listings: {e}")
                        break

                    if job_index >= len(job_listings):
                        print_lg(f"[STALE-RECOVERY] Job index {job_index} out of bounds after DOM refresh. Ending page loop.")
                        break

                    job = job_listings[job_index]
                    
                    try:
                        print_lg("\n-@-\n")

                        job_id,title,company,work_location,work_style,skip = get_job_main_details(job, blacklisted_companies, rejected_jobs)
                        
                        if skip: continue
                        # Primary check: SQLite (new architecture standard)
                        if application_exists(job_id, company):
                            print_lg(f'Already applied to "{title} | {company}" job (Detected via SQLite). Job ID: {job_id}!')
                            continue

                        # Secondary check: local applied_jobs set (runtime cache)
                        if job_id in applied_jobs:
                            print_lg(f'Already applied to "{title} | {company}" job (Detected via cache). Job ID: {job_id}!')
                            continue

                        job_link = "https://www.linkedin.com/jobs/view/"+job_id
                        application_link = "Easy Applied"
                        date_applied = "Pending"
                        hr_link = "Unknown"
                        hr_name = "Unknown"
                        connect_request = "In Development" # Still in development
                        date_listed = "Unknown"
                        skills = "Needs an AI" # Still in development
                        resume = "Pending"
                        reposted = False
                        questions_list = None
                        screenshot_name = "Not Available"

                        try:
                            rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs,job_id,company,blacklisted_companies)
                        except ValueError as e:
                            print_lg(e, 'Skipping this job!\n')
                            failed_job(job_id, job_link, resume, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name)
                            skip_count += 1
                            continue
                        except Exception as e:
                            print_lg("Failed to scroll to About Company!")
                            # print_lg(e)

                        # Hiring Manager info
                        try:
                            hr_info_card = WebDriverWait(driver,2).until(EC.presence_of_element_located((By.CLASS_NAME, "hirer-card__hirer-information")))
                            hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                            hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                        except Exception as e:
                            print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')
                            # print_lg(e)

                        # Calculation of date posted
                        try:
                            time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                            print("Time Posted: " + time_posted_text)
                            if time_posted_text.__contains__("Reposted"):
                                reposted = True
                                time_posted_text = time_posted_text.replace("Reposted", "")
                            date_listed = calculate_date_posted(time_posted_text.strip())
                        except Exception as e:
                            print_lg("Failed to calculate the date posted!",e)

                        description, experience_required, skip, reason, message, confidence_score = get_job_description(title)
                        if skip:
                            print_lg(message)
                            failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
                            rejected_jobs.add(job_id)
                            skip_count += 1
                            continue

                        if use_AI and description != "Unknown":
                            try:
                                if ai_provider.lower() == "openai":
                                    skills = ai_extract_skills(aiClient, description)
                                elif ai_provider.lower() == "deepseek":
                                    skills = deepseek_extract_skills(aiClient, description)
                                elif ai_provider.lower() == "gemini":
                                    skills = gemini_extract_skills(aiClient, description)
                                else:
                                    skills = "In Development"
                                print_lg(f"Extracted skills using {ai_provider} AI")
                            except Exception as e:
                                print_lg("Failed to extract skills:", e)
                                skills = "Error extracting skills"

                        uploaded = False
                        # Case 1: Easy Apply Button
                        is_easy_apply = False
                        easy_apply_xpaths = [
                            ".//button[contains(@class,'jobs-apply-button') and contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'easy apply')]",
                            ".//button[contains(@class,'jobs-apply-button') and .//span[contains(normalize-space(.), 'Easy Apply')]]",
                            ".//button[contains(@aria-label, 'Easy Apply')]",
                        ]
                        for easy_apply_xpath in easy_apply_xpaths:
                            is_easy_apply = try_xp(driver, easy_apply_xpath)
                            if is_easy_apply:
                                print_lg(f"[APPLY-DEBUG] Easy Apply button detected with selector: {easy_apply_xpath}")
                                break
                        if not is_easy_apply:
                            try:
                                apply_link_el = driver.find_element(By.XPATH, ".//a[contains(@href, 'openSDUIApplyFlow=true')]")
                                if apply_link_el:
                                    apply_link_el.click()
                                    is_easy_apply = True
                                    print_lg("Detected Easy Apply via URL pattern (openSDUIApplyFlow)")
                            except:
                                pass
                        if not is_easy_apply:
                            try:
                                apply_btn = driver.find_element(By.XPATH, ".//button[contains(@class,'jobs-apply-button')]")
                                if apply_btn:
                                    tabs_before = len(driver.window_handles)
                                    apply_btn.click()
                                    buffer(click_gap)
                                    tabs_after = len(driver.window_handles)
                                    if tabs_after > tabs_before:
                                        driver.switch_to.window(driver.window_handles[-1])
                                        if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
                                        driver.switch_to.window(linkedIn_tab)
                                        print_lg("External apply detected via new tab, skipping")
                                    else:
                                        try:
                                            find_easy_apply_modal(3)
                                            is_easy_apply = True
                                            print_lg("Detected Easy Apply via modal appearance after click")
                                        except:
                                            try: actions.send_keys(Keys.ESCAPE).perform()
                                            except: pass
                            except:
                                pass
                        if is_easy_apply:
                            try: 
                                modal = None
                                questions_list = set()
                                errored = ""
                                try:
                                    modal = find_easy_apply_modal(5)
                                    if find_action_button(modal, "Next", 1):
                                        click_modal_action(modal, "Next", 3)
                                    resume = "Previous resume"
                                    next_button = True
                                    next_counter = 0
                                    while next_button:
                                        next_counter += 1
                                        if next_counter >= 15: 
                                            if pause_at_failed_question:
                                                screenshot(driver, job_id, "Needed manual intervention for failed question")
                                                safe_alert("Couldn't answer one or more questions.\nPlease click \"Continue\" once done.\nDO NOT CLICK Back, Next or Review button in LinkedIn.\n\n\n\n\nYou can turn off \"Pause at failed question\" setting in config.py", "Help Needed", "Continue")
                                                next_counter = 1
                                                continue
                                            if questions_list: print_lg("Stuck for one or some of the following questions...", questions_list)
                                            screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                            errored = "stuck"
                                            raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")
                                        questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                        if useNewResume and not uploaded: uploaded, resume = upload_resume(modal, default_resume_path)
                                        debug_modal_state(modal, f"step-{next_counter}")
                                        next_button = find_action_button(modal, "Review", 1) or find_action_button(modal, "Next", 1)
                                        if find_action_button(modal, "Submit application", 0.5):
                                            print_lg("[APPLY-DEBUG] Submit button visible; leaving step loop.")
                                            break
                                        if not next_button:
                                            raise NoSuchElementException("Could not find enabled Next or Review button in Easy Apply modal")
                                        try:
                                            scroll_to_view(driver, next_button)
                                            next_button.click()
                                        except ElementClickInterceptedException: break
                                        except Exception:
                                            driver.execute_script("arguments[0].click();", next_button)
                                        buffer(click_gap)

                                except NoSuchElementException: errored = "nose"
                                finally:
                                    if questions_list and errored != "stuck": 
                                        print_lg("Answered the following questions...", questions_list)
                                        print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                    if modal is None:
                                        raise NoSuchElementException("Easy Apply modal was not available")
                                    if find_action_button(modal, "Review", 1):
                                        click_modal_action(modal, "Review", 3)
                                    cur_pause_before_submit = pause_before_submit
                                    if errored != "stuck" and cur_pause_before_submit:
                                        decision = safe_confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', "Confirm your information",["Disable Pause", "Discard Application", "Submit Application"])
                                        if decision == "Discard Application": raise Exception("Job application discarded by user!")
                                        pause_before_submit = False if "Disable Pause" == decision else True
                                    follow_company(modal)
                                    if click_modal_action(modal, "Submit application", 5): 
                                        completion_modal = modal
                                        try:
                                            completion_modal = find_easy_apply_modal(2)
                                        except Exception:
                                            pass
                                        confirmed, confirmation_reason = verify_easy_apply_submission(completion_modal, job_id, title, company)
                                        if not confirmed:
                                            raise Exception(f"Submit clicked but LinkedIn confirmation was not detected ({confirmation_reason})")
                                        date_applied = datetime.now()
                                        print_lg(f"[APPLY-SUCCESS] Confirmed application for job_id={job_id}, title={title}, company={company}, at={date_applied}, confirmation={confirmation_reason}")
                                        if not click_modal_action(completion_modal, "Done", 5): actions.send_keys(Keys.ESCAPE).perform()
                                    elif errored != "stuck" and cur_pause_before_submit and "Yes" in safe_confirm("You submitted the application, didn't you 😒?", "Failed to find Submit Application!", ["Yes", "No"]):
                                        print_lg(f"[APPLY-UNVERIFIED] Manual confirmation is not enough to mark success for job_id={job_id}, title={title}, company={company}")
                                        raise Exception("Manual submit confirmation without LinkedIn success confirmation")
                                    else:
                                        print_lg("Since, Submit Application failed, discarding the job application...")
                                        raise Exception("Failed to click Submit application")

                            except UserCancelledException as e:
                                print_lg(f"Skipping job application intentionally: {e}")
                                failed_job(job_id, job_link, resume, date_listed, "Skipped due to unanswered question", e, application_link, screenshot_name, confidence_score)
                                skip_count += 1
                                discard_job()
                                continue
                            except Exception as e:
                                print_lg("Failed to Easy apply!")
                                print_lg(f"[APPLY-FAILURE] job_id={job_id}, title={title}, company={company}, reason={type(e).__name__}: {e}")
                                critical_error_log("Somewhere in Easy Apply process",e)
                                failed_job(job_id, job_link, resume, date_listed, "Problem in Easy Applying", e, application_link, screenshot_name, confidence_score)
                                failed_count += 1
                                discard_job()
                                continue
                        else:
                            skip, application_link, tabs_count = external_apply(pagination_element, job_id, job_link, resume, date_listed, application_link, screenshot_name)
                            if dailyEasyApplyLimitReached:
                                print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                                return
                            if skip: continue

                        submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required, skills, hr_name, hr_link, resume, reposted, date_listed, date_applied, job_link, application_link, questions_list, connect_request, confidence_score)
                        if uploaded:   useNewResume = False

                        print_lg(f'[APPLICATION-SAVED] Successfully saved "{title} | {company}" job. Job ID: {job_id}, application_link={application_link}')
                        current_count += 1
                        if application_link == "Easy Applied": easy_applied_count += 1
                        else:   external_jobs_count += 1
                        applied_jobs.add(job_id)
                        if max_applications_this_run and easy_applied_count + external_jobs_count >= max_applications_this_run:
                            print_lg(f"Reached MAX_APPLICATIONS_PER_RUN={max_applications_this_run}. Stopping this run.")
                            return

                    except (NoSuchWindowException, WebDriverException) as web_exc:
                        print_lg("Browser window was closed or Selenium session invalid. Terminating page loop.", web_exc)
                        raise web_exc
                    except Exception as e:
                        print_lg(f"[STALE-RECOVERY] Recovered from unexpected job processing error: {type(e).__name__}: {e}")
                        try:
                            actions.send_keys(Keys.ESCAPE).perform()
                        except:
                            pass
                        continue



                # Switching to next page
                if pagination_element == None:
                    print_lg("Couldn't find pagination element, probably at the end page of results!")
                    break
                try:
                    pagination_element.find_element(By.XPATH, f"//button[@aria-label='Page {current_page+1}']").click()
                    print_lg(f"\n>-> Now on Page {current_page+1} \n")
                except NoSuchElementException:
                    print_lg(f"\n>-> Didn't find Page {current_page+1}. Probably at the end page of results!\n")
                    break

        except (NoSuchWindowException, WebDriverException) as e:
            print_lg("Browser window closed or session is invalid. Ending application process.", e)
            raise e # Re-raise to be caught by main
        except Exception as e:
            print_lg("Failed to find Job listings!")
            critical_error_log("In Applier", e)
            try:
                print_lg(driver.page_source, pretty=True)
            except Exception as page_source_error:
                print_lg(f"Failed to get page source, browser might have crashed. {page_source_error}")
            # print_lg(e)

        
def run(total_runs: int) -> int:
    if dailyEasyApplyLimitReached:
        return total_runs
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for jobs posted within '{date_posted}' and sorting them by '{sort_by}'")
    apply_to_jobs(search_terms)
    print_lg(f"[POST-APPLY-TRANSITION] Apply cycle complete for runtime_batch_id={get_current_runtime_batch_id()}. Preparing next phase.")
    print_lg("########################################################################################################################\n")
    if is_validation_context():
        print_lg("Validation mode enabled; skipping post-run sleep.")
    elif not dailyEasyApplyLimitReached:
        print_lg("[COOLDOWN-REDUCED] Inter-platform/post-apply cooldown capped at 90 seconds.")
        sleep(45)
        print_lg("[COOLDOWN-REDUCED] Cold-email transition starts in about 45 seconds.")
        sleep(45)
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def is_validation_context() -> bool:
    return is_automation_context()

def main() -> None:
    safe_alert(
        "Naukri_Guru — AI-Powered Job Automation Platform\n\n"
        "Developer: Manvendra Singh\n"
        "IIIT Raichur | B.Tech CSE (2026)\n\n"
        "Make sure Chrome is closed before proceeding.",
        "Naukri_Guru", "Start"
    )
    total_runs = 1
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient, options, driver, actions, wait, RUNTIME_BATCH_ID
        alert_title = "Error Occurred. Closing Browser!"
        global date_posted
        date_posted = normalize_date_posted_value(date_posted, "runAiBot.startup")
        validate_config()
        RUNTIME_BATCH_ID = set_current_runtime_batch_id()
        print_lg(f"[RUNTIME-BATCH] Started runtime_batch_id={RUNTIME_BATCH_ID}")

        try:
            from modules.storage import init_db, run_db_maintenance
            init_db()
            run_db_maintenance()
        except Exception as db_init_err:
            print_lg(f"Database initialization/maintenance failed: {db_init_err}")

        try:
            from modules.email.updater import sync_gmail_lifecycle_statuses
            sync_gmail_lifecycle_statuses()
        except Exception as email_sync_error:
            print_lg(f"Gmail lifecycle sync failed safely before automation: {type(email_sync_error).__name__}: {email_sync_error}")
        
        if not os.path.exists(default_resume_path):
            safe_alert(text='Your default resume "{}" is missing! Please update it\'s folder path "default_resume_path" in config.py\n\nOR\n\nAdd a resume with exact name and path (check for spelling mistakes including cases).\n\n\nFor now the bot will continue using your previous upload from LinkedIn!'.format(default_resume_path), title="Missing Resume", button="OK")
            useNewResume = False

        options, driver, actions, wait = initialize_chrome_session()
        
        # Login to LinkedIn
        tabs_count = len(driver.window_handles)
        
        # Navigate to feed first (works if already logged in via profile cookies)
        print_lg("Navigating to LinkedIn...")
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(3)  # Give LinkedIn time to load/redirect
        assert_browser_healthy(driver)
        detect_captcha(driver)
        
        if not is_linkedin_logged_out(driver) and is_logged_in_LN():
            print_lg("Already logged in via saved session! Skipping login.")
        else:
            print_lg("Not logged in. Proceeding to login page...")
            login_LN()
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         driver.get("https://chat.openai.com/")
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if use_AI:
            if ai_provider == "openai":
                aiClient = ai_create_openai_client()
            ##> ------ Yang Li : MARKYangL - Feature ------
            # Create DeepSeek client
            elif ai_provider == "deepseek":
                aiClient = deepseek_create_client()
            elif ai_provider == "gemini":
                aiClient = gemini_create_client()
            ##<

            try:
                about_company_for_ai = " ".join([word for word in (first_name+" "+last_name).split() if len(word) > 3])
                print_lg(f"Extracted about company info for AI: '{about_company_for_ai}'")
            except Exception as e:
                print_lg("Failed to extract about company info!", e)
        
        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if dailyEasyApplyLimitReached:
                break
        

    except (NoSuchWindowException, WebDriverException) as e:
        print_lg("Browser window closed or session is invalid. Exiting.", e)
    except Exception as e:
        critical_error_log("In Applier Main", e)
        safe_alert(e,alert_title)
    finally:
        summary = "Total runs: {}\nJobs Easy Applied: {}\nExternal job links collected: {}\nTotal applied or collected: {}\nFailed jobs: {}\nIrrelevant jobs skipped: {}\n".format(total_runs,easy_applied_count,external_jobs_count,easy_applied_count + external_jobs_count,failed_count,skip_count)
        print_lg(summary)
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        quotes = choice([
            "Success is not final, failure is not fatal. It is the courage to continue that counts. - Winston Churchill",
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Opportunities don't happen, you create them. - Chris Grosser",
            "The road to success and the road to failure are almost exactly the same. The difference is perseverance. - Colin R. Davis",
            "Obstacles are those frightful things you see when you take your eyes off your goal. - Henry Ford",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson",
            "Every job is a self-portrait of the person who does it. Autograph your work with excellence. - Jessica Guidobono",
            ])
        timeSaved = (easy_applied_count * 80) + (external_jobs_count * 20) + (skip_count * 10)
        timeSavedMsg = ""
        if timeSaved > 0:
            timeSaved += 60
            timeSavedMsg = f"In this run, you saved approx {round(timeSaved/60)} mins ({timeSaved} secs)."
        msg = f"{quotes}\n\n{timeSavedMsg}\n\nSummary:\n{summary}\n\nNaukri_Guru — AI-Powered Job Automation\nDeveloper: Manvendra Singh\nhttps://www.linkedin.com/in/manvendra-singh-837874290"
        safe_alert(msg, "Naukri_Guru — Session Complete")
        print_lg(msg)
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            safe_alert(msg, "Naukri_Guru — Info")
            print_lg("\n"+msg)
        if use_AI and aiClient:
            try:
                if ai_provider.lower() == "openai":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "deepseek":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "gemini":
                    pass # Gemini client does not need to be closed
                print_lg(f"Closed {ai_provider} AI client.")
            except Exception as e:
                print_lg("Failed to close AI client:", e)
        try:
            from modules.storage import export_db_to_csv
            export_db_to_csv(file_name)
            from modules.export_to_excel import convert_csvs_to_excel
            convert_csvs_to_excel()
        except Exception as e:
            print_lg("Failed to export to excel", e)

        # ── Cold Email Pipeline ──
        try:
            from config.settings import COLD_EMAIL_ENABLED
            if COLD_EMAIL_ENABLED:
                print_lg("[COLD-EMAIL-PRE-QUIT] Starting recruiter outreach before browser shutdown...")
                from modules.cold_email import run_cold_email_pipeline
                # Check browser health before calling the cold email pipeline
                healthy_driver = driver if assert_browser_healthy(driver) else None
                if healthy_driver is None:
                    print_lg("[DRIVER-HEALTH-CHECK] Cold email enrichment skipped: Browser session is dead or window closed. Proceeding with outreach only.")
                print_lg(f"[POST-APPLY-TRANSITION] Starting queue-based cold email pipeline. runtime_batch_id metadata={RUNTIME_BATCH_ID}.")
                cold_email_result = run_cold_email_pipeline(healthy_driver, runtime_batch_id=RUNTIME_BATCH_ID)
                print_lg(f"Cold email pipeline completed: {cold_email_result}")
            else:
                print_lg("Cold email pipeline skipped (COLD_EMAIL_ENABLED=False)")
        except Exception as cold_email_error:
            print_lg(f"Cold email pipeline failed safely: {type(cold_email_error).__name__}: {cold_email_error}")

        try:
            if driver:
                print_lg("Closing the browser...")
                driver.quit()
        except WebDriverException as e:
            print_lg("Browser already closed.", e)
        except Exception as e: 
            critical_error_log("When quitting...", e)
            
        try:
            from modules.storage import export_db_to_csv
            export_db_to_csv(file_name)
            from modules.export_to_excel import convert_csvs_to_excel
            convert_csvs_to_excel()
        except Exception as e:
            print_lg("Failed second export after cold emails", e)

if __name__ == "__main__":
    main()
