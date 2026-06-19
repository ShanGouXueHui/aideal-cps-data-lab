from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .jd_page import JDPageAdapter
from .repository import atomic_json, load_json
from .settings import HZ24Settings, load_settings
from .validation_config import ValidationConfig, load_validation_config
from .validation_io import index_by_sku, read_jsonl_checked
from .validation_rules import validate_linked_rows, validate_unavailable_rows


@dataclass(slots=True)
class ValidationData:
    queue_rows: list[dict[str, Any]]
    linked_rows: list[dict[str, Any]]
    unavailable_rows: list[dict[str, Any]]
    queue_invalid: int
    linked_invalid: int
    unavailable_invalid: int
    queue_raw: bytes
    linked_raw: bytes
    unavailable_raw: bytes


def _read_data(settings: HZ24Settings) -> ValidationData:
    queue_rows, queue_invalid = read_jsonl_checked(
        settings.contracts.queue_file
    )
    linked_rows, linked_invalid = read_jsonl_checked(
        settings.contracts.linked_file
    )
    unavailable_rows, unavailable_invalid = read_jsonl_checked(
        settings.contracts.unavailable_file
    )
    return ValidationData(
        queue_rows=queue_rows,
        linked_rows=linked_rows,
        unavailable_rows=unavailable_rows,
        queue_invalid=queue_invalid,
        linked_invalid=linked_invalid,
        unavailable_invalid=unavailable_invalid,
        queue_raw=(
            settings.contracts.queue_file.read_bytes()
            if settings.contracts.queue_file.exists()
            else b""
        ),
        linked_raw=(
            settings.contracts.linked_file.read_bytes()
            if settings.contracts.linked_file.exists()
            else b""
        ),
        unavailable_raw=(
            settings.contracts.unavailable_file.read_bytes()
            if settings.contracts.unavailable_file.exists()
            else b""
        ),
    )


def _checks(
    settings: HZ24Settings,
    data: ValidationData,
    queue_manifest: dict[str, Any],
    queue_by_sku: dict[str, dict[str, Any]],
    linked_by_sku: dict[str, dict[str, Any]],
    unavailable_by_sku: dict[str, dict[str, Any]],
    linked_duplicates: int,
    unavailable_duplicates: int,
    linked_issues: dict[str, list[str]],
    unavailable_issues: dict[str, list[str]],
) -> tuple[dict[str, bool], list[str], list[str], list[str]]:
    queue_skus = set(queue_by_sku)
    linked_skus = set(linked_by_sku)
    unavailable_skus = set(unavailable_by_sku)
    overlap = sorted(linked_skus & unavailable_skus)
    extras = sorted((linked_skus | unavailable_skus) - queue_skus)
    missing = sorted(queue_skus - linked_skus - unavailable_skus)
    queue_sha = hashlib.sha256(data.queue_raw).hexdigest()
    checks = {
        "queue_present": settings.contracts.queue_file.exists(),
        "queue_manifest_present": bool(queue_manifest),
        "queue_json_valid": data.queue_invalid == 0,
        "queue_checksum_valid": queue_sha
        == str(queue_manifest.get("data_sha256") or ""),
        "queue_row_count_valid": len(data.queue_rows)
        == int(queue_manifest.get("row_count") or -1),
        "linked_json_valid": data.linked_invalid == 0,
        "unavailable_json_valid": data.unavailable_invalid == 0,
        "all_queue_skus_accounted": not missing,
        "no_extra_skus": not extras,
        "linked_unavailable_overlap_zero": not overlap,
        "duplicate_sku_zero": linked_duplicates == 0
        and unavailable_duplicates == 0,
        "trusted_url_only": not linked_issues["untrusted"],
        "linked_required_fields_complete": not linked_issues["incomplete"],
        "linked_hash_valid": not linked_issues["hash_mismatch"],
        "linked_source_tab_valid": not linked_issues["tab_mismatch"],
        "unsafe_legacy_source_zero": not linked_issues["unsafe"],
        "unavailable_reason_valid": not unavailable_issues["invalid_reason"],
        "unavailable_hash_valid": not unavailable_issues["hash_mismatch"],
        "unavailable_source_tab_valid": not unavailable_issues["tab_mismatch"],
    }
    return checks, missing, extras, overlap


def _manifest(
    validation: ValidationConfig,
    generated_at: str,
    data: ValidationData,
    queue_count: int,
    linked_count: int,
    unavailable_count: int,
    missing_count: int,
    ready: bool,
) -> dict[str, Any]:
    return {
        "schema_version": validation.outcome_manifest_schema,
        "generated_at": generated_at,
        "status": "validated_candidate" if ready else "incomplete",
        "queue_row_count": queue_count,
        "linked_row_count": linked_count,
        "unavailable_row_count": unavailable_count,
        "accounted_row_count": linked_count + unavailable_count,
        "missing_count": missing_count,
        "linked_sha256": hashlib.sha256(data.linked_raw).hexdigest(),
        "unavailable_sha256": hashlib.sha256(
            data.unavailable_raw
        ).hexdigest(),
        "commercial_enabled": False,
        "merge_allowed": ready,
        "merge_linked_only": True,
    }


def run_validation(settings: HZ24Settings | None = None) -> int:
    settings = settings or load_settings()
    validation = load_validation_config(settings)
    data = _read_data(settings)
    queue_manifest = load_json(settings.contracts.queue_manifest_file)
    queue_by_sku, _ = index_by_sku(data.queue_rows)
    linked_by_sku, linked_duplicates = index_by_sku(data.linked_rows)
    unavailable_by_sku, unavailable_duplicates = index_by_sku(
        data.unavailable_rows
    )
    adapter = JDPageAdapter(settings)
    linked_issues = validate_linked_rows(
        settings,
        validation,
        adapter,
        queue_by_sku,
        linked_by_sku,
    )
    unavailable_issues = validate_unavailable_rows(
        settings,
        queue_by_sku,
        unavailable_by_sku,
    )
    checks, missing, extras, overlap = _checks(
        settings,
        data,
        queue_manifest,
        queue_by_sku,
        linked_by_sku,
        unavailable_by_sku,
        linked_duplicates,
        unavailable_duplicates,
        linked_issues,
        unavailable_issues,
    )
    ready = all(checks.values())
    generated_at = datetime.now().isoformat(timespec="seconds")
    manifest = _manifest(
        validation,
        generated_at,
        data,
        len(queue_by_sku),
        len(set(linked_by_sku) & set(queue_by_sku)),
        len(set(unavailable_by_sku) & set(queue_by_sku)),
        len(missing),
        ready,
    )
    atomic_json(settings.contracts.outcome_manifest_file, manifest)
    report = {
        "ok": ready,
        "generated_at": generated_at,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "queue_count": len(queue_by_sku),
        "linked_count": manifest["linked_row_count"],
        "unavailable_count": manifest["unavailable_row_count"],
        "accounted_count": manifest["accounted_row_count"],
        "missing_count": len(missing),
        "missing_samples": missing[:30],
        "extra_count": len(extras),
        "overlap_count": len(overlap),
        "untrusted_url_count": len(linked_issues["untrusted"]),
        "incomplete_linked_count": len(linked_issues["incomplete"]),
        "linked_hash_mismatch_count": len(linked_issues["hash_mismatch"]),
        "unavailable_invalid_reason_count": len(
            unavailable_issues["invalid_reason"]
        ),
        "unavailable_hash_mismatch_count": len(
            unavailable_issues["hash_mismatch"]
        ),
        "merge_allowed": ready,
        "merge_linked_only": True,
    }
    atomic_json(settings.contracts.validation_report_file, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if ready else 1
