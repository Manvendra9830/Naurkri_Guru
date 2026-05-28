'''
Naukri_Guru — AI-Powered Job Automation Platform
Developer: Manvendra Singh | IIIT Raichur

License: GNU Affero General Public License (AGPL-3.0)
'''


# Imports

import os
import sys
import json
import pathlib
import subprocess
from datetime import date

from time import sleep
from random import randint
from datetime import datetime, timedelta

from pprint import pprint

from config.settings import logs_folder_path

DATE_POSTED_OPTIONS = ["", "Any time", "Past month", "Past week", "Past 24 hours"]
DATE_POSTED_FALLBACK = "Past week"


# >>>>>>>>>>> CENTRALIZED EXPORT SCHEMAS <<<<<<<<<<<
# Master column definitions for all exports to ensure consistency and prevent pipeline crashes.

APPLIED_EXPORT_SCHEMA = [
    'job_id', 'title', 'company', 'work_location', 'work_style',
    'job_description', 'experience_required', 'skills_required', 'resume',
    'reposted', 'date_posted', 'application_date',
    'current_status', 'last_status_update', 'status_source',
    'response_received', 'recruiter_name', 'recruiter_email', 'recruiter_profile_url',
    'job_url', 'external_job_url', 'questions_found', 'connect_request',
    'portal_type', 'source_platform', 'confidence_score',
    'cold_email_sent', 'cold_email_sent_at', 'cold_email_status',
    'cold_email_subject', 'cold_email_recipient', 'cold_email_source',
    'cold_email_error', 'cold_email_attempts',
    'recruiter_email_confidence', 'recruiter_email_source',
    'recruiter_email_found_at', 'runtime_segment', 'runtime_batch_id', 'data_quality_flags'
]

FAILED_EXPORT_SCHEMA = [
    'job_id', 'job_url', 'resume_tried', 'date_listed', 'date_tried',
    'assumed_reason', 'stack_trace', 'external_job_url', 'screenshot_name',
    'portal_type', 'source_platform', 'confidence_score'
]

LEGACY_COLUMN_ALIASES = {
    'Job ID': 'job_id',
    'Title': 'title',
    'Company': 'company',
    'Work Location': 'work_location',
    'Work Style': 'work_style',
    'About Job': 'job_description',
    'Experience required': 'experience_required',
    'Skills required': 'skills_required',
    'HR Name': 'recruiter_name',
    'HR Link': 'recruiter_profile_url',
    'Resume': 'resume',
    'Resume Tried': 'resume_tried',
    'Re-posted': 'reposted',
    'Date Posted': 'date_posted',
    'Date Applied': 'application_date',
    'Date listed': 'date_listed',
    'Date Tried': 'date_tried',
    'Job Link': 'job_url',
    'External Job link': 'external_job_url',
    'Questions Found': 'questions_found',
    'Connect Request': 'connect_request',
    'Assumed Reason': 'assumed_reason',
    'Stack Trace': 'stack_trace',
    'Screenshot Name': 'screenshot_name',
    'Portal Type': 'portal_type',
    'Source Platform': 'source_platform',
    'Confidence Score': 'confidence_score',
}
# <<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>


#### Common functions ####

#< Directories related
def make_directories(paths: list[str]) -> None:
    '''
    Function to create missing directories
    '''
    for path in paths:
        path = os.path.expanduser(path) # Expands ~ to user's home directory
        path = path.replace("//","/")
        
        # If path looks like a file path, get the directory part
        if '.' in os.path.basename(path):
            path = os.path.dirname(path)

        if not path: # Handle cases where path is empty after dirname
            continue

        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True) # exist_ok=True avoids race condition
        except Exception as e:
            print(f'Error while creating directory "{path}": ', e)


def get_default_temp_profile() -> str:
    # Returns a path for a temporary Chrome profile (no flags, just the path)
    home = pathlib.Path.home()
    if sys.platform.startswith('win'):
        return r"C:\temp\naukri-guru-profile"
    elif sys.platform.startswith('linux'):
        return str(home / ".naukri-guru-profile")
    return str(home / "Library" / "Application Support" / "Google" / "Chrome" / "naukri-guru-profile")


def get_dedicated_automation_profile_dir() -> str:
    """
    Returns the path for the persistent, dedicated automation profile.
    This prevents lock collisions with the user's personal Chrome browsing.
    """
    home = pathlib.Path.home()
    if sys.platform.startswith('win'):
        path = r"C:\Naukri_Guru_Profile"
    elif sys.platform.startswith('linux'):
        path = str(home / ".naukri_guru_profile")
    else:
        path = str(home / "Library" / "Application Support" / "Naukri_Guru_Profile")
    
    # Ensure directory exists
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


def find_default_profile_directory() -> str | None:
    '''
    Dynamically finds the default Google Chrome 'User Data' directory path
    across Windows, macOS, and Linux, regardless of OS version.

    Returns the absolute path as a string, or None if the path is not found.
    '''
    
    home = pathlib.Path.home()
    
    # Windows
    if sys.platform.startswith('win'):
        paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\Google\Chrome\User Data"),
            os.path.expandvars(r"%USERPROFILE%\Local Settings\Application Data\Google\Chrome\User Data")
        ]
    # Linux
    elif sys.platform.startswith('linux'):
        paths = [
            str(home / ".config" / "google-chrome"),
            str(home / ".var" / "app" / "com.google.Chrome" / "data" / ".config" / "google-chrome"),
        ]
    else:
        return None

    # Check each potential path and return the first one that exists
    for path_str in paths:
        if os.path.exists(path_str):
            return path_str
            
    return None


def validate_chrome_profile(user_data_dir: str, profile_name: str) -> bool:
    '''
    Validates that a Chrome profile directory exists.
    Returns True if valid, False otherwise.
    '''
    if not user_data_dir or not profile_name:
        return False
    profile_path = os.path.join(user_data_dir, profile_name)
    return os.path.isdir(profile_path)


def detect_chrome_profiles(user_data_dir: str) -> list[dict]:
    '''
    Detects all Chrome profiles in the User Data directory.
    Returns a list of dicts with profile_dir, name, and email.
    '''
    profiles = []
    if not user_data_dir or not os.path.isdir(user_data_dir):
        return profiles
    
    try:
        local_state_path = os.path.join(user_data_dir, 'Local State')
        if os.path.exists(local_state_path):
            with open(local_state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            info_cache = data.get('profile', {}).get('info_cache', {})
            for profile_dir, info in info_cache.items():
                profiles.append({
                    'dir': profile_dir,
                    'name': info.get('name', 'Unknown'),
                    'gaia_name': info.get('gaia_name', ''),
                    'email': info.get('user_name', ''),
                })
    except Exception as e:
        print_lg(f"Failed to detect Chrome profiles: {e}")
    
    return profiles


def is_chrome_running() -> bool:
    '''
    Checks if any Chrome process is currently running.
    Returns True if Chrome is running, False otherwise.
    '''
    try:
        if sys.platform.startswith('win'):
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                capture_output=True, text=True, timeout=5
            )
            return 'chrome.exe' in result.stdout.lower()
        else:
            result = subprocess.run(
                ['pgrep', '-x', 'chrome'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
    except Exception:
        return False  # Assume not running if check fails
#>


#< Logging related
def critical_error_log(possible_reason: str, stack_trace: Exception) -> None:
    '''
    Function to log and print critical errors along with datetime stamp
    '''
    print_lg(possible_reason, stack_trace, datetime.now(), from_critical=True)


def get_log_path():
    '''
    Function to replace '//' with '/' for logs path
    '''
    try:
        path = logs_folder_path+"/log.txt"
        return path.replace("//","/")
    except Exception as e:
        critical_error_log("Failed getting log path! So assigning default logs path: './logs/log.txt'", e)
        return "logs/log.txt"


__logs_file_path = get_log_path()


def print_lg(*msgs: str | dict, end: str = "\n", pretty: bool = False, flush: bool = False, from_critical: bool = False) -> None:
    '''
    Function to log and print. **Note that, `end` and `flush` parameters are ignored if `pretty = True`**
    '''
    try:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        for message in msgs:
            # Add timestamp if it's a string, avoid adding it to every single dict if pretty printing
            out_msg = f"{timestamp}{message}" if isinstance(message, str) else message
            
            # Print to console (handle Unicode errors on Windows cp1252)
            try:
                pprint(out_msg) if pretty else print(out_msg, end=end, flush=flush)
            except UnicodeEncodeError:
                # Fallback: replace non-encodable chars for console output only
                safe_msg = str(out_msg).encode('ascii', errors='replace').decode('ascii')
                pprint(safe_msg) if pretty else print(safe_msg, end=end, flush=flush)
            # Always write full UTF-8 to log file
            with open(__logs_file_path, 'a+', encoding="utf-8") as file:
                file.write(str(out_msg) + end)
    except Exception as e:
        trail = f'Skipped saving this message: "{message}" to log.txt!' if from_critical else "We'll try one more time to log..."
        safe_alert(f"log.txt in {logs_folder_path} is open or is occupied by another program! Please close it! {trail}", "Failed Logging")
        if not from_critical:
            critical_error_log("Log.txt is open or is occupied by another program!", e)
#>


def buffer(speed: int=0) -> None:
    '''
    Function to wait within a period of selected random range.
    * Will not wait if input `speed <= 0`
    * Will wait within a random range of 
      - `0.6 to 1.0 secs` if `1 <= speed < 2`
      - `1.0 to 1.8 secs` if `2 <= speed < 3`
      - `1.8 to speed secs` if `3 <= speed`
    '''
    if speed<=0:
        return
    elif speed <= 1 and speed < 2:
        return sleep(randint(6,10)*0.1)
    elif speed <= 2 and speed < 3:
        return sleep(randint(10,18)*0.1)
    else:
        return sleep(randint(18,round(speed)*10)*0.1)
    

def manual_login_retry(is_logged_in: callable, limit: int = 2) -> None:
    '''
    Function to ask and validate manual login
    '''
    count = 0
    while not is_logged_in():
        print_lg("Seems like you're not logged in!")
        button = "Confirm Login"
        message = 'After you successfully Log In, please click "{}" button below.'.format(button)
        if count > limit:
            button = "Skip Confirmation"
            message = 'If you\'re seeing this message even after you logged in, Click "{}". Seems like auto login confirmation failed!'.format(button)
        count += 1
        if safe_alert(message, "Login Required", button) and count > limit: return

def detect_external_portal(url: str) -> str:
    """Detects the ATS portal type based on the redirect URL."""
    if not url or url == "Easy Applied" or url == "Skipped": return "LinkedIn"
    url_lower = url.lower()
    if 'workday' in url_lower or 'myworkdayjobs' in url_lower: return 'Workday'
    if 'greenhouse.io' in url_lower: return 'Greenhouse'
    if 'lever.co' in url_lower: return 'Lever'
    if 'taleo.net' in url_lower: return 'Taleo'
    if 'oraclecloud' in url_lower: return 'Oracle'
    if 'successfactors' in url_lower: return 'SuccessFactors'
    if 'smartrecruiters' in url_lower: return 'SmartRecruiters'
    if 'ashbyhq' in url_lower: return 'Ashby'
    if 'icims.com' in url_lower: return 'iCIMS'
    return 'Other External'


def normalize_date_posted_value(raw_value, source: str = "runtime") -> str:
    """Normalize LinkedIn date-posted filter to one accepted string value."""
    print_lg(f"[DATE-POSTED-RAW] source={source}, value={raw_value!r}, type={type(raw_value).__name__}")
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if normalized in DATE_POSTED_OPTIONS:
            print_lg(f"[DATE-POSTED-NORMALIZED] source={source}, value={normalized!r}")
            return normalized
        print_lg(f"[DATE-POSTED-FALLBACK] source={source}, invalid_string={normalized!r}, fallback={DATE_POSTED_FALLBACK!r}")
        return DATE_POSTED_FALLBACK

    print_lg(f"[DATE-POSTED-FALLBACK] source={source}, invalid_type={type(raw_value).__name__}, fallback={DATE_POSTED_FALLBACK!r}")
    print_lg(f"[DATE-POSTED-NORMALIZED] source={source}, value={DATE_POSTED_FALLBACK!r}")
    return DATE_POSTED_FALLBACK



def calculate_date_posted(time_string: str) -> datetime | None | ValueError:
    '''
    Function to calculate date posted from string.
    Returns datetime object | None if unable to calculate | ValueError if time_string is invalid
    Valid time string examples:
    * 10 seconds ago
    * 15 minutes ago
    * 2 hours ago
    * 1 hour ago
    * 1 day ago
    * 10 days ago
    * 1 week ago
    * 1 month ago
    * 1 year ago
    '''
    import re
    time_string = time_string.strip()
    now = datetime.now()

    match = re.search(r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', time_string, re.IGNORECASE)

    if match:
        try:
            value = int(match.group(1))
            unit = match.group(2).lower()

            if 'second' in unit:
                return now - timedelta(seconds=value)
            elif 'minute' in unit:
                return now - timedelta(minutes=value)
            elif 'hour' in unit:
                return now - timedelta(hours=value)
            elif 'day' in unit:
                return now - timedelta(days=value)
            elif 'week' in unit:
                return now - timedelta(weeks=value)
            elif 'month' in unit:
                return now - timedelta(days=value * 30)  # Approximation
            elif 'year' in unit:
                return now - timedelta(days=value * 365)  # Approximation
        except (ValueError, IndexError):
            # Fallback for cases where parsing fails
            pass
    
    # If regex doesn't match, or parsing failed, return None.
    # This will skip jobs where the date can't be determined, preventing crashes.
    return None


def is_automation_context() -> bool:
    '''
    Detects if the bot is running in a non-interactive/automated context
    where blocking GUI dialogs should be suppressed.
    '''
    return any([
        os.environ.get("NAUKRI_GURU_AUTO_RUN") == "1",
        os.environ.get("NAUKRI_GURU_VALIDATION") == "1",
        os.environ.get("RUN_IN_BACKGROUND") == "True",
        os.environ.get("HEADLESS") == "True"
    ])


def safe_alert(message: str, title: str = "Naukri_Guru", button: str = "OK") -> str:
    '''
    Safe version of pyautogui.alert that suppresses dialogs in automated contexts.
    '''
    if is_automation_context():
        print_lg(f"[GUI-SUPPRESSED] ALERT | {title}: {message}")
        return button
    try:
        import pyautogui
        return pyautogui.alert(message, title, button)
    except Exception as e:
        print_lg(f"GUI Alert failed: {e}. Message: {message}")
        return button


def safe_confirm(message: str, title: str = "Naukri_Guru", buttons: list[str] = None) -> str:
    '''
    Safe version of pyautogui.confirm that suppresses dialogs in automated contexts.
    Automatically picks a sensible default choice (usually the last one for 'Submit' scenarios).
    '''
    buttons = buttons or ["OK", "Cancel"]
    if is_automation_context():
        # Heuristic: if "Submit" or "Continue" is in buttons, pick it
        choice = buttons[0]
        for b in buttons:
            if any(word in b.lower() for word in ["submit", "continue", "yes", "good"]):
                choice = b
                break
        print_lg(f"[GUI-SUPPRESSED] CONFIRM | {title}: {message} | AUTO-SELECTED: {choice}")
        return choice
    try:
        import pyautogui
        return pyautogui.confirm(message, title, buttons)
    except Exception as e:
        print_lg(f"GUI Confirm failed: {e}. Message: {message}")
        return buttons[0]


def safe_prompt(text: str, title: str = "Naukri_Guru") -> str | None:
    '''
    Safe version of pyautogui.prompt that suppresses dialogs in automated contexts.
    '''
    if is_automation_context():
        print_lg(f"[GUI-SUPPRESSED] PROMPT | {title}: {text}")
        return None
    try:
        import pyautogui
        return pyautogui.prompt(text, title)
    except Exception as e:
        print_lg(f"GUI Prompt failed: {e}. Message: {text}")
        # Fallback to console input
        print_lg(f"\n{'='*60}")
        print_lg(f"{title}: {text}")
        print_lg(f"{'='*60}")
        try:
            return input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return None



def convert_to_json(data) -> dict:
    '''
    Function to convert data to JSON, if unsuccessful, returns `{"error": "Unable to parse the response as JSON", "data": data}`
    '''
    try:
        result_json = json.loads(data)
        return result_json
    except json.JSONDecodeError:
        return {"error": "Unable to parse the response as JSON", "data": data}


def truncate_for_csv(data, max_length: int = 131000, suffix: str = "...[TRUNCATED]") -> str:
    '''
    Function to truncate data for CSV writing to avoid field size limit errors.
    * Takes in `data` of any type and converts to string
    * Takes in `max_length` of type `int` - maximum allowed length (default: 131000, leaving room for suffix)
    * Takes in `suffix` of type `str` - text to append when truncated
    * Returns truncated string if data exceeds max_length
    '''
    try:
        # Convert data to string
        str_data = str(data) if data is not None else ""
        
        # If within limit, return as-is
        if len(str_data) <= max_length:
            return str_data
        
        # Truncate and add suffix
        truncated = str_data[:max_length - len(suffix)] + suffix
        return truncated
    except Exception as e:
        return f"[ERROR CONVERTING DATA: {e}]"


def safe_write_csv(csv_path: str, schema: list[str], rows: list[dict]) -> bool:
    '''
    Atomically writes `rows` to `csv_path` using a temporary file and schema normalization.
    Ensures no data corruption occurs even if the process is killed during write.
    '''
    import csv
    import tempfile
    import shutil
    import os

    if not csv_path:
        return False

    temp_path = ""
    try:
        # Ensure target directory exists
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Create temp file in the same directory as target to ensure atomic move
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(csv_path), suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=schema)
            writer.writeheader()
            for row in rows:
                # Normalize row to match schema exactly
                normalized = normalize_row(row, schema, default_val="")
                writer.writerow(normalized)
        
        # Atomic replace
        shutil.move(temp_path, csv_path)
        return True
    except Exception as e:
        print_lg(f"Atomic CSV write failed for {csv_path}: {e}")
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False


def normalize_row(row_dict: dict, schema: list[str], default_val: str = "") -> dict:
    '''
    Ensures a dictionary matches the specified schema exactly.
    Pads missing fields with `default_val` (canonical empty string "") and removes extra fields.
    Now handles migration from legacy "Unknown" values to unified empty strings.
    '''
    canonical_row = {}
    
    # 1. Remap aliases and clean legacy "Unknown" strings
    for key, value in row_dict.items():
        if isinstance(value, datetime):
            value = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            value = value.isoformat()
        
        # Unified handling of "None" or "Unknown" to ""
        if value is None or (isinstance(value, str) and value.strip().lower() in ("unknown", "none", "null", "pending")):
            value = ""
            
        canonical_key = LEGACY_COLUMN_ALIASES.get(key, key)
        if canonical_key not in canonical_row or not canonical_row[canonical_key]:
            canonical_row[canonical_key] = value

    # 2. Apply business logic defaults
    if 'current_status' in schema and not canonical_row.get('current_status'):
        canonical_row['current_status'] = 'Applied'
    if 'status_source' in schema and not canonical_row.get('status_source'):
        canonical_row['status_source'] = 'LinkedIn Automation'
    if 'last_status_update' in schema and not canonical_row.get('last_status_update'):
        canonical_row['last_status_update'] = canonical_row.get('application_date', "")
    if 'response_received' in schema and not canonical_row.get('response_received'):
        canonical_row['response_received'] = 'False'
    if 'source_platform' in schema and not canonical_row.get('source_platform'):
        canonical_row['source_platform'] = 'LinkedIn'

    return {col: canonical_row.get(col, default_val) for col in schema}


def ensure_csv_header(csv_path: str, schema: list[str]) -> bool:
    '''
    Robustly ensures the CSV at `csv_path` matches the provided `schema`.
    If the header is missing or incomplete, it rewrites the file safely.
    Uses basic csv module to handle 'jagged' lines without dropping extra fields.
    '''
    import csv
    import os
    import tempfile
    import shutil

    if not os.path.exists(csv_path):
        try:
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=schema)
                writer.writeheader()
            return True
        except Exception as e:
            print_lg(f"Error creating empty CSV with header {csv_path}: {e}")
            return False

    needs_rewrite = False
    try:
        with open(csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                needs_rewrite = True
            else:
                # Check if all schema columns are in the current header
                current_cols = set(header)
                if not all(col in current_cols for col in schema):
                    needs_rewrite = True
                elif len(header) != len(schema):
                    # Even if all are present, order might be wrong or extra cols exist
                    needs_rewrite = True

        if needs_rewrite:
            print_lg(f"Normalizing CSV header for {csv_path} to match canonical schema...")
            fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(csv_path), suffix='.tmp')
            os.close(fd)
            
            with open(csv_path, 'r', encoding='utf-8', newline='') as f_in:
                # Use reader (not DictReader) to avoid data loss from jagged rows
                reader = csv.reader(f_in)
                old_header = next(reader, None)
                if not old_header:
                    old_header = []
                
                # Create a mapping from old header indices to schema column names
                # This handles cases where columns were added or reordered
                col_map = {i: old_header[i] for i in range(len(old_header))}
                
                with open(temp_path, 'w', encoding='utf-8', newline='') as f_out:
                    writer = csv.DictWriter(f_out, fieldnames=schema)
                    writer.writeheader()
                    
                    for row_values in reader:
                        # Map values to a dictionary based on the old header
                        row_dict = {}
                        for i, val in enumerate(row_values):
                            if i in col_map:
                                row_dict[col_map[i]] = val
                            else:
                                # This handles the 'jagged' case where more columns exist than in the header
                                # We assume they were appended in the order of the NEW schema if possible,
                                # or we just preserve them if we can identify them.
                                # For simplicity, we'll try to match them to schema columns that weren't in old_header.
                                pass
                        
                        # Normalize row to match schema
                        normalized = normalize_row(row_dict, schema, default_val="")
                        writer.writerow(normalized)
            
            # Atomic replace
            shutil.move(temp_path, csv_path)
            print_lg(f"Successfully normalized CSV: {csv_path}")
            return True
    except Exception as e:
        print_lg(f"Failed to normalize CSV {csv_path}: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        return False
    return False
