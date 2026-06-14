#!/usr/bin/env bash
# Read-only status publication. Does not restart the observer or touch JD browser automation.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p reports logs

OUT="reports/hz23_commercial_status_v2_latest.json"
SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
SERVICE_PID="$(systemctl show aideal-hz23-observer.service -p MainPID --value 2>/dev/null || true)"
SERVICE_STARTED_AT="$(systemctl show aideal-hz23-observer.service -p ActiveEnterTimestamp --value 2>/dev/null || true)"
LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"

python3 - "$OUT" "$SERVICE_STATE" "$SERVICE_PID" "$SERVICE_STARTED_AT" "$LOCAL_HEAD" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

out_path = Path(sys.argv[1])
service_state = sys.argv[2] or "unknown"
service_pid = sys.argv[3] or None
service_started_at = sys.argv[4] or None
git_head = sys.argv[5] or None


def load(path: str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def pick(value: dict[str, Any] | None, keys: list[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    return {key: value.get(key) for key in keys}

state = load("run/hz23_observer_state.json")
observer_status = load("reports/hz23_observer_status_latest.json")
probe_prepare = load("reports/hz23_probe_prepare_latest.json")
probe_scan = load("reports/hz23_probe_scan_latest.json")
round_report = load("reports/hz23_round_latest.json")
manifest = load("data/export/aideal_cps_products_commercial_candidate_manifest.json")

successful_probes = int((state or {}).get("successful_probes") or 0)
failed_probes = int((state or {}).get("failed_probes") or 0)
observation_started_at = (state or {}).get("observation_started_at") or (state or {}).get("created_at")
observation_hours = 0.0
if observation_started_at:
    try:
        observation_hours = max(
            0.0,
            (datetime.now() - datetime.fromisoformat(str(observation_started_at))).total_seconds() / 3600.0,
        )
    except Exception:
        observation_hours = 0.0

completed_pages = (round_report or {}).get("completed_pages") or []
unfinished_pages = (round_report or {}).get("unfinished_pages")
scanned_total = int((round_report or {}).get("scanned_total") or 0)
stop_reason = (round_report or {}).get("stop_reason")
round_complete = bool(
    round_report
    and round_report.get("commercial_segment_complete") is True
    and completed_pages == list(range(1, 68))
    and unfinished_pages == []
    and stop_reason in (None, "")
    and scanned_total >= 3900
)

candidate_integrity_ready = bool(
    manifest
    and manifest.get("candidate_integrity_ready") is True
    and int(manifest.get("duplicate_sku_count") or 0) == 0
    and int(((manifest.get("rejected") or {}).get("unsafe_hz20")) or 0) == 0
    and int(((manifest.get("rejected") or {}).get("untrusted_promotion_url")) or 0) == 0
    and bool(manifest.get("data_sha256"))
    and int(manifest.get("row_count") or 0) > 0
)

checks = {
    "service_active": service_state == "active",
    "successful_probes_minimum": successful_probes >= 2,
    "observation_hours_minimum": observation_hours >= 48.0,
    "full_round_present": round_report is not None,
    "full_round_complete": round_complete,
    "candidate_manifest_present": manifest is not None,
    "candidate_integrity_ready": candidate_integrity_ready,
    "commercial_switch_still_off": not bool((manifest or {}).get("commercial_enabled")),
}

payload = {
    "schema_version": "aideal-hz23-commercial-status/v2",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "git_head": git_head,
    "service": {
        "state": service_state,
        "main_pid": service_pid,
        "active_enter_timestamp": service_started_at,
    },
    "observer_state": pick(
        state,
        [
            "version",
            "created_at",
            "observation_started_at",
            "next_probe_due_at",
            "next_full_due_at",
            "last_probe_at",
            "first_successful_probe_at",
            "successful_probes",
            "failed_probes",
            "last_probe_ok",
            "last_probe_reason",
            "last_full_started_at",
            "last_full_finished_at",
            "last_full_round_id",
            "last_full_complete",
            "last_stop_reason",
            "requires_manual",
            "successful_full_rounds",
        ],
    ),
    "observation_hours": round(observation_hours, 2),
    "latest_observer_status": pick(observer_status, ["ts", "mode"]),
    "latest_probe_prepare": pick(probe_prepare, ["ts", "target_page", "ok", "reason"]),
    "latest_probe_scan": pick(
        probe_scan,
        ["ts", "round_id", "page_no", "ok", "reason", "scanned", "new", "changed", "unchanged", "risk"],
    ),
    "latest_round": pick(
        round_report,
        [
            "round_id",
            "commercial_segment_complete",
            "completed_pages",
            "unfinished_pages",
            "scanned_total",
            "catalog_new",
            "catalog_changed",
            "catalog_unchanged",
            "last_known_sku_count",
            "stop_page",
            "stop_reason",
            "duration_seconds",
        ],
    ),
    "candidate_manifest": pick(
        manifest,
        [
            "generated_at",
            "round_id",
            "data_sha256",
            "row_count",
            "trusted_dedup_sku_count",
            "source_duplicate_sku_count",
            "catalog_index_sku_count",
            "round_seen_sku_count",
            "eligible_sku_count",
            "duplicate_sku_count",
            "rejected",
            "round_complete",
            "candidate_integrity_ready",
            "successful_probes",
            "observation_hours",
            "gate_checks",
            "gate_failures",
            "observation_ready",
            "commercial_enabled",
        ],
    ),
    "checks": checks,
    "gate_failures": [name for name, passed in checks.items() if not passed],
    "observation_ready": all(checks.values()),
    "mysql_initialization_allowed": all(checks.values()),
}

tmp = out_path.with_suffix(out_path.suffix + ".tmp")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
tmp.replace(out_path)
PY
BUILD_RC=$?

if [ "$BUILD_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAILED"
  echo "STEP=build_status"
  echo "RC=$BUILD_RC"
  exit "$BUILD_RC"
fi

git add "$OUT"
if git diff --cached --quiet; then
  COMMIT_STATUS="no_change"
else
  git commit -m "reports: publish HZ23 commercial status v2"
  COMMIT_RC=$?
  if [ "$COMMIT_RC" != "0" ]; then
    echo "===== SUMMARY ====="
    echo "STATUS=FAILED"
    echo "STEP=commit"
    echo "RC=$COMMIT_RC"
    exit "$COMMIT_RC"
  fi
  COMMIT_STATUS="committed"
fi

GIT_TERMINAL_PROMPT=0 git fetch origin main
FETCH_RC=$?
if [ "$FETCH_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git rebase origin/main
  REBASE_RC=$?
else
  REBASE_RC=99
fi

if [ "$FETCH_RC" = "0" ] && [ "$REBASE_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main
  PUSH_RC=$?
else
  PUSH_RC=99
fi

SUMMARY="$(python3 - "$OUT" <<'PY'
import json,sys
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
s=x.get('observer_state') or {}
r=x.get('latest_round') or {}
m=x.get('candidate_manifest') or {}
print(
    f"SUCCESSFUL_PROBES={s.get('successful_probes') or 0} "
    f"FAILED_PROBES={s.get('failed_probes') or 0} "
    f"OBSERVATION_HOURS={x.get('observation_hours') or 0} "
    f"FULL_ROUND_PRESENT={str(r is not None).lower()} "
    f"FULL_ROUND_COMPLETE={str(bool((x.get('checks') or {}).get('full_round_complete'))).lower()} "
    f"SCANNED_TOTAL={r.get('scanned_total') if r else ''} "
    f"CANDIDATE_ROWS={m.get('row_count') if m else ''} "
    f"OBSERVATION_READY={str(bool(x.get('observation_ready'))).lower()} "
    f"GATE_FAILURES={','.join(x.get('gate_failures') or [])}"
)
PY
)"

LOCAL_AFTER="$(git rev-parse HEAD 2>/dev/null || true)"
REMOTE_HEAD="$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
STATUS="PASS"
if [ "$FETCH_RC" != "0" ] || [ "$REBASE_RC" != "0" ] || [ "$PUSH_RC" != "0" ] || [ "$LOCAL_AFTER" != "$REMOTE_HEAD" ]; then
  STATUS="FAIL"
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "SERVICE_PID=$SERVICE_PID"
echo "COMMIT_STATUS=$COMMIT_STATUS"
echo "FETCH_RC=$FETCH_RC"
echo "REBASE_RC=$REBASE_RC"
echo "PUSH_RC=$PUSH_RC"
echo "LOCAL_HEAD=$LOCAL_AFTER"
echo "REMOTE_HEAD=$REMOTE_HEAD"
echo "$SUMMARY"

[ "$STATUS" = "PASS" ]
