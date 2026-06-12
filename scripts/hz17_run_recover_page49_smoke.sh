#!/usr/bin/env bash
# Run HZ17 short-url recovery smoke for page 49 and publish report to GitHub.
# No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG="logs/hz17_recover_page49_smoke_${TS}.log"
  JSON="reports/hz17_recover_short_url_page_latest.json"
  MD="docs/ops/DL2_HZ17_RECOVER_PAGE49_SMOKE.md"

  echo "===== HZ17 recover page49 smoke ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop HZ15 collector only, keep browser/supervisor ====="
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 3
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz15_jump_pages_collector|hz17_recover|chrome.*19228" | head -n 100 || true

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile run/hz17_recover_short_url_page.py
  STATIC_RC=$?

  echo "===== run recovery smoke ====="
  HZ17_PAGE_SEQUENCE=49 HZ17_LIMIT=20 HZ17_RETRY=1 HZ17_FAIL_FUSE=5 HZ17_ITEM_SLEEP_MIN=2 HZ17_ITEM_SLEEP_MAX=5 .venv-browser/bin/python run/hz17_recover_short_url_page.py > "$LOG" 2>&1
  HZ17_RC=$?

  echo "===== render markdown summary ====="
  python3 - <<'PY'
import json
from pathlib import Path
j=Path('reports/hz17_recover_short_url_page_latest.json')
md=Path('docs/ops/DL2_HZ17_RECOVER_PAGE49_SMOKE.md')
if not j.exists():
    md.write_text('# DL2 HZ17 Recover Page49 Smoke\n\nNo JSON report found.\n', encoding='utf-8')
else:
    x=json.loads(j.read_text(encoding='utf-8'))
    lines=[]
    lines.append('# DL2 HZ17 Recover Page49 Smoke')
    lines.append('')
    for k in ['ts','ok','reason','pages','limit','retry','total_ok','total_fail','known_sku_count']:
        lines.append(f'- {k}: `{x.get(k)}`')
    lines.append(f'- page_summary: `{json.dumps(x.get("page_summary"), ensure_ascii=False)}`')
    lines.append('')
    lines.append('## initial/final')
    lines.append('```json')
    lines.append(json.dumps({'initial':x.get('initial'), 'page_ready':x.get('page_ready'), 'final':x.get('final')}, ensure_ascii=False, indent=2)[:6000])
    lines.append('```')
    lines.append('')
    lines.append('## results tail')
    lines.append('```json')
    lines.append(json.dumps((x.get('results') or [])[-20:], ensure_ascii=False, indent=2)[:12000])
    lines.append('```')
    md.write_text('\n'.join(lines), encoding='utf-8')
PY

  echo "===== commit reports/data/log ====="
  git add "$JSON" "$MD" "$LOG" run/hz17_recover_short_url_page.py scripts/hz17_run_recover_page49_smoke.sh data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json
  git commit -m "docs: publish HZ17 page49 recovery smoke" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ17_RC=$HZ17_RC"
  echo "LOG=$LOG"
  echo "REPORT=$JSON"
  echo "MD=$MD"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
