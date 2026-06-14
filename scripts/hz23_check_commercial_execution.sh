#!/usr/bin/env bash
# Read-only commercial execution check. It does not restart services or operate JD pages.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports

bash scripts/hz23_publish_commercial_status_v2.sh \
  > logs/hz23_commercial_status_publish_check.log 2>&1
PUBLISH_RC=$?

REPORT="reports/hz23_commercial_status_v2_latest.json"
if [ ! -f "$REPORT" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAIL"
  echo "STEP=status_report_missing"
  echo "PUBLISH_RC=$PUBLISH_RC"
  exit 1
fi

python3 - "$REPORT" "$PUBLISH_RC" <<'PY'
import json,sys
from pathlib import Path

path=Path(sys.argv[1]); publish_rc=int(sys.argv[2])
x=json.loads(path.read_text(encoding='utf-8'))
service=x.get('service') or {}
state=x.get('observer_state') or {}
round_report=x.get('latest_round')
manifest=x.get('candidate_manifest')
checks=x.get('checks') or {}

full_present=round_report is not None
manifest_present=manifest is not None
status='PASS' if publish_rc==0 and service.get('state')=='active' else 'FAIL'

print('===== SUMMARY =====')
print(f'STATUS={status}')
print(f'PUBLISH_RC={publish_rc}')
print(f'SERVICE_STATE={service.get("state") or ""}')
print(f'SERVICE_PID={service.get("main_pid") or ""}')
print(f'OBSERVER_MODE={(x.get("latest_observer_status") or {}).get("mode") or ""}')
print(f'SUCCESSFUL_PROBES={state.get("successful_probes") or 0}')
print(f'FAILED_PROBES={state.get("failed_probes") or 0}')
print(f'OBSERVATION_HOURS={x.get("observation_hours") or 0}')
print(f'LAST_FULL_STARTED_AT={state.get("last_full_started_at") or ""}')
print(f'LAST_FULL_FINISHED_AT={state.get("last_full_finished_at") or ""}')
print(f'LAST_FULL_ROUND_ID={state.get("last_full_round_id") or ""}')
print(f'LAST_FULL_COMPLETE={str(bool(state.get("last_full_complete"))).lower()}')
print(f'LAST_STOP_REASON={state.get("last_stop_reason") or ""}')
print(f'FULL_ROUND_PRESENT={str(full_present).lower()}')
print(f'FULL_ROUND_COMPLETE={str(bool(checks.get("full_round_complete"))).lower()}')
print(f'COMPLETED_PAGE_COUNT={len((round_report or {}).get("completed_pages") or [])}')
print(f'UNFINISHED_PAGE_COUNT={len((round_report or {}).get("unfinished_pages") or [])}')
print(f'SCANNED_TOTAL={(round_report or {}).get("scanned_total") if full_present else ""}')
print(f'CATALOG_NEW={(round_report or {}).get("catalog_new") if full_present else ""}')
print(f'CATALOG_CHANGED={(round_report or {}).get("catalog_changed") if full_present else ""}')
print(f'CATALOG_UNCHANGED={(round_report or {}).get("catalog_unchanged") if full_present else ""}')
print(f'LAST_KNOWN_SKU_COUNT={(round_report or {}).get("last_known_sku_count") if full_present else ""}')
print(f'CANDIDATE_MANIFEST_PRESENT={str(manifest_present).lower()}')
print(f'CANDIDATE_ROWS={(manifest or {}).get("row_count") if manifest_present else ""}')
print(f'DUPLICATE_SKU_COUNT={(manifest or {}).get("duplicate_sku_count") if manifest_present else ""}')
print(f'UNSAFE_HZ20_COUNT={((manifest or {}).get("rejected") or {}).get("unsafe_hz20") if manifest_present else ""}')
print(f'UNTRUSTED_PROMOTION_URL_COUNT={((manifest or {}).get("rejected") or {}).get("untrusted_promotion_url") if manifest_present else ""}')
print(f'CANDIDATE_INTEGRITY_READY={str(bool(checks.get("candidate_integrity_ready"))).lower()}')
print(f'OBSERVATION_READY={str(bool(x.get("observation_ready"))).lower()}')
print(f'MYSQL_INITIALIZATION_ALLOWED={str(bool(x.get("mysql_initialization_allowed"))).lower()}')
print(f'GATE_FAILURES={",".join(x.get("gate_failures") or [])}')
PY
CHECK_RC=$?

if [ "$PUBLISH_RC" != "0" ] || [ "$CHECK_RC" != "0" ]; then
  exit 1
fi
exit 0
