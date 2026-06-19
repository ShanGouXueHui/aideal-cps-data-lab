from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import ABS_PATH_RE, IP_RE, URL_RE, is_configuration_file, iter_engineering_files
from .models import Finding, FunctionFingerprint
from .python_scan import scan_python
from .shell_scan import scan_shell


def _merge_literals(
    target: dict[str, set[str]],
    source: dict[str, set[str]],
) -> None:
    for value, paths in source.items():
        target[value].update(paths)


def _scan_generic(
    root: Path,
    path: Path,
    settings: dict[str, object],
) -> list[Finding]:
    findings: list[Finding] = []
    text = (root / path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > int(settings["large_file_line_limit"]):
        findings.append(
            Finding(
                "blocker",
                "large_file",
                str(path),
                1,
                "",
                f"{len(lines)} lines exceeds {settings['large_file_line_limit']}",
            )
        )
    if is_configuration_file(path, settings):
        return findings
    for line_number, line in enumerate(lines, start=1):
        for category, pattern in (
            ("hardcoded_url", URL_RE),
            ("hardcoded_ip", IP_RE),
            ("hardcoded_absolute_path", ABS_PATH_RE),
        ):
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(
                        "blocker",
                        category,
                        str(path),
                        line_number,
                        "",
                        match.group(0)[:240],
                    )
                )
    return findings


def _duplicate_implementation_findings(
    fingerprints: list[FunctionFingerprint],
    settings: dict[str, object],
) -> list[Finding]:
    ignored = set(str(value) for value in settings["ignored_function_names"])
    minimum = int(settings["duplicate_function_min_lines"])
    groups: dict[tuple[str, str], list[FunctionFingerprint]] = defaultdict(list)
    for item in fingerprints:
        if item.name in ignored or item.line_count < minimum:
            continue
        groups[(item.name, item.digest)].append(item)

    findings: list[Finding] = []
    for (name, _), group in groups.items():
        if len({item.path for item in group}) < 2:
            continue
        detail = ", ".join(f"{item.path}:{item.line}" for item in group)
        for item in group:
            findings.append(
                Finding(
                    "blocker",
                    "duplicate_implementation",
                    item.path,
                    item.line,
                    name,
                    detail,
                )
            )
    return findings


def run_audit(root: Path, settings: dict[str, object]) -> dict[str, Any]:
    findings: list[Finding] = []
    fingerprints: list[FunctionFingerprint] = []
    literals: dict[str, set[str]] = defaultdict(set)
    files = list(iter_engineering_files(root, settings))

    for path in files:
        if path.suffix == ".py":
            file_findings, file_fingerprints, file_literals = scan_python(
                root,
                path,
                settings,
            )
            findings.extend(file_findings)
            fingerprints.extend(file_fingerprints)
            _merge_literals(literals, file_literals)
        elif path.suffix == ".sh":
            file_findings, file_literals = scan_shell(root, path, settings)
            findings.extend(file_findings)
            _merge_literals(literals, file_literals)
        else:
            findings.extend(_scan_generic(root, path, settings))

    findings.extend(_duplicate_implementation_findings(fingerprints, settings))
    minimum_files = int(settings["repeated_literal_min_files"])
    for value, paths in literals.items():
        if len(paths) < minimum_files:
            continue
        findings.append(
            Finding(
                "warning",
                "repeated_literal",
                sorted(paths)[0],
                0,
                "",
                f"{value[:160]!r} repeated in {len(paths)} files: {', '.join(sorted(paths))}",
            )
        )

    findings = sorted(
        findings,
        key=lambda item: (
            item.severity != "blocker",
            item.path,
            item.line,
            item.category,
        ),
    )
    blocker_count = sum(item.severity == "blocker" for item in findings)
    warning_count = sum(item.severity == "warning" for item in findings)
    return {
        "schema_version": str(settings["schema_version"]),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if blocker_count == 0 else "FAIL",
        "files_scanned": len(files),
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "findings": [asdict(item) for item in findings],
    }
