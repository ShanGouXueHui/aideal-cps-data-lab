#!/usr/bin/env bash
# HZ21 mainline remaining collector.
# It reuses the validated safe-pages template and runs a configurable page range.
# Default target after validated 50-57: pages 58-67.
# It stops immediately on JD verification/risk and preserves the last valid progress.
# No exit and no set -e are used.

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
  TEMPLATE="scripts/hz21_run_safe_pages_50_52.sh"
  GENERATED="run/hz21_run_safe_pages_${PAGE_START}_${PAGE_END}_generated.sh"

  PAGES_SPACED="$(seq "$PAGE_START" "$PAGE_END" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  PAGES_COMMA="$(seq "$PAGE_START" "$PAGE_END" | paste -sd, -)"

  echo "===== HZ21 mainline safe remaining runner ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "PAGE_START=$PAGE_START"
  echo "PAGE_END=$PAGE_END"
  echo "PAGES=$PAGES_SPACED"

  if [ ! -f "$TEMPLATE" ]; then
    echo "===== SUMMARY ====="
    echo "ERROR=TEMPLATE_NOT_FOUND"
    echo "TEMPLATE=$TEMPLATE"
  else
    cp "$TEMPLATE" "$GENERATED"
    python3 - "$GENERATED" "$PAGE_START" "$PAGE_END" "$PAGES_SPACED" "$PAGES_COMMA" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1])
start=sys.argv[2]
end=sys.argv[3]
pages_spaced=sys.argv[4]
pages_comma=sys.argv[5]
s=path.read_text(encoding='utf-8')
s=s.replace('50-52', f'{start}-{end}')
s=s.replace('50_52', f'{start}_{end}')
s=s.replace('for PAGE_NO in 50 51 52; do', f'for PAGE_NO in {pages_spaced}; do')
s=s.replace("'pages':[50,51,52]", f"'pages':[{pages_comma}]")
s=s.replace('pages 50-52', f'pages {start}-{end}')

# Read the actual prepare reason so risk/verification is distinguishable from ordinary page failure.
s=s.replace(
'''    echo "PAGE=${PAGE_NO} PREP_RC=${PREP_RC} SAFE=${SAFE}" | tee -a "$LOG"

    if [ "$SAFE" = "true" ]; then''',
'''    PREP_REASON="$(python3 - "$PREP_JSON" <<'PY_REASON'
import json, sys
from pathlib import Path
try:
  x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
  print(x.get('reason') or '')
except Exception:
  print('')
PY_REASON
)"
    echo "PAGE=${PAGE_NO} PREP_RC=${PREP_RC} SAFE=${SAFE} PREP_REASON=${PREP_REASON}" | tee -a "$LOG"

    if [ "$SAFE" = "true" ]; then'''
)

# Preserve the concrete prepare reason in the per-page report.
s=s.replace(
'''      python3 - "$PAGE_NO" <<'PY'
import json, sys
from pathlib import Path
row={'page':int(sys.argv[1]),'rc':99,'ok':False,'reason':'prepare_not_safe','total_ok':0,'total_fail':0}
Path('reports/hz21_safe_pages_'''+f'{start}_{end}'+'''_per_page.jsonl').open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\\n')
PY
    fi
    sleep 5''',
'''      python3 - "$PAGE_NO" "$PREP_REASON" <<'PY'
import json, sys
from pathlib import Path
row={'page':int(sys.argv[1]),'rc':99,'ok':False,'reason':sys.argv[2] or 'prepare_not_safe','total_ok':0,'total_fail':0}
Path('reports/hz21_safe_pages_'''+f'{start}_{end}'+'''_per_page.jsonl').open('a',encoding='utf-8').write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\\n')
PY
    fi
    if echo "$PREP_REASON" | grep -q '^risk_'; then
      echo "MAINLINE_STOP_REQUIRED=JD_VERIFICATION PAGE=${PAGE_NO} REASON=${PREP_REASON}" | tee -a "$LOG"
      break
    fi
    sleep 5'''
)

# Preserve the last non-null known_sku_count when later pages are skipped/stopped.
s=s.replace(
'''out={'pages':['''+pages_comma+'''],'rows':rows,'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),'last_known_sku_count': rows[-1].get('known_sku_count') if rows else None}''',
'''known=[r.get('known_sku_count') for r in rows if r.get('known_sku_count') is not None]
out={'pages':['''+pages_comma+'''],'rows':rows,'total_ok':sum(int(r.get('total_ok') or 0) for r in rows),'total_fail':sum(int(r.get('total_fail') or 0) for r in rows),'last_known_sku_count': known[-1] if known else None}'''
)

path.write_text(s, encoding='utf-8')
print(f'GENERATED={path}')
PY
    chmod +x "$GENERATED"

    echo "===== run generated safe-pages collector ====="
    bash "$GENERATED"
    RUN_RC=$?

    echo "===== commit generated mainline script marker ====="
    git add "$GENERATED" 2>/dev/null || true
    git commit -m "chore: keep generated HZ21 mainline safe page runner" >/dev/null 2>&1 || true
    GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
    GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
    GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

    echo "===== SUMMARY ====="
    echo "RUN_RC=$RUN_RC"
    echo "PAGE_START=$PAGE_START"
    echo "PAGE_END=$PAGE_END"
    echo "GENERATED=$GENERATED"
    echo "SUMMARY_JSON=reports/hz21_safe_pages_${PAGE_START}_${PAGE_END}_latest.json"
    echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
    git status --short | head -n 80
  fi
fi
