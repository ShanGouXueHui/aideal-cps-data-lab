from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.git_state import (
    active_paths_unchanged_since,
    current_git_head,
)

from .jd_page import JDPageAdapter
from .repository import atomic_json, load_json
from .settings import HZ24Settings, load_settings
from .state_store import load_queue
from .validation_config import load_validation_config
from .validation_io import index_by_sku, read_jsonl_checked
from .validation_rules import validate_linked_rows, validate_unavailable_rows

config_path = Path("config/hz24-resume-gate.toml")


def load_gate_config(path: Path = config_path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def issue_count(issues: dict[str, list[str]]) -> int:
    return sum(len(values) for values in issues.values())


def artifact_checks(
    config: dict[str, Any],
    engineering: dict[str, Any],
    offline: dict[str, Any],
    migration: dict[str, Any],
) -> dict[str, bool]:
    expected_unavailable = int(config["expected_unavailable_count"])
    tested_head = str(offline.get("git_head") or "")
    return {
        "engineering_gate_passed": (
            engineering.get("status") == "PASS"
            and int(engineering.get("gate_blocker_count") or 0) == 0
        ),
        "offline_quality_passed": offline.get("status") == "PASS",
        "offline_quality_active_paths_current": active_paths_unchanged_since(
            tested_head
        ),
        "offline_quality_no_jd_live": offline.get("jd_live_called") is False,
        "sold_out_migration_passed": migration.get("ok") is True,
        "sold_out_migration_executed": migration.get("executed") is True,
        "sold_out_evidence_count_matches": int(
            migration.get("evidence_count") or -1
        )
        == expected_unavailable,
        "sold_out_linked_hash_unchanged": (
            (migration.get("post_checks") or {}).get("linked_hash_unchanged")
            is True
        ),
    }


def dataset_checks(
    config: dict[str, Any],
    queue: dict[str, dict[str, Any]],
    linked_rows: list[dict[str, Any]],
    unavailable_rows: list[dict[str, Any]],
    linked_invalid: int,
    unavailable_invalid: int,
    linked_issues: dict[str, list[str]],
    unavailable_issues: dict[str, list[str]],
) -> tuple[dict[str, bool], dict[str, int]]:
    linked, linked_duplicates = index_by_sku(linked_rows)
    unavailable, unavailable_duplicates = index_by_sku(unavailable_rows)
    queue_skus = set(queue)
    linked_skus = set(linked)
    unavailable_skus = set(unavailable)
    pending = queue_skus - linked_skus - unavailable_skus
    sold_out_count = sum(
        row.get("status") == "unavailable" and row.get("reason") == "sold_out"
        for row in unavailable.values()
    )
    counts = {
        "queue": len(queue_skus),
        "linked": len(linked_skus & queue_skus),
        "unavailable": len(unavailable_skus & queue_skus),
        "sold_out": sold_out_count,
        "pending": len(pending),
        "linked_duplicates": linked_duplicates,
        "unavailable_duplicates": unavailable_duplicates,
    }
    checks = {
        "queue_count_matches": counts["queue"] == int(config["expected_queue_count"]),
        "linked_count_matches": counts["linked"] == int(config["expected_linked_count"]),
        "unavailable_count_matches": counts["unavailable"]
        == int(config["expected_unavailable_count"]),
        "sold_out_count_matches": counts["sold_out"]
        == int(config["expected_unavailable_count"]),
        "pending_count_matches": counts["pending"]
        == int(config["expected_pending_count"]),
        "linked_json_valid": linked_invalid == 0,
        "unavailable_json_valid": unavailable_invalid == 0,
        "duplicate_sku_zero": linked_duplicates == 0 and unavailable_duplicates == 0,
        "terminal_overlap_zero": not (linked_skus & unavailable_skus),
        "terminal_extra_zero": not ((linked_skus | unavailable_skus) - queue_skus),
        "linked_status_valid": all(row.get("status") == "ok" for row in linked.values()),
        "unavailable_status_valid": all(
            row.get("status") == "unavailable" for row in unavailable.values()
        ),
        "linked_validation_clean": issue_count(linked_issues) == 0,
        "unavailable_validation_clean": issue_count(unavailable_issues) == 0,
        "queue_accounting_valid": (
            counts["linked"] + counts["unavailable"] + counts["pending"]
            == counts["queue"]
        ),
    }
    return checks, counts


def validate_datasets(
    settings: HZ24Settings,
    config: dict[str, Any],
) -> tuple[dict[str, bool], dict[str, int], dict[str, Any]]:
    queue, queue_sha = load_queue(settings)
    linked_rows, linked_invalid = read_jsonl_checked(settings.contracts.linked_file)
    unavailable_rows, unavailable_invalid = read_jsonl_checked(
        settings.contracts.unavailable_file
    )
    linked, _ = index_by_sku(linked_rows)
    unavailable, _ = index_by_sku(unavailable_rows)
    adapter = JDPageAdapter(settings)
    validation = load_validation_config(settings)
    linked_issues = validate_linked_rows(
        settings,
        validation,
        adapter,
        queue,
        linked,
    )
    unavailable_issues = validate_unavailable_rows(
        settings,
        queue,
        unavailable,
    )
    checks, counts = dataset_checks(
        config,
        queue,
        linked_rows,
        unavailable_rows,
        linked_invalid,
        unavailable_invalid,
        linked_issues,
        unavailable_issues,
    )
    details = {
        "queue_sha256": queue_sha,
        "linked_issues": linked_issues,
        "unavailable_issues": unavailable_issues,
    }
    return checks, counts, details


def run_resume_gate(
    settings: HZ24Settings | None = None,
    path: Path = config_path,
) -> int:
    settings = settings or load_settings()
    config = load_gate_config(path)
    engineering = load_json(Path(str(config["engineering_report"])))
    offline = load_json(Path(str(config["offline_quality_report"])))
    migration = load_json(Path(str(config["sold_out_migration_report"])))
    artifacts = artifact_checks(config, engineering, offline, migration)
    try:
        datasets, counts, details = validate_datasets(settings, config)
    except Exception as error:
        datasets = {"dataset_validation_completed": False}
        counts = {}
        details = {"dataset_error": repr(error)}
    checks = {**artifacts, **datasets}
    result = {
        "schema_version": str(config["schema_version"]),
        "git_head": current_git_head(),
        "tested_git_head": offline.get("git_head"),
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "counts": counts,
        "details": details,
        "resume_allowed": all(checks.values()),
        "collection_started": False,
    }
    atomic_json(Path(str(config["resume_report"])), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["resume_allowed"] else 1
