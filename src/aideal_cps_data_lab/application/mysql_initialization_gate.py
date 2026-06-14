from __future__ import annotations

from typing import Any


def build_mysql_initialization_gate(
    status: dict[str, Any],
    manifest: dict[str, Any],
    candidate_validation: dict[str, Any],
    *,
    candidate_present: bool,
    upgrade_present: bool,
    rollback_present: bool,
) -> dict[str, Any]:
    status_round = str(((status.get("latest_round") or {}).get("round_id")) or "")
    manifest_round = str(manifest.get("round_id") or "")
    checks = {
        "status_present": bool(status),
        "service_active": ((status.get("service") or {}).get("state") == "active"),
        "observation_ready": status.get("observation_ready") is True,
        "mysql_initialization_allowed": status.get("mysql_initialization_allowed") is True,
        "full_round_complete": ((status.get("checks") or {}).get("full_round_complete") is True),
        "candidate_integrity_ready": ((status.get("checks") or {}).get("candidate_integrity_ready") is True),
        "candidate_file_present": candidate_present,
        "candidate_manifest_present": bool(manifest),
        "candidate_validation_present": bool(candidate_validation),
        "candidate_validation_ok": candidate_validation.get("ok") is True,
        "candidate_hash_mismatch_zero": int(candidate_validation.get("payload_hash_mismatch_count") or 0) == 0,
        "candidate_duplicate_sku_zero": int(candidate_validation.get("duplicate_sku_count") or 0) == 0,
        "candidate_invalid_row_zero": int(candidate_validation.get("invalid_row_count") or 0) == 0,
        "candidate_row_count_matches_manifest": bool(
            candidate_validation
            and int(candidate_validation.get("row_count") or 0)
            == int(manifest.get("row_count") or -1)
        ),
        "candidate_checksum_matches_manifest": bool(
            candidate_validation
            and candidate_validation.get("file_sha256") == manifest.get("data_sha256")
        ),
        "upgrade_file_present": upgrade_present,
        "rollback_file_present": rollback_present,
        "commercial_switch_off": manifest.get("commercial_enabled") is False,
        "round_id_present": bool(status_round and manifest_round),
        "round_id_consistent": bool(status_round and status_round == manifest_round),
    }
    return {
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "ready": all(checks.values()),
        "round_id": manifest_round or None,
    }
