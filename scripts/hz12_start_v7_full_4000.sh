#!/usr/bin/env bash
# HZ12 v7 full product_all 4000 starter.
# No `exit` is used because the user's shell environment may logout on exit.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz12_start_v7_full_4000.sh

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行；不要在生产机 deploy 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import

  echo "===== HZ12 v7 full 4000 start ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop old HZ12 worker only, keep Chrome ====="
  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  sleep 2

  echo "===== backup and reset HZ12 full state ====="
  for f in \
    run/hz12_product_all_STOP_REQUIRED.json \
    run/hz12_product_all_full_state.json \
    data/import/hz_jd_union_product_all_full_links_latest.jsonl
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz12z_v7_full_${TS}" || true
    fi
  done

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile \
    run/hz12_product_all_full_collector.py \
    run/hz12_product_all_full_collector_v3.py \
    run/hz12_product_all_full_collector_v5.py \
    run/hz12_product_all_full_collector_v7.py
  STATIC_RC=$?

  if [ "$STATIC_RC" != "0" ]; then
    HZ12_PID=SKIPPED
    HZ12_LOG=""
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== start background v7 full target 4000 ====="
    HZ12_LOG="logs/hz12z_product_all_v7_full_4000_${TS}.log"
    (
      set -a
      . config/hz12_product_all_full.env
      set +a
      export HZ12_RUN_ONCE=false
      export HZ12_PAGE_MAX=260
      export HZ12_TARGET_TOTAL=4000
      export HZ12_ITEMS_PER_PAGE_LIMIT=20
      export HZ12_ITEM_SLEEP_MIN=4
      export HZ12_ITEM_SLEEP_MAX=8
      export HZ12_PAGE_SLEEP_MIN=2
      export HZ12_PAGE_SLEEP_MAX=4
      nohup .venv-browser/bin/python run/hz12_product_all_full_collector_v7.py > "$HZ12_LOG" 2>&1 &
      echo $! > run/hz12_product_all_full.pid
    )
    sleep 5
    HZ12_PID="$(cat run/hz12_product_all_full.pid 2>/dev/null || true)"
  fi

  echo "===== initial status ====="
  pgrep -af "hz12_product_all_full_collector|chrome.*19228|chrome.*19229" | head -n 80 || true
  if [ -n "${HZ12_LOG:-}" ] && [ -f "$HZ12_LOG" ]; then
    tail -n 80 "$HZ12_LOG" || true
  fi

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ12_PID=$HZ12_PID"
  echo "HZ12_LOG=$HZ12_LOG"
  echo "REPORT=run/hz12_product_all_full_report_latest.json"
  echo "LATEST=data/import/hz_jd_union_product_all_full_links_latest.jsonl"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
