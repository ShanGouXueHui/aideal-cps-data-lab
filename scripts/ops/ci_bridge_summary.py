#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AUDIT_SUMMARY_FIELDS = (
    ("DUPLICATE_DEFINITION", "duplicate_definition"),
    ("DUPLICATE_ASSIGNMENT", "duplicate_assignment"),
    ("DUPLICATE_CONSTANT_ASSIGNMENT", "duplicate_constant_assignment"),
    ("DUPLICATE_CONFIG_KEY", "duplicate_config_key"),
    ("DUPLICATE_DEFAULT_SOURCE", "duplicate_default_source"),
    ("DUPLICATE_IMPLEMENTATION", "duplicate_implementation"),
    ("LARGE_FILE", "large_file"),
    ("LONG_FUNCTION", "long_function"),
    ("PYTHON_SYNTAX", "python_syntax"),
    ("SHELL_SYNTAX", "shell_syntax"),
    ("CONFIG_SYNTAX", "config_syntax"),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def emit(name: str, value: object) -> None:
    print(f"{name}={value}")


def emit_offline(offline: dict[str, Any]) -> None:
    emit("OFFLINE_STATUS", offline.get("status", "MISSING"))
    emit("OFFLINE_GIT_HEAD", offline.get("git_head", ""))
    emit("TESTS_RUN", offline.get("tests_run", -1))
    emit("TEST_FAILURES", offline.get("test_failure_count", -1))
    emit("TEST_ERRORS", offline.get("test_error_count", -1))
    emit("JD_LIVE_CALLED", str(offline.get("jd_live_called")).lower())


def emit_audit(audit: dict[str, Any]) -> None:
    counts = audit.get("quality_gate_counts") or {}
    emit("AUDIT_STATUS", audit.get("status", "MISSING"))
    emit("AUDIT_GIT_HEAD", audit.get("git_head", ""))
    emit("GLOBAL_BLOCKERS", audit.get("global_blocker_count", -1))
    emit("FULL_GATE_BLOCKERS", audit.get("full_gate_blocker_count", -1))
    emit("ACTIVE_BLOCKERS", audit.get("active_blocker_count", -1))
    emit("COMPATIBILITY_BLOCKERS", audit.get("compatibility_blocker_count", -1))
    emit("HISTORICAL_BLOCKERS", audit.get("historical_blocker_count", -1))
    emit("SUPPORT_BLOCKERS", audit.get("support_blocker_count", -1))
    emit("PYTHON_SHELL_SYNTAX", audit.get("python_shell_syntax", "MISSING"))
    for output_name, category in AUDIT_SUMMARY_FIELDS:
        emit(output_name, counts.get(category, audit.get(f"{category}_count", -1)))


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    emit_offline(load_json(root / "reports/offline_quality_latest.json"))
    emit_audit(load_json(root / "reports/project_engineering_audit_latest.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
