#!/usr/bin/env bash
# HZ15 one-command overnight runner: pages 40..67, strict 4000 all-product page gate.
# Scope: JD Union 商品推广 / 全部商品 only.
# Current browser page must already be a usable 商品推广 / 全部商品 page with 共4000条 + ~60 items.
# This script does not bypass JD verification. If the browser is on risk_handler / 京东验证, it will STOP safely.
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

  echo "===== HZ15 one-command overnight pages 40..67 no-reset strict-4000 v6 ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop old HZ15 worker only, keep Chrome/noVNC ====="
  pkill -f "python.*run/hz15_jump_pages_collector" 2>/dev/null || true
  sleep 3

  echo "===== backup STOP/state/report; keep data/import files ====="
  for f in run/hz14_STOP_REQUIRED.json run/hz14_all_product_full_state.json run/hz14_all_product_full_report_latest.json
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz15_no_reset_v6_40_67_overnight_${TS}" || true
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
    HZ15_PID=SKIPPED
    HZ15_LOG=""
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== start background HZ15 strict-4000 overnight collector v6 pages 40..67 ====="
    HZ15_LOG="logs/hz15_jump_pages_resume_40_67_no_reset_v6_strict_4000_overnight_${TS}.log"
    (
      export HZ15_RUN_ONCE=true
      export HZ15_TARGET_TOTAL=4000
      export HZ15_PAGE_START=40
      export HZ15_PAGE_END=67
      export HZ15_PAGE_SEQUENCE="40-67"
      export HZ15_ITEMS_PER_PAGE_LIMIT=60
      export HZ15_ITEM_SLEEP_MIN=12
      export HZ15_ITEM_SLEEP_MAX=28
      export HZ15_PAGE_SLEEP_MIN=900
      export HZ15_PAGE_SLEEP_MAX=1500
      export HZ15_MAX_FAIL_STREAK=3
      nohup .venv-browser/bin/python run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py > "$HZ15_LOG" 2>&1 &
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
