#!/usr/bin/env bash
# Run HZ16 short-url diagnosis and publish compact report to GitHub.
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
  LOG="logs/hz16_short_url_diag_page49_${TS}.log"
  JSON="reports/hz16_short_url_diag_latest.json"
  MD="docs/ops/DL2_HZ16_SHORT_URL_DIAG.md"

  echo "===== HZ16 short-url diagnosis page 49 ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop collector only, keep supervisor/browser ====="
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 3
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz15_jump_pages_collector|chrome.*19228" | head -n 80 || true

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile run/hz16_short_url_diag.py
  STATIC_RC=$?

  echo "===== run diagnosis ====="
  HZ16_DIAG_PAGE=49 HZ16_DIAG_LIMIT=6 HZ16_DIAG_WAIT=12 .venv-browser/bin/python run/hz16_short_url_diag.py > "$LOG" 2>&1
  DIAG_RC=$?

  echo "===== render markdown summary ====="
  python3 - <<'PY'
import json
from pathlib import Path
j=Path('reports/hz16_short_url_diag_latest.json')
md=Path('docs/ops/DL2_HZ16_SHORT_URL_DIAG.md')
if not j.exists():
    md.write_text('# DL2 HZ16 Short URL Diagnosis\n\nNo JSON report found.\n', encoding='utf-8')
else:
    x=json.loads(j.read_text(encoding='utf-8'))
    lines=[]
    lines.append('# DL2 HZ16 Short URL Diagnosis')
    lines.append('')
    lines.append(f'- ts: `{x.get("ts")}`')
    lines.append(f'- ok: `{x.get("ok")}`')
    lines.append(f'- page_no: `{x.get("page_no")}`')
    lines.append(f'- diagnosis: `{x.get("diagnosis")}`')
    lines.append(f'- class_counts: `{json.dumps(x.get("class_counts"), ensure_ascii=False)}`')
    lines.append(f'- candidate_summary: `{json.dumps(x.get("candidate_summary"), ensure_ascii=False)[:1200]}`')
    lines.append('')
    lines.append('## Initial / after jump')
    lines.append('```json')
    lines.append(json.dumps({'initial':x.get('initial'), 'after_jump':x.get('after_jump'), 'jump':x.get('jump')}, ensure_ascii=False, indent=2)[:6000])
    lines.append('```')
    lines.append('')
    for idx,r in enumerate(x.get('results') or [],1):
        brief={k:r.get(k) for k in ['sku','title','order','class','click']}
        polls=r.get('polls') or []
        brief['last_poll']=polls[-1] if polls else None
        brief['first_poll']=polls[0] if polls else None
        brief['snapshots']=r.get('snapshots')
        brief['visible_head']=r.get('visible_head')
        lines.append(f'## Result {idx}')
        lines.append('```json')
        lines.append(json.dumps(brief, ensure_ascii=False, indent=2)[:8000])
        lines.append('```')
        lines.append('')
    md.write_text('\n'.join(lines), encoding='utf-8')
PY

  echo "===== commit reports ====="
  git add "$JSON" "$MD" "$LOG" run/hz16_short_url_diag.py scripts/hz16_run_short_url_diag_page49.sh
  git commit -m "docs: publish HZ16 short url diagnosis" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "DIAG_RC=$DIAG_RC"
  echo "LOG=$LOG"
  echo "REPORT=$JSON"
  echo "MD=$MD"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
