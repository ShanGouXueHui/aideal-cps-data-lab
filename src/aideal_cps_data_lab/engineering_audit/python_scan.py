from __future__ import annotations

import ast
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import ABS_PATH_RE, IP_RE, URL_RE, is_configuration_file
from .models import Finding, FunctionFingerprint


def _literal(node: ast.AST | None) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
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


def _scan_scope(
    body: list[ast.stmt],
    path: Path,
    scope: str,
    settings: dict[str, object],
) -> tuple[list[Finding], list[FunctionFingerprint]]:
    findings: list[Finding] = []
    fingerprints: list[FunctionFingerprint] = []
    definitions: dict[str, list[ast.AST]] = defaultdict(list)
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name].append(node)
    for name, nodes in definitions.items():
        if len(nodes) > 1:
            for node in nodes[1:]:
                findings.append(
                    Finding(
                        "blocker",
                        "duplicate_definition",
                        str(path),
                        int(node.lineno),
                        f"{scope}.{name}",
                        f"same scope defines {name!r} {len(nodes)} times",
                    )
                )
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            line_count = int((node.end_lineno or node.lineno) - node.lineno + 1)
            digest = hashlib.sha256(
                ast.dump(
                    ast.Module(body=node.body, type_ignores=[]),
                    include_attributes=False,
                ).encode("utf-8")
            ).hexdigest()
            fingerprints.append(
                FunctionFingerprint(node.name, str(path), int(node.lineno), line_count, digest)
            )
            nested_findings, nested_fingerprints = _scan_scope(
                node.body,
                path,
                f"{scope}.{node.name}",
                settings,
            )
            findings.extend(nested_findings)
            fingerprints.extend(nested_fingerprints)
        elif isinstance(node, ast.ClassDef):
            nested_findings, nested_fingerprints = _scan_scope(
                node.body,
                path,
                f"{scope}.{node.name}",
                settings,
            )
            findings.extend(nested_findings)
            fingerprints.extend(nested_fingerprints)
    return findings, fingerprints


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

    duplicate_findings, fingerprints = _scan_scope(
        getattr(tree, "body", []), path, "module", settings
    )
    findings.extend(duplicate_findings)
    for item in fingerprints:
        if item.line_count > int(settings["long_function_line_limit"]):
            findings.append(
                Finding(
                    "blocker",
                    "long_function",
                    item.path,
                    item.line,
                    item.name,
                    f"{item.line_count} lines exceeds {settings['long_function_line_limit']}",
                )
            )

    config_file = is_configuration_file(path, settings)
    fragments = tuple(str(value).lower() for value in settings["hardcoded_name_fragments"])
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = _literal(node.value)
            if value is not None and not config_file:
                for name in _assigned_names(node):
                    if any(fragment in name.lower() for fragment in fragments):
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
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip()
            if len(value) >= int(settings["repeated_literal_min_length"]):
                repeated_literals[value].add(str(path))
            if config_file:
                continue
            for category, pattern in (
                ("hardcoded_url", URL_RE),
                ("hardcoded_ip", IP_RE),
                ("hardcoded_absolute_path", ABS_PATH_RE),
            ):
                if pattern.search(value):
                    findings.append(
                        Finding(
                            "blocker",
                            category,
                            str(path),
                            int(getattr(node, "lineno", 0) or 0),
                            "",
                            value[:240],
                        )
                    )
    return findings, fingerprints, repeated_literals
