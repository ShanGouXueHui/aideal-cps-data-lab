#!/usr/bin/env python3
from __future__ import annotations

import json
import tomllib
from collections import Counter
from pathlib import Path

from aideal_cps_data_lab.engineering_audit.limits import load_limits
from aideal_cps_data_lab.engineering_audit.service import run_audit


def _active(path: str, scope: dict[str, object]) -> bool:
    if any(path.startswith(str(value)) for value in scope["active_prefixes"]):
        return True
    if path in {str(value) for value in scope["active_run_files"]}:
        return True
    if any(path.startswith(str(value)) for value in scope["active_run_prefixes"]):
        return True
    if any(path.startswith(str(value)) for value in scope["active_script_prefixes"]):
        return True
    if path in {str(value) for value in scope["active_script_names"]}:
        return True
    return path.startswith("scripts/") and any(
        str(value) in path
        for value in scope["active_script_fragments"]
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    settings = load_limits()
    settings["excluded_directories"] = [
        value
        for value in settings["excluded_directories"]
        if value != "run"
    ]
    with (root / "config/engineering-active-scope.toml").open("rb") as stream:
        scope = tomllib.load(stream)
    full = run_audit(root, settings)
    findings = [
        item
        for item in full["findings"]
        if _active(str(item.get("path") or ""), scope)
    ]
    blockers = sum(item["severity"] == "blocker" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    categories = Counter(str(item["category"]) for item in findings)
    payload = {
        "schema_version": str(scope["schema_version"]),
        "generated_at": full["generated_at"],
        "status": "PASS" if blockers == 0 else "FAIL",
        "full_files_scanned": full["files_scanned"],
        "active_blocker_count": blockers,
        "active_warning_count": warnings,
        "category_counts": dict(sorted(categories.items())),
        "findings": findings,
    }
    report = root / "reports/project_engineering_active_audit_latest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("===== SUMMARY =====")
    print("STATUS=" + payload["status"])
    print("ACTIVE_BLOCKER_COUNT=" + str(blockers))
    print("ACTIVE_WARNING_COUNT=" + str(warnings))
    print("REPORT=" + str(report.relative_to(root)))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
