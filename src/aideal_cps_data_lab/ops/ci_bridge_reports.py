from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPORT_PATHS = (
    Path("reports/offline_quality_latest.json"),
    Path("reports/project_engineering_audit_latest.json"),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def archive_reports(root: Path, stamp: str) -> list[str]:
    archive = root / "run" / f"ci_bridge_previous_{stamp}"
    moved: list[str] = []
    for relative in REPORT_PATHS:
        source = root / relative
        if not source.exists():
            continue
        archive.mkdir(parents=True, exist_ok=True)
        destination = archive / relative.name
        source.replace(destination)
        moved.append(str(relative))
    return moved


def _require_equal(
    payload: dict[str, Any],
    key: str,
    expected: object,
    error: str,
    errors: list[str],
) -> None:
    if payload.get(key) != expected:
        errors.append(error)


def _load_reports(root: Path, expected_head: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    for relative in REPORT_PATHS:
        target = root / relative
        if not target.exists():
            errors.append(f"missing:{relative}")
            continue
        try:
            payload = load_json(target)
        except Exception as error:
            errors.append(f"invalid_json:{relative}:{error!r}")
            continue
        payloads[str(relative)] = payload
        if payload.get("git_head") != expected_head:
            errors.append(f"git_head_mismatch:{relative}")
        if not payload.get("generated_at"):
            errors.append(f"generated_at_missing:{relative}")
    return payloads, errors


def _validate_offline(payload: dict[str, Any], errors: list[str]) -> None:
    if not payload:
        return
    _require_equal(payload, "status", "PASS", "offline_status_not_pass", errors)
    _require_equal(payload, "offline_mode", True, "offline_mode_not_enabled", errors)
    _require_equal(payload, "jd_live_called", False, "jd_live_called_not_false", errors)
    _require_equal(payload, "test_failure_count", 0, "offline_failures_not_zero", errors)
    _require_equal(payload, "test_error_count", 0, "offline_errors_not_zero", errors)


def _validate_audit(payload: dict[str, Any], errors: list[str]) -> None:
    if not payload:
        return
    _require_equal(payload, "status", "PASS", "audit_status_not_pass", errors)
    _require_equal(payload, "global_blocker_count", 0, "global_blockers_not_zero", errors)
    _require_equal(payload, "full_gate_blocker_count", 0, "full_gate_blockers_not_zero", errors)


def validate_reports(root: Path, expected_head: str) -> list[str]:
    payloads, errors = _load_reports(root, expected_head)
    _validate_offline(payloads.get(str(REPORT_PATHS[0]), {}), errors)
    _validate_audit(payloads.get(str(REPORT_PATHS[1]), {}), errors)
    return errors
