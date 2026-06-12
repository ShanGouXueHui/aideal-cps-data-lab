#!/usr/bin/env bash
# Run HZ18 card-scoped click recovery smoke for page 49 and publish report to GitHub.
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
  LOG="logs/hz18_card_click_page49_smoke_${TS}.log"
  JSON="reports/hz18_card_click_recover_latest.json"
  MD="docs/ops/DL2_HZ18_CARD_CLICK_PAGE49_SMOKE.md"

  echo "===== HZ18 card-click page49 smoke ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop HZ17/HZ15 collector only, keep browser/supervisor ====="
  pkill -f "run/hz17_recover_short_url_page.py" || true
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 3
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz17_recover|hz18_card|chrome.*19228" | head -n 100 || true

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile run/hz18_card_click_recover_page.py
  STATIC_RC=$?

  echo "===== run HZ18 card-click smoke ====="
  HZ18_PAGE_SEQUENCE=49 HZ18_LIMIT=15 HZ18_WAIT=8 HZ18_FAIL_FUSE=5 HZ18_ITEM_SLEEP_MIN=1 HZ18_ITEM_SLEEP_MAX=3 .venv-browser/bin/python run/hz18_card_click_recover_page.py > "$LOG" 2>&1
  HZ18_RC=$?

  echo "===== render markdown summary ====="
  python3 - <<'PY'
import json
from pathlib import Path
j=Path('reports/hz18_card_click_recover_latest.json')
md=Path('docs/ops/DL2_HZ18_CARD_CLICK_PAGE49_SMOKE.md')
if not j.exists():
    md.write_text('# DL2 HZ18 Card Click Page49 Smoke\n\nNo JSON report found.\n', encoding='utf-8')
else:
    x=json.loads(j.read_text(encoding='utf-8'))
    lines=[]
    lines.append('# DL2 HZ18 Card Click Page49 Smoke')
    lines.append('')
    for k in ['ts','ok','reason','pages','limit','wait','total_ok','total_fail','known_sku_count']:
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
    lines.append(json.dumps((x.get('results') or [])[-20:], ensure_ascii=False, indent=2)[:16000])
    lines.append('```')
    md.write_text('\n'.join(lines), encoding='utf-8')
PY

  echo "===== commit reports/data/log ====="
  git add "$JSON" "$MD" "$LOG" run/hz18_card_click_recover_page.py scripts/hz18_run_card_click_page49_smoke.sh data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json
  git commit -m "docs: publish HZ18 card click page49 smoke" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ18_RC=$HZ18_RC"
  echo "LOG=$LOG"
  echo "REPORT=$JSON"
  echo "MD=$MD"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
