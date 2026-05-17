#!/usr/bin/env bash
# HZ12 official product_all full collection starter.
# Usage on collector server:
#   bash scripts/hz12_start_product_all_full_v3.sh
#
# Notes:
# - Uses the user's Aliyun collector server and logged-in Chrome profile.
# - Does not close Chrome.
# - Does not store account/password/cookie/token/HAR/QR.
# - Stops old HZ12 worker only.
# - Resets HZ12 STOP/state/full-latest before a fresh official full run.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1

TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p backups logs reports docs/ops run data/import

echo "===== HZ12 start product_all full v3 ====="
echo "PWD=$(pwd)"
echo "USER=$(whoami)"
echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

echo "===== sync repo ====="
GIT_TERMINAL_PROMPT=0 git fetch origin main
FETCH_RC=$?
if [ "$FETCH_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git rebase origin/main
  REBASE_RC=$?
else
  REBASE_RC=SKIPPED
fi

echo "===== stop old HZ12 worker only, keep Chrome ====="
pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
sleep 2

echo "===== backup and clear old HZ12 STOP/state/lATEST for fresh full run ====="
for f in \
  run/hz12_product_all_STOP_REQUIRED.json \
  run/hz12_product_all_full_state.json \
  data/import/hz_jd_union_product_all_full_links_latest.jsonl
 do
  if [ -e "$f" ]; then
    mv -v "$f" "backups/$(basename "$f").before_hz12_full_${TS}" || true
  fi
 done

echo "===== static check ====="
.venv-browser/bin/python -m py_compile \
  run/hz12_product_all_full_collector.py \
  run/hz12_product_all_full_collector_v3.py
STATIC_RC=$?

if [ "$STATIC_RC" != "0" ]; then
  echo "STATIC_RC=$STATIC_RC"
  echo "ABORT_STATIC_CHECK_FAILED"
  exit 1
fi

echo "===== start background full collector ====="
HZ12_LOG="logs/hz12_product_all_full_v3_overnight_${TS}.log"
(
  set -a
  . config/hz12_product_all_full.env
  set +a
  export HZ12_RUN_ONCE=false
  nohup .venv-browser/bin/python run/hz12_product_all_full_collector_v3.py > "$HZ12_LOG" 2>&1 &
  echo $! > run/hz12_product_all_full.pid
)

sleep 5
PID="$(cat run/hz12_product_all_full.pid 2>/dev/null || true)"

echo "===== initial compact status ====="
pgrep -af "hz12_product_all_full_collector|chrome.*19228|chrome.*19229" | head -n 80 || true

tail -n 60 "$HZ12_LOG" || true

echo "===== SUMMARY ====="
echo "FETCH_RC=$FETCH_RC"
echo "REBASE_RC=$REBASE_RC"
echo "STATIC_RC=$STATIC_RC"
echo "HZ12_PID=$PID"
echo "HZ12_LOG=$HZ12_LOG"
echo "REPORT=run/hz12_product_all_full_report_latest.json"
echo "LATEST=data/import/hz_jd_union_product_all_full_links_latest.jsonl"
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
