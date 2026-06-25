#!/usr/bin/env bash
# HZ23 commercial-observation refresh mainline.
# - Daytime only: 09:30-21:30 server-local.
# - Explicit 商品推广/全部商品 preparation.
# - Full card scan updates last_checked/last_seen and records field changes.
# - HZ21 generates links for newly discovered SKUs when the controlled collector is available.
# - Missing/not-mainlined HZ21 collector is recorded as collect_unavailable and does not block scan observation.
# - Strong JD verification signals stop safely with checkpoint.
# - HZ23_RESUME=1 preserves successful rows from the same round.
# - Runtime evidence publishing uses JSON-only files accepted by scripts/git_publish_files_via_worktree.sh.
# - Page switching uses random sleeps, plus a longer randomized pause every 10-15 successful pages by default.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="${PROJECT_DIR}/src:${PYTHONPATH:-}"
. config/hz23-service.env
mkdir -p logs reports run data/import data/state data/history data/export

LOCK_FILE="run/hz23_mainline.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "===== SUMMARY ====="
  echo "RUN_RC=75"
  echo "STOP_REASON=mainline_lock_busy"
  exit 75
fi

PAGE_START="${HZ23_PAGE_START:-1}"
PAGE_END="${HZ23_PAGE_END:-67}"
ROUND_PAGE_START="${HZ23_ROUND_PAGE_START:-$PAGE_START}"
RESUME="${HZ23_RESUME:-0}"
ITEM_MIN="$HZ23_ITEM_SLEEP_MIN"
ITEM_MAX="$HZ23_ITEM_SLEEP_MAX"
PAGE_MIN="$HZ23_PAGE_SLEEP_MIN"
PAGE_MAX="$HZ23_PAGE_SLEEP_MAX"
LONG_PAUSE_INTERVAL_MIN="${HZ23_LONG_PAUSE_INTERVAL_MIN:-10}"
LONG_PAUSE_INTERVAL_MAX="${HZ23_LONG_PAUSE_INTERVAL_MAX:-15}"
LONG_PAUSE_MIN="${HZ23_LONG_PAGE_SLEEP_MIN:-600}"
LONG_PAUSE_MAX="${HZ23_LONG_PAGE_SLEEP_MAX:-1200}"
LONG_PAUSE_PROGRESS=0
LIMIT="$HZ23_LIMIT"
ROUND_ID="${HZ23_ROUND_ID:-$(date +%Y%m%d_%H%M%S)}"
DAY_START="$HZ23_DAY_START"
DAY_END="$HZ23_DAY_END"
ROWS="reports/hz23_round_${ROUND_ID}_rows.jsonl"
SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"
LATEST_SUMMARY="reports/hz23_round_latest.json"
RESUME_SUMMARY="${HZ23_RESUME_SUMMARY:-$LATEST_SUMMARY}"
PREVIOUS_DURATION_SECONDS=0

random_float() {
  python3 - "$1" "$2" <<'PY'
import random, sys
lo=float(sys.argv[1]); hi=float(sys.argv[2])
if hi < lo:
    lo, hi = hi, lo
print(round(random.uniform(lo, hi), 2))
PY
}

random_int() {
  python3 - "$1" "$2" <<'PY'
import random, sys
lo=int(float(sys.argv[1])); hi=int(float(sys.argv[2]))
if hi < lo:
    lo, hi = hi, lo
print(random.randint(lo, hi))
PY
}

LONG_PAUSE_NEXT_AFTER="$(random_int "$LONG_PAUSE_INTERVAL_MIN" "$LONG_PAUSE_INTERVAL_MAX")"
echo "HZ23_SLEEP_CONFIG PAGE_MIN=$PAGE_MIN PAGE_MAX=$PAGE_MAX LONG_INTERVAL=${LONG_PAUSE_INTERVAL_MIN}-${LONG_PAUSE_INTERVAL_MAX} LONG_SLEEP=${LONG_PAUSE_MIN}-${LONG_PAUSE_MAX} NEXT_LONG_AFTER=$LONG_PAUSE_NEXT_AFTER"

if [ "$RESUME" = "1" ]; then
  if [ ! -f "$RESUME_SUMMARY" ]; then
    echo "===== SUMMARY ====="
    echo "RUN_RC=2"
    echo "STOP_REASON=resume_summary_missing"
    exit 2
  fi
  PREVIOUS_DURATION_SECONDS="$(python3 - "$RESUME_SUMMARY" "$ROUND_ID" "$ROWS" <<'PY'
import json,sys
from pathlib import Path
source=Path(sys.argv[1]); round_id=sys.argv[2]; rows_path=Path(sys.argv[3])
x=json.loads(source.read_text(encoding='utf-8'))
if str(x.get('round_id') or '') != round_id:
    raise SystemExit('resume_round_id_mismatch')
rows_by_page={}
for row in x.get('rows') or []:
    page=row.get('page')
    if row.get('ok') is True and isinstance(page,int):
        rows_by_page[page]=row
text=''.join(json.dumps(rows_by_page[p],ensure_ascii=False,sort_keys=True)+'\n' for p in sorted(rows_by_page))
rows_path.write_text(text,encoding='utf-8')
print(int(x.get('duration_seconds') or 0))
PY
)"
  SEED_RC=$?
  if [ "$SEED_RC" != "0" ]; then
    echo "===== SUMMARY ====="
    echo "RUN_RC=$SEED_RC"
    echo "STOP_REASON=resume_seed_failed"
    exit "$SEED_RC"
  fi
else
  : > "$ROWS"
fi

STOP_PAGE=""
STOP_REASON=""
RUN_RC=0
START_EPOCH="$(date +%s)"

inside_daytime() {
  python3 - "$DAY_START" "$DAY_END" <<'PY'
from datetime import datetime
import sys
start,end=sys.argv[1],sys.argv[2]
now=datetime.now()
cur=now.hour*60+now.minute
sh,sm=map(int,start.split(':')); eh,em=map(int,end.split(':'))
print('true' if sh*60+sm <= cur < eh*60+em else 'false')
PY
}

append_failed_row() {
  python3 - "$1" "$2" "$ROWS" <<'PY'
import json,sys
from pathlib import Path
row={'page':int(sys.argv[1]),'ok':False,'reason':sys.argv[2],'scan_ok':False,'total_ok':0,'total_fail':0,'known_sku_count':None}
Path(sys.argv[3]).open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
PY
}

for PAGE_NO in $(seq "$PAGE_START" "$PAGE_END"); do
  if [ "$(inside_daytime)" != "true" ]; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="outside_daytime"
    RUN_RC=88
    echo "HZ23_STOP PAGE=$PAGE_NO REASON=$STOP_REASON DAY_WINDOW=$DAY_START-$DAY_END"
    break
  fi

  PREP="reports/hz23_prepare_page${PAGE_NO}_latest.json"
  SCAN="reports/hz23_scan_page${PAGE_NO}_latest.json"
  COLLECT="reports/hz23_collect_page_${PAGE_NO}_latest.json"
  rm -f "$PREP" "$SCAN" "$COLLECT" reports/hz21_strict_card_dom_recover_latest.json

  echo "===== HZ23 prepare page ${PAGE_NO} ====="
  .venv-browser/bin/python run/hz22_prepare_all_product_page.py "$PAGE_NO" "$PREP"
  PREP_RC=$?
  if [ "$PREP_RC" != "0" ]; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="prep_entry_failed"
    RUN_RC="$PREP_RC"
    append_failed_row "$PAGE_NO" "$STOP_REASON"
    break
  fi
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
    x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print(x.get('reason') or '')
except Exception:
    print('prep_report_error')
PY
)"
  echo "PAGE=$PAGE_NO PREP_RC=$PREP_RC PREP_OK=$PREP_OK PREP_REASON=$PREP_REASON"

  if [ "$PREP_OK" != "true" ]; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="$PREP_REASON"
    RUN_RC=99
    append_failed_row "$PAGE_NO" "$STOP_REASON"
    break
  fi

  echo "===== HZ23 scan page ${PAGE_NO} ====="
  .venv-browser/bin/python run/hz23_scan_current_page.py "$PAGE_NO" "$ROUND_ID" "$SCAN"
  SCAN_RC=$?
  if [ "$SCAN_RC" != "0" ]; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="scan_entry_failed"
    RUN_RC="$SCAN_RC"
    append_failed_row "$PAGE_NO" "$STOP_REASON"
    break
  fi
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
  if [ "$SCAN_OK" != "true" ]; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="scan_failed"
    RUN_RC=98
    append_failed_row "$PAGE_NO" "$STOP_REASON"
    break
  fi

  echo "===== HZ23 collect new SKUs page ${PAGE_NO} ====="
  HZ21_PAGE_SEQUENCE="$PAGE_NO" \
  HZ21_LIMIT="$LIMIT" \
  HZ21_WAIT=10 \
  HZ21_FAIL_FUSE=6 \
  HZ21_ITEM_SLEEP_MIN="$ITEM_MIN" \
  HZ21_ITEM_SLEEP_MAX="$ITEM_MAX" \
  bash scripts/hz21_run_strong_risk_collector.sh
  COLLECT_RC=$?
  cp reports/hz21_strict_card_dom_recover_latest.json "$COLLECT" 2>/dev/null || true

  python3 - "$PAGE_NO" "$COLLECT_RC" "$SCAN" "$ROWS" <<'PY'
import json,sys
from pathlib import Path
page=int(sys.argv[1]); rc=int(sys.argv[2]); scan_path=Path(sys.argv[3]); out=Path(sys.argv[4])
collect_path=Path('reports/hz21_strict_card_dom_recover_latest.json')
collect=json.loads(collect_path.read_text(encoding='utf-8')) if collect_path.exists() else {}
scan=json.loads(scan_path.read_text(encoding='utf-8')) if scan_path.exists() else {}
reason=collect.get('reason')
soft_reasons={'runtime_collector_missing','hz21_collector_not_mainlined'}
collect_ok=bool(collect.get('ok'))
collect_unavailable=(rc != 0 and str(reason or '') in soft_reasons)
row={
 'page':page,'rc':rc,'ok':bool(scan.get('ok')) and (collect_ok or collect_unavailable),
 'reason':reason,'scan_ok':scan.get('ok'),'scanned':scan.get('scanned',0),
 'new_catalog':scan.get('new',0),'changed_catalog':scan.get('changed',0),'unchanged_catalog':scan.get('unchanged',0),
 'collect_ok':collect_ok,'collect_unavailable':collect_unavailable,
 'total_ok':collect.get('total_ok',0),'total_fail':collect.get('total_fail',0),
 'known_sku_count':collect.get('known_sku_count'),
 'page_summary':(collect.get('page_summary') or {}).get(str(page))
}
out.open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'event':'HZ23_PAGE_DONE',**row},ensure_ascii=False,sort_keys=True))
PY

  RESULT_REASON="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz21_strict_card_dom_recover_latest.json')
try:
    print(json.loads(p.read_text(encoding='utf-8')).get('reason') or '')
except Exception:
    print('collector_report_error')
PY
)"
  if echo "$RESULT_REASON" | grep -q '^risk_'; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="$RESULT_REASON"
    RUN_RC="$COLLECT_RC"
    break
  fi
  if [ "$COLLECT_RC" != "0" ]; then
    case "$RESULT_REASON" in
      runtime_collector_missing|hz21_collector_not_mainlined)
        echo "HZ23_COLLECT_SOFT_FAIL PAGE=$PAGE_NO REASON=$RESULT_REASON"
        ;;
      *)
        STOP_PAGE="$PAGE_NO"
        STOP_REASON="${RESULT_REASON:-collector_failed}"
        RUN_RC="$COLLECT_RC"
        break
        ;;
    esac
  fi

  if [ "$PAGE_NO" -lt "$PAGE_END" ]; then
    LONG_PAUSE_PROGRESS=$((LONG_PAUSE_PROGRESS + 1))
    if [ "$LONG_PAUSE_PROGRESS" -ge "$LONG_PAUSE_NEXT_AFTER" ]; then
      SLEEP_S="$(random_float "$LONG_PAUSE_MIN" "$LONG_PAUSE_MAX")"
      echo "HZ23_PAGE_LONG_SLEEP PAGE=$PAGE_NO SECONDS=$SLEEP_S AFTER_PAGES=$LONG_PAUSE_PROGRESS NEXT_INTERVAL_RANGE=${LONG_PAUSE_INTERVAL_MIN}-${LONG_PAUSE_INTERVAL_MAX}"
      sleep "$SLEEP_S"
      LONG_PAUSE_PROGRESS=0
      LONG_PAUSE_NEXT_AFTER="$(random_int "$LONG_PAUSE_INTERVAL_MIN" "$LONG_PAUSE_INTERVAL_MAX")"
      echo "HZ23_NEXT_LONG_SLEEP_AFTER PAGES=$LONG_PAUSE_NEXT_AFTER"
    else
      SLEEP_S="$(random_float "$PAGE_MIN" "$PAGE_MAX")"
      echo "HZ23_PAGE_SLEEP PAGE=$PAGE_NO SECONDS=$SLEEP_S LONG_PROGRESS=$LONG_PAUSE_PROGRESS LONG_NEXT_AFTER=$LONG_PAUSE_NEXT_AFTER"
      sleep "$SLEEP_S"
    fi
  fi
done

END_EPOCH="$(date +%s)"
python3 - "$ROUND_PAGE_START" "$PAGE_END" "$ROWS" "$SUMMARY" "$LATEST_SUMMARY" "$STOP_PAGE" "$STOP_REASON" "$ROUND_ID" "$START_EPOCH" "$END_EPOCH" "$PREVIOUS_DURATION_SECONDS" <<'PY'
import json,sys
from pathlib import Path
start,end=int(sys.argv[1]),int(sys.argv[2])
rows_path,summary,latest=map(Path,sys.argv[3:6])
stop_page=sys.argv[6] or None; stop_reason=sys.argv[7] or None; round_id=sys.argv[8]
start_epoch,end_epoch=int(sys.argv[9]),int(sys.argv[10]); previous=int(sys.argv[11])
rows=[]
if rows_path.exists():
    rows=[json.loads(x) for x in rows_path.read_text(encoding='utf-8').splitlines() if x.strip()]
rows_by_page={}
for row in rows:
    page=row.get('page')
    if isinstance(page,int): rows_by_page[page]=row
rows=[rows_by_page[p] for p in sorted(rows_by_page)]
completed=[r.get('page') for r in rows if r.get('ok') is True]
known=[r.get('known_sku_count') for r in rows if r.get('known_sku_count') is not None]
unfinished=[p for p in range(start,end+1) if p not in completed]
out={
 'round_id':round_id,'pages':list(range(start,end+1)),'rows':rows,'completed_pages':completed,'unfinished_pages':unfinished,
 'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),
 'scanned_total':sum(int(r.get('scanned') or 0) for r in rows),'catalog_new':sum(int(r.get('new_catalog') or 0) for r in rows),
 'catalog_changed':sum(int(r.get('changed_catalog') or 0) for r in rows),'catalog_unchanged':sum(int(r.get('unchanged_catalog') or 0) for r in rows),
 'collect_unavailable_pages':[r.get('page') for r in rows if r.get('collect_unavailable') is True],
 'last_known_sku_count':known[-1] if known else None,'stop_page':int(stop_page) if stop_page else None,'stop_reason':stop_reason,
 'commercial_segment_complete':len(unfinished)==0 and not stop_reason,'duration_seconds':previous+max(0,end_epoch-start_epoch),
 'resumed':previous>0
}
text=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)
summary.write_text(text,encoding='utf-8')
latest.write_text(text,encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,sort_keys=True))
PY

COMPLETE="$(python3 - "$SUMMARY" <<'PY'
import json,sys
from pathlib import Path
try:
    print('true' if json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')).get('commercial_segment_complete') else 'false')
except Exception:
    print('false')
PY
)"
if [ "$COMPLETE" = "true" ]; then
  .venv-browser/bin/python run/hz23_finalize_round.py "$ROUND_ID" "$SUMMARY"
fi

PUBLISH_FILES=("$SUMMARY" "$LATEST_SUMMARY")
for f in reports/hz23_prepare_page*_latest.json reports/hz23_scan_page*_latest.json reports/hz23_collect_page_*_latest.json reports/hz21_strict_card_dom_recover_latest.json data/export/aideal_cps_products_commercial_candidate_manifest.json; do
  [ -f "$f" ] && PUBLISH_FILES+=("$f")
done
bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 observation round ${ROUND_ID}" \
  "${PUBLISH_FILES[@]}" \
  > logs/hz23_round_publish.log 2>&1
PUBLISH_RC=$?

echo "===== SUMMARY ====="
echo "RUN_RC=$RUN_RC"
echo "ROUND_ID=$ROUND_ID"
echo "PAGE_START=$PAGE_START"
echo "PAGE_END=$PAGE_END"
echo "STOP_PAGE=$STOP_PAGE"
echo "STOP_REASON=$STOP_REASON"
echo "RESUME=$RESUME"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "SUMMARY_JSON=$SUMMARY"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
git status --short | head -n 60

if [ "$PUBLISH_RC" != "0" ] && [ "$RUN_RC" = "0" ]; then
  exit 1
fi
exit "$RUN_RC"
