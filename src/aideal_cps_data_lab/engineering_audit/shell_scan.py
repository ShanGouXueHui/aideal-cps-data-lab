from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

from .common import (
    ABS_PATH_RE,
    IP_RE,
    SHELL_FUNCTION_RE,
    URL_RE,
    is_configuration_file,
    name_has_fragment,
)
from .default_sources import shell_default_sources
from .models import DefaultSource, Finding
from .shell_assignments import (
    AssignmentMap,
    assignment_findings,
    parse_assignment,
    record_assignment,
)

QUOTED_LITERAL_RE = re.compile(r"['\"]([^'\"]{8,})['\"]")
DYNAMIC_VALUE_RE = re.compile(r"\$\{|\$\(|\$[A-Za-z_?]")
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
FUNCTION_END_RE = re.compile(r"^\s*}\s*(?:#.*)?$")


def _environment_findings(
    path: Path,
    line_number: int,
    line: str,
    shebang: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    url_match = URL_RE.search(line)
    if url_match:
        findings.append(
            Finding(
                "blocker",
                "hardcoded_url",
                str(path),
                line_number,
                "",
                url_match.group(0)[:240],
            )
        )
    else:
        ip_match = IP_RE.search(line)
        if ip_match:
            findings.append(
                Finding(
                    "blocker",
                    "hardcoded_ip",
                    str(path),
                    line_number,
                    "",
                    ip_match.group(0)[:240],
                )
            )
    if not shebang:
        path_match = ABS_PATH_RE.search(line)
        if path_match:
            findings.append(
                Finding(
                    "blocker",
                    "hardcoded_absolute_path",
                    str(path),
                    line_number,
                    "",
                    path_match.group(0)[:240],
                )
            )
    return findings


def _hardcoded_assignment(
    path: Path,
    line_number: int,
    assignment: tuple[str, str, bool],
    fragments: tuple[str, ...],
) -> Finding | None:
    name, value, _ = assignment
    if (
        not name.isupper()
        or not name_has_fragment(name, fragments)
        or DYNAMIC_VALUE_RE.search(value)
    ):
        return None
    return Finding(
        "blocker",
        "hardcoded_parameter",
        str(path),
        line_number,
        name,
        value.strip()[:240],
    )


def _function_findings(
    path: Path,
    functions: dict[str, list[int]],
    ranges: list[tuple[str, int, int]],
    long_function_limit: int,
) -> list[Finding]:
    findings: list[Finding] = []
    for name, locations in functions.items():
        for line_number in locations[1:]:
            findings.append(
                Finding(
                    "blocker",
                    "duplicate_definition",
                    str(path),
                    line_number,
                    name,
                    f"shell function defined {len(locations)} times",
                )
            )
    for name, start, end in ranges:
        line_count = end - start + 1
        if line_count > long_function_limit:
            findings.append(
                Finding(
                    "blocker",
                    "long_function",
                    str(path),
                    start,
                    name,
                    f"{line_count} lines exceeds {long_function_limit}",
                )
            )
    return findings


def _shell_syntax_findings(root: Path, path: Path) -> list[Finding]:
    completed = subprocess.run(
        ["bash", "-n", str(root / path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return []
    detail = (completed.stderr or completed.stdout or "bash -n failed").strip()[:500]
    return [Finding("blocker", "shell_syntax", str(path), 0, "", detail)]


def _is_preamble_safe(
    line: str,
    assignment: tuple[str, str, bool] | None,
) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith("#")
        or assignment is not None
        or stripped.startswith("source ")
        or stripped.startswith(". ")
    )


def _scan_line(
    path: Path,
    line: str,
    line_number: int,
    fragments: tuple[str, ...],
    config_file: bool,
) -> tuple[list[Finding], tuple[str, str, bool] | None]:
    findings: list[Finding] = []
    if not config_file:
        findings.extend(
            _environment_findings(
                path,
                line_number,
                line,
                line_number == 1 and line.startswith("#!"),
            )
        )
    assignment = parse_assignment(line)
    if assignment and not config_file:
        hardcoded = _hardcoded_assignment(path, line_number, assignment, fragments)
        if hardcoded:
            findings.append(hardcoded)
    return findings, assignment


def _scan_lines(
    path: Path,
    lines: list[str],
    fragments: tuple[str, ...],
    config_file: bool,
) -> tuple[
    list[Finding],
    dict[str, set[str]],
    dict[str, list[int]],
    AssignmentMap,
    list[tuple[str, int, int]],
]:
    findings: list[Finding] = []
    repeated: dict[str, set[str]] = defaultdict(set)
    functions: dict[str, list[int]] = defaultdict(list)
    assignments: AssignmentMap = {}
    ranges: list[tuple[str, int, int]] = []
    heredoc_delimiter: str | None = None
    current_function: tuple[str, int] | None = None
    module_preamble = True
    for line_number, line in enumerate(lines, start=1):
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        line_findings, assignment = _scan_line(
            path,
            line,
            line_number,
            fragments,
            config_file,
        )
        findings.extend(line_findings)
        for value in QUOTED_LITERAL_RE.findall(line):
            repeated[value].add(str(path))
        function_match = SHELL_FUNCTION_RE.match(line)
        if function_match:
            name = function_match.group(1)
            functions[name].append(line_number)
            current_function = (name, line_number)
            module_preamble = False
        if assignment:
            scope = current_function[0] if current_function else "module"
            record_assignment(
                assignments,
                scope,
                assignment,
                line_number,
                bool(scope == "module" and module_preamble),
            )
        if current_function and FUNCTION_END_RE.match(line):
            ranges.append((current_function[0], current_function[1], line_number))
            current_function = None
        if current_function is None and module_preamble:
            module_preamble = _is_preamble_safe(line, assignment)
        heredoc_match = HEREDOC_RE.search(line)
        if heredoc_match:
            heredoc_delimiter = heredoc_match.group(1)
    if current_function:
        ranges.append((current_function[0], current_function[1], len(lines)))
    return findings, repeated, functions, assignments, ranges


def scan_shell(
    root: Path,
    path: Path,
    settings: dict[str, object],
) -> tuple[list[Finding], dict[str, set[str]], list[DefaultSource]]:
    text = (root / path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings: list[Finding] = []
    limit = int(settings["large_file_line_limit"])
    if len(lines) > limit:
        findings.append(
            Finding(
                "blocker",
                "large_file",
                str(path),
                1,
                "",
                f"{len(lines)} lines exceeds {limit}",
            )
        )
    fragments = tuple(
        str(value).lower() for value in settings["hardcoded_name_fragments"]
    )
    scanned, repeated, functions, assignments, ranges = _scan_lines(
        path,
        lines,
        fragments,
        is_configuration_file(path, settings),
    )
    findings.extend(scanned)
    findings.extend(assignment_findings(path, assignments))
    findings.extend(
        _function_findings(
            path,
            functions,
            ranges,
            int(settings["long_function_line_limit"]),
        )
    )
    findings.extend(_shell_syntax_findings(root, path))
    return findings, repeated, shell_default_sources(lines, path)
