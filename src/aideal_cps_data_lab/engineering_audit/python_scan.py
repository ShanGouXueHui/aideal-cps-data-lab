from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from .models import Finding, FunctionFingerprint
from .python_definitions import definition_findings
from .python_hardcoding import constant_findings, string_findings


def scan_python(
    root: Path,
    path: Path,
    settings: dict[str, object],
) -> tuple[list[Finding], list[FunctionFingerprint], dict[str, set[str]]]:
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
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        findings.append(
            Finding(
                "blocker",
                "python_syntax",
                str(path),
                int(exc.lineno or 0),
                "",
                str(exc.msg),
            )
        )
        return findings, [], repeated_literals

    definition_issues, fingerprints = definition_findings(
        tree,
        path,
        int(settings["long_function_line_limit"]),
    )
    findings.extend(definition_issues)
    fragments = tuple(
        str(value).lower()
        for value in settings["hardcoded_name_fragments"]
    )
    findings.extend(constant_findings(tree, path, fragments))
    string_issues, repeated_literals = string_findings(
        tree,
        path,
        int(settings["repeated_literal_min_length"]),
    )
    findings.extend(string_issues)
    return findings, fingerprints, repeated_literals
