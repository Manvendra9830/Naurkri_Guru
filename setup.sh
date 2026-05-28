#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON:-python3}"

echo "Naukri_Guru setup"
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY

if [ ! -x "venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv venv
fi

./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python tools/validate_environment.py

echo "Setup complete. Use ./venv/bin/python runAiBot.py"
