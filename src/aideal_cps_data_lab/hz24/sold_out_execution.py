from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .records import build_unavailable_row, stable_hash
from .repair_preflight import RepairSnapshot
from .repository import atomic_bytes, upsert_jsonl_rows_by_sku
from .settings import HZ24Settings
from .sold_out_evidence import SoldOutEvidence


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    existed: bool
    data: bytes


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def capture_file(path: Path) -> FileSnapshot:
    return FileSnapshot(
        existed=path.exists(),
        data=path.read_bytes() if path.exists() else b"",
    )


def restore_file(path: Path, snapshot: FileSnapshot) -> None:
    if snapshot.existed:
        atomic_bytes(path, snapshot.data)
    else:
        path.unlink(missing_ok=True)


def migration_row(
    settings: HZ24Settings,
    queue_row: dict[str, Any],
    evidence: SoldOutEvidence,
    source_report: Path,
    source_sha: str,
    observed_at: str | None,
) -> dict[str, Any]:
    card = {
        "sku": evidence.sku,
        "itemUrl": evidence.item_url,
        "raw_text": evidence.root_text,
        "title": None,
    }
    row = build_unavailable_row(
        settings,
        card,
        queue_row,
        evidence.tab,
        "sold_out",
        observed_at=observed_at,
    )
    row["migration_source_report"] = str(source_report)
    row["migration_source_report_sha256"] = source_sha
    row["record_sha256"] = stable_hash(
        row,
        tuple(key for key in row if key != "record_sha256"),
    )
    return row


def build_rows(
    settings: HZ24Settings,
    queue: dict[str, dict[str, Any]],
    evidence: list[SoldOutEvidence],
    source_report: Path,
    observed_at: str | None,
) -> list[dict[str, Any]]:
    source_sha = file_digest(source_report)
    return [
        migration_row(
            settings,
            queue[item.sku],
            item,
            source_report,
            source_sha,
            observed_at,
        )
        for item in evidence
    ]


def apply_rows(
    settings: HZ24Settings,
    rows: list[dict[str, Any]],
) -> None:
    upsert_jsonl_rows_by_sku(settings.contracts.unavailable_file, rows)


def post_checks(
    config: dict[str, Any],
    before: RepairSnapshot,
    after: RepairSnapshot,
    evidence_skus: set[str],
    linked_sha_before: str,
    linked_sha_after: str,
) -> dict[str, bool]:
    unavailable_skus = set(after.unavailable)
    return {
        "linked_hash_unchanged": linked_sha_before == linked_sha_after,
        "linked_skus_unchanged": set(before.linked) == set(after.linked),
        "unavailable_count_matches": after.counts["unavailable"]
        == int(config["expected_unavailable_after"]),
        "pending_count_matches": after.counts["pending"]
        == int(config["expected_pending_after"]),
        "migrated_rows_present": evidence_skus.issubset(unavailable_skus),
        "unavailable_exactly_evidence": unavailable_skus == evidence_skus,
        "post_preflight_passed": after.ok,
    }


def summary_payload(
    config: dict[str, Any],
    source_report: Path,
    evidence_skus: set[str],
    preflight: RepairSnapshot,
    evidence_checks: dict[str, bool],
    postflight: RepairSnapshot,
    checks_after: dict[str, bool],
    *,
    execute: bool,
    rolled_back: bool,
    linked_sha_before: str,
    linked_sha_after: str,
    execution_error: str = "",
) -> dict[str, Any]:
    all_checks = {
        **{f"preflight_{name}": value for name, value in preflight.checks.items()},
        **evidence_checks,
        **checks_after,
    }
    if execution_error:
        all_checks["execution_error_empty"] = False
    return {
        "schema_version": str(config["schema_version"]),
        "mode": "execute" if execute else "dry_run",
        "source_report": str(source_report),
        "source_report_sha256": file_digest(source_report),
        "checks": all_checks,
        "failures": [name for name, passed in all_checks.items() if not passed],
        "evidence_count": len(evidence_skus),
        "evidence_skus": sorted(evidence_skus),
        "before_counts": preflight.counts,
        "after_counts": postflight.counts,
        "linked_sha256_before": linked_sha_before,
        "linked_sha256_after": linked_sha_after,
        "executed": execute and not rolled_back,
        "rolled_back": rolled_back,
        "execution_error": execution_error,
        "postflight_issues": postflight.issues,
        "ok": all(all_checks.values()) and not rolled_back,
    }
