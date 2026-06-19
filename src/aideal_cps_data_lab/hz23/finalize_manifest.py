from __future__ import annotations

from pathlib import Path
from typing import Any

from aideal_cps_data_lab.application.candidate_validation import (
    expected_feed_schema,
    expected_manifest_schema,
)

from .finalize_io import FinalizePaths, observation_hours

expected_pages = set(range(1, 68))
minimum_scanned_total = 3900
minimum_successful_probes = 2
minimum_observation_hours = 48.0


def gate_state(
    summary: dict[str, Any],
    state: dict[str, Any],
    source_present: bool,
    eligible: list[dict[str, Any]],
    unsafe_count: int,
    untrusted_count: int,
    export_sha: str,
    generated_at: str,
) -> tuple[dict[str, bool], dict[str, Any]]:
    completed = {
        int(value)
        for value in summary.get("completed_pages") or []
        if str(value).isdigit()
    }
    unfinished = summary.get("unfinished_pages") or []
    scanned = int(summary.get("scanned_total") or 0)
    probes = int(state.get("successful_probes") or 0)
    hours = observation_hours(state, generated_at)
    skus = [str(row.get("sku") or "") for row in eligible]
    duplicates = len(skus) - len(set(skus))
    checks = {
        "source_present": source_present,
        "commercial_segment_complete": summary.get("commercial_segment_complete") is True,
        "all_pages_completed": completed == expected_pages,
        "unfinished_pages_empty": unfinished == [],
        "stop_reason_null": summary.get("stop_reason") in (None, ""),
        "scanned_total_minimum": scanned >= minimum_scanned_total,
        "candidate_nonempty": bool(eligible),
        "candidate_duplicate_sku_zero": duplicates == 0,
        "unsafe_hz20_zero": unsafe_count == 0,
        "untrusted_promotion_url_zero": untrusted_count == 0,
        "checksum_valid": len(export_sha) == 64,
        "successful_probes_minimum": probes >= minimum_successful_probes,
        "observation_hours_minimum": hours >= minimum_observation_hours,
    }
    values = {
        "completed": completed,
        "unfinished": unfinished,
        "scanned": scanned,
        "probes": probes,
        "hours": hours,
        "duplicates": duplicates,
    }
    return checks, values


def readiness(checks: dict[str, bool]) -> tuple[bool, bool, bool]:
    round_names = (
        "commercial_segment_complete",
        "all_pages_completed",
        "unfinished_pages_empty",
        "stop_reason_null",
        "scanned_total_minimum",
    )
    integrity_names = (
        "source_present",
        "candidate_nonempty",
        "candidate_duplicate_sku_zero",
        "unsafe_hz20_zero",
        "untrusted_promotion_url_zero",
        "checksum_valid",
    )
    return (
        all(checks[name] for name in round_names),
        all(checks[name] for name in integrity_names),
        all(checks.values()),
    )


def lineage_fields(
    summary: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "commercial_segment_complete": summary.get("commercial_segment_complete"),
        "completed_pages": sorted(values["completed"]),
        "unfinished_pages": values["unfinished"],
        "scanned_total": values["scanned"],
        "catalog_new": summary.get("catalog_new"),
        "catalog_changed": summary.get("catalog_changed"),
        "catalog_unchanged": summary.get("catalog_unchanged"),
        "last_known_sku_count": summary.get("last_known_sku_count"),
        "stop_page": summary.get("stop_page"),
        "stop_reason": summary.get("stop_reason"),
    }


def build_manifest(
    round_id: str,
    generated_at: str,
    source: Path | None,
    paths: FinalizePaths,
    eligible: list[dict[str, Any]],
    dedup: dict[str, dict[str, Any]],
    source_duplicates: int,
    products: dict[str, Any],
    seen: set[str],
    rejected: dict[str, int],
    summary: dict[str, Any],
    checks: dict[str, bool],
    values: dict[str, Any],
    export_sha: str,
) -> dict[str, Any]:
    round_ready, integrity_ready, observation_ready = readiness(checks)
    manifest = {
        "schema_version": expected_manifest_schema,
        "feed_schema_version": expected_feed_schema,
        "feed_status": "candidate",
        "generated_at": generated_at,
        "round_id": round_id,
        "source_file": str(source) if source else None,
        "data_file": paths.export.name,
        "candidate_file": str(paths.export),
        "data_sha256": export_sha,
        "row_count": len(eligible),
        "trusted_dedup_sku_count": len(dedup),
        "source_duplicate_sku_count": source_duplicates,
        "catalog_index_sku_count": len(products),
        "round_seen_sku_count": len(seen),
        "eligible_sku_count": len(eligible),
        "rejected": rejected,
        "duplicate_sku_count": values["duplicates"],
        "round_complete": round_ready,
        "candidate_integrity_ready": integrity_ready,
        "successful_probes": values["probes"],
        "minimum_successful_probes": minimum_successful_probes,
        "observation_hours": round(values["hours"], 2),
        "minimum_observation_hours": minimum_observation_hours,
        "gate_checks": checks,
        "gate_failures": [name for name, passed in checks.items() if not passed],
        "observation_ready": observation_ready,
        "commercial_enabled": False,
    }
    manifest.update(lineage_fields(summary, values))
    return manifest
