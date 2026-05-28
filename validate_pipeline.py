"""
Convenience entry point for the pipeline validation suite.

It prefers the project virtual environment so dependencies such as pandas and
openpyxl are resolved consistently even when system Python is first on PATH.
"""

from __future__ import annotations

import os
import runpy
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")


def _same_python(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


if os.path.exists(VENV_PYTHON) and not _same_python(sys.executable, VENV_PYTHON):
    raise SystemExit(subprocess.call([VENV_PYTHON, "-m", "tests.validate_pipeline"]))

runpy.run_module("tests.validate_pipeline", run_name="__main__")
