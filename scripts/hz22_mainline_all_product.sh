#!/usr/bin/env bash
# Explicitly selects 商品推广/全部商品, jumps via the 4000-row pager, then runs HZ21.
# Stops on strong JD verification signals and preserves an aggregate checkpoint.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports docs/ops run data/import

PAGE_START="${HZ22_PAGE_START:-61}"
PAGE_END="${HZ22_PAGE_END:-67}"
ITEM_MIN="${HZ22_ITEM_SLEEP_MIN:-3}"
ITEM_MAX="${HZ22_ITEM_SLEEP_MAX:-7}"
PAGE_MIN="${HZ22_PAGE_SLEEP_MIN:-90}"
PAGE_MAX="${HZ22_PAGE_SLEEP_MAX:-210}"
LIMIT="${HZ22_LIMIT:-25}"
ROWS="reports/hz22_pages_${PAGE_START}_${PAGE_END}_rows.jsonl"
SUMMARY="reports/hz22_pages_${PAGE_START}_${PAGE_END}_latest.json"
MD="docs/ops/DL2_HZ22_PAGES_${PAGE_START}_${PAGE_END}.md"

: > "$ROWS"
STOP_PAGE=""
STOP_REASON=""
RUN_RC=0

for PAGE_NO in $(seq "$PAGE_START" "$PAGE_END"); do
  PREP="reports/hz22_prepare_all_product_page${PAGE_NO}_latest.json"
  echo "===== HZ22 prepare page ${PAGE_NO} ====="
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
row={'page':int(sys.argv[1]),'ok':False,'reason':sys.argv[2],'total_ok':0,'total_fail':0,'known_sku_count':None}
Path(sys.argv[3]).open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
PY
    break
  fi

  echo "===== HZ22 collect page ${PAGE_NO} ====="
  HZ21_PAGE_SEQUENCE="$PAGE_NO" \
  HZ21_LIMIT="$LIMIT" \
  HZ21_WAIT=10 \
  HZ21_FAIL_FUSE=6 \
  HZ21_ITEM_SLEEP_MIN="$ITEM_MIN" \
  HZ21_ITEM_SLEEP_MAX="$ITEM_MAX" \
  bash scripts/hz21_run_strong_risk_collector.sh
  COLLECT_RC=$?

  cp reports/hz21_strict_card_dom_recover_latest.json "reports/hz22_page_${PAGE_NO}_latest.json" 2>/dev/null || true
  python3 - "$PAGE_NO" "$COLLECT_RC" "$ROWS" <<'PY'
import json,sys
from pathlib import Path
page=int(sys.argv[1]); rc=int(sys.argv[2]); out=Path(sys.argv[3])
p=Path('reports/hz21_strict_card_dom_recover_latest.json')
x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
row={
 'page':page,'rc':rc,'ok':x.get('ok'),'reason':x.get('reason'),
 'total_ok':x.get('total_ok',0),'total_fail':x.get('total_fail',0),
 'known_sku_count':x.get('known_sku_count'),
 'page_summary':(x.get('page_summary') or {}).get(str(page))
}
out.open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'event':'HZ22_PAGE_DONE',**row},ensure_ascii=False,sort_keys=True))
PY

  RESULT_REASON="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('reports/hz21_strict_card_dom_recover_latest.json')
try:
    x=json.loads(p.read_text(encoding='utf-8'))
    print(x.get('reason') or '')
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
    echo "HZ22_PAGE_SLEEP PAGE=$PAGE_NO SECONDS=$SLEEP_S"
    sleep "$SLEEP_S"
  fi
done

python3 - "$PAGE_START" "$PAGE_END" "$ROWS" "$SUMMARY" "$MD" "$STOP_PAGE" "$STOP_REASON" <<'PY'
import json,sys
from pathlib import Path
start,end=int(sys.argv[1]),int(sys.argv[2])
rows_path,out_path,md_path=Path(sys.argv[3]),Path(sys.argv[4]),Path(sys.argv[5])
stop_page=sys.argv[6] or None; stop_reason=sys.argv[7] or None
rows=[]
if rows_path.exists():
    rows=[json.loads(x) for x in rows_path.read_text(encoding='utf-8').splitlines() if x.strip()]
completed=[r.get('page') for r in rows if r.get('ok') is True]
known=[r.get('known_sku_count') for r in rows if r.get('known_sku_count') is not None]
unfinished=[p for p in range(start,end+1) if p not in completed]
out={
 'pages':list(range(start,end+1)),'rows':rows,'completed_pages':completed,
 'unfinished_pages':unfinished,'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),
 'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),
 'last_known_sku_count':known[-1] if known else None,
 'stop_page':int(stop_page) if stop_page else None,'stop_reason':stop_reason,
 'commercial_segment_complete':len(unfinished)==0 and not stop_reason
}
out_path.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
md_path.write_text('# DL2 HZ22 All Product Mainline\n\n```json\n'+json.dumps(out,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,sort_keys=True))
PY

for f in "$ROWS" "$SUMMARY" "$MD" reports/hz22_prepare_all_product_page*_latest.json reports/hz22_page_*_latest.json reports/hz21_strict_card_dom_recover_latest.json data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json; do
  if [ -e "$f" ]; then git add "$f" 2>/dev/null || true; fi
done
git commit -m "docs: publish HZ22 all-product pages ${PAGE_START}-${PAGE_END}" >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

echo "===== SUMMARY ====="
echo "RUN_RC=$RUN_RC"
echo "PAGE_START=$PAGE_START"
echo "PAGE_END=$PAGE_END"
echo "STOP_PAGE=$STOP_PAGE"
echo "STOP_REASON=$STOP_REASON"
echo "SUMMARY_JSON=$SUMMARY"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
git status --short | head -n 60
