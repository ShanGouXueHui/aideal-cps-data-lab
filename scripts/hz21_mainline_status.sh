#!/usr/bin/env bash
# Check HZ21 mainline background status and print compact latest result.
# No exit and no set -e are used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  PID_FILE="run/hz21_mainline_remaining.pid"
  META_FILE="run/hz21_mainline_remaining_meta.json"

  echo "===== HZ21 mainline status ====="
  echo "PWD=$(pwd)"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"

  if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  else
    PID=""
  fi

  if [ -n "$PID" ]; then
    echo "PID=$PID"
    ps -p "$PID" -o pid,ppid,etime,cmd || true
  else
    echo "PID="
    echo "PID_FILE_NOT_FOUND=$PID_FILE"
  fi

  if [ -f "$META_FILE" ]; then
    echo "===== meta ====="
    cat "$META_FILE"
    echo
  fi

  BG_LOG="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('run/hz21_mainline_remaining_meta.json')
if p.exists():
  try: print(json.loads(p.read_text(encoding='utf-8')).get('log') or '')
  except Exception: print('')
else:
  logs=sorted(Path('logs').glob('hz21_mainline_remaining_background_*.log'), key=lambda x:x.stat().st_mtime)
  print(str(logs[-1]) if logs else '')
PY
)"

  if [ -n "$BG_LOG" ] && [ -f "$BG_LOG" ]; then
    echo "===== background log tail ====="
    tail -n 120 "$BG_LOG"
  fi

  echo "===== compact summary json ====="
  python3 - <<'PY'
import json
from pathlib import Path
meta=Path('run/hz21_mainline_remaining_meta.json')
summary=''
if meta.exists():
    try: summary=json.loads(meta.read_text(encoding='utf-8')).get('summary_json') or ''
    except Exception: summary=''
if not summary:
    files=sorted(Path('reports').glob('hz21_safe_pages_*_latest.json'), key=lambda p:p.stat().st_mtime)
    summary=str(files[-1]) if files else ''
print('SUMMARY_JSON='+summary)
if summary and Path(summary).exists():
    x=json.loads(Path(summary).read_text(encoding='utf-8'))
    print(json.dumps({
      'pages': x.get('pages'),
      'total_ok': x.get('total_ok'),
      'total_fail': x.get('total_fail'),
      'last_known_sku_count': x.get('last_known_sku_count'),
      'rows': [
        {
          'page': r.get('page'),
          'ok': r.get('ok'),
          'reason': r.get('reason'),
          'total_ok': r.get('total_ok'),
          'total_fail': r.get('total_fail'),
          'known_sku_count': r.get('known_sku_count'),
          'page_summary': r.get('page_summary'),
        } for r in x.get('rows', [])
      ]
    }, ensure_ascii=False, indent=2))
else:
    print('SUMMARY_JSON_NOT_READY=1')
PY

  echo "===== SUMMARY ====="
  echo "PID=$PID"
  echo "BG_LOG=$BG_LOG"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 80
fi
