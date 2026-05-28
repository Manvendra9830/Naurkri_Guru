from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options

from modules.helpers import get_dedicated_automation_profile_dir, print_lg


@dataclass(frozen=True)
class ChromeInfo:
    executable_path: str
    version: str
    major: int


LOCK_FILES = {"SingletonLock", "SingletonCookie", "SingletonSocket"}


def _candidate_paths() -> list[str]:
    if sys.platform.startswith("win"):
        return [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    if sys.platform == "darwin":
        return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return [
        shutil.which("google-chrome") or "",
        shutil.which("google-chrome-stable") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]


def _run_version_command(path: str) -> str:
    if sys.platform.startswith("win"):
        ps = f"(Get-Item -LiteralPath '{path.replace(chr(39), chr(39)+chr(39))}').VersionInfo.ProductVersion"
        completed = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=10)
        output = f"{completed.stdout} {completed.stderr}".strip()
        match = re.search(r"(\d+\.\d+\.\d+\.\d+|\d+\.\d+\.\d+|\d+\.\d+)", output)
        if match:
            return match.group(1)
    completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
    output = f"{completed.stdout} {completed.stderr}".strip()
    match = re.search(r"(\d+\.\d+\.\d+\.\d+|\d+\.\d+\.\d+|\d+\.\d+)", output)
    return match.group(1) if match else ""


def detect_chrome() -> ChromeInfo:
    for candidate in _candidate_paths():
        if not candidate or not os.path.exists(candidate):
            continue
        version = _run_version_command(candidate)
        if version:
            return ChromeInfo(candidate, version, int(version.split(".", 1)[0]))
    raise RuntimeError("Google Chrome was not found. Install Chrome and rerun setup validation.")


def ensure_profile_ready(profile_path: str | None = None) -> str:
    profile_path = profile_path or get_dedicated_automation_profile_dir()
    Path(profile_path).mkdir(parents=True, exist_ok=True)
    default_profile = Path(profile_path) / "Default"
    default_profile.mkdir(parents=True, exist_ok=True)

    for lock_file in LOCK_FILES:
        lock_path = Path(profile_path) / lock_file
        try:
            if lock_path.exists():
                lock_path.unlink()
                print_lg(f"Removed stale Chrome profile lock: {lock_path}")
        except OSError as exc:
            print_lg(f"Chrome profile lock is active and could not be removed: {lock_path} ({exc})")
    return profile_path


def kill_profile_chrome_processes(profile_path: str) -> None:
    normalized = os.path.normcase(os.path.abspath(profile_path))
    try:
        if sys.platform.startswith("win"):
            ps = (
                "Get-CimInstance Win32_Process -Filter \"name = 'chrome.exe'\" | "
                "Where-Object { $_.CommandLine -and "
                f"$_.CommandLine.ToLower().Contains('{normalized.lower().replace(chr(39), chr(39)+chr(39))}') }} | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
        else:
            subprocess.run(["pkill", "-f", re.escape(profile_path)], capture_output=True, text=True, timeout=15)
    except Exception as exc:
        print_lg(f"Could not clean Chrome processes for automation profile: {exc}")


def build_chrome_options(chrome: ChromeInfo, profile_path: str, *, headless: bool, disable_extensions: bool) -> Options:
    options = Options()
    options.binary_location = chrome.executable_path
    if headless:
        options.add_argument("--headless=new")
    if disable_extensions:
        options.add_argument("--disable-extensions")
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-features=Translate,AutofillServerCommunication")
    options.add_argument("--remote-debugging-port=0")
    options.page_load_strategy = "eager"
    return options


def driver_version(driver) -> str:
    try:
        capabilities = driver.capabilities or {}
        chrome_info = capabilities.get("chrome", {})
        return chrome_info.get("chromedriverVersion", "").split(" ", 1)[0] or "unknown"
    except Exception:
        return "unknown"


def launch_chrome(*, stealth: bool, headless: bool, disable_extensions: bool):
    chrome = detect_chrome()
    profile_path = get_dedicated_automation_profile_dir()
    kill_profile_chrome_processes(profile_path)
    profile_path = ensure_profile_ready(profile_path)
    options = build_chrome_options(chrome, profile_path, headless=headless, disable_extensions=disable_extensions)

    print_lg("Chrome startup diagnostics")
    print_lg(f"  OS: {platform.platform()}")
    print_lg(f"  Chrome executable: {chrome.executable_path}")
    print_lg(f"  Chrome version: {chrome.version} (major={chrome.major})")
    print_lg(f"  Automation profile: {profile_path}")

    if stealth:
        try:
            import undetected_chromedriver as uc

            uc_options = uc.ChromeOptions()
            for argument in options.arguments:
                uc_options.add_argument(argument)
            uc_options.binary_location = chrome.executable_path
            print_lg(f"Launching undetected-chromedriver with version_main={chrome.major}")
            driver = uc.Chrome(
                options=uc_options,
                version_main=chrome.major,
                browser_executable_path=chrome.executable_path,
                use_subprocess=True,
            )
            print_lg(f"ChromeDriver version: {driver_version(driver)}")
            return options, driver
        except (SessionNotCreatedException, WebDriverException, RuntimeError, OSError) as exc:
            print_lg(f"undetected-chromedriver startup failed, falling back to Selenium Manager: {exc}")

    driver = webdriver.Chrome(options=options)
    print_lg(f"ChromeDriver version: {driver_version(driver)}")
    return options, driver
