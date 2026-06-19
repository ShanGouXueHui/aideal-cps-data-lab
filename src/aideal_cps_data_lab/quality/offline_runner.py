from __future__ import annotations

import compileall
import io
import json
import os
import py_compile
import subprocess
import tomllib
import traceback
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.hz24.repository import atomic_json

config_path = Path("config/offline-quality.toml")


def load_config(path: Path = config_path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def compile_python_paths(entrypoints: list[str]) -> list[str]:
    failures: list[str] = []
    if not compileall.compile_dir("src", quiet=1):
        failures.append("src")
    for value in entrypoints:
        try:
            py_compile.compile(value, doraise=True)
        except Exception as error:
            failures.append(f"{value}: {error!r}")
    return failures


def check_shell_paths(entrypoints: list[str]) -> list[str]:
    failures: list[str] = []
    for value in entrypoints:
        result = subprocess.run(
            ["bash", "-n", value],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            failures.append(f"{value}: {detail}")
    return failures


def compile_paths(
    python_entrypoints: list[str],
    shell_entrypoints: list[str],
) -> tuple[bool, list[str]]:
    failures = compile_python_paths(python_entrypoints)
    failures.extend(check_shell_paths(shell_entrypoints))
    return not failures, failures


def build_suite(patterns: list[str]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for pattern in patterns:
        suite.addTests(loader.discover("tests", pattern=pattern))
    return suite


def run_tests(patterns: list[str]) -> tuple[unittest.TestResult, str]:
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        build_suite(patterns)
    )
    return result, stream.getvalue()


def dependency_install_ok() -> bool:
    return os.environ.get("AIDEAL_DEPENDENCY_INSTALL_OUTCOME", "success") == "success"


def build_report(
    config: dict[str, Any],
    compile_ok: bool,
    compile_failures: list[str],
    test_result: unittest.TestResult | None,
    test_output: str,
    runner_error: str,
) -> dict[str, Any]:
    live_marker = Path("run/jd_live_called.flag")
    tests_ok = test_result is not None and test_result.wasSuccessful()
    checks = {
        "dependency_install_ok": dependency_install_ok(),
        "compile_ok": compile_ok,
        "tests_ok": tests_ok,
        "runner_error_empty": not runner_error,
        "jd_live_called_false": not live_marker.exists(),
        "git_head_present": bool(git_head()),
    }
    return {
        "schema_version": str(config.get("schema_version") or "offline-quality/v1"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "compile_failures": compile_failures,
        "tests_run": test_result.testsRun if test_result is not None else 0,
        "test_failure_count": len(test_result.failures) if test_result is not None else 0,
        "test_error_count": len(test_result.errors) if test_result is not None else 0,
        "test_skipped_count": (
            len(getattr(test_result, "skipped", [])) if test_result is not None else 0
        ),
        "test_output_tail": test_output[-12000:],
        "runner_error": runner_error[-12000:],
        "jd_live_called": live_marker.exists(),
        "offline_mode": os.environ.get("AIDEAL_OFFLINE_TEST") == "1",
    }


def fallback_config(path: Path) -> dict[str, Any]:
    return {
        "schema_version": "offline-quality/v1",
        "report_path": "reports/offline_quality_latest.json",
        "entrypoints": [],
        "shell_entrypoints": [],
        "test_patterns": [],
        "config_error": f"failed_to_load:{path}",
    }


def run_offline_quality(path: Path = config_path) -> int:
    os.environ["AIDEAL_OFFLINE_TEST"] = "1"
    config: dict[str, Any]
    compile_ok = False
    compile_failures: list[str] = []
    test_result: unittest.TestResult | None = None
    test_output = ""
    runner_error = ""
    try:
        config = load_config(path)
    except Exception:
        config = fallback_config(path)
        runner_error = traceback.format_exc()
    if not runner_error:
        try:
            compile_ok, compile_failures = compile_paths(
                [str(value) for value in config["entrypoints"]],
                [str(value) for value in config.get("shell_entrypoints") or []],
            )
            test_result, test_output = run_tests(
                [str(value) for value in config["test_patterns"]]
            )
        except Exception:
            runner_error = traceback.format_exc()
    report = build_report(
        config,
        compile_ok,
        compile_failures,
        test_result,
        test_output,
        runner_error,
    )
    report_path = Path(str(config.get("report_path") or "reports/offline_quality_latest.json"))
    atomic_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1
