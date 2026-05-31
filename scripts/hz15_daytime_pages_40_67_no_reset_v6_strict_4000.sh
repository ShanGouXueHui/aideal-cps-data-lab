#!/usr/bin/env bash
# HZ15 daytime guarded runner: pages 40..67, strict 4000 all-product page gate.
# Purpose: run during human-like daytime hours and stop at night.
# Default server-local window: 09:30-21:30.
# Scope: JD Union 商品推广 / 全部商品 only.
# Current browser page must already show 商品推广 / 全部商品 with 共4000条 + ~60 items.
# This script does not bypass JD verification. If browser is on risk_handler / 京东验证, it will STOP safely.
# No exit and no set -e are used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
START_HOUR="${HZ15_DAY_START_HOUR:-9}"
START_MINUTE="${HZ15_DAY_START_MINUTE:-30}"
STOP_HOUR="${HZ15_DAY_STOP_HOUR:-21}"
STOP_MINUTE="${HZ15_DAY_STOP_MINUTE:-30}"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import

  NOW_HOUR="$(date +%H)"
  NOW_MINUTE="$(date +%M)"
  NOW_TOTAL=$((10#$NOW_HOUR * 60 + 10#$NOW_MINUTE))
  START_TOTAL=$((10#$START_HOUR * 60 + 10#$START_MINUTE))
  STOP_TOTAL=$((10#$STOP_HOUR * 60 + 10#$STOP_MINUTE))
  SECONDS_TO_STOP=$(((STOP_TOTAL - NOW_TOTAL) * 60))

  echo "===== HZ15 daytime pages 40..67 no-reset strict-4000 v6 ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "DAY_WINDOW=${START_HOUR}:${START_MINUTE}-${STOP_HOUR}:${STOP_MINUTE} server-local"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  if [ "$NOW_TOTAL" -lt "$START_TOTAL" ] || [ "$NOW_TOTAL" -ge "$STOP_TOTAL" ]; then
    echo "===== outside daytime window; not starting collector ====="
    HZ15_PID=SKIPPED_OUTSIDE_DAYTIME
    HZ15_LOG=""
    STATIC_RC=SKIPPED
  else
    echo "===== stop old HZ15 worker only, keep Chrome/noVNC ====="
    pkill -f "python.*run/hz15_jump_pages_collector" 2>/dev/null || true
    pkill -f "hz15_daytime_stop_watchdog" 2>/dev/null || true
    sleep 3

    echo "===== backup STOP/state/report; keep data/import files ====="
    for f in run/hz14_STOP_REQUIRED.json run/hz14_all_product_full_state.json run/hz14_all_product_full_report_latest.json
    do
      if [ -e "$f" ]; then
        mv -v "$f" "backups/$(basename "$f").before_hz15_daytime_40_67_${TS}" || true
      fi
    done

    echo "===== static check ====="
    .venv-browser/bin/python -m py_compile \
      run/hz12_product_all_full_collector.py \
      run/hz12_product_all_full_collector_v3.py \
      run/hz12_product_all_full_collector_v5.py \
      run/hz12_product_all_full_collector_v7.py \
      run/hz12_product_all_full_collector_v8.py \
      run/hz14_all_product_full_collector.py \
      run/hz14_all_product_full_collector_v2.py \
      run/hz14_all_product_full_collector_v3.py \
      run/hz14_all_product_full_collector_v4.py \
      run/hz15_jump_pages_collector.py \
      run/hz15_jump_pages_collector_v5_no_reset.py \
      run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py
    STATIC_RC=$?

    if [ "$STATIC_RC" != "0" ]; then
      HZ15_PID=SKIPPED_STATIC_FAILED
      HZ15_LOG=""
      echo "STATIC_CHECK_FAILED"
    else
      echo "===== start background HZ15 daytime collector v6 pages 40..67 ====="
      HZ15_LOG="logs/hz15_daytime_40_67_no_reset_v6_strict_4000_${TS}.log"
      WATCH_LOG="logs/hz15_daytime_40_67_stop_watchdog_${TS}.log"
      (
        export HZ15_RUN_ONCE=true
        export HZ15_TARGET_TOTAL=4000
        export HZ15_PAGE_START=40
        export HZ15_PAGE_END=67
        export HZ15_PAGE_SEQUENCE="40-67"
        export HZ15_ITEMS_PER_PAGE_LIMIT=60
        export HZ15_ITEM_SLEEP_MIN=18
        export HZ15_ITEM_SLEEP_MAX=45
        export HZ15_PAGE_SLEEP_MIN=1200
        export HZ15_PAGE_SLEEP_MAX=2400
        export HZ15_MAX_FAIL_STREAK=3
        nohup .venv-browser/bin/python run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py > "$HZ15_LOG" 2>&1 &
        echo $! > run/hz15_jump_pages.pid
      )
      sleep 5
      HZ15_PID="$(cat run/hz15_jump_pages.pid 2>/dev/null || true)"

      if [ "$SECONDS_TO_STOP" -gt 0 ]; then
        (
          echo "hz15_daytime_stop_watchdog start ts=$(date '+%Y-%m-%d %H:%M:%S') seconds_to_stop=$SECONDS_TO_STOP target_pid=$HZ15_PID" >> "$WATCH_LOG"
          sleep "$SECONDS_TO_STOP"
          echo "hz15_daytime_stop_watchdog stopping ts=$(date '+%Y-%m-%d %H:%M:%S') target_pid=$HZ15_PID" >> "$WATCH_LOG"
          if [ -n "$HZ15_PID" ]; then
            kill "$HZ15_PID" >> "$WATCH_LOG" 2>&1 || true
          fi
          pkill -f "python.*run/hz15_jump_pages_collector" >> "$WATCH_LOG" 2>&1 || true
        ) &
        echo $! > run/hz15_daytime_stop_watchdog.pid
      fi
    fi
  fi

  echo "===== process check ====="
  pgrep -af "hz15_jump_pages_collector|hz15_daytime_stop_watchdog|chrome.*19228" | head -n 100 || true
  if [ -n "${HZ15_LOG:-}" ] && [ -f "$HZ15_LOG" ]; then
    tail -n 100 "$HZ15_LOG" || true
  fi

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ15_PID=$HZ15_PID"
  echo "HZ15_LOG=$HZ15_LOG"
  echo "WATCH_LOG=${WATCH_LOG:-}"
  echo "DAY_WINDOW=${START_HOUR}:${START_MINUTE}-${STOP_HOUR}:${STOP_MINUTE} server-local"
  echo "REPORT=run/hz14_all_product_full_report_latest.json"
  echo "LATEST=data/import/hz_jd_union_all_product_full_links_latest.jsonl"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
