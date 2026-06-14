#!/usr/bin/env bash
# Publish a compact HZ23 status snapshot without starting, restarting, or touching JD browser automation.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1

mkdir -p reports
OUT="reports/hz23_compact_status_latest.json"
SERVICE_STATE="$(systemctl is-active aideal-hz23-observer.service 2>/dev/null || true)"
LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"

python3 - "$OUT" "$SERVICE_STATE" "$LOCAL_HEAD" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

out_path = Path(sys.argv[1])
service_state = sys.argv[2] or "unknown"
local_head = sys.argv[3] or None


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

state_path = "run/hz23_observer_state.json"
observer_status_path = "reports/hz23_observer_status_latest.json"
probe_prepare_path = "reports/hz23_probe_prepare_latest.json"
probe_scan_path = "reports/hz23_probe_scan_latest.json"
round_path = "reports/hz23_round_latest.json"
manifest_path = "data/export/aideal_cps_products_commercial_candidate_manifest.json"

state = load(state_path)
observer_status = load(observer_status_path)
probe_prepare = load(probe_prepare_path)
probe_scan = load(probe_scan_path)
round_report = load(round_path)
manifest = load(manifest_path)

round_fields = [
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
]
manifest_fields = [
    "generated_at",
    "round_id",
    "data_sha256",
    "row_count",
    "trusted_dedup_sku_count",
    "catalog_index_sku_count",
    "round_seen_sku_count",
    "eligible_sku_count",
    "duplicate_sku_count",
    "round_complete",
    "observation_ready",
    "commercial_enabled",
    "rejected",
]

compact_round = pick(round_report, round_fields)
compact_manifest = pick(manifest, manifest_fields)

round_complete = bool(round_report and round_report.get("commercial_segment_complete") is True)
manifest_ready = bool(manifest and manifest.get("observation_ready") is True)

payload = {
    "schema_version": "aideal-hz23-compact-status/v1",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "git_head": local_head,
    "service_state": service_state,
    "evidence": {
        state_path: Path(state_path).exists(),
        observer_status_path: Path(observer_status_path).exists(),
        probe_prepare_path: Path(probe_prepare_path).exists(),
        probe_scan_path: Path(probe_scan_path).exists(),
        round_path: Path(round_path).exists(),
        manifest_path: Path(manifest_path).exists(),
    },
    "observer_state": pick(
        state,
        [
            "created_at",
            "next_full_due_at",
            "next_probe_due_at",
            "last_probe_at",
            "last_full_started_at",
            "last_full_finished_at",
            "last_full_round_id",
            "last_full_complete",
            "last_stop_reason",
            "requires_manual",
            "successful_full_rounds",
        ],
    ),
    "observer_status": pick(observer_status, ["ts", "mode"]),
    "latest_probe_prepare": pick(probe_prepare, ["ts", "target_page", "ok", "reason"]),
    "latest_probe_scan": pick(
        probe_scan,
        ["ts", "round_id", "page_no", "ok", "reason", "scanned", "new", "changed", "unchanged", "risk"],
    ),
    "latest_round": compact_round,
    "candidate_manifest": compact_manifest,
    "assessment": {
        "full_round_evidence_present": round_report is not None,
        "full_round_complete": round_complete,
        "candidate_manifest_present": manifest is not None,
        "observation_ready": round_complete and manifest_ready,
        "commercial_enabled": bool(manifest and manifest.get("commercial_enabled") is True),
    },
}

tmp = out_path.with_suffix(out_path.suffix + ".tmp")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
tmp.replace(out_path)
PY

PY_RC=$?
if [ "$PY_RC" != "0" ]; then
  echo "===== SUMMARY ====="
  echo "STATUS=FAILED"
  echo "STEP=build_compact_status"
  echo "RC=$PY_RC"
  exit "$PY_RC"
fi

git add "$OUT"
if git diff --cached --quiet; then
  COMMIT_STATUS="no_change"
else
  git commit -m "docs: publish compact HZ23 observer status"
  COMMIT_RC=$?
  if [ "$COMMIT_RC" != "0" ]; then
    echo "===== SUMMARY ====="
    echo "STATUS=FAILED"
    echo "STEP=git_commit"
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

REMOTE_HEAD="$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
LOCAL_HEAD_AFTER="$(git rev-parse HEAD 2>/dev/null || true)"

ASSESSMENT="$(python3 - "$OUT" <<'PY'
import json,sys
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
a=x.get('assessment') or {}
r=x.get('latest_round') or {}
print(
    f"FULL_EVIDENCE={str(bool(a.get('full_round_evidence_present'))).lower()} "
    f"FULL_COMPLETE={str(bool(a.get('full_round_complete'))).lower()} "
    f"OBSERVATION_READY={str(bool(a.get('observation_ready'))).lower()} "
    f"ROUND_ID={r.get('round_id') or ''} "
    f"SCANNED_TOTAL={r.get('scanned_total') if r.get('scanned_total') is not None else ''} "
    f"STOP_REASON={r.get('stop_reason') or ''}"
)
PY
)"

echo "===== SUMMARY ====="
echo "STATUS_FILE=$OUT"
echo "SERVICE_STATE=$SERVICE_STATE"
echo "COMMIT_STATUS=$COMMIT_STATUS"
echo "FETCH_RC=$FETCH_RC"
echo "REBASE_RC=$REBASE_RC"
echo "PUSH_RC=$PUSH_RC"
echo "LOCAL_HEAD=$LOCAL_HEAD_AFTER"
echo "REMOTE_HEAD=$REMOTE_HEAD"
echo "$ASSESSMENT"
