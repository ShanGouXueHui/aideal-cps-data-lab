from __future__ import annotations

import re
import shlex
from pathlib import Path

from .default_sources import is_default_name
from .models import Finding

_ASSIGNMENT_TOKEN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_READONLY_PREFIXES = {("readonly",), ("declare", "-r"), ("typeset", "-r")}
AssignmentRecord = tuple[int, bool, bool]
AssignmentMap = dict[tuple[str, str], list[AssignmentRecord]]


def parse_assignment(line: str) -> tuple[str, str, bool] | None:
    try:
        tokens = shlex.split(line, comments=True, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    immutable = False
    assignment_token = ""
    if len(tokens) == 1:
        assignment_token = tokens[0]
    elif len(tokens) == 2 and tokens[0] == "export":
        assignment_token = tokens[1]
    elif len(tokens) == 2 and (tokens[0],) in _READONLY_PREFIXES:
        immutable = True
        assignment_token = tokens[1]
    elif len(tokens) == 3 and tuple(tokens[:2]) in _READONLY_PREFIXES:
        immutable = True
        assignment_token = tokens[2]
    else:
        return None
    match = _ASSIGNMENT_TOKEN_RE.fullmatch(assignment_token)
    if not match:
        return None
    return match.group(1), match.group(2), immutable


def record_assignment(
    assignments: AssignmentMap,
    scope: str,
    assignment: tuple[str, str, bool],
    line_number: int,
    declaration: bool,
) -> None:
    assignments.setdefault((scope, assignment[0]), []).append(
        (line_number, declaration, assignment[2])
    )


def assignment_findings(path: Path, assignments: AssignmentMap) -> list[Finding]:
    findings: list[Finding] = []
    for (scope, name), records in assignments.items():
        declarations = [record for record in records if record[1] or record[2]]
        if len(declarations) < 2:
            continue
        if is_default_name(name):
            category = "duplicate_default_source"
        elif any(record[2] for record in declarations) or name.isupper():
            category = "duplicate_constant_assignment"
        else:
            category = "duplicate_assignment"
        for line_number, _, _ in declarations[1:]:
            findings.append(
                Finding(
                    "blocker",
                    category,
                    str(path),
                    line_number,
                    f"{scope}.{name}",
                    f"same shell scope declares {name!r} {len(declarations)} times",
                )
            )
    return findings
