#!/usr/bin/env bash
# HZ21 mainline remaining collector.
# Runs the validated safe-page flow one page at a time, stops on JD verification,
# preserves completed progress, and builds one aggregate report.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import

  PAGE_START="${HZ21_MAINLINE_PAGE_START:-58}"
  PAGE_END="${HZ21_MAINLINE_PAGE_END:-67}"
  ITEM_SLEEP_MIN="${HZ21_MAINLINE_ITEM_SLEEP_MIN:-3}"
  ITEM_SLEEP_MAX="${HZ21_MAINLINE_ITEM_SLEEP_MAX:-7}"
  PAGE_SLEEP_MIN="${HZ21_MAINLINE_PAGE_SLEEP_MIN:-90}"
  PAGE_SLEEP_MAX="${HZ21_MAINLINE_PAGE_SLEEP_MAX:-210}"
  TEMPLATE="scripts/hz21_run_safe_pages_50_52.sh"
  AGG_JSON="reports/hz21_safe_pages_${PAGE_START}_${PAGE_END}_latest.json"
  AGG_MD="docs/ops/DL2_HZ21_SAFE_PAGES_${PAGE_START}_${PAGE_END}_MAINLINE.md"
  AGG_ROWS="reports/hz21_safe_pages_${PAGE_START}_${PAGE_END}_aggregate_rows.jsonl"

  echo "===== HZ21 mainline safe remaining runner ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PAGE_START=$PAGE_START"
  echo "PAGE_END=$PAGE_END"
  echo "ITEM_SLEEP=${ITEM_SLEEP_MIN}-${ITEM_SLEEP_MAX}s"
  echo "PAGE_SLEEP=${PAGE_SLEEP_MIN}-${PAGE_SLEEP_MAX}s"

  : > "$AGG_ROWS"
  RUN_RC=0
  STOP_REASON=""
  STOP_PAGE=""

  if [ ! -f "$TEMPLATE" ]; then
    RUN_RC=2
    STOP_REASON="template_not_found"
    echo "ERROR=TEMPLATE_NOT_FOUND TEMPLATE=$TEMPLATE"
  else
    for PAGE_NO in $(seq "$PAGE_START" "$PAGE_END"); do
      GENERATED="/tmp/hz21_safe_page_${PAGE_NO}_$$_generated.sh"
      cp "$TEMPLATE" "$GENERATED"

      python3 - "$GENERATED" "$PAGE_NO" "$ITEM_SLEEP_MIN" "$ITEM_SLEEP_MAX" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
page=sys.argv[2]
item_min=sys.argv[3]
item_max=sys.argv[4]
s=p.read_text(encoding='utf-8')
s=s.replace('50-52', f'{page}-{page}')
s=s.replace('50_52', f'{page}_{page}')
s=s.replace('for PAGE_NO in 50 51 52; do', f'for PAGE_NO in {page}; do')
s=s.replace("'pages':[50,51,52]", f"'pages':[{page}]")
s=s.replace('pages 50-52', f'page {page}')
s=s.replace('HZ21_ITEM_SLEEP_MIN=1 HZ21_ITEM_SLEEP_MAX=3', f'HZ21_ITEM_SLEEP_MIN={item_min} HZ21_ITEM_SLEEP_MAX={item_max}')
p.write_text(s, encoding='utf-8')
print(f'GENERATED={p}')
PY
      GEN_RC=$?

      if [ "$GEN_RC" != "0" ]; then
        RUN_RC=$GEN_RC
        STOP_REASON="generate_failed"
        STOP_PAGE="$PAGE_NO"
        echo "MAINLINE_STOP PAGE=$PAGE_NO REASON=$STOP_REASON RC=$RUN_RC"
        rm -f "$GENERATED"
        break
      fi

      chmod +x "$GENERATED"
      echo "===== run safe page ${PAGE_NO} ====="
      bash "$GENERATED"
      PAGE_RC=$?
      rm -f "$GENERATED"

      PAGE_SUMMARY="reports/hz21_safe_pages_${PAGE_NO}_${PAGE_NO}_latest.json"
      PREP_JSON="reports/hz21_prepare_4000_pager_page${PAGE_NO}_latest.json"

      python3 - "$PAGE_NO" "$PAGE_RC" "$PAGE_SUMMARY" "$PREP_JSON" "$AGG_ROWS" <<'PY'
import json, sys
from pathlib import Path
page=int(sys.argv[1]); rc=int(sys.argv[2])
summary=Path(sys.argv[3]); prep=Path(sys.argv[4]); out=Path(sys.argv[5])
row={'page':page,'rc':rc,'ok':False,'reason':'summary_not_found','total_ok':0,'total_fail':0,'known_sku_count':None}
if summary.exists():
    try:
        x=json.loads(summary.read_text(encoding='utf-8'))
        rows=x.get('rows') or []
        if rows:
            row=dict(rows[-1])
            row['page']=page
            row['rc']=rc
        else:
            row.update(ok=bool(x.get('total_ok') is not None), reason='empty_rows', total_ok=x.get('total_ok',0), total_fail=x.get('total_fail',0), known_sku_count=x.get('last_known_sku_count'))
    except Exception as exc:
        row['reason']='summary_parse_error:'+repr(exc)
if prep.exists():
    try:
        p=json.loads(prep.read_text(encoding='utf-8'))
        row['prepare_ok']=p.get('ok')
        row['prepare_reason']=p.get('reason')
        row['prepare_after']=p.get('after')
        if not p.get('ok'):
            row['ok']=False
            row['reason']=p.get('reason') or row.get('reason')
    except Exception as exc:
        row['prepare_parse_error']=repr(exc)
out.open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'event':'MAINLINE_PAGE_RESULT',**row},ensure_ascii=False,sort_keys=True))
PY

      PREP_REASON="$(python3 - "$PREP_JSON" <<'PY'
import json, sys
from pathlib import Path
try:
    x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print(x.get('reason') or '')
except Exception:
    print('')
PY
)"

      git add reports/hz21_strict_card_dom_recover_latest.json 2>/dev/null || true
      git commit -m "docs: update HZ21 latest report page ${PAGE_NO}" >/dev/null 2>&1 || true
      GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
      GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
      GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

      if echo "$PREP_REASON" | grep -q '^risk_'; then
        RUN_RC=99
        STOP_REASON="$PREP_REASON"
        STOP_PAGE="$PAGE_NO"
        echo "MAINLINE_STOP_REQUIRED=JD_VERIFICATION PAGE=$PAGE_NO REASON=$PREP_REASON"
        break
      fi

      if [ "$PAGE_RC" != "0" ]; then
        RUN_RC=$PAGE_RC
        STOP_REASON="page_runner_failed"
        STOP_PAGE="$PAGE_NO"
        echo "MAINLINE_STOP PAGE=$PAGE_NO REASON=$STOP_REASON RC=$RUN_RC"
        break
      fi

      if [ "$PAGE_NO" -lt "$PAGE_END" ]; then
        PAGE_SLEEP="$(python3 - "$PAGE_SLEEP_MIN" "$PAGE_SLEEP_MAX" <<'PY'
import random, sys
lo=float(sys.argv[1]); hi=float(sys.argv[2])
print(round(random.uniform(lo,hi),2))
PY
)"
        echo "MAINLINE_PAGE_SLEEP PAGE=$PAGE_NO SECONDS=$PAGE_SLEEP"
        sleep "$PAGE_SLEEP"
      fi
    done
  fi

  python3 - "$PAGE_START" "$PAGE_END" "$AGG_ROWS" "$AGG_JSON" "$AGG_MD" "$STOP_PAGE" "$STOP_REASON" <<'PY'
import json, sys
from pathlib import Path
start=int(sys.argv[1]); end=int(sys.argv[2])
rows_path=Path(sys.argv[3]); out_path=Path(sys.argv[4]); md_path=Path(sys.argv[5])
stop_page=sys.argv[6] or None; stop_reason=sys.argv[7] or None
rows=[]
if rows_path.exists():
    for line in rows_path.read_text(encoding='utf-8',errors='replace').splitlines():
        if line.strip():
            try: rows.append(json.loads(line))
            except Exception: pass
known=[r.get('known_sku_count') for r in rows if r.get('known_sku_count') is not None]
completed=[r.get('page') for r in rows if r.get('ok') is True]
attempted=[r.get('page') for r in rows]
unfinished=[p for p in range(start,end+1) if p not in attempted or p not in completed]
out={
    'pages':list(range(start,end+1)),
    'rows':rows,
    'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),
    'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),
    'last_known_sku_count':known[-1] if known else None,
    'completed_pages':completed,
    'unfinished_pages':unfinished,
    'stop_page':int(stop_page) if stop_page else None,
    'stop_reason':stop_reason,
    'commercial_segment_complete':len(unfinished)==0 and not stop_reason,
}
out_path.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
md=['# DL2 HZ21 Mainline Safe Pages', '', '```json', json.dumps(out,ensure_ascii=False,indent=2), '```']
md_path.write_text('\n'.join(md),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,sort_keys=True))
PY

  echo "===== commit aggregate result ====="
  for f in "$AGG_JSON" "$AGG_MD" "$AGG_ROWS" reports/hz21_strict_card_dom_recover_latest.json; do
    if [ -f "$f" ]; then git add "$f"; fi
  done
  git commit -m "docs: publish HZ21 mainline pages ${PAGE_START}-${PAGE_END}" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "RUN_RC=$RUN_RC"
  echo "PAGE_START=$PAGE_START"
  echo "PAGE_END=$PAGE_END"
  echo "STOP_PAGE=$STOP_PAGE"
  echo "STOP_REASON=$STOP_REASON"
  echo "SUMMARY_JSON=$AGG_JSON"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 80
fi
