#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def emit(name: str, value: object) -> None:
    print(f"{name}={value}")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    offline = load_json(root / "reports/offline_quality_latest.json")
    audit = load_json(root / "reports/project_engineering_audit_latest.json")
    categories = (audit.get("summary") or {}).get("category_counts") or {}

    emit("OFFLINE_STATUS", offline.get("status", "MISSING"))
    emit("OFFLINE_GIT_HEAD", offline.get("git_head", ""))
    emit("TESTS_RUN", offline.get("tests_run", -1))
    emit("TEST_FAILURES", offline.get("test_failure_count", -1))
    emit("TEST_ERRORS", offline.get("test_error_count", -1))
    emit("JD_LIVE_CALLED", str(offline.get("jd_live_called")).lower())

    emit("AUDIT_STATUS", audit.get("status", "MISSING"))
    emit("AUDIT_GIT_HEAD", audit.get("git_head", ""))
    emit("GLOBAL_BLOCKERS", audit.get("blocker_count", -1))
    emit("FULL_GATE_BLOCKERS", audit.get("full_gate_blocker_count", -1))
    emit("ACTIVE_BLOCKERS", audit.get("active_blocker_count", -1))
    emit("COMPATIBILITY_BLOCKERS", audit.get("compatibility_blocker_count", -1))
    emit("HISTORICAL_BLOCKERS", audit.get("historical_blocker_count", -1))
    emit("SUPPORT_BLOCKERS", audit.get("support_blocker_count", -1))
    emit("DUPLICATE_DEFINITION", categories.get("duplicate_definition", 0))
    emit("DUPLICATE_ASSIGNMENT", categories.get("duplicate_assignment", 0))
    emit("DUPLICATE_CONFIG_KEY", categories.get("duplicate_config_key", 0))
    emit("DUPLICATE_IMPLEMENTATION", categories.get("duplicate_implementation", 0))
    emit("LARGE_FILE", categories.get("large_file", 0))
    emit("LONG_FUNCTION", categories.get("long_function", 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
