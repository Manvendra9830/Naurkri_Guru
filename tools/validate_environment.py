from __future__ import annotations

import importlib
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from modules.browser.chrome_manager import detect_chrome


REQUIRED_PACKAGES = [
    "selenium",
    "undetected_chromedriver",
    "webdriver_manager",
    "pandas",
    "openpyxl",
    "bs4",
    "requests",
    "fake_useragent",
]


def main() -> int:
    print("Naukri_Guru environment validation")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 10):
        print("FAIL: Python 3.10+ is required.")
        return 1

    failed = False
    for package in REQUIRED_PACKAGES:
        try:
            module = importlib.import_module(package)
            version = getattr(module, "__version__", "installed")
            print(f"OK: {package} {version}")
        except Exception as exc:
            failed = True
            print(f"FAIL: {package} import failed: {exc}")

    try:
        chrome = detect_chrome()
        print(f"OK: Chrome {chrome.version}")
        print(f"Chrome path: {chrome.executable_path}")
    except Exception as exc:
        failed = True
        print(f"FAIL: Chrome detection failed: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
