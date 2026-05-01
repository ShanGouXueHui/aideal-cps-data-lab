#!/usr/bin/env bash
FAILED=0

ROOT="${AIDEAL_DATA_LAB_ROOT:-$HOME/projects/aideal-cps-data-lab}"
PYTHON="${PYTHON:-python3}"
VENV="${AIDEAL_DATA_LAB_BROWSER_VENV:-.venv-browser}"

echo "===== setup browser runtime ====="
echo "root=$ROOT"
echo "python=$PYTHON"
echo "venv=$VENV"

cd "$ROOT" || exit 1

"$PYTHON" -m venv "$VENV" || FAILED=1

if [ -f "$VENV/bin/activate" ]; then
  . "$VENV/bin/activate"
else
  echo "missing venv activate"
  FAILED=1
fi

python -m pip install --upgrade pip wheel setuptools || FAILED=1

if [ -n "${PIP_INDEX_URL:-}" ]; then
  python -m pip install -i "$PIP_INDEX_URL" -r requirements-browser.txt || FAILED=1
else
  python -m pip install -r requirements-browser.txt || FAILED=1
fi

python -m playwright install chromium || FAILED=1

python - <<'PY'
from playwright.sync_api import sync_playwright
print("playwright_import_ok")
PY

if [ "$FAILED" = "0" ]; then
  echo "BROWSER_RUNTIME_SETUP_OK"
else
  echo "BROWSER_RUNTIME_SETUP_FAILED"
fi

exit "$FAILED"
