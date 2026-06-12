#!/usr/bin/env bash
# Start HZ21 mainline remaining collector in background.
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
  BG_LOG="logs/hz21_mainline_remaining_background_${TS}.log"
  PID_FILE="run/hz21_mainline_remaining.pid"
  META_FILE="run/hz21_mainline_remaining_meta.json"

  PAGE_START="${HZ21_MAINLINE_PAGE_START:-58}"
  PAGE_END="${HZ21_MAINLINE_PAGE_END:-67}"

  echo "===== start HZ21 mainline background ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "PAGE_START=$PAGE_START"
  echo "PAGE_END=$PAGE_END"

  echo "===== stop old HZ21 mainline background only ====="
  if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ]; then
      kill "$OLD_PID" 2>/dev/null || true
    fi
  fi
  pkill -f "scripts/hz21_mainline_safe_remaining.sh" || true
  pkill -f "run/hz21_run_safe_pages_.*_generated.sh" || true
  sleep 2

  echo "===== launch ====="
  HZ21_MAINLINE_PAGE_START="$PAGE_START" HZ21_MAINLINE_PAGE_END="$PAGE_END" nohup bash scripts/hz21_mainline_safe_remaining.sh > "$BG_LOG" 2>&1 &
  PID=$!
  echo "$PID" > "$PID_FILE"
  python3 - <<PY
import json
from pathlib import Path
meta={
  'pid': $PID,
  'page_start': int('$PAGE_START'),
  'page_end': int('$PAGE_END'),
  'log': '$BG_LOG',
  'summary_json': f'reports/hz21_safe_pages_{int("$PAGE_START")}_{int("$PAGE_END")}_latest.json',
}
Path('$META_FILE').write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
PY

  echo "===== initial status ====="
  ps -p "$PID" -o pid,ppid,etime,cmd || true
  echo "BG_LOG=$BG_LOG"
  echo "PID_FILE=$PID_FILE"
  echo "META_FILE=$META_FILE"

  echo "===== SUMMARY ====="
  echo "PID=$PID"
  echo "PAGE_START=$PAGE_START"
  echo "PAGE_END=$PAGE_END"
  echo "BG_LOG=$BG_LOG"
  echo "SUMMARY_JSON=reports/hz21_safe_pages_${PAGE_START}_${PAGE_END}_latest.json"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 80
fi
