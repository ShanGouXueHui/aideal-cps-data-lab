from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .browser_contract import DISABLED_CARD_CLASS, SOLD_OUT_TEXT
from .records import build_unavailable_row, stable_hash
from .repository import (
    atomic_json,
    load_json,
    read_jsonl,
    upsert_jsonl_by_sku,
)
from .settings import HZ24Settings, load_settings
from .state_store import load_queue
from .terminal_state import load_terminal_state

migration_report_path = Path("reports/hz24_sold_out_migration_latest.json")


@dataclass(frozen=True, slots=True)
class SoldOutEvidence:
    sku: str
    tab: str
    item_url: str
    root_text: str


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def evidence_from_failure(failure: dict[str, Any]) -> SoldOutEvidence | None:
    click = failure.get("click") or {}
    hit = click.get("hit") or {}
    matched = ((click.get("mark") or {}).get("matched") or {})
    root_text = str(matched.get("rootText") or "")
    sku = str(failure.get("sku") or click.get("sku") or "").strip()
    tab = str(failure.get("tab") or "").strip()
    if not sku or not tab:
        return None
    if DISABLED_CARD_CLASS not in str(hit.get("cls") or ""):
        return None
    if SOLD_OUT_TEXT not in root_text:
        return None
    return SoldOutEvidence(
        sku=sku,
        tab=tab,
        item_url=str(matched.get("itemUrl") or "").strip(),
        root_text=root_text,
    )


def collect_evidence(report: dict[str, Any]) -> tuple[list[SoldOutEvidence], int]:
    indexed: dict[str, SoldOutEvidence] = {}
    duplicate_count = 0
    for failure in report.get("failures") or []:
        if not isinstance(failure, dict):
            continue
        evidence = evidence_from_failure(failure)
        if evidence is None:
            continue
        if evidence.sku in indexed:
            duplicate_count += 1
        indexed[evidence.sku] = evidence
    return [indexed[sku] for sku in sorted(indexed)], duplicate_count


def validate_evidence(
    evidence: list[SoldOutEvidence],
    queue: dict[str, dict[str, Any]],
    linked: set[str],
    expected_count: int | None,
    duplicate_count: int,
) -> dict[str, bool]:
    queue_skus = set(queue)
    return {
        "evidence_nonempty": bool(evidence),
        "evidence_duplicate_zero": duplicate_count == 0,
        "expected_count_matches": (
            expected_count is None or len(evidence) == expected_count
        ),
        "all_evidence_in_queue": all(item.sku in queue_skus for item in evidence),
        "none_already_linked": all(item.sku not in linked for item in evidence),
        "source_tabs_match_queue": all(
            item.tab in set(queue.get(item.sku, {}).get("source_tabs") or [])
            for item in evidence
        ),
    }


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


def write_rows(
    settings: HZ24Settings,
    queue: dict[str, dict[str, Any]],
    evidence: list[SoldOutEvidence],
    source_report: Path,
    source_sha: str,
    observed_at: str | None,
) -> None:
    for item in evidence:
        row = migration_row(
            settings,
            queue[item.sku],
            item,
            source_report,
            source_sha,
            observed_at,
        )
        upsert_jsonl_by_sku(settings.contracts.unavailable_file, row)


def build_summary(
    settings: HZ24Settings,
    queue: dict[str, dict[str, Any]],
    linked_before: set[str],
    evidence: list[SoldOutEvidence],
    checks: dict[str, bool],
    source_report: Path,
    source_sha: str,
    execute: bool,
    linked_sha_before: str,
) -> dict[str, Any]:
    state_after = load_terminal_state(
        settings.contracts.linked_file,
        settings.contracts.unavailable_file,
    )
    queue_skus = set(queue)
    pending = queue_skus - state_after.linked - state_after.unavailable
    linked_sha_after = file_digest(settings.contracts.linked_file)
    migrated = {item.sku for item in evidence}
    post_checks = {
        "linked_hash_unchanged": linked_sha_before == linked_sha_after,
        "linked_count_unchanged": linked_before == state_after.linked,
        "migrated_rows_present": (
            not execute or migrated.issubset(state_after.unavailable)
        ),
        "terminal_overlap_zero": not state_after.overlap,
        "terminal_subset_of_queue": (
            state_after.linked | state_after.unavailable
        ).issubset(queue_skus),
        "queue_accounting_valid": (
            len(state_after.linked)
            + len(state_after.unavailable)
            + len(pending)
            == len(queue_skus)
        ),
    }
    return {
        "schema_version": "aideal-hz24-sold-out-migration/v1",
        "mode": "execute" if execute else "dry_run",
        "source_report": str(source_report),
        "source_report_sha256": source_sha,
        "checks": checks,
        "post_checks": post_checks,
        "failures": [
            name
            for name, passed in {**checks, **post_checks}.items()
            if not passed
        ],
        "evidence_count": len(evidence),
        "evidence_skus": sorted(migrated),
        "queue_count": len(queue_skus),
        "linked_count": len(state_after.linked),
        "unavailable_count": len(state_after.unavailable),
        "pending_count": len(pending),
        "linked_sha256_before": linked_sha_before,
        "linked_sha256_after": linked_sha_after,
        "executed": execute,
        "ok": all(checks.values()) and all(post_checks.values()),
    }


def run_migration(
    source_report: Path,
    *,
    execute: bool,
    expected_count: int | None,
    settings: HZ24Settings | None = None,
) -> int:
    settings = settings or load_settings()
    report = load_json(source_report)
    if not report:
        result = {"ok": False, "error": "source_report_missing_or_invalid"}
        atomic_json(migration_report_path, result)
        return 2
    queue, _ = load_queue(settings)
    state_before = load_terminal_state(
        settings.contracts.linked_file,
        settings.contracts.unavailable_file,
    )
    evidence, duplicate_count = collect_evidence(report)
    checks = validate_evidence(
        evidence,
        queue,
        state_before.linked,
        expected_count,
        duplicate_count,
    )
    linked_sha_before = file_digest(settings.contracts.linked_file)
    if execute and all(checks.values()):
        write_rows(
            settings,
            queue,
            evidence,
            source_report,
            file_digest(source_report),
            str(report.get("generated_at") or "") or None,
        )
    result = build_summary(
        settings,
        queue,
        state_before.linked,
        evidence,
        checks,
        source_report,
        file_digest(source_report),
        execute and all(checks.values()),
        linked_sha_before,
    )
    atomic_json(migration_report_path, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-report",
        type=Path,
        default=Path("reports/hz24_increment_collection_latest.json"),
    )
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute and args.expected_count is None:
        parser.error("--expected-count is required with --execute")
    return run_migration(
        args.source_report,
        execute=args.execute,
        expected_count=args.expected_count,
    )
