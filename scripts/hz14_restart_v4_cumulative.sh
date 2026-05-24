#!/usr/bin/env bash
# Restart HZ14 all-product full collector with v4 cumulative latest bootstrap.
# Scope: 商品推广 / 全部商品 only.
# No exit is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import

  echo "===== HZ14 restart v4 cumulative ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop old HZ14 worker only, keep Chrome/noVNC ====="
  pkill -f "python.*run/hz14_all_product_full_collector" 2>/dev/null || true
  sleep 3

  echo "===== backup STOP/state/report; keep data/import files ====="
  for f in \
    run/hz14_STOP_REQUIRED.json \
    run/hz14_all_product_full_state.json \
    run/hz14_all_product_full_report_latest.json
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz14_v4_restart_${TS}" || true
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
    run/hz14_all_product_full_collector_v4.py
  STATIC_RC=$?

  if [ "$STATIC_RC" != "0" ]; then
    HZ14_PID=SKIPPED
    HZ14_LOG=""
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== start background HZ14 v4 full collector ====="
    HZ14_LOG="logs/hz14_all_product_full_v4_4000_${TS}.log"
    (
      export HZ14_RUN_ONCE=false
      export HZ14_TARGET_TOTAL=4000
      export HZ14_PAGE_START=1
      export HZ14_PAGE_MAX=67
      export HZ14_ITEMS_PER_PAGE_LIMIT=60
      export HZ14_ITEM_SLEEP_MIN=6
      export HZ14_ITEM_SLEEP_MAX=12
      export HZ14_PAGE_SLEEP_MIN=75
      export HZ14_PAGE_SLEEP_MAX=125
      export HZ14_MAX_FAIL_STREAK=3
      nohup .venv-browser/bin/python run/hz14_all_product_full_collector_v4.py > "$HZ14_LOG" 2>&1 &
      echo $! > run/hz14_all_product_full.pid
    )
    sleep 5
    HZ14_PID="$(cat run/hz14_all_product_full.pid 2>/dev/null || true)"
  fi

  echo "===== process check ====="
  pgrep -af "hz14_all_product_full_collector|chrome.*19228" | head -n 80 || true
  if [ -n "${HZ14_LOG:-}" ] && [ -f "$HZ14_LOG" ]; then
    tail -n 100 "$HZ14_LOG" || true
  fi

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ14_PID=$HZ14_PID"
  echo "HZ14_LOG=$HZ14_LOG"
  echo "REPORT=run/hz14_all_product_full_report_latest.json"
  echo "LATEST=data/import/hz_jd_union_all_product_full_links_latest.jsonl"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
