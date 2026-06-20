from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

from .common import (
    ABS_PATH_RE,
    IP_RE,
    SHELL_ASSIGN_RE,
    SHELL_FUNCTION_RE,
    URL_RE,
    is_configuration_file,
    name_has_fragment,
)
from .default_sources import is_default_name, shell_default_sources
from .models import DefaultSource, Finding

QUOTED_LITERAL_RE = re.compile(r"['\"]([^'\"]{8,})['\"]")
DYNAMIC_VALUE_RE = re.compile(r"\$\{|\$\(|\$[A-Za-z_?]")
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
FUNCTION_END_RE = re.compile(r"^\s*}\s*(?:#.*)?$")


def _environment_findings(path: Path, line_number: int, line: str, shebang: bool) -> list[Finding]:
    findings: list[Finding] = []
    url_match = URL_RE.search(line)
    if url_match:
        findings.append(Finding("blocker", "hardcoded_url", str(path), line_number, "", url_match.group(0)[:240]))
    else:
        ip_match = IP_RE.search(line)
        if ip_match:
            findings.append(Finding("blocker", "hardcoded_ip", str(path), line_number, "", ip_match.group(0)[:240]))
    if not shebang:
        path_match = ABS_PATH_RE.search(line)
        if path_match:
            findings.append(Finding("blocker", "hardcoded_absolute_path", str(path), line_number, "", path_match.group(0)[:240]))
    return findings


def _hardcoded_assignment(path: Path, line_number: int, line: str, fragments: tuple[str, ...]) -> Finding | None:
    match = SHELL_ASSIGN_RE.match(line)
    if not match:
        return None
    name, value = match.groups()
    if not name.isupper() or not name_has_fragment(name, fragments) or DYNAMIC_VALUE_RE.search(value):
        return None
    return Finding("blocker", "hardcoded_parameter", str(path), line_number, name, value.strip()[:240])


def _duplicate_assignment_category(name: str, scope: str, fragments: tuple[str, ...]) -> str | None:
    if is_default_name(name):
        return "duplicate_default_source"
    if name.isupper() and (scope == "module" or name_has_fragment(name, fragments)):
        return "duplicate_constant_assignment"
    if scope == "module" and name_has_fragment(name, fragments):
        return "duplicate_assignment"
    return None


def _assignment_findings(
    path: Path,
    assignments: dict[tuple[str, str], list[int]],
    fragments: tuple[str, ...],
) -> list[Finding]:
    findings: list[Finding] = []
    for (scope, name), locations in assignments.items():
        category = _duplicate_assignment_category(name, scope, fragments)
        if category is None or len(locations) < 2:
            continue
        for line_number in locations[1:]:
            findings.append(
                Finding(
                    "blocker",
                    category,
                    str(path),
                    line_number,
                    f"{scope}.{name}",
                    f"same shell scope assigns {name!r} {len(locations)} times",
                )
            )
    return findings


def _function_findings(
    path: Path,
    functions: dict[str, list[int]],
    ranges: list[tuple[str, int, int]],
    long_function_limit: int,
) -> list[Finding]:
    findings: list[Finding] = []
    for name, locations in functions.items():
        for line_number in locations[1:]:
            findings.append(Finding("blocker", "duplicate_definition", str(path), line_number, name, f"shell function defined {len(locations)} times"))
    for name, start, end in ranges:
        line_count = end - start + 1
        if line_count > long_function_limit:
            findings.append(Finding("blocker", "long_function", str(path), start, name, f"{line_count} lines exceeds {long_function_limit}"))
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


def _scan_lines(
    path: Path,
    lines: list[str],
    fragments: tuple[str, ...],
    config_file: bool,
) -> tuple[list[Finding], dict[str, set[str]], dict[str, list[int]], dict[tuple[str, str], list[int]], list[tuple[str, int, int]]]:
    findings: list[Finding] = []
    repeated: dict[str, set[str]] = defaultdict(set)
    functions: dict[str, list[int]] = defaultdict(list)
    assignments: dict[tuple[str, str], list[int]] = defaultdict(list)
    ranges: list[tuple[str, int, int]] = []
    heredoc_delimiter: str | None = None
    current_function: tuple[str, int] | None = None
    for line_number, line in enumerate(lines, start=1):
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        if not config_file:
            findings.extend(_environment_findings(path, line_number, line, line_number == 1 and line.startswith("#!")))
        for value in QUOTED_LITERAL_RE.findall(line):
            repeated[value].add(str(path))
        function_match = SHELL_FUNCTION_RE.match(line)
        if function_match:
            name = function_match.group(1)
            functions[name].append(line_number)
            current_function = (name, line_number)
        assignment_match = SHELL_ASSIGN_RE.match(line)
        if assignment_match:
            scope = current_function[0] if current_function else "module"
            assignments[(scope, assignment_match.group(1))].append(line_number)
            if not config_file:
                hardcoded = _hardcoded_assignment(path, line_number, line, fragments)
                if hardcoded:
                    findings.append(hardcoded)
        if current_function and FUNCTION_END_RE.match(line):
            ranges.append((current_function[0], current_function[1], line_number))
            current_function = None
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
        findings.append(Finding("blocker", "large_file", str(path), 1, "", f"{len(lines)} lines exceeds {limit}"))
    fragments = tuple(str(value).lower() for value in settings["hardcoded_name_fragments"])
    scanned, repeated, functions, assignments, ranges = _scan_lines(
        path, lines, fragments, is_configuration_file(path, settings)
    )
    findings.extend(scanned)
    findings.extend(_assignment_findings(path, assignments, fragments))
    findings.extend(_function_findings(path, functions, ranges, int(settings["long_function_line_limit"])))
    findings.extend(_shell_syntax_findings(root, path))
    return findings, repeated, shell_default_sources(lines, path)
