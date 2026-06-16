#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aideal_cps_data_lab.application import validate_candidate
from hz23_quarantine_unsafe_source_rows import unsafe_reason

ROUND = Path("reports/hz23_round_latest.json")
STATE = Path("run/hz23_observer_state.json")
MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
CANDIDATE = Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl")
REPORT = Path("reports/hz23_manifest_gate_refresh_latest.json")
EXPECTED_PAGES = list(range(1, 68))
MIN_SCANNED_TOTAL = 3900
MIN_SUCCESSFUL_PROBES = 2
MIN_OBSERVATION_HOURS = 48.0


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def trusted_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname == "u.jd.com"


def source_audit(path: Path) -> dict[str, int]:
    unsafe = 0
    untrusted = 0
    invalid = 0
    rows = 0
    if not path.exists():
        return {"rows": 0, "unsafe": 0, "untrusted": 0, "invalid": 0}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            invalid += 1
            continue
        if not isinstance(row, dict):
            invalid += 1
            continue
        rows += 1
        if unsafe_reason(row):
            unsafe += 1
        if row.get("status") == "ok" and row.get("short_url") and not trusted_url(row.get("short_url")):
            untrusted += 1
    return {"rows": rows, "unsafe": unsafe, "untrusted": untrusted, "invalid": invalid}


def observation_hours(state: dict[str, Any]) -> float:
    started = state.get("observation_started_at") or state.get("created_at")
    if not started:
        return 0.0
    try:
        return max(0.0, (datetime.now() - datetime.fromisoformat(str(started))).total_seconds() / 3600.0)
    except Exception:
        return 0.0


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    manifest = load(MANIFEST)
    round_report = load(ROUND)
    state = load(STATE)
    if not manifest or not round_report or not CANDIDATE.exists():
        result = {
            "ok": False,
            "error": "required_artifact_missing",
            "manifest_present": bool(manifest),
            "round_present": bool(round_report),
            "candidate_present": CANDIDATE.exists(),
        }
        atomic_json(REPORT, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1

    if str(manifest.get("round_id") or "") != str(round_report.get("round_id") or ""):
        result = {"ok": False, "error": "round_id_mismatch"}
        atomic_json(REPORT, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1

    validation = validate_candidate(CANDIDATE, MANIFEST).as_dict()
    source = Path(str(manifest.get("source_file") or ""))
    audit = source_audit(source)
    completed = round_report.get("completed_pages") or []
    unfinished = round_report.get("unfinished_pages") or []
    scanned = int(round_report.get("scanned_total") or 0)
    successful_probes = int(state.get("successful_probes") or 0)
    hours = observation_hours(state)

    checks = {
        "source_present": source.exists(),
        "source_json_valid": audit["invalid"] == 0,
        "commercial_segment_complete": round_report.get("commercial_segment_complete") is True,
        "all_pages_completed": completed == EXPECTED_PAGES,
        "unfinished_pages_empty": unfinished == [],
        "stop_reason_null": round_report.get("stop_reason") in (None, ""),
        "scanned_total_minimum": scanned >= MIN_SCANNED_TOTAL,
        "candidate_validation_ok": validation.get("ok") is True,
        "candidate_nonempty": int(validation.get("row_count") or 0) > 0,
        "candidate_duplicate_sku_zero": int(validation.get("duplicate_sku_count") or 0) == 0,
        "candidate_hash_mismatch_zero": int(validation.get("payload_hash_mismatch_count") or 0) == 0,
        "unsafe_hz20_zero": audit["unsafe"] == 0,
        "untrusted_promotion_url_zero": audit["untrusted"] == 0,
        "successful_probes_minimum": successful_probes >= MIN_SUCCESSFUL_PROBES,
        "observation_hours_minimum": hours >= MIN_OBSERVATION_HOURS,
    }
    integrity_names = [
        "source_present",
        "source_json_valid",
        "candidate_validation_ok",
        "candidate_nonempty",
        "candidate_duplicate_sku_zero",
        "candidate_hash_mismatch_zero",
        "unsafe_hz20_zero",
        "untrusted_promotion_url_zero",
    ]
    round_names = [
        "commercial_segment_complete",
        "all_pages_completed",
        "unfinished_pages_empty",
        "stop_reason_null",
        "scanned_total_minimum",
    ]

    rejected = dict(manifest.get("rejected") or {})
    rejected["unsafe_hz20"] = audit["unsafe"]
    rejected["untrusted_promotion_url"] = audit["untrusted"]
    manifest.update(
        gate_refreshed_at=datetime.now().isoformat(timespec="seconds"),
        successful_probes=successful_probes,
        observation_hours=round(hours, 2),
        rejected=rejected,
        gate_checks=checks,
        gate_failures=[name for name, passed in checks.items() if not passed],
        round_complete=all(checks[name] for name in round_names),
        candidate_integrity_ready=all(checks[name] for name in integrity_names),
        observation_ready=all(checks.values()),
        commercial_enabled=False,
    )
    atomic_json(MANIFEST, manifest)

    result = {
        "ok": True,
        "round_id": manifest.get("round_id"),
        "source_audit": audit,
        "candidate_validation_ok": validation.get("ok"),
        "candidate_row_count": validation.get("row_count"),
        "candidate_integrity_ready": manifest["candidate_integrity_ready"],
        "successful_probes": successful_probes,
        "observation_hours": manifest["observation_hours"],
        "observation_ready": manifest["observation_ready"],
        "gate_failures": manifest["gate_failures"],
    }
    atomic_json(REPORT, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
