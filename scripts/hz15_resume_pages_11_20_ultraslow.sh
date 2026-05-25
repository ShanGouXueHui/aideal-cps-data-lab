#!/usr/bin/env bash
# HZ15 ultra-slow segmented resume: pages 11..20.
# Use after manual JD risk verification is completed in noVNC.
# Scope: JD Union 商品推广 / 全部商品 only.
# Purpose: reduce risk by running a smaller page segment with longer page sleeps.
# No exit and no set -e are used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import

  echo "===== HZ15 resume pages 11..20 ultra-slow ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== backup STOP/state/report; keep data/import files ====="
  for f in run/hz14_STOP_REQUIRED.json run/hz14_all_product_full_state.json run/hz14_all_product_full_report_latest.json
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz15_resume_11_20_${TS}" || true
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
    run/hz15_jump_pages_collector.py
  STATIC_RC=$?

  if [ "$STATIC_RC" != "0" ]; then
    HZ15_PID=SKIPPED
    HZ15_LOG=""
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== start background HZ15 ultra-slow segmented collector ====="
    HZ15_LOG="logs/hz15_jump_pages_resume_11_20_ultraslow_${TS}.log"
    (
      export HZ15_RUN_ONCE=true
      export HZ15_TARGET_TOTAL=4000
      export HZ15_PAGE_START=11
      export HZ15_PAGE_END=20
      export HZ15_PAGE_SEQUENCE="11-20"
      export HZ15_ITEMS_PER_PAGE_LIMIT=60
      export HZ15_ITEM_SLEEP_MIN=10
      export HZ15_ITEM_SLEEP_MAX=22
      export HZ15_PAGE_SLEEP_MIN=300
      export HZ15_PAGE_SLEEP_MAX=520
      export HZ15_MAX_FAIL_STREAK=3
      nohup .venv-browser/bin/python run/hz15_jump_pages_collector.py > "$HZ15_LOG" 2>&1 &
      echo $! > run/hz15_jump_pages.pid
    )
    sleep 5
    HZ15_PID="$(cat run/hz15_jump_pages.pid 2>/dev/null || true)"
  fi

  echo "===== process check ====="
  pgrep -af "hz15_jump_pages_collector|chrome.*19228" | head -n 80 || true
  if [ -n "${HZ15_LOG:-}" ] && [ -f "$HZ15_LOG" ]; then
    tail -n 100 "$HZ15_LOG" || true
  fi

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "HZ15_PID=$HZ15_PID"
  echo "HZ15_LOG=$HZ15_LOG"
  echo "REPORT=run/hz14_all_product_full_report_latest.json"
  echo "LATEST=data/import/hz_jd_union_all_product_full_links_latest.jsonl"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
