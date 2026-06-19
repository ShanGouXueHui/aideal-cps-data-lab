from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aideal_cps_data_lab.application import validate_candidate
from aideal_cps_data_lab.hz23.safety import unsafe_source_reason
from aideal_cps_data_lab.hz24.repository import atomic_json, load_json
from aideal_cps_data_lab.hz24.settings import load_settings

ROUND = Path("reports/hz23_round_latest.json")
STATE = Path("run/hz23_observer_state.json")
MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
CANDIDATE = Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl")
VALIDATION_MANIFEST = Path("run/hz23_manifest_for_validation.json")
REPORT = Path("reports/hz23_manifest_gate_refresh_latest.json")
EXPECTED_PAGES = list(range(1, 68))
MIN_SCANNED_TOTAL = 3900
MIN_SUCCESSFUL_PROBES = 2
MIN_OBSERVATION_HOURS = 48.0


def source_audit(path: Path) -> dict[str, int]:
    settings = load_settings()
    unsafe = untrusted = invalid = rows = 0
    if not path.exists():
        return {"rows": 0, "unsafe": 0, "untrusted": 0, "invalid": 0}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            invalid += 1
            continue
        if not isinstance(row, dict):
            invalid += 1
            continue
        rows += 1
        if unsafe_source_reason(row):
            unsafe += 1
        value = row.get("short_url")
        parsed = urlparse(str(value or "").strip())
        trusted = (
            parsed.scheme == settings.browser.trusted_link_scheme
            and parsed.hostname == settings.browser.trusted_link_host
        )
        if row.get("status") == "ok" and value and not trusted:
            untrusted += 1
    return {"rows": rows, "unsafe": unsafe, "untrusted": untrusted, "invalid": invalid}


def observation_hours(state: dict[str, Any]) -> float:
    started = state.get("observation_started_at") or state.get("created_at")
    if not started:
        return 0.0
    try:
        elapsed = datetime.now() - datetime.fromisoformat(str(started))
    except Exception:
        return 0.0
    return max(0.0, elapsed.total_seconds() / 3600.0)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    atomic_json(VALIDATION_MANIFEST, manifest)
    try:
        return validate_candidate(CANDIDATE, VALIDATION_MANIFEST).as_dict()
    finally:
        VALIDATION_MANIFEST.unlink(missing_ok=True)


def gate_checks(
    source: Path,
    audit: dict[str, int],
    round_report: dict[str, Any],
    validation: dict[str, Any],
    successful_probes: int,
    hours: float,
) -> dict[str, bool]:
    completed = round_report.get("completed_pages") or []
    unfinished = round_report.get("unfinished_pages") or []
    scanned = int(round_report.get("scanned_total") or 0)
    return {
        "source_present": source.exists(),
        "source_json_valid": audit["invalid"] == 0,
        "commercial_segment_complete": (
            round_report.get("commercial_segment_complete") is True
        ),
        "all_pages_completed": completed == EXPECTED_PAGES,
        "unfinished_pages_empty": unfinished == [],
        "stop_reason_null": round_report.get("stop_reason") in (None, ""),
        "scanned_total_minimum": scanned >= MIN_SCANNED_TOTAL,
        "candidate_validation_ok": validation.get("ok") is True,
        "candidate_nonempty": int(validation.get("row_count") or 0) > 0,
        "candidate_duplicate_sku_zero": int(
            validation.get("duplicate_sku_count") or 0
        )
        == 0,
        "candidate_hash_mismatch_zero": int(
            validation.get("payload_hash_mismatch_count") or 0
        )
        == 0,
        "unsafe_hz20_zero": audit["unsafe"] == 0,
        "untrusted_promotion_url_zero": audit["untrusted"] == 0,
        "successful_probes_minimum": successful_probes >= MIN_SUCCESSFUL_PROBES,
        "observation_hours_minimum": hours >= MIN_OBSERVATION_HOURS,
    }


def refresh_manifest(
    manifest: dict[str, Any],
    rejected: dict[str, Any],
    checks: dict[str, bool],
    successful_probes: int,
    hours: float,
) -> None:
    integrity_names = (
        "source_present",
        "source_json_valid",
        "candidate_validation_ok",
        "candidate_nonempty",
        "candidate_duplicate_sku_zero",
        "candidate_hash_mismatch_zero",
        "unsafe_hz20_zero",
        "untrusted_promotion_url_zero",
    )
    round_names = (
        "commercial_segment_complete",
        "all_pages_completed",
        "unfinished_pages_empty",
        "stop_reason_null",
        "scanned_total_minimum",
    )
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


def failure(error: str, **details: Any) -> int:
    result = {"ok": False, "error": error, **details}
    atomic_json(REPORT, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1


def run_gate_refresh() -> int:
    manifest = load_json(MANIFEST)
    round_report = load_json(ROUND)
    state = load_json(STATE)
    if not manifest or not round_report or not CANDIDATE.exists():
        return failure(
            "required_artifact_missing",
            manifest_present=bool(manifest),
            round_present=bool(round_report),
            candidate_present=CANDIDATE.exists(),
        )
    if str(manifest.get("round_id") or "") != str(round_report.get("round_id") or ""):
        return failure("round_id_mismatch")
    source = Path(str(manifest.get("source_file") or ""))
    audit = source_audit(source)
    rejected = dict(manifest.get("rejected") or {})
    rejected.update(
        unsafe_hz20=audit["unsafe"],
        untrusted_promotion_url=audit["untrusted"],
    )
    validation_manifest = dict(manifest)
    validation_manifest["rejected"] = rejected
    validation = validate_manifest(validation_manifest)
    successful_probes = int(state.get("successful_probes") or 0)
    hours = observation_hours(state)
    checks = gate_checks(
        source,
        audit,
        round_report,
        validation,
        successful_probes,
        hours,
    )
    refresh_manifest(manifest, rejected, checks, successful_probes, hours)
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
