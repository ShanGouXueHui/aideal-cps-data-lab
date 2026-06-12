#!/usr/bin/env bash
# Prepare visual probe for one failed SKU. It clicks the target SKU and holds the browser
# so a noVNC screenshot can be taken. No exit and no set -e are used.
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  mkdir -p logs reports docs/ops run data/import
  TS="$(date +%Y%m%d_%H%M%S)"
  LOG="logs/hz19_visual_probe_failed_sku_${TS}.log"
  JSON="reports/hz19_visual_probe_failed_sku_latest.json"

  echo "===== HZ19 visual probe failed sku ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop collectors only, keep browser/supervisor ====="
  pkill -f "run/hz17_recover_short_url_page.py" || true
  pkill -f "run/hz18_card_click_recover_page.py" || true
  pkill -f "hz15_jump_pages_collector_v6_no_reset_strict_4000.py" || true
  sleep 3
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz17_recover|hz18_card|hz19_visual|chrome.*19228" | head -n 100 || true

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile run/hz19_visual_probe_failed_sku.py
  STATIC_RC=$?

  echo "===== run visual probe ====="
  echo "When the log shows VISUAL_READY_TAKE_SCREENSHOT_NOW, open noVNC and send one screenshot."
  HZ19_PAGE=49 HZ19_SKU=100016509578 HZ19_TITLE_KEY="佳帮手折叠扫把簸箕" HZ19_HOLD_SECONDS=420 .venv-browser/bin/python run/hz19_visual_probe_failed_sku.py > "$LOG" 2>&1 &
  PROBE_PID=$!

  echo "===== wait for visual ready, max 45s ====="
  READY="false"
  for i in $(seq 1 45); do
    if grep -q "VISUAL_READY_TAKE_SCREENSHOT_NOW" "$LOG" 2>/dev/null; then
      READY="true"
      break
    fi
    sleep 1
  done

  echo "===== probe log tail ====="
  tail -n 80 "$LOG" 2>/dev/null || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "READY=$READY"
  echo "PROBE_PID=$PROBE_PID"
  echo "LOG=$LOG"
  echo "REPORT=$JSON"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "NOVNC=http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale"
  git status --short | head -n 60
fi
