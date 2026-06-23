#!/usr/bin/env bash
# HZ21 strong-risk collector wrapper.
# Runtime collector must be explicitly present; stale reports are removed before each run.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"

SOURCE="run/hz21_strict_card_dom_recover_page.py"
TMP="run/.hz21_strong_risk_runtime.py"
LATEST="reports/hz21_strict_card_dom_recover_latest.json"

rm -f "$TMP" "$LATEST"

if [ ! -f "$SOURCE" ]; then
  mkdir -p reports logs
  python3 - <<'PY'
import json
from datetime import datetime
from pathlib import Path
payload={
  'ok': False,
  'reason': 'runtime_collector_missing',
  'source': 'run/hz21_strict_card_dom_recover_page.py',
  'generated_at': datetime.utcnow().isoformat(timespec='seconds')+'Z',
}
Path('reports').mkdir(exist_ok=True)
Path('reports/hz21_strict_card_dom_recover_latest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
PY
  echo "HZ21_COLLECTOR_STATUS=missing_runtime_collector"
  exit 66
fi

cp "$SOURCE" "$TMP"
PREPARE_RC=$?
if [ "$PREPARE_RC" != "0" ]; then
  echo "HZ21_COLLECTOR_STATUS=runtime_prepare_failed"
  exit "$PREPARE_RC"
fi

.venv-browser/bin/python "$TMP"
RC=$?
rm -f "$TMP"
exit "$RC"
