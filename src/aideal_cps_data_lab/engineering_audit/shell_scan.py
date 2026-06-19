from __future__ import annotations

import re
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
from .models import Finding


QUOTED_LITERAL_RE = re.compile(r"['\"]([^'\"]{8,})['\"]")
DYNAMIC_VALUE_RE = re.compile(r"\$\{|\$\(|\$[A-Za-z_?]")
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")


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


def _assignment_finding(
    path: Path,
    line_number: int,
    line: str,
    fragments: tuple[str, ...],
) -> Finding | None:
    match = SHELL_ASSIGN_RE.match(line)
    if not match:
        return None
    name, value = match.groups()
    if not name.isupper() or not name_has_fragment(name, fragments):
        return None
    if DYNAMIC_VALUE_RE.search(value):
        return None
    return Finding(
        "blocker",
        "hardcoded_parameter",
        str(path),
        line_number,
        name,
        value.strip()[:240],
    )


def _scan_lines(
    path: Path,
    lines: list[str],
    fragments: tuple[str, ...],
    config_file: bool,
) -> tuple[list[Finding], dict[str, set[str]], dict[str, list[int]]]:
    findings: list[Finding] = []
    repeated: dict[str, set[str]] = defaultdict(set)
    functions: dict[str, list[int]] = defaultdict(list)
    heredoc_delimiter: str | None = None
    for line_number, line in enumerate(lines, start=1):
        if not config_file:
            findings.extend(
                _environment_findings(
                    path,
                    line_number,
                    line,
                    line_number == 1 and line.startswith("#!"),
                )
            )
        for value in QUOTED_LITERAL_RE.findall(line):
            repeated[value].add(str(path))
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        function_match = SHELL_FUNCTION_RE.match(line)
        if function_match:
            functions[function_match.group(1)].append(line_number)
        if not config_file:
            finding = _assignment_finding(path, line_number, line, fragments)
            if finding:
                findings.append(finding)
        heredoc_match = HEREDOC_RE.search(line)
        if heredoc_match:
            heredoc_delimiter = heredoc_match.group(1)
    return findings, repeated, functions


def _duplicate_definitions(
    path: Path,
    functions: dict[str, list[int]],
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
    return findings


def scan_shell(
    root: Path,
    path: Path,
    settings: dict[str, object],
) -> tuple[list[Finding], dict[str, set[str]]]:
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
    line_findings, repeated, functions = _scan_lines(
        path,
        lines,
        fragments,
        is_configuration_file(path, settings),
    )
    findings.extend(line_findings)
    findings.extend(_duplicate_definitions(path, functions))
    return findings, repeated
