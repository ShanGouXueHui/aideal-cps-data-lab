#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aideal_cps_data_lab.engineering_audit.inventory import blocker_files_by_scope
from aideal_cps_data_lab.engineering_audit.limits import load_limits
from aideal_cps_data_lab.engineering_audit.service import AUDIT_GATE_CATEGORIES, run_audit
from aideal_cps_data_lab.git_state import current_git_head


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    settings = load_limits()
    settings["scan_extensions"] = sorted(
        set(settings["scan_extensions"])
        | {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".vue"}
    )
    payload = run_audit(root, settings)
    payload["git_head"] = current_git_head()
    payload["summary"]["blocker_files_by_scope"] = blocker_files_by_scope(payload["findings"])
    report = root / "reports/project_engineering_audit_latest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("===== SUMMARY =====")
    for key in (
        "status",
        "git_head",
        "files_scanned",
        "global_blocker_count",
        "active_blocker_count",
        "compatibility_blocker_count",
        "historical_blocker_count",
        "support_blocker_count",
        "gate_blocker_count",
        "full_gate_blocker_count",
        "warning_count",
        "python_shell_syntax",
    ):
        print(f"{key.upper()}={payload[key]}")
    for category in AUDIT_GATE_CATEGORIES:
        print(f"{category.upper()}={payload[f'{category}_count']}")
    print("REPORT=" + str(report.relative_to(root)))
    return 1 if payload["full_gate_blocker_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
