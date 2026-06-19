from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import (
    ABS_PATH_RE,
    IP_RE,
    URL_RE,
    name_has_fragment,
)
from .models import Finding


def _literal(node: ast.AST | None) -> Any:
    if isinstance(node, ast.Constant) and isinstance(
        node.value,
        (str, int, float, bool),
    ):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_literal(item) for item in node.elts]
        return values if all(value is not None for value in values) else None
    return None


def _assigned_names(node: ast.AST) -> list[str]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return [target.id for target in targets if isinstance(target, ast.Name)]


def _meaningful(value: Any) -> bool:
    if value in (None, False, True, 0, 1, ""):
        return False
    if isinstance(value, (list, tuple, set)) and not value:
        return False
    return True


def _version_literal(value: str, start: int) -> bool:
    return start > 0 and value[start - 1] == "/"


def constant_findings(
    tree: ast.Module,
    path: Path,
    fragments: tuple[str, ...],
) -> list[Finding]:
    findings: list[Finding] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = _literal(node.value)
        if not _meaningful(value):
            continue
        for name in _assigned_names(node):
            if not name.isupper() or not name_has_fragment(name, fragments):
                continue
            findings.append(
                Finding(
                    "blocker",
                    "hardcoded_parameter",
                    str(path),
                    int(node.lineno),
                    name,
                    repr(value)[:240],
                )
            )
    return findings


def string_findings(
    tree: ast.Module,
    path: Path,
    repeated_literal_min_length: int,
) -> tuple[list[Finding], dict[str, set[str]]]:
    findings: list[Finding] = []
    repeated: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value.strip()
        if len(value) >= repeated_literal_min_length:
            repeated[value].add(str(path))
        line = int(getattr(node, "lineno", 0) or 0)
        url_match = URL_RE.search(value)
        if url_match:
            findings.append(
                Finding(
                    "blocker",
                    "hardcoded_url",
                    str(path),
                    line,
                    "",
                    url_match.group(0)[:240],
                )
            )
            continue
        ip_match = IP_RE.search(value)
        if ip_match and not _version_literal(value, ip_match.start()):
            findings.append(
                Finding(
                    "blocker",
                    "hardcoded_ip",
                    str(path),
                    line,
                    "",
                    ip_match.group(0)[:240],
                )
            )
        path_match = ABS_PATH_RE.search(value)
        if path_match:
            findings.append(
                Finding(
                    "blocker",
                    "hardcoded_absolute_path",
                    str(path),
                    line,
                    "",
                    path_match.group(0)[:240],
                )
            )
    return findings, repeated
