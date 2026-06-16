#!/usr/bin/env bash
# Single-account, serial, read-only JD tab pool analysis. No link generation.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab"
CD_RC=$?
if [ "$CD_RC" != "0" ]; then
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

if pgrep -af 'scripts/[h]z23_mainline_refresh.sh|scripts/[h]z23_resume_after_manual_verification.sh' >/dev/null 2>&1; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=collection_process_running"
  exit 1
fi

.venv-browser/bin/python -m py_compile \
  run/hz24_inspect_tab_pool_structure.py \
  scripts/hz24_analyze_tab_overlap.py \
  > logs/hz24_tab_pool_compile.log 2>&1
COMPILE_RC=$?

OLD_SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
if [ "$OLD_SERVICE_STATE" = "active" ]; then
  sudo systemctl stop aideal-hz23-observer.service
  STOP_RC=$?
else
  STOP_RC=0
fi

if [ "$COMPILE_RC" = "0" ] && [ "$STOP_RC" = "0" ]; then
  .venv-browser/bin/python run/hz24_inspect_tab_pool_structure.py \
    > logs/hz24_tab_pool_structure.log 2>&1
  INSPECT_RC=$?
else
  INSPECT_RC=99
fi

if [ "$OLD_SERVICE_STATE" = "active" ]; then
  sudo systemctl start aideal-hz23-observer.service
  START_RC=$?
else
  START_RC=0
fi
sleep 2
SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
SERVICE_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"

if [ "$INSPECT_RC" = "0" ]; then
  PYTHONPATH=src python3 scripts/hz24_analyze_tab_overlap.py \
    > logs/hz24_tab_overlap_analysis.log 2>&1
  ANALYZE_RC=$?
else
  ANALYZE_RC=99
fi

PUBLISH_RC=99
if [ -f reports/hz24_tab_pool_structure_latest.json ] && [ -f reports/hz24_tab_overlap_analysis_latest.json ]; then
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ24 tab pool overlap analysis" \
    reports/hz24_tab_pool_structure_latest.json \
    reports/hz24_tab_overlap_analysis_latest.json \
    > logs/hz24_tab_pool_publish.log 2>&1
  PUBLISH_RC=$?
fi

METRICS="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz24_tab_overlap_analysis_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
per=x.get('per_tab') or []
checks=x.get('checks') or {}
print('ANALYSIS_READY='+str(bool(x.get('analysis_ready'))).lower())
print('ALL_SPECIAL_TABS_SINGLE_PAGE_CONFIRMED='+str(bool(checks.get('all_special_tabs_single_page_confirmed'))).lower())
print('CANDIDATE_SKU_COUNT='+str(x.get('candidate_sku_count') or 0))
print('TRUSTED_SOURCE_SKU_COUNT='+str(x.get('trusted_source_sku_count') or 0))
print('SPECIAL_TAB_MEMBERSHIP_COUNT='+str(x.get('special_tab_membership_count') or 0))
print('SPECIAL_TAB_UNION_SKU_COUNT='+str(x.get('special_tab_union_sku_count') or 0))
print('CROSS_TAB_DUPLICATE_MEMBERSHIP_COUNT='+str(x.get('cross_tab_duplicate_membership_count') or 0))
print('SPECIAL_UNION_OVERLAP_WITH_CANDIDATE_COUNT='+str(x.get('special_union_overlap_with_candidate_count') or 0))
print('SPECIAL_UNION_INCREMENT_VS_CANDIDATE_COUNT='+str(x.get('special_union_increment_vs_candidate_count') or 0))
print('SPECIAL_UNION_PROMOTION_LINK_REQUIRED_COUNT='+str(x.get('special_union_promotion_link_required_count') or 0))
print('SPECIAL_UNION_ALREADY_LINKED_NOT_CANDIDATE_COUNT='+str(x.get('special_union_already_linked_not_candidate_count') or 0))
print('PER_TAB='+';'.join(f"{r.get('tab_name')}:{r.get('pool_sku_count',0)}/{r.get('increment_vs_candidate_count',0)}/{r.get('promotion_link_required_count',0)}" for r in per))
print('RECOMMENDED_NEXT_STEP='+str(x.get('recommended_next_step') or ''))
print('ANALYSIS_FAILURES='+(','.join(x.get('failures') or []) or '-'))
PY
)"
METRIC_RC=$?

STATUS=PASS
if [ "$COMPILE_RC" != "0" ] || [ "$INSPECT_RC" != "0" ] || [ "$ANALYZE_RC" != "0" ] || [ "$START_RC" != "0" ] || [ "$PUBLISH_RC" != "0" ] || [ "$METRIC_RC" != "0" ]; then
  STATUS=FAIL
fi
if [ "$OLD_SERVICE_STATE" = "active" ] && [ "$SERVICE_STATE" != "active" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "COMPILE_RC=$COMPILE_RC"
echo "INSPECT_RC=$INSPECT_RC"
echo "ANALYZE_RC=$ANALYZE_RC"
echo "STOP_RC=$STOP_RC"
echo "START_RC=$START_RC"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"
echo "PUBLISH_RC=$PUBLISH_RC"
printf '%s\n' "$METRICS"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

[ "$STATUS" = PASS ]
