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
    elif IP_RE.search(line):
        match = IP_RE.search(line)
        findings.append(
            Finding(
                "blocker",
                "hardcoded_ip",
                str(path),
                line_number,
                "",
                str(match.group(0))[:240],
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


def scan_shell(
    root: Path,
    path: Path,
    settings: dict[str, object],
) -> tuple[list[Finding], dict[str, set[str]]]:
    findings: list[Finding] = []
    repeated_literals: dict[str, set[str]] = defaultdict(set)
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

    functions: dict[str, list[int]] = defaultdict(list)
    fragments = tuple(
        str(value).lower()
        for value in settings["hardcoded_name_fragments"]
    )
    config_file = is_configuration_file(path, settings)
    heredoc_delimiter: str | None = None
    for line_number, line in enumerate(lines, start=1):
        shebang = line_number == 1 and line.startswith("#!")
        if not config_file:
            findings.extend(
                _environment_findings(path, line_number, line, shebang)
            )
        for value in QUOTED_LITERAL_RE.findall(line):
            repeated_literals[value].add(str(path))

        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue

        function_match = SHELL_FUNCTION_RE.match(line)
        if function_match:
            functions[function_match.group(1)].append(line_number)

        assignment_match = SHELL_ASSIGN_RE.match(line)
        if assignment_match and not config_file:
            name, value = assignment_match.groups()
            if (
                name.isupper()
                and name_has_fragment(name, fragments)
                and not DYNAMIC_VALUE_RE.search(value)
            ):
                findings.append(
                    Finding(
                        "blocker",
                        "hardcoded_parameter",
                        str(path),
                        line_number,
                        name,
                        value.strip()[:240],
                    )
                )

        heredoc_match = HEREDOC_RE.search(line)
        if heredoc_match:
            heredoc_delimiter = heredoc_match.group(1)

    for name, locations in functions.items():
        if len(locations) <= 1:
            continue
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
    return findings, repeated_literals
