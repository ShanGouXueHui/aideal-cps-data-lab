#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aideal_cps_data_lab.engineering_audit.limits import load_limits
from aideal_cps_data_lab.engineering_audit.service import run_audit
from aideal_cps_data_lab.git_state import current_git_head


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    settings = load_limits()
    settings["excluded_directories"] = [
        value for value in settings["excluded_directories"] if value != "run"
    ]
    settings["scan_extensions"] = sorted(
        set(settings["scan_extensions"])
        | {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".vue"}
    )
    payload = run_audit(root, settings)
    payload["git_head"] = current_git_head()
    report = root / "reports/project_engineering_audit_latest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("===== SUMMARY =====")
    print("STATUS=" + str(payload["status"]))
    print("GIT_HEAD=" + str(payload["git_head"]))
    print("FILES_SCANNED=" + str(payload["files_scanned"]))
    print("GLOBAL_BLOCKER_COUNT=" + str(payload["blocker_count"]))
    print("ACTIVE_BLOCKER_COUNT=" + str(payload["active_blocker_count"]))
    print("COMPATIBILITY_BLOCKER_COUNT=" + str(payload["compatibility_blocker_count"]))
    print("HISTORICAL_BLOCKER_COUNT=" + str(payload["historical_blocker_count"]))
    print("SUPPORT_BLOCKER_COUNT=" + str(payload["support_blocker_count"]))
    print("GATE_BLOCKER_COUNT=" + str(payload["gate_blocker_count"]))
    print("WARNING_COUNT=" + str(payload["warning_count"]))
    print("REPORT=" + str(report.relative_to(root)))
    return 1 if payload["gate_blocker_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
