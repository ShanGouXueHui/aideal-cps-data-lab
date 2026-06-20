from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

from .ci_bridge_reports import archive_reports, validate_reports


def run_logged(
    command: list[str],
    root: Path,
    log: TextIO,
    env: dict[str, str] | None = None,
) -> int:
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.returncode


def git_value(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def write_summary(path: Path, values: list[tuple[str, object]]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values:
            line = f"{key}={value}"
            print(line)
            stream.write(line + "\n")


def validation_environment() -> dict[str, str]:
    env = dict(os.environ)
    env["AIDEAL_OFFLINE_TEST"] = "1"
    env["AIDEAL_DEPENDENCY_INSTALL_OUTCOME"] = "success"
    env["PYTHONPATH"] = "src"
    return env


def run_checks(root: Path, log: TextIO) -> tuple[int, int, int]:
    python = sys.executable
    env = validation_environment()
    compile_rc = run_logged(
        [python, "-m", "compileall", "-q", "src", "scripts", "tests"],
        root,
        log,
        env,
    )
    offline_rc = run_logged(
        [python, "scripts/run_offline_quality.py"], root, log, env
    )
    audit_rc = run_logged(
        [python, "scripts/engineering_scan_full.py"], root, log, env
    )
    return compile_rc, offline_rc, audit_rc


def publish_reports(root: Path, log: TextIO, expected_head: str) -> int:
    fetch_rc = run_logged(["git", "fetch", "origin", "main"], root, log)
    remote_head = git_value(root, "rev-parse", "origin/main")
    if fetch_rc != 0 or remote_head != expected_head:
        return 1
    return run_logged(
        [
            "bash",
            "scripts/git_publish_files_via_worktree.sh",
            "reports: refresh Singapore CI bridge validation",
            "reports/offline_quality_latest.json",
            "reports/project_engineering_audit_latest.json",
        ],
        root,
        log,
    )


def run_bridge(root: Path, action: str) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = root / "logs" / f"ci_bridge_{timestamp}.log"
    summary_path = root / "run" / "ci_bridge_latest.env"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("", encoding="utf-8")
    expected_head = git_value(root, "rev-parse", "HEAD")

    with log_path.open("a", encoding="utf-8") as log:
        archive_reports(root, timestamp)
        compile_rc, offline_rc, audit_rc = run_checks(root, log)
        report_errors = validate_reports(root, expected_head)
        report_gate_rc = 0 if not report_errors else 1
        for error in report_errors:
            log.write("REPORT_GATE_ERROR=" + error + "\n")

        summary_result = subprocess.run(
            [sys.executable, "scripts/ops/ci_bridge_summary.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if summary_result.stdout:
            with summary_path.open("a", encoding="utf-8") as stream:
                stream.write(summary_result.stdout)
            print(summary_result.stdout, end="")

        publish_rc = 0
        if action == "validate-publish" and report_gate_rc == 0:
            publish_rc = publish_reports(root, log, expected_head)
        elif action == "validate-publish":
            publish_rc = 1

    values = [
        ("ACTION", action),
        ("GIT_HEAD", expected_head),
        ("COMPILE_RC", compile_rc),
        ("OFFLINE_RC", offline_rc),
        ("AUDIT_RC", audit_rc),
        ("REPORT_GATE_RC", report_gate_rc),
        ("PUBLISH_RC", publish_rc),
        ("LOG_FILE", log_path),
    ]
    failed = any(value != 0 for value in (
        compile_rc,
        offline_rc,
        audit_rc,
        report_gate_rc,
        publish_rc,
    ))
    values.append(("STATUS", "FAIL" if failed else "PASS"))
    write_summary(summary_path, values)
    print("===== LOG TAIL =====")
    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]
    print("\n".join(tail))
    return 1 if failed else 0
