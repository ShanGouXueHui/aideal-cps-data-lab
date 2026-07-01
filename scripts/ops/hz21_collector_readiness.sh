#!/usr/bin/env bash
# HZ21 collector readiness audit.
# Does not execute the collector. It checks wrapper/runtime file/schema prerequisites only.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run data/import data/export data/state

REPORT="reports/hz21_collector_readiness_latest.json"
WRAPPER="scripts/hz21_run_strong_risk_collector.sh"
SOURCE="run/hz21_strict_card_dom_recover_page.py"
PYBIN=".venv-browser/bin/python"
LATEST="reports/hz21_strict_card_dom_recover_latest.json"

python3 - "$REPORT" "$WRAPPER" "$SOURCE" "$PYBIN" "$LATEST" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

report_path=Path(sys.argv[1])
wrapper=Path(sys.argv[2])
source=Path(sys.argv[3])
pybin=Path(sys.argv[4])
latest=Path(sys.argv[5])
checks={}
values={}

checks['wrapper_exists']=wrapper.exists()
checks['python_exists']=pybin.exists()
checks['runtime_source_exists']=source.exists()

if source.exists():
    raw=source.read_bytes()
    values['runtime_source_sha256']=hashlib.sha256(raw).hexdigest()
    values['runtime_source_bytes']=len(raw)
    proc=subprocess.run(
        [str(pybin) if pybin.exists() else sys.executable, '-m', 'py_compile', str(source)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    checks['runtime_source_py_compile_ok']=proc.returncode == 0
    values['py_compile_rc']=proc.returncode
    values['py_compile_stderr_tail']=proc.stderr[-1000:]
else:
    checks['runtime_source_py_compile_ok']=False
    values['runtime_source_sha256']=None
    values['runtime_source_bytes']=0

latest_payload={}
if latest.exists():
    try:
        latest_payload=json.loads(latest.read_text(encoding='utf-8'))
    except Exception as exc:
        latest_payload={'parse_error':repr(exc)}
values['latest_report_reason']=latest_payload.get('reason')
values['latest_report_ok']=latest_payload.get('ok')
values['latest_report_generated_at']=latest_payload.get('generated_at')

hard_failures=[]
for key in ('wrapper_exists','python_exists','runtime_source_exists','runtime_source_py_compile_ok'):
    if not checks.get(key):
        hard_failures.append(key)

payload={
  'schema_version':'hz21-collector-readiness/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'ready':not hard_failures,
  'hard_failures':hard_failures,
  'checks':checks,
  'values':values,
  'paths':{
    'wrapper':str(wrapper),
    'runtime_source':str(source),
    'python':str(pybin),
    'latest_report':str(latest),
  },
}
report_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(f'READINESS_REPORT={report_path}')
print(f'READY={payload["ready"]}')
print(f'HARD_FAILURES={",".join(hard_failures) if hard_failures else "none"}')
print(f'WRAPPER_EXISTS={checks["wrapper_exists"]}')
print(f'PYTHON_EXISTS={checks["python_exists"]}')
print(f'RUNTIME_SOURCE_EXISTS={checks["runtime_source_exists"]}')
print(f'RUNTIME_SOURCE_PY_COMPILE_OK={checks["runtime_source_py_compile_ok"]}')
print(f'RUNTIME_SOURCE_SHA256={values["runtime_source_sha256"]}')
print(f'LATEST_REPORT_OK={values["latest_report_ok"]}')
print(f'LATEST_REPORT_REASON={values["latest_report_reason"]}')
PY
READINESS_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ21 collector readiness" \
  "$REPORT" \
  > logs/hz21_collector_readiness_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "READINESS_RC=$READINESS_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
