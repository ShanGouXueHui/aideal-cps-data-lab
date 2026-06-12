#!/usr/bin/env bash
# Run HZ21 strict DOM-card SKU recovery smoke for page 49 and publish report to GitHub.
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
  LOG="logs/hz21_strict_card_dom_page49_smoke_${TS}.log"
  JSON="reports/hz21_strict_card_dom_recover_latest.json"
  MD="docs/ops/DL2_HZ21_STRICT_CARD_DOM_PAGE49_SMOKE.md"

  echo "===== HZ21 strict-card-dom page49 smoke ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop collectors only, keep browser/supervisor ====="
  pkill -f "run/hz17_recover_short_url_page.py" || true
  pkill -f "run/hz18_card_click_recover_page.py" || true
  pkill -f "run/hz20_mouse_click_recover_page.py" || true
  pkill -f "run/hz21_strict_card_dom_recover_page.py" || true
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 3
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz17_recover|hz18_card|hz20_mouse|hz21_strict|chrome.*19228" | head -n 100 || true

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile run/hz21_strict_card_dom_recover_page.py
  STATIC_RC=$?

  echo "===== run HZ21 strict-card-dom smoke ====="
  HZ21_PAGE_SEQUENCE=49 HZ21_LIMIT=20 HZ21_WAIT=10 HZ21_FAIL_FUSE=6 HZ21_ITEM_SLEEP_MIN=1 HZ21_ITEM_SLEEP_MAX=3 .venv-browser/bin/python run/hz21_strict_card_dom_recover_page.py > "$LOG" 2>&1
  HZ21_RC=$?

  echo "===== render markdown summary ====="
  python3 - <<'PY'
import json
from pathlib import Path
j=Path('reports/hz21_strict_card_dom_recover_latest.json')
md=Path('docs/ops/DL2_HZ21_STRICT_CARD_DOM_PAGE49_SMOKE.md')
if not j.exists():
    md.write_text('# DL2 HZ21 Strict Card DOM Page49 Smoke\n\nNo JSON report found.\n', encoding='utf-8')
else:
    x=json.loads(j.read_text(encoding='utf-8'))
    lines=[]
    lines.append('# DL2 HZ21 Strict Card DOM Page49 Smoke')
    lines.append('')
    for k in ['ts','ok','reason','pages','limit','wait','total_ok','total_fail','known_sku_count','quarantine']:
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
    lines.append(json.dumps((x.get('results') or [])[-30:], ensure_ascii=False, indent=2)[:20000])
    lines.append('```')
    md.write_text('\n'.join(lines), encoding='utf-8')
PY

  echo "===== commit reports/data/log ====="
  git add "$JSON" "$MD" "$LOG" run/hz21_strict_card_dom_recover_page.py scripts/hz21_run_strict_card_dom_page49_smoke.sh data/import/hz_jd_union_all_product_full_links_latest.jsonl data/import/hz_jd_union_product_all_full_links_latest.jsonl run/hz14_all_product_full_report_latest.json run/hz14_all_product_full_state.json
  git commit -m "docs: publish HZ21 strict card dom page49 smoke" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ21_RC=$HZ21_RC"
  echo "LOG=$LOG"
  echo "REPORT=$JSON"
  echo "MD=$MD"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
