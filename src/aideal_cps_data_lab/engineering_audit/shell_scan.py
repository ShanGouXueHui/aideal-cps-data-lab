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
)
from .models import Finding


QUOTED_LITERAL_RE = re.compile(r"['\"]([^'\"]{8,})['\"]")
DYNAMIC_VALUE_RE = re.compile(r"\$\{|\$\(|\$[A-Za-z_]")


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
    fragments = tuple(str(value).lower() for value in settings["hardcoded_name_fragments"])
    config_file = is_configuration_file(path, settings)
    for line_number, line in enumerate(lines, start=1):
        function_match = SHELL_FUNCTION_RE.match(line)
        if function_match:
            functions[function_match.group(1)].append(line_number)

        assignment_match = SHELL_ASSIGN_RE.match(line)
        if assignment_match and not config_file:
            name, value = assignment_match.groups()
            if (
                any(fragment in name.lower() for fragment in fragments)
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

        if not config_file:
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

        for value in QUOTED_LITERAL_RE.findall(line):
            repeated_literals[value].add(str(path))

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
