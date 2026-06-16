#!/usr/bin/env bash
# Daytime, read-only JD promotion tab audit. No promotion link generation.

cd "${HOME}/projects/aideal-cps-data-lab"
if [ "$?" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=project_directory_missing"
  exit 1
fi
mkdir -p logs reports

DAYTIME="$(python3 - <<'PY'
from datetime import datetime
n=datetime.now(); m=n.hour*60+n.minute
print('true' if 570 <= m < 1290 else 'false')
PY
)"
if [ "$DAYTIME" != "true" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=outside_daytime"
  exit 1
fi

.venv-browser/bin/python -m py_compile run/hz24_audit_product_tabs.py > logs/hz24_tab_compile.log 2>&1
COMPILE_RC=$?

sudo systemctl stop aideal-hz23-observer.service
STOP_RC=$?

if [ "$COMPILE_RC" = "0" ] && [ "$STOP_RC" = "0" ]; then
  .venv-browser/bin/python run/hz24_audit_product_tabs.py > logs/hz24_tab_audit.log 2>&1
  AUDIT_RC=$?
else
  AUDIT_RC=99
fi

sudo systemctl start aideal-hz23-observer.service
START_RC=$?
sleep 2
SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"

PUBLISH_RC=99
if [ -f reports/hz24_product_tab_audit_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish JD product tab audit" \
    reports/hz24_product_tab_audit_latest.json \
    > logs/hz24_tab_publish.log 2>&1
  PUBLISH_RC=$?
fi

METRICS="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz24_product_tab_audit_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
tabs=x.get('tabs') or []
groups=x.get('candidate_tab_groups') or []
print('REPORT_OK='+str(bool(x.get('ok'))).lower())
print('REPORT_ERROR='+str(x.get('error') or ''))
print('DETECTED_TAB_NAMES='+'|'.join(str(v) for v in (x.get('detected_tab_names') or [])))
print('CANDIDATE_GROUP_COUNT='+str(len(groups)))
print('BEST_CANDIDATE_GROUP='+(groups[0].get('signature') if groups else ''))
print('TAB_COUNT='+str(len(tabs)))
print('TAB_NAMES='+'|'.join(str(t.get('tab_name') or '') for t in tabs))
print('TAB_METRICS='+';'.join(f"{t.get('tab_name')}:{t.get('first_page_sku_count',0)}/{t.get('unique_vs_all_count',0)}/{t.get('jaccard_with_all')}" for t in tabs))
print('RISK='+','.join(x.get('risk') or []))
PY
)"
METRIC_RC=$?

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$AUDIT_RC" != "0" ] || [ "$START_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ] || [ "$METRIC_RC" != "0" ] || [ "$SERVICE_STATE" != "active" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "AUDIT_RC=$AUDIT_RC"
echo "STOP_RC=$STOP_RC"
echo "START_RC=$START_RC"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "PUBLISH_RC=$PUBLISH_RC"
printf '%s\n' "$METRICS"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
