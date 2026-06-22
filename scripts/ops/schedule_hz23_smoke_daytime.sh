#!/usr/bin/env bash
# Schedule one HZ23 smoke run for the next daytime window and publish JSON evidence.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run

SCHEDULER_LOG="logs/hz23_smoke_daytime_scheduler.log"
PID_FILE="run/hz23_smoke_daytime_scheduler.pid"
REPORT="reports/hz23_smoke_auto_latest.json"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "===== SUMMARY ====="
    echo "SCHEDULE_RC=75"
    echo "REASON=already_scheduled"
    echo "PID=$OLD_PID"
    echo "REPORT=$REPORT"
    exit 0
  fi
fi

python3 - <<'PY' > run/hz23_smoke_delay.env
from datetime import datetime, timedelta
now = datetime.now()
start = now.replace(hour=9, minute=35, second=0, microsecond=0)
end = now.replace(hour=21, minute=20, second=0, microsecond=0)
if now < start:
    target = start
elif now <= end:
    target = now + timedelta(minutes=1)
else:
    target = start + timedelta(days=1)
seconds = max(0, int((target - now).total_seconds()))
print(f"DELAY_SECONDS={seconds}")
print(f"TARGET_TIME={target.strftime('%Y-%m-%d %H:%M:%S')}")
PY
. run/hz23_smoke_delay.env

(
  echo "SCHEDULED_AT=$(date '+%Y-%m-%d %H:%M:%S') TARGET_TIME=$TARGET_TIME DELAY_SECONDS=$DELAY_SECONDS"
  sleep "$DELAY_SECONDS"
  cd "$PROJECT_DIR" || exit 1
  git fetch origin main >/dev/null 2>&1 || true
  git reset --hard origin/main >/dev/null 2>&1 || true
  git clean -fd reports docs/ops >/dev/null 2>&1 || true
  ROUND_ID="smoke_$(date +%Y%m%d_%H%M%S)"
  RUN_LOG="logs/hz23_${ROUND_ID}.log"
  echo "RUN_START=$(date '+%Y-%m-%d %H:%M:%S') ROUND_ID=$ROUND_ID" | tee -a "$SCHEDULER_LOG"
  HZ23_ROUND_ID="$ROUND_ID" HZ23_PAGE_START=1 HZ23_PAGE_END=1 HZ23_RESUME=0 bash scripts/hz23_mainline_refresh.sh > "$RUN_LOG" 2>&1
  RUN_RC=$?
  python3 - "$ROUND_ID" "$RUN_RC" "$RUN_LOG" "$REPORT" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
round_id=sys.argv[1]
run_rc=int(sys.argv[2])
log_path=Path(sys.argv[3])
report_path=Path(sys.argv[4])
summary_path=Path(f"reports/hz23_round_{round_id}_latest.json")
summary={}
if summary_path.exists():
    try:
        summary=json.loads(summary_path.read_text(encoding='utf-8'))
    except Exception as exc:
        summary={"summary_parse_error": repr(exc)}
log_tail=[]
if log_path.exists():
    lines=log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    log_tail=lines[-160:]
payload={
    "schema_version":"hz23-smoke-auto/v1",
    "generated_at":datetime.utcnow().isoformat(timespec='seconds')+'Z',
    "round_id":round_id,
    "run_rc":run_rc,
    "summary_path":str(summary_path),
    "log_path":str(log_path),
    "summary":summary,
    "log_tail":log_tail,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
print(json.dumps({"event":"HZ23_SMOKE_AUTO_REPORT", "round_id":round_id, "run_rc":run_rc, "report":str(report_path)}, ensure_ascii=False, sort_keys=True))
PY
  bash scripts/git_publish_files_via_worktree.sh \
    "reports: publish HZ23 smoke auto result" \
    "$REPORT" \
    "reports/hz23_round_${ROUND_ID}_latest.json" \
    reports/hz23_round_latest.json \
    > logs/hz23_smoke_auto_publish.log 2>&1
  PUBLISH_RC=$?
  echo "RUN_DONE=$(date '+%Y-%m-%d %H:%M:%S') ROUND_ID=$ROUND_ID RUN_RC=$RUN_RC PUBLISH_RC=$PUBLISH_RC REPORT=$REPORT" | tee -a "$SCHEDULER_LOG"
  rm -f "$PID_FILE"
) >> "$SCHEDULER_LOG" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

python3 - "$REPORT" "$PID" "$TARGET_TIME" "$DELAY_SECONDS" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
report=Path(sys.argv[1])
payload={
    "schema_version":"hz23-smoke-auto/v1",
    "generated_at":datetime.utcnow().isoformat(timespec='seconds')+'Z',
    "status":"SCHEDULED",
    "pid":sys.argv[2],
    "target_time":sys.argv[3],
    "delay_seconds":int(sys.argv[4]),
}
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY
bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish HZ23 smoke auto schedule" \
  "$REPORT" \
  >/dev/null 2>&1
PUBLISH_RC=$?

echo "===== SUMMARY ====="
echo "SCHEDULE_RC=0"
echo "PID=$PID"
echo "TARGET_TIME=$TARGET_TIME"
echo "DELAY_SECONDS=$DELAY_SECONDS"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "REPORT=$REPORT"
