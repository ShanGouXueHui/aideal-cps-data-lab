from __future__ import annotations

import tomli
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .jd_page import JDPageAdapter
from .settings import HZ24Settings
from .state_store import load_queue
from .validation_config import load_validation_config
from .validation_io import index_by_sku, read_jsonl_checked
from .validation_rules import validate_linked_rows, validate_unavailable_rows

repair_config_path = Path("config/hz24-repair.toml")


@dataclass(frozen=True, slots=True)
class RepairSnapshot:
    queue: dict[str, dict[str, Any]]
    linked: dict[str, dict[str, Any]]
    unavailable: dict[str, dict[str, Any]]
    pending: set[str]
    checks: dict[str, bool]
    counts: dict[str, int]
    issues: dict[str, dict[str, list[str]]]

    @property
    def ok(self) -> bool:
        return all(self.checks.values())


def load_repair_config(path: Path = repair_config_path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomli.load(stream)


def _issue_count(issues: dict[str, list[str]]) -> int:
    return sum(len(values) for values in issues.values())


def collect_snapshot(
    settings: HZ24Settings,
    config: dict[str, Any],
    evidence_skus: set[str],
) -> RepairSnapshot:
    queue, _ = load_queue(settings)
    linked_rows, linked_invalid = read_jsonl_checked(settings.contracts.linked_file)
    unavailable_rows, unavailable_invalid = read_jsonl_checked(
        settings.contracts.unavailable_file
    )
    linked, linked_duplicates = index_by_sku(linked_rows)
    unavailable, unavailable_duplicates = index_by_sku(unavailable_rows)
    queue_skus = set(queue)
    linked_skus = set(linked)
    unavailable_skus = set(unavailable)
    pending = queue_skus - linked_skus - unavailable_skus
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
    counts = {
        "queue": len(queue_skus),
        "linked": len(linked_skus & queue_skus),
        "unavailable": len(unavailable_skus & queue_skus),
        "pending": len(pending),
        "linked_duplicates": linked_duplicates,
        "unavailable_duplicates": unavailable_duplicates,
    }
    allowed_unavailable = {
        int(value) for value in config["expected_unavailable_before"]
    }
    allowed_pending = {int(value) for value in config["expected_pending_before"]}
    checks = {
        "queue_count_matches": counts["queue"]
        == int(config["expected_queue_count"]),
        "linked_count_matches": counts["linked"]
        == int(config["expected_linked_count"]),
        "unavailable_count_allowed": counts["unavailable"] in allowed_unavailable,
        "pending_count_allowed": counts["pending"] in allowed_pending,
        "json_valid": linked_invalid == 0 and unavailable_invalid == 0,
        "duplicate_sku_zero": linked_duplicates == 0
        and unavailable_duplicates == 0,
        "terminal_overlap_zero": not (linked_skus & unavailable_skus),
        "terminal_extra_zero": not ((linked_skus | unavailable_skus) - queue_skus),
        "linked_validation_clean": _issue_count(linked_issues) == 0,
        "unavailable_validation_clean": _issue_count(unavailable_issues) == 0,
        "evidence_in_queue": evidence_skus.issubset(queue_skus),
        "evidence_not_linked": not (evidence_skus & linked_skus),
        "existing_unavailable_matches_evidence": (
            not unavailable_skus or unavailable_skus == evidence_skus
        ),
        "queue_accounting_valid": (
            counts["linked"] + counts["unavailable"] + counts["pending"]
            == counts["queue"]
        ),
    }
    return RepairSnapshot(
        queue=queue,
        linked=linked,
        unavailable=unavailable,
        pending=pending,
        checks=checks,
        counts=counts,
        issues={"linked": linked_issues, "unavailable": unavailable_issues},
    )
