#!/usr/bin/env bash
# Immediate one-page HZ23 smoke test. Bypasses daytime wait intentionally for manual validation only.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
. config/hz23-service.env
mkdir -p logs reports run data/import data/state data/history data/export

# Stop a pending auto-smoke scheduler if present.
if [ -f run/hz23_smoke_daytime_scheduler.pid ]; then
  OLD_PID="$(cat run/hz23_smoke_daytime_scheduler.pid 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    kill "$OLD_PID" 2>/dev/null || true
  fi
  rm -f run/hz23_smoke_daytime_scheduler.pid
fi

ROUND_ID="smoke_now_$(date +%Y%m%d_%H%M%S)"
PREP="reports/hz23_prepare_page1_latest.json"
SCAN="reports/hz23_scan_page1_latest.json"
COLLECT="reports/hz23_collect_page_1_latest.json"
HZ21="reports/hz21_strict_card_dom_recover_latest.json"
ROWS="reports/hz23_round_${ROUND_ID}_rows.jsonl"
SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"
LATEST_SUMMARY="reports/hz23_round_latest.json"
REPORT="reports/hz23_smoke_now_latest.json"
LOG="logs/hz23_${ROUND_ID}.log"

rm -f "$PREP" "$SCAN" "$COLLECT" "$HZ21" "$ROWS" "$SUMMARY" "$REPORT"
: > "$ROWS"
: > "$LOG"

RUN_RC=0
STOP_REASON=""
STOP_PAGE=""

{
  echo "===== HZ23 smoke-now preflight imports ====="
  .venv-browser/bin/python - <<'PY'
import importlib
mods = [
    'aideal_cps_data_lab.hz22.page_prepare',
    'aideal_cps_data_lab.hz23.page_scan',
    'aideal_cps_data_lab.hz21.strict_card_dom_recover',
]
for name in mods:
    importlib.import_module(name)
    print(f'IMPORT_OK {name}')
PY
  PREFLIGHT_RC=$?
  echo "PREFLIGHT_RC=$PREFLIGHT_RC"
  if [ "$PREFLIGHT_RC" != "0" ]; then
    RUN_RC="$PREFLIGHT_RC"
    STOP_REASON="preflight_import_failed"
  fi

  if [ "$RUN_RC" = "0" ]; then
    echo "===== HZ23 prepare page 1 ====="
    .venv-browser/bin/python run/hz22_prepare_all_product_page.py 1 "$PREP"
    PREP_RC=$?
    echo "PREP_RC=$PREP_RC"
    if [ "$PREP_RC" != "0" ]; then
      RUN_RC="$PREP_RC"
      STOP_REASON="prep_entry_failed"
      STOP_PAGE=1
    fi
  fi

  if [ "$RUN_RC" = "0" ]; then
    PREP_OK="$(python3 - "$PREP" <<'PY'
import json,sys
from pathlib import Path
try:
    x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print('true' if x.get('ok') else 'false')
except Exception:
    print('false')
PY
)"
    PREP_REASON="$(python3 - "$PREP" <<'PY'
import json,sys
from pathlib import Path
try:
    print(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')).get('reason') or '')
except Exception:
    print('prep_report_error')
PY
)"
    echo "PREP_OK=$PREP_OK PREP_REASON=$PREP_REASON"
    if [ "$PREP_OK" != "true" ]; then
      RUN_RC=99
      STOP_REASON="${PREP_REASON:-prep_failed}"
      STOP_PAGE=1
    fi
  fi

  if [ "$RUN_RC" = "0" ]; then
    echo "===== HZ23 scan page 1 ====="
    .venv-browser/bin/python run/hz23_scan_current_page.py 1 "$ROUND_ID" "$SCAN"
    SCAN_RC=$?
    echo "SCAN_RC=$SCAN_RC"
    if [ "$SCAN_RC" != "0" ]; then
      RUN_RC="$SCAN_RC"
      STOP_REASON="scan_entry_failed"
      STOP_PAGE=1
    fi
  fi

  if [ "$RUN_RC" = "0" ]; then
    SCAN_OK="$(python3 - "$SCAN" <<'PY'
import json,sys
from pathlib import Path
try:
    x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print('true' if x.get('ok') else 'false')
except Exception:
    print('false')
PY
)"
    echo "SCAN_OK=$SCAN_OK"
    if [ "$SCAN_OK" != "true" ]; then
      RUN_RC=98
      STOP_REASON="scan_failed"
      STOP_PAGE=1
    fi
  fi

  if [ "$RUN_RC" = "0" ]; then
    echo "===== HZ23 collect new SKUs page 1 ====="
    HZ21_PAGE_SEQUENCE=1 \
    HZ21_LIMIT="${HZ23_LIMIT:-3}" \
    HZ21_WAIT=10 \
    HZ21_FAIL_FUSE=6 \
    HZ21_ITEM_SLEEP_MIN="$HZ23_ITEM_SLEEP_MIN" \
    HZ21_ITEM_SLEEP_MAX="$HZ23_ITEM_SLEEP_MAX" \
    bash scripts/hz21_run_strong_risk_collector.sh
    COLLECT_RC=$?
    cp "$HZ21" "$COLLECT" 2>/dev/null || true
    echo "COLLECT_RC=$COLLECT_RC"
  else
    COLLECT_RC=0
  fi

  python3 - "$ROUND_ID" "$RUN_RC" "${STOP_REASON}" "${STOP_PAGE}" "$PREP" "$SCAN" "$HZ21" "$ROWS" "$SUMMARY" "$LATEST_SUMMARY" <<'PY'
import json, sys
from pathlib import Path
round_id=sys.argv[1]
run_rc=int(sys.argv[2])
stop_reason=sys.argv[3] or None
stop_page=int(sys.argv[4]) if sys.argv[4] else None
prep_path, scan_path, hz21_path, rows_path, summary_path, latest_path = map(Path, sys.argv[5:11])

def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'parse_error': repr(exc)}
prep=read_json(prep_path)
scan=read_json(scan_path)
collect=read_json(hz21_path)
reason=collect.get('reason')
soft_reasons={'runtime_collector_missing','hz21_collector_not_mainlined'}
collect_ok=bool(collect.get('ok'))
collect_unavailable=bool(run_rc == 0 and collect.get('ok') is False and str(reason or '') in soft_reasons)
if run_rc == 0 and not collect_ok and not collect_unavailable:
    run_rc = 1
    stop_reason = reason or 'collector_failed'
    stop_page = 1
row={
    'page':1,
    'rc':run_rc,
    'ok':run_rc == 0 or collect_unavailable,
    'reason':reason,
    'prep_ok':prep.get('ok'),
    'prep_reason':prep.get('reason'),
    'scan_ok':scan.get('ok'),
    'scanned':scan.get('scanned',0),
    'new_catalog':scan.get('new',0),
    'changed_catalog':scan.get('changed',0),
    'unchanged_catalog':scan.get('unchanged',0),
    'collect_ok':collect_ok,
    'collect_unavailable':collect_unavailable,
    'total_ok':collect.get('total_ok',0),
    'total_fail':collect.get('total_fail',0),
    'known_sku_count':collect.get('known_sku_count'),
}
rows_path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True)+'\n', encoding='utf-8')
summary={
    'round_id': round_id,
    'pages': [1],
    'rows': [row],
    'completed_pages': [1] if row['ok'] else [],
    'unfinished_pages': [] if row['ok'] else [1],
    'scanned_total': int(row.get('scanned') or 0),
    'catalog_new': int(row.get('new_catalog') or 0),
    'catalog_changed': int(row.get('changed_catalog') or 0),
    'catalog_unchanged': int(row.get('unchanged_catalog') or 0),
    'collect_unavailable_pages': [1] if row.get('collect_unavailable') else [],
    'stop_page': stop_page,
    'stop_reason': stop_reason,
    'commercial_segment_complete': row['ok'] and not stop_reason,
    'total_ok': int(row.get('total_ok') or 0),
    'total_fail': int(row.get('total_fail') or 0),
    'last_known_sku_count': row.get('known_sku_count'),
}
text=json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
summary_path.write_text(text+'\n', encoding='utf-8')
latest_path.write_text(text+'\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
if stop_reason:
    raise SystemExit(run_rc or 1)
PY
  FINAL_RC=$?
  echo "FINAL_RC=$FINAL_RC"
  if [ "$FINAL_RC" != "0" ] && [ "$RUN_RC" = "0" ]; then
    RUN_RC="$FINAL_RC"
  fi
} >> "$LOG" 2>&1

python3 - "$ROUND_ID" "$RUN_RC" "$REPORT" "$SUMMARY" "$LOG" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
run_rc=int(sys.argv[2])
report=Path(sys.argv[3])
summary_path=Path(sys.argv[4])
log_path=Path(sys.argv[5])
summary={}
if summary_path.exists():
    try:
        summary=json.loads(summary_path.read_text(encoding='utf-8'))
    except Exception as exc:
        summary={'summary_parse_error': repr(exc)}
log_tail=[]
if log_path.exists():
    log_tail=log_path.read_text(encoding='utf-8', errors='replace').splitlines()[-220:]
payload={
    'schema_version':'hz23-smoke-now/v1',
    'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
    'round_id':round_id,
    'run_rc':run_rc,
    'summary_path':str(summary_path),
    'log_path':str(log_path),
    'summary':summary,
    'log_tail':log_tail,
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 smoke now result" \
  "$REPORT" "$SUMMARY" "$LATEST_SUMMARY" "$PREP" "$SCAN" "$COLLECT" "$HZ21" \
  > logs/hz23_smoke_now_publish.log 2>&1
PUBLISH_RC=$?

echo "===== SUMMARY ====="
echo "RUN_RC=$RUN_RC"
echo "ROUND_ID=$ROUND_ID"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=$REPORT"
echo "SUMMARY_JSON=$SUMMARY"
echo "LOG=$LOG"
exit 0
