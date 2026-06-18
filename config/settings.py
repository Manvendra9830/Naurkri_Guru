######################################################  NAUKRI_GURU — CONFIGURATION  ######################################################
# Naukri_Guru: AI-Powered Job Automation Platform
# Developer: Manvendra Singh | IIIT Raichur
######################################################################################################################

# >>>>>>>>>>> LinkedIn Settings <<<<<<<<<<<

# Keep the External Application tabs open?
close_tabs = True                  # True or False, Note: True or False are case-sensitive
'''
Note: RECOMMENDED TO LEAVE IT AS `True`, if you set it `False`, be sure to CLOSE ALL TABS BEFORE CLOSING THE BROWSER!!!
'''

# Follow easy applied companies
follow_companies = True            # True or False, Note: True or False are case-sensitive

## Upcoming features (In Development)
# # Send connection requests to HR's 
# connect_hr = True                  # True or False, Note: True or False are case-sensitive

# # What message do you want to send during connection request? (Max. 200 Characters)
# connect_request_message = ""       # Leave Empty to send connection request without personalized invitation (recommended to leave it empty, since you only get 10 per month without LinkedIn Premium*)

# Do you want the program to run continuously until you stop it? (Beta)
run_non_stop = False                # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
alternate_sortby = True             # True or False, Note: True or False are case-sensitive
cycle_date_posted = True            # True or False, Note: True or False are case-sensitive
stop_date_cycle_at_24hr = True      # True or False, Note: True or False are case-sensitive





# >>>>>>>>>>> RESUME GENERATOR (Experimental & In Development) <<<<<<<<<<<

# Give the path to the folder where all the generated resumes are to be stored
generated_resume_path = "all resumes/" # (In Development)





# >>>>>>>>>>> Global Settings <<<<<<<<<<<

# >>>>>>>>>>> Automated Daily Execution <<<<<<<<<<<

# If True, the scheduled runner is allowed to start the bot automatically.
# Manual execution of runAiBot.py is still controlled by you and is not blocked by this flag.
AUTO_RUN_ENABLED = True            # True or False

# Daily run time used by the Windows Task Scheduler registration helper.
# Format: "HH:MM" in 24-hour local time. Example: "06:00"
AUTO_RUN_TIME = "11:00"

# Testing safety cap. Set to 0 or None to disable the per-run application cap.
MAX_APPLICATIONS_PER_RUN = 5


# Directory and name of the files where history of applied jobs is saved (Sentence after the last "/" will be considered as the file name).
file_name = "all excels/all_applied_applications_history.csv"
failed_file_name = "all excels/all_failed_applications_history.csv"
logs_folder_path = "logs/"


# >>>>>>>>>>> Gmail IMAP Lifecycle Sync <<<<<<<<<<<

# Reads recruiter/application emails before automation starts and updates lifecycle status.
GMAIL_SYNC_ENABLED = True           # True or False
GMAIL_ENV_PATH = "config/email/.env"
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_LOOKBACK_DAYS = 20
GMAIL_MAX_EMAILS = 50
GMAIL_MATCH_THRESHOLD = 0.75
GMAIL_CLASSIFICATION_THRESHOLD = 0.65

# Set the maximum amount of time allowed to wait between each click in secs
click_gap = 1                       # Enter max allowed secs to wait approximately. (Only Non Negative Integers Eg: 0,1,2,3,....)

# If you want to see Chrome running then set run_in_background as False (May reduce performance). 
run_in_background = False           # True or False, Note: True or False are case-sensitive ,   If True, this will make pause_at_failed_question, pause_before_submit and run_in_background as False

# If you want to disable extensions then set disable_extensions as True (Better for performance)
disable_extensions = False          # True or False, Note: True or False are case-sensitive

# Run in safe mode. Set this true if chrome is taking too long to open or if you have multiple profiles in browser. This will open chrome in guest profile!
safe_mode = True                   # True or False, Note: True or False are case-sensitive

# Do you want scrolling to be smooth or instantaneous? (Can reduce performance if True)
smooth_scroll = False               # True or False, Note: True or False are case-sensitive

# If enabled (True), the program would keep your screen active and prevent PC from sleeping. Instead you could disable this feature (set it to false) and adjust your PC sleep settings to Never Sleep or a preferred time. 
keep_screen_awake = True            # True or False, Note: True or False are case-sensitive (Note: Will temporarily deactivate when any application dialog boxes are present (Eg: Pause before submit, Help needed for a question..))

# Run in undetected mode to bypass anti-bot protections (Preview Feature, UNSTABLE. Recommended to leave it as False)
stealth_mode = True                # True or False, Note: True or False are case-sensitive


# >>>>>>>>>>> Chrome Profile Settings <<<<<<<<<<<

# Legacy flag retained for config compatibility.
# Production Chrome startup always uses the isolated automation-only profile.
use_real_chrome_profile = False     # True or False

# Which Chrome profile to use. Run the bot once to see detected profiles in the log.
# Common values: "Default", "Profile 1", "Profile 2", etc.
chrome_profile_name = "Default"     # Your Chrome profile directory name

# Keep browser session data persistent between runs
persistent_session = True           # True or False

# Do you want to get alerts on errors related to AI API connection?
showAiErrorAlerts = False            # True or False, Note: True or False are case-sensitive

# Use ChatGPT for resume building (Experimental Feature can break the application. Recommended to leave it as False) 
# use_resume_generator = False       # True or False, Note: True or False are case-sensitive ,   This feature may only work with 'stealth_mode = True'. As ChatGPT website is hosted by CloudFlare which is protected by Anti-bot protections!


# >>>>>>>>>>> Cold Email Settings <<<<<<<<<<<
COLD_EMAIL_ENABLED = True           # True or False
COLD_EMAIL_RESUME_DIR = "all resumes/"
COLD_EMAIL_COVER_LETTER_DIR = "all cover_Letter/"
COLD_EMAIL_RESUME_TEXT = "resume_text.txt"
MAX_COLD_EMAILS_PER_RUN = 10       # Max cold emails to send per outreach queue run
COLD_EMAIL_DRY_RUN = False         # Print queued recipients without sending SMTP mail
VALIDATION_EMAIL_MODE = True      # Legacy QA flag retained; queue mode includes validation rows
EMAIL_SEND_DELAY_SECONDS = 10      # Delay between SMTP sends to protect sender reputation


# >>>>>>>>>>> Indeed Scraper Settings <<<<<<<<<<<
INDEED_ENABLED = True
INDEED_MAX_JOBS_TO_SCRAPE = 5      # Max jobs to collect per run (0 = unlimited)
INDEED_MAX_JOBS_PER_TERM = 5     # Max jobs to collect per search term
MIN_MONTHLY_SALARY_INR = 30000
MIN_ANNUAL_CTC_LPA = 4
ALLOW_UNDISCLOSED_SALARY = False


##############################################################################################################
