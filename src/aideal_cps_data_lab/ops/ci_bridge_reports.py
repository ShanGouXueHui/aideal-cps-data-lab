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


def validate_reports(root: Path, expected_head: str) -> list[str]:
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

    offline = payloads.get(str(REPORT_PATHS[0]), {})
    if offline and offline.get("offline_mode") is not True:
        errors.append("offline_mode_not_enabled")
    if offline and offline.get("jd_live_called") is not False:
        errors.append("jd_live_called_not_false")

    audit = payloads.get(str(REPORT_PATHS[1]), {})
    if audit and "full_gate_blocker_count" not in audit:
        errors.append("full_gate_blocker_count_missing")
    return errors
