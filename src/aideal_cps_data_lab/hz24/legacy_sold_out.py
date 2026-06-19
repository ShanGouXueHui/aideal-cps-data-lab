from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .repair_preflight import collect_snapshot, load_repair_config
from .repository import atomic_json, load_json
from .settings import HZ24Settings, load_settings
from .sold_out_evidence import (
    SoldOutEvidence,
    collect_evidence,
    evidence_checks,
    evidence_from_failure,
)
from .sold_out_execution import (
    apply_rows,
    build_rows,
    capture_file,
    file_digest,
    post_checks,
    restore_file,
    summary_payload,
)


def validate_evidence(
    evidence: list[SoldOutEvidence],
    queue: dict[str, dict[str, Any]],
    linked: set[str],
    expected_count: int | None,
    duplicate_count: int,
) -> dict[str, bool]:
    expected = len(evidence) if expected_count is None else expected_count
    return evidence_checks(evidence, queue, linked, expected, duplicate_count)


def _write_report(config: dict[str, Any], payload: dict[str, Any]) -> None:
    atomic_json(Path(str(config["migration_report"])), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _missing_source(
    config: dict[str, Any],
    source_report: Path,
) -> int:
    result = {
        "ok": False,
        "error": "source_report_missing_or_invalid",
        "source_report": str(source_report),
    }
    _write_report(config, result)
    return 2


def _dry_run(
    config: dict[str, Any],
    source_report: Path,
    evidence_skus: set[str],
    preflight,
    checks: dict[str, bool],
    linked_sha: str,
) -> dict[str, Any]:
    return summary_payload(
        config,
        source_report,
        evidence_skus,
        preflight,
        checks,
        preflight,
        {"dry_run_ready": preflight.ok and all(checks.values())},
        execute=False,
        rolled_back=False,
        linked_sha_before=linked_sha,
        linked_sha_after=linked_sha,
    )


def _execute(
    settings: HZ24Settings,
    config: dict[str, Any],
    source_report: Path,
    source: dict[str, Any],
    evidence: list[SoldOutEvidence],
    preflight,
    checks: dict[str, bool],
) -> dict[str, Any]:
    evidence_skus = {item.sku for item in evidence}
    linked_sha_before = file_digest(settings.contracts.linked_file)
    unavailable_before = capture_file(settings.contracts.unavailable_file)
    execution_error = ""
    rolled_back = False
    try:
        rows = build_rows(
            settings,
            preflight.queue,
            evidence,
            source_report,
            str(source.get("generated_at") or "") or None,
        )
        apply_rows(settings, rows)
        postflight = collect_snapshot(settings, config, evidence_skus)
        linked_sha_after = file_digest(settings.contracts.linked_file)
        after_checks = post_checks(
            config,
            preflight,
            postflight,
            evidence_skus,
            linked_sha_before,
            linked_sha_after,
        )
        if not all(after_checks.values()):
            restore_file(settings.contracts.unavailable_file, unavailable_before)
            rolled_back = True
            after_checks["rollback_restored"] = (
                capture_file(settings.contracts.unavailable_file) == unavailable_before
            )
    except Exception as error:
        execution_error = repr(error)
        restore_file(settings.contracts.unavailable_file, unavailable_before)
        rolled_back = True
        postflight = collect_snapshot(settings, config, evidence_skus)
        linked_sha_after = file_digest(settings.contracts.linked_file)
        after_checks = {
            "execution_completed": False,
            "rollback_restored": (
                capture_file(settings.contracts.unavailable_file) == unavailable_before
            ),
        }
    return summary_payload(
        config,
        source_report,
        evidence_skus,
        preflight,
        checks,
        postflight,
        after_checks,
        execute=True,
        rolled_back=rolled_back,
        linked_sha_before=linked_sha_before,
        linked_sha_after=linked_sha_after,
        execution_error=execution_error,
    )


def run_migration(
    source_report: Path,
    *,
    execute: bool,
    expected_count: int | None,
    settings: HZ24Settings | None = None,
) -> int:
    settings = settings or load_settings()
    config = load_repair_config()
    source = load_json(source_report)
    if not source:
        return _missing_source(config, source_report)
    evidence, duplicate_count = collect_evidence(source)
    evidence_skus = {item.sku for item in evidence}
    preflight = collect_snapshot(settings, config, evidence_skus)
    expected = int(config["expected_evidence_count"])
    if expected_count is not None:
        expected = expected_count
    checks = validate_evidence(
        evidence,
        preflight.queue,
        set(preflight.linked),
        expected,
        duplicate_count,
    )
    linked_sha = file_digest(settings.contracts.linked_file)
    if not execute:
        result = _dry_run(
            config,
            source_report,
            evidence_skus,
            preflight,
            checks,
            linked_sha,
        )
    elif not preflight.ok or not all(checks.values()):
        result = summary_payload(
            config,
            source_report,
            evidence_skus,
            preflight,
            checks,
            preflight,
            {"execution_gate_ready": False},
            execute=True,
            rolled_back=False,
            linked_sha_before=linked_sha,
            linked_sha_after=linked_sha,
        )
    else:
        result = _execute(
            settings,
            config,
            source_report,
            source,
            evidence,
            preflight,
            checks,
        )
    _write_report(config, result)
    return 0 if result["ok"] else 1


def main() -> int:
    config = load_repair_config()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-report",
        type=Path,
        default=Path(str(config["source_report"])),
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
