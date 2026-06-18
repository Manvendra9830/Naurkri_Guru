from __future__ import annotations

from selenium.common.exceptions import WebDriverException

from modules.helpers import print_lg


def detect_captcha(driver) -> bool:
    try:
        source = (driver.page_source or "").lower()
        url = (driver.current_url or "").lower()
        markers = ["captcha", "checkpoint/challenge", "security verification", "verify you're human"]
        detected = any(marker in source or marker in url for marker in markers)
        if detected:
            print_lg("CAPTCHA/checkpoint detected. Automation should pause for manual recovery.")
        return detected
    except WebDriverException:
        print_lg("Browser health check failed while detecting CAPTCHA.")
        return False


def is_linkedin_logged_out(driver) -> bool:
    try:
        url = (driver.current_url or "").lower()
        source = (driver.page_source or "").lower()
        logged_out = "linkedin.com/login" in url or "sign in" in source and "join now" in source
        if logged_out:
            print_lg("LinkedIn auth state: logged out or login wall detected.")
        return logged_out
    except WebDriverException:
        print_lg("Browser health check failed while detecting LinkedIn auth state.")
        return True


def assert_browser_healthy(driver) -> bool:
    if driver is None:
        print_lg("[BROWSER-HEALTH] status=missing_driver")
        return False
    try:
        _ = driver.current_window_handle
        print_lg("[BROWSER-HEALTH] status=healthy")
        return True
    except WebDriverException as exc:
        print_lg(f"[BROWSER-HEALTH] status=unhealthy; error={type(exc).__name__}: {exc}")
        return False
