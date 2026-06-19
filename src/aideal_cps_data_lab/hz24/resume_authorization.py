from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.git_state import active_paths_unchanged_since

from .jd_page import JDPageAdapter
from .repository import atomic_json, load_json
from .resume_gate import load_gate_config
from .settings import HZ24Settings, load_settings
from .state_store import load_queue
from .validation_config import load_validation_config
from .validation_io import index_by_sku, read_jsonl_checked
from .validation_rules import validate_linked_rows, validate_unavailable_rows


def _issue_count(issues: dict[str, list[str]]) -> int:
    return sum(len(values) for values in issues.values())


def _current_state(settings: HZ24Settings) -> dict[str, Any]:
    queue, queue_sha = load_queue(settings)
    linked_rows, linked_invalid = read_jsonl_checked(settings.contracts.linked_file)
    unavailable_rows, unavailable_invalid = read_jsonl_checked(
        settings.contracts.unavailable_file
    )
    linked, linked_duplicates = index_by_sku(linked_rows)
    unavailable, unavailable_duplicates = index_by_sku(unavailable_rows)
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
    queue_skus = set(queue)
    linked_skus = set(linked)
    unavailable_skus = set(unavailable)
    pending = queue_skus - linked_skus - unavailable_skus
    return {
        "queue": queue_skus,
        "queue_sha256": queue_sha,
        "linked": linked_skus,
        "unavailable": unavailable_skus,
        "pending": pending,
        "linked_invalid": linked_invalid,
        "unavailable_invalid": unavailable_invalid,
        "linked_duplicates": linked_duplicates,
        "unavailable_duplicates": unavailable_duplicates,
        "linked_issues": linked_issues,
        "unavailable_issues": unavailable_issues,
    }


def _authorization_checks(
    resume: dict[str, Any],
    current: dict[str, Any],
    *,
    require_pending: bool,
) -> dict[str, bool]:
    details = resume.get("details") or {}
    baseline_counts = resume.get("counts") or {}
    baseline_linked = set(details.get("baseline_linked_skus") or [])
    baseline_unavailable = set(details.get("baseline_unavailable_skus") or [])
    queue = current["queue"]
    linked = current["linked"]
    unavailable = current["unavailable"]
    pending = current["pending"]
    return {
        "resume_report_allowed": resume.get("resume_allowed") is True,
        "resume_report_code_current": active_paths_unchanged_since(
            str(resume.get("git_head") or "")
        ),
        "queue_hash_unchanged": current["queue_sha256"]
        == str(details.get("queue_sha256") or ""),
        "baseline_linked_present": bool(baseline_linked)
        and baseline_linked.issubset(linked),
        "baseline_unavailable_present": bool(baseline_unavailable)
        and baseline_unavailable.issubset(unavailable),
        "linked_count_monotonic": len(linked)
        >= int(baseline_counts.get("linked") or -1),
        "unavailable_count_monotonic": len(unavailable)
        >= int(baseline_counts.get("unavailable") or -1),
        "pending_count_monotonic": len(pending)
        <= int(baseline_counts.get("pending") or -1),
        "pending_state_valid": bool(pending) if require_pending else True,
        "json_valid": current["linked_invalid"] == 0
        and current["unavailable_invalid"] == 0,
        "duplicate_sku_zero": current["linked_duplicates"] == 0
        and current["unavailable_duplicates"] == 0,
        "terminal_overlap_zero": not (linked & unavailable),
        "terminal_extra_zero": not ((linked | unavailable) - queue),
        "linked_validation_clean": _issue_count(current["linked_issues"]) == 0,
        "unavailable_validation_clean": _issue_count(
            current["unavailable_issues"]
        )
        == 0,
        "queue_accounting_valid": len(linked) + len(unavailable) + len(pending)
        == len(queue),
    }


def authorize_collection(
    settings: HZ24Settings | None = None,
    *,
    require_pending: bool = True,
) -> tuple[bool, dict[str, Any]]:
    settings = settings or load_settings()
    config = load_gate_config()
    resume = load_json(Path(str(config["resume_report"])))
    try:
        current = _current_state(settings)
        checks = _authorization_checks(
            resume,
            current,
            require_pending=require_pending,
        )
        counts = {
            "queue": len(current["queue"]),
            "linked": len(current["linked"]),
            "unavailable": len(current["unavailable"]),
            "pending": len(current["pending"]),
        }
        details = {
            "queue_sha256": current["queue_sha256"],
            "baseline_git_head": resume.get("git_head"),
            "baseline_counts": resume.get("counts") or {},
            "require_pending": require_pending,
        }
    except Exception as error:
        checks = {"authorization_evaluation_completed": False}
        counts = {}
        details = {"error": repr(error), "require_pending": require_pending}
    result = {
        "schema_version": "aideal-hz24-collection-authorization/v1",
        "authorized": all(checks.values()),
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "counts": counts,
        "details": details,
        "collection_started": False,
    }
    atomic_json(Path(str(config["authorization_report"])), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return bool(result["authorized"]), result
