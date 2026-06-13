#!/usr/bin/env bash
# HZ23 commercial-observation refresh mainline.
# - Daytime only: 09:30-21:30 server-local.
# - Explicit 商品推广/全部商品 preparation.
# - Full card scan updates last_checked/last_seen and records field changes.
# - HZ21 only generates links for newly discovered SKUs.
# - Strong JD verification signals stop safely with checkpoint.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports docs/ops run data/import data/state data/history data/export

PAGE_START="${HZ23_PAGE_START:-1}"
PAGE_END="${HZ23_PAGE_END:-67}"
ITEM_MIN="${HZ23_ITEM_SLEEP_MIN:-3}"
ITEM_MAX="${HZ23_ITEM_SLEEP_MAX:-7}"
PAGE_MIN="${HZ23_PAGE_SLEEP_MIN:-90}"
PAGE_MAX="${HZ23_PAGE_SLEEP_MAX:-210}"
LIMIT="${HZ23_LIMIT:-25}"
ROUND_ID="${HZ23_ROUND_ID:-$(date +%Y%m%d_%H%M%S)}"
DAY_START="${HZ23_DAY_START:-09:30}"
DAY_END="${HZ23_DAY_END:-21:30}"
ROWS="reports/hz23_round_${ROUND_ID}_rows.jsonl"
SUMMARY="reports/hz23_round_${ROUND_ID}_latest.json"
LATEST_SUMMARY="reports/hz23_round_latest.json"
MD="docs/ops/DL2_HZ23_ROUND_${ROUND_ID}.md"

: > "$ROWS"
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

  echo "===== HZ23 prepare page ${PAGE_NO} ====="
  .venv-browser/bin/python run/hz22_prepare_all_product_page.py "$PAGE_NO" "$PREP"
  PREP_RC=$?
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
    python3 - "$PAGE_NO" "$PREP_REASON" "$ROWS" <<'PY'
import json,sys
from pathlib import Path
row={'page':int(sys.argv[1]),'ok':False,'reason':sys.argv[2],'scan_ok':False,'total_ok':0,'total_fail':0,'known_sku_count':None}
Path(sys.argv[3]).open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
PY
    break
  fi

  echo "===== HZ23 scan page ${PAGE_NO} ====="
  .venv-browser/bin/python run/hz23_scan_current_page.py "$PAGE_NO" "$ROUND_ID" "$SCAN"
  SCAN_RC=$?
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
    RUN_RC="$SCAN_RC"
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
  cp reports/hz21_strict_card_dom_recover_latest.json "reports/hz23_collect_page_${PAGE_NO}_latest.json" 2>/dev/null || true

  python3 - "$PAGE_NO" "$COLLECT_RC" "$SCAN" "$ROWS" <<'PY'
import json,sys
from pathlib import Path
page=int(sys.argv[1]); rc=int(sys.argv[2]); scan_path=Path(sys.argv[3]); out=Path(sys.argv[4])
collect_path=Path('reports/hz21_strict_card_dom_recover_latest.json')
collect=json.loads(collect_path.read_text(encoding='utf-8')) if collect_path.exists() else {}
scan=json.loads(scan_path.read_text(encoding='utf-8')) if scan_path.exists() else {}
row={
 'page':page,'rc':rc,'ok':bool(collect.get('ok')) and bool(scan.get('ok')),
 'reason':collect.get('reason'),'scan_ok':scan.get('ok'),'scanned':scan.get('scanned',0),
 'new_catalog':scan.get('new',0),'changed_catalog':scan.get('changed',0),'unchanged_catalog':scan.get('unchanged',0),
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
  if [ "$COLLECT_RC" != "0" ] || echo "$RESULT_REASON" | grep -q '^risk_'; then
    STOP_PAGE="$PAGE_NO"
    STOP_REASON="${RESULT_REASON:-collector_failed}"
    RUN_RC="$COLLECT_RC"
    break
  fi

  if [ "$PAGE_NO" -lt "$PAGE_END" ]; then
    SLEEP_S="$(python3 - "$PAGE_MIN" "$PAGE_MAX" <<'PY'
import random,sys
print(round(random.uniform(float(sys.argv[1]),float(sys.argv[2])),2))
PY
)"
    echo "HZ23_PAGE_SLEEP PAGE=$PAGE_NO SECONDS=$SLEEP_S"
    sleep "$SLEEP_S"
  fi
done

END_EPOCH="$(date +%s)"
python3 - "$PAGE_START" "$PAGE_END" "$ROWS" "$SUMMARY" "$LATEST_SUMMARY" "$MD" "$STOP_PAGE" "$STOP_REASON" "$ROUND_ID" "$START_EPOCH" "$END_EPOCH" <<'PY'
import json,sys
from pathlib import Path
start,end=int(sys.argv[1]),int(sys.argv[2])
rows_path,summary,latest,md=map(Path,sys.argv[3:7])
stop_page=sys.argv[7] or None; stop_reason=sys.argv[8] or None; round_id=sys.argv[9]
start_epoch,end_epoch=int(sys.argv[10]),int(sys.argv[11])
rows=[]
if rows_path.exists():
    rows=[json.loads(x) for x in rows_path.read_text(encoding='utf-8').splitlines() if x.strip()]
completed=[r.get('page') for r in rows if r.get('ok') is True]
known=[r.get('known_sku_count') for r in rows if r.get('known_sku_count') is not None]
unfinished=[p for p in range(start,end+1) if p not in completed]
out={
 'round_id':round_id,'pages':list(range(start,end+1)),'rows':rows,'completed_pages':completed,'unfinished_pages':unfinished,
 'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),
 'scanned_total':sum(int(r.get('scanned') or 0) for r in rows),'catalog_new':sum(int(r.get('new_catalog') or 0) for r in rows),
 'catalog_changed':sum(int(r.get('changed_catalog') or 0) for r in rows),'catalog_unchanged':sum(int(r.get('unchanged_catalog') or 0) for r in rows),
 'last_known_sku_count':known[-1] if known else None,'stop_page':int(stop_page) if stop_page else None,'stop_reason':stop_reason,
 'commercial_segment_complete':len(unfinished)==0 and not stop_reason,'duration_seconds':max(0,end_epoch-start_epoch)
}
text=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)
summary.write_text(text,encoding='utf-8'); latest.write_text(text,encoding='utf-8')
md.write_text('# DL2 HZ23 Observation Round\n\n```json\n'+text+'\n```\n',encoding='utf-8')
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

for f in "$ROWS" "$SUMMARY" "$LATEST_SUMMARY" "$MD" reports/hz23_prepare_page*_latest.json reports/hz23_scan_page*_latest.json reports/hz23_collect_page_*_latest.json reports/hz21_strict_card_dom_recover_latest.json data/export/aideal_cps_products_commercial_candidate_manifest.json; do
  if [ -e "$f" ]; then git add "$f" 2>/dev/null || true; fi
done
git commit -m "docs: publish HZ23 observation round ${ROUND_ID}" >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

echo "===== SUMMARY ====="
echo "RUN_RC=$RUN_RC"
echo "ROUND_ID=$ROUND_ID"
echo "PAGE_START=$PAGE_START"
echo "PAGE_END=$PAGE_END"
echo "STOP_PAGE=$STOP_PAGE"
echo "STOP_REASON=$STOP_REASON"
echo "SUMMARY_JSON=$SUMMARY"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
git status --short | head -n 60
