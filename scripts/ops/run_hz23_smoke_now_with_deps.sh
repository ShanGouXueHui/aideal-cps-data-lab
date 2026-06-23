#!/usr/bin/env bash
# Ensure minimal browser runtime dependencies, then run immediate HZ23 smoke-now.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"

INSTALL_RC=0
.venv-browser/bin/python - <<'PY' >/dev/null 2>&1
import tomli
PY
TOMLI_RC=$?
if [ "$TOMLI_RC" != "0" ]; then
  echo "Installing missing runtime dependency: tomli"
  .venv-browser/bin/python -m pip install 'tomli>=2.0.1,<3' > logs/hz23_smoke_now_deps_install.log 2>&1
  INSTALL_RC=$?
fi

VERIFY_RC=0
.venv-browser/bin/python - <<'PY'
import importlib
mods = [
    'tomli',
    'aideal_cps_data_lab.hz22.page_prepare',
    'aideal_cps_data_lab.hz23.page_scan',
    'aideal_cps_data_lab.hz21.strict_card_dom_recover',
]
for name in mods:
    importlib.import_module(name)
    print(f'IMPORT_OK {name}')
PY
VERIFY_RC=$?

if [ "$INSTALL_RC" != "0" ] || [ "$VERIFY_RC" != "0" ]; then
  python3 - "$INSTALL_RC" "$VERIFY_RC" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
payload = {
    'schema_version': 'hz23-smoke-now-deps/v1',
    'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
    'status': 'DEPENDENCY_PRECHECK_FAILED',
    'install_rc': int(sys.argv[1]),
    'verify_rc': int(sys.argv[2]),
    'install_log': 'logs/hz23_smoke_now_deps_install.log',
}
Path('reports').mkdir(exist_ok=True)
Path('reports/hz23_smoke_now_latest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 smoke dependency failure" \
    reports/hz23_smoke_now_latest.json \
    >/dev/null 2>&1
  PUBLISH_RC=$?
  echo "===== SUMMARY ====="
  echo "RUN_RC=1"
  echo "INSTALL_RC=$INSTALL_RC"
  echo "VERIFY_RC=$VERIFY_RC"
  echo "PUBLISH_RC=$PUBLISH_RC"
  echo "REPORT=reports/hz23_smoke_now_latest.json"
  exit 0
fi

bash scripts/ops/run_hz23_smoke_now.sh
RUN_RC=$?
echo "DEPENDENCY_INSTALL_RC=$INSTALL_RC"
echo "DEPENDENCY_VERIFY_RC=$VERIFY_RC"
exit "$RUN_RC"
