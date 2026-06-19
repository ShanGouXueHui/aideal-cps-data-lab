#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from aideal_cps_data_lab.engineering_audit.limits import load_limits
from aideal_cps_data_lab.engineering_audit.service import run_audit


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
    report = root / "reports/project_engineering_audit_latest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("===== SUMMARY =====")
    print("STATUS=" + str(payload["status"]))
    print("FILES_SCANNED=" + str(payload["files_scanned"]))
    print("BLOCKER_COUNT=" + str(payload["blocker_count"]))
    print("WARNING_COUNT=" + str(payload["warning_count"]))
    print("REPORT=" + str(report.relative_to(root)))
    return 1 if payload["blocker_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
