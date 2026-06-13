#!/usr/bin/env bash
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs run reports
TS="$(date +%Y%m%d_%H%M%S)"
PAGE_START="${HZ22_PAGE_START:-61}"
PAGE_END="${HZ22_PAGE_END:-67}"
BG_LOG="logs/hz22_all_product_background_${TS}.log"
PID_FILE="run/hz22_all_product.pid"
META="run/hz22_all_product_meta.json"

if [ -f "$PID_FILE" ]; then
  OLD="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD" ]; then kill "$OLD" 2>/dev/null || true; fi
fi
pkill -f "scripts/hz22_mainline_all_product.sh" || true
sleep 2

HZ22_PAGE_START="$PAGE_START" HZ22_PAGE_END="$PAGE_END" nohup bash scripts/hz22_mainline_all_product.sh > "$BG_LOG" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
python3 - <<PY
import json
from pathlib import Path
Path('$META').write_text(json.dumps({'pid':$PID,'page_start':$PAGE_START,'page_end':$PAGE_END,'log':'$BG_LOG','summary_json':'reports/hz22_pages_${PAGE_START}_${PAGE_END}_latest.json'},ensure_ascii=False,indent=2),encoding='utf-8')
PY

echo "===== SUMMARY ====="
echo "PID=$PID"
echo "PAGE_START=$PAGE_START"
echo "PAGE_END=$PAGE_END"
echo "BG_LOG=$BG_LOG"
echo "SUMMARY_JSON=reports/hz22_pages_${PAGE_START}_${PAGE_END}_latest.json"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
git status --short | head -n 60
