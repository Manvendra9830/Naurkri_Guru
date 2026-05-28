"""
Chrome session bootstrap for Naukri_Guru.

Chrome is initialized only when initialize_chrome_session() is called. The
browser always uses the dedicated automation profile and never attaches to the
user's personal Chrome profile.
"""

import time

from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait

from config.questions import default_resume_path
from config.settings import (
    disable_extensions,
    failed_file_name,
    file_name,
    generated_resume_path,
    logs_folder_path,
    run_in_background,
    safe_mode,
    stealth_mode,
)
from modules.browser.chrome_manager import ensure_profile_ready, kill_profile_chrome_processes, launch_chrome
from modules.helpers import critical_error_log, make_directories, print_lg, safe_alert


options, driver, actions, wait = None, None, None, None


def kill_chrome_processes():
    """Clean only stale Chrome processes tied to the automation profile."""
    profile_path = ensure_profile_ready()
    kill_profile_chrome_processes(profile_path)
    time.sleep(2)
    return True


def ensure_chrome_closed():
    """Prepare the isolated automation profile without touching personal Chrome."""
    kill_chrome_processes()


def createChromeSession(isRetry: bool = False):
    make_directories([
        file_name,
        failed_file_name,
        logs_folder_path + "/screenshots",
        default_resume_path,
        generated_resume_path + "/temp",
    ])
    if isRetry:
        print_lg("Retrying Chrome launch with the same isolated automation profile.")
    if safe_mode:
        print_lg("Safe mode is enabled; production profile isolation still uses the automation profile.")

    chrome_options, chrome_driver = launch_chrome(
        stealth=stealth_mode,
        headless=run_in_background,
        disable_extensions=disable_extensions,
    )

    time.sleep(3)
    chrome_driver.maximize_window()
    chrome_wait = WebDriverWait(chrome_driver, 20)
    chrome_actions = ActionChains(chrome_driver)

    print_lg("Chrome session created successfully.")
    return chrome_options, chrome_driver, chrome_actions, chrome_wait


def initialize_chrome_session():
    global options, driver, actions, wait
    try:
        options, driver, actions, wait = createChromeSession()
        return options, driver, actions, wait
    except SessionNotCreatedException as exc:
        critical_error_log("Failed to create Chrome session, retrying once", exc)
        try:
            options, driver, actions, wait = createChromeSession(True)
            return options, driver, actions, wait
        except Exception as retry_exc:
            critical_error_log("Chrome retry failed", retry_exc)
            safe_alert(
                "Naukri_Guru - Chrome failed to launch.\n\n"
                "The dedicated automation profile was cleaned and retried once.\n"
                "Check logs for Chrome/ChromeDriver diagnostics.",
                "Naukri_Guru - Critical Error",
            )
            raise SystemExit(1)
    except Exception as exc:
        msg = (
            "Naukri_Guru - Failed to launch Chrome.\n\n"
            "Chrome and ChromeDriver are detected automatically. "
            "Check logs for version/profile diagnostics."
        )
        print_lg(msg)
        critical_error_log("In Opening Chrome", exc)
        safe_alert(msg, "Naukri_Guru - Chrome Error")
        try:
            if driver:
                driver.quit()
        except WebDriverException:
            pass
        raise SystemExit(1)
