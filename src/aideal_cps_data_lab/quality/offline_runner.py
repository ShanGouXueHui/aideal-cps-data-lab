from __future__ import annotations

import compileall
import io
import json
import os
import py_compile
import subprocess
import tomllib
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


def compile_paths(entrypoints: list[str]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not compileall.compile_dir("src", quiet=1):
        failures.append("src")
    for value in entrypoints:
        try:
            py_compile.compile(value, doraise=True)
        except Exception:
            failures.append(value)
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


def build_report(
    config: dict[str, Any],
    compile_ok: bool,
    compile_failures: list[str],
    test_result: unittest.TestResult,
    test_output: str,
) -> dict[str, Any]:
    live_marker = Path("run/jd_live_called.flag")
    checks = {
        "compile_ok": compile_ok,
        "tests_ok": test_result.wasSuccessful(),
        "jd_live_called_false": not live_marker.exists(),
        "git_head_present": bool(git_head()),
    }
    return {
        "schema_version": str(config["schema_version"]),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "compile_failures": compile_failures,
        "tests_run": test_result.testsRun,
        "test_failure_count": len(test_result.failures),
        "test_error_count": len(test_result.errors),
        "test_skipped_count": len(getattr(test_result, "skipped", [])),
        "test_output_tail": test_output[-12000:],
        "jd_live_called": live_marker.exists(),
        "offline_mode": os.environ.get("AIDEAL_OFFLINE_TEST") == "1",
    }


def run_offline_quality(path: Path = config_path) -> int:
    os.environ["AIDEAL_OFFLINE_TEST"] = "1"
    config = load_config(path)
    compile_ok, compile_failures = compile_paths(
        [str(value) for value in config["entrypoints"]]
    )
    result, output = run_tests([str(value) for value in config["test_patterns"]])
    report = build_report(config, compile_ok, compile_failures, result, output)
    atomic_json(Path(str(config["report_path"])), report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1
