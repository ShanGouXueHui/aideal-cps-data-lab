from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.quality.offline_runner import run_offline_quality

from .legacy_sold_out import run_migration
from .repair_preflight import load_repair_config
from .repository import atomic_json, load_json
from .resume_gate import run_resume_gate


def _report_path(config: dict[str, Any]) -> Path:
    return Path(str(config["repair_report"]))


def _write(config: dict[str, Any], payload: dict[str, Any]) -> None:
    atomic_json(_report_path(config), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _base_payload(execute: bool) -> dict[str, Any]:
    return {
        "schema_version": "aideal-hz24-terminal-repair-run/v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "execute" if execute else "dry_run",
        "collection_started": False,
        "steps": {},
        "ok": False,
        "ready_for_execute": False,
        "resume_allowed": False,
    }


def _finish(
    config: dict[str, Any],
    payload: dict[str, Any],
    code: int,
) -> int:
    payload["finished_at"] = datetime.now().isoformat(timespec="seconds")
    _write(config, payload)
    return code


def run_terminal_repair(*, execute: bool) -> int:
    config = load_repair_config()
    payload = _base_payload(execute)

    quality_rc = run_offline_quality()
    quality = load_json(Path("reports/offline_quality_latest.json"))
    payload["steps"]["offline_quality"] = {
        "rc": quality_rc,
        "status": quality.get("status"),
        "tests_run": quality.get("tests_run"),
        "git_head": quality.get("git_head"),
        "jd_live_called": quality.get("jd_live_called"),
    }
    if quality_rc != 0 or quality.get("status") != "PASS":
        payload["error"] = "offline_quality_failed"
        return _finish(config, payload, 1)

    source_report = Path(str(config["source_report"]))
    expected = int(config["expected_evidence_count"])
    dry_rc = run_migration(
        source_report,
        execute=False,
        expected_count=expected,
    )
    migration = load_json(Path(str(config["migration_report"])))
    payload["steps"]["migration_dry_run"] = {
        "rc": dry_rc,
        "ok": migration.get("ok"),
        "failures": migration.get("failures") or [],
        "before_counts": migration.get("before_counts") or {},
        "evidence_count": migration.get("evidence_count"),
    }
    if dry_rc != 0 or migration.get("ok") is not True:
        payload["error"] = "migration_dry_run_failed"
        return _finish(config, payload, 1)

    payload["ready_for_execute"] = True
    if not execute:
        payload["ok"] = True
        return _finish(config, payload, 0)

    execute_rc = run_migration(
        source_report,
        execute=True,
        expected_count=expected,
    )
    migration = load_json(Path(str(config["migration_report"])))
    payload["steps"]["migration_execute"] = {
        "rc": execute_rc,
        "ok": migration.get("ok"),
        "executed": migration.get("executed"),
        "rolled_back": migration.get("rolled_back"),
        "failures": migration.get("failures") or [],
        "after_counts": migration.get("after_counts") or {},
    }
    if execute_rc != 0 or migration.get("ok") is not True:
        payload["error"] = "migration_execute_failed"
        return _finish(config, payload, 1)

    gate_rc = run_resume_gate()
    gate = load_json(Path("reports/hz24_resume_gate_latest.json"))
    payload["steps"]["resume_gate"] = {
        "rc": gate_rc,
        "resume_allowed": gate.get("resume_allowed"),
        "failures": gate.get("failures") or [],
        "counts": gate.get("counts") or {},
    }
    payload["resume_allowed"] = gate.get("resume_allowed") is True
    payload["ok"] = gate_rc == 0 and payload["resume_allowed"]
    if not payload["ok"]:
        payload["error"] = "resume_gate_failed"
    return _finish(config, payload, 0 if payload["ok"] else 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    return run_terminal_repair(execute=args.execute)
