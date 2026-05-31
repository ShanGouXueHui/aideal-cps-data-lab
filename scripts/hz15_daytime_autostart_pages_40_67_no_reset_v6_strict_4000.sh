#!/usr/bin/env bash
# HZ15 daytime autostart supervisor: pages 40..67, strict 4000 all-product page gate.
# Run this once. It starts a background supervisor that:
# - waits until server-local daytime window, default 09:30-21:30
# - starts the HZ15 collector during daytime only
# - stops old HZ15 collectors outside the window
# - stops the collector at night
# - never bypasses JD verification; risk_handler / 京东验证 will create STOP and supervisor exits.
# Scope: JD Union 商品推广 / 全部商品 only.
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

  echo "===== HZ15 daytime autostart supervisor pages 40..67 ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "SERVER_TIME=$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "DAY_WINDOW=${START_HOUR}:${START_MINUTE}-${STOP_HOUR}:${STOP_MINUTE} server-local"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

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

  SUPERVISOR_PID=SKIPPED
  SUPERVISOR_LOG="logs/hz15_daytime_autostart_40_67_supervisor_${TS}.log"

  if [ "$STATIC_RC" != "0" ]; then
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== stop old daytime supervisors; keep Chrome/noVNC ====="
    pkill -f "hz15_daytime_autostart_supervisor_40_67" 2>/dev/null || true
    sleep 2

    cat > run/hz15_daytime_autostart_supervisor_40_67.sh <<'SUP'
#!/usr/bin/env bash
# hz15_daytime_autostart_supervisor_40_67
PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
START_HOUR="${HZ15_DAY_START_HOUR:-9}"
START_MINUTE="${HZ15_DAY_START_MINUTE:-30}"
STOP_HOUR="${HZ15_DAY_STOP_HOUR:-21}"
STOP_MINUTE="${HZ15_DAY_STOP_MINUTE:-30}"
cd "$PROJECT_DIR" || {
  echo "SUPERVISOR_PROJECT_DIR_NOT_FOUND project_dir=$PROJECT_DIR ts=$(date '+%Y-%m-%d %H:%M:%S')"
  exit 0
}

in_daytime() {
  local h m now start stop
  h="$(date +%H)"
  m="$(date +%M)"
  now=$((10#$h * 60 + 10#$m))
  start=$((10#$START_HOUR * 60 + 10#$START_MINUTE))
  stop=$((10#$STOP_HOUR * 60 + 10#$STOP_MINUTE))
  [ "$now" -ge "$start" ] && [ "$now" -lt "$stop" ]
}

seconds_until_stop() {
  local h m now stop seconds
  h="$(date +%H)"
  m="$(date +%M)"
  now=$((10#$h * 60 + 10#$m))
  stop=$((10#$STOP_HOUR * 60 + 10#$STOP_MINUTE))
  seconds=$(((stop - now) * 60))
  if [ "$seconds" -lt 60 ]; then seconds=60; fi
  echo "$seconds"
}

stop_hz15_workers() {
  pkill -f "python.*run/hz15_jump_pages_collector" 2>/dev/null || true
}

start_collector() {
  local ts log pid
  ts="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import
  for f in run/hz14_STOP_REQUIRED.json run/hz14_all_product_full_state.json run/hz14_all_product_full_report_latest.json
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz15_daytime_autostart_40_67_${ts}" || true
    fi
  done
  log="logs/hz15_daytime_40_67_no_reset_v6_strict_4000_${ts}.log"
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
    nohup .venv-browser/bin/python run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py > "$log" 2>&1 &
    echo $! > run/hz15_jump_pages.pid
  )
  pid="$(cat run/hz15_jump_pages.pid 2>/dev/null || true)"
  echo "COLLECTOR_STARTED ts=$(date '+%Y-%m-%d %H:%M:%S') pid=$pid log=$log"
}

echo "SUPERVISOR_START ts=$(date '+%Y-%m-%d %H:%M:%S') window=${START_HOUR}:${START_MINUTE}-${STOP_HOUR}:${STOP_MINUTE}"

while true
 do
  if [ -e run/hz14_STOP_REQUIRED.json ]; then
    echo "SUPERVISOR_STOP_EXISTS ts=$(date '+%Y-%m-%d %H:%M:%S') stop_file=run/hz14_STOP_REQUIRED.json"
    stop_hz15_workers
    break
  fi

  if in_daytime; then
    if pgrep -f "python.*run/hz15_jump_pages_collector_v6_no_reset_strict_4000.py" >/dev/null 2>&1; then
      secs="$(seconds_until_stop)"
      if [ "$secs" -le 120 ]; then
        echo "SUPERVISOR_DAY_END_STOP ts=$(date '+%Y-%m-%d %H:%M:%S')"
        stop_hz15_workers
        sleep 180
      else
        echo "SUPERVISOR_COLLECTOR_RUNNING ts=$(date '+%Y-%m-%d %H:%M:%S') seconds_until_stop=$secs"
        sleep 300
      fi
    else
      echo "SUPERVISOR_DAYTIME_STARTING_COLLECTOR ts=$(date '+%Y-%m-%d %H:%M:%S')"
      start_collector
      sleep 300
    fi
  else
    if pgrep -f "python.*run/hz15_jump_pages_collector" >/dev/null 2>&1; then
      echo "SUPERVISOR_OUTSIDE_DAYTIME_STOPPING_COLLECTOR ts=$(date '+%Y-%m-%d %H:%M:%S')"
      stop_hz15_workers
    else
      echo "SUPERVISOR_WAITING_DAYTIME ts=$(date '+%Y-%m-%d %H:%M:%S')"
    fi
    sleep 600
  fi
 done

echo "SUPERVISOR_EXIT ts=$(date '+%Y-%m-%d %H:%M:%S')"
SUP
    chmod +x run/hz15_daytime_autostart_supervisor_40_67.sh
    nohup bash run/hz15_daytime_autostart_supervisor_40_67.sh > "$SUPERVISOR_LOG" 2>&1 &
    SUPERVISOR_PID=$!
    echo "$SUPERVISOR_PID" > run/hz15_daytime_autostart_supervisor_40_67.pid
    sleep 3
    tail -n 80 "$SUPERVISOR_LOG" || true
  fi

  echo "===== process check ====="
  pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz15_jump_pages_collector|chrome.*19228" | head -n 100 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "SUPERVISOR_PID=$SUPERVISOR_PID"
  echo "SUPERVISOR_LOG=$SUPERVISOR_LOG"
  echo "DAY_WINDOW=${START_HOUR}:${START_MINUTE}-${STOP_HOUR}:${STOP_MINUTE} server-local"
  echo "REPORT=run/hz14_all_product_full_report_latest.json"
  echo "LATEST=data/import/hz_jd_union_all_product_full_links_latest.jsonl"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  git status --short | head -n 60
fi
