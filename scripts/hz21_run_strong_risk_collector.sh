#!/usr/bin/env bash
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
TMP="run/.hz21_strong_risk_runtime.py"
python3 - <<'PY'
from pathlib import Path
src=Path('run/hz21_strict_card_dom_recover_page.py').read_text(encoding='utf-8')
src=src.replace("'滑块','购物无忧'", "'滑块'")
src=src.replace("\"滑块\",\"购物无忧\"", "\"滑块\"")
Path('run/.hz21_strong_risk_runtime.py').write_text(src, encoding='utf-8')
PY
.venv-browser/bin/python "$TMP"
RC=$?
rm -f "$TMP"
exit "$RC"
