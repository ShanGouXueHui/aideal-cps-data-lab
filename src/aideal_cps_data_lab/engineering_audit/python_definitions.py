from __future__ import annotations

import ast
import hashlib
from collections import defaultdict
from pathlib import Path

from .models import Finding, FunctionFingerprint


def _scan_scope(
    body: list[ast.stmt],
    path: Path,
    scope: str,
) -> tuple[list[Finding], list[FunctionFingerprint]]:
    findings: list[Finding] = []
    fingerprints: list[FunctionFingerprint] = []
    definitions: dict[str, list[ast.AST]] = defaultdict(list)
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name].append(node)
    for name, nodes in definitions.items():
        if len(nodes) <= 1:
            continue
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
                FunctionFingerprint(
                    node.name,
                    str(path),
                    int(node.lineno),
                    line_count,
                    digest,
                )
            )
            nested_findings, nested_fingerprints = _scan_scope(
                node.body,
                path,
                f"{scope}.{node.name}",
            )
            findings.extend(nested_findings)
            fingerprints.extend(nested_fingerprints)
        elif isinstance(node, ast.ClassDef):
            nested_findings, nested_fingerprints = _scan_scope(
                node.body,
                path,
                f"{scope}.{node.name}",
            )
            findings.extend(nested_findings)
            fingerprints.extend(nested_fingerprints)
    return findings, fingerprints


def definition_findings(
    tree: ast.Module,
    path: Path,
    long_function_limit: int,
) -> tuple[list[Finding], list[FunctionFingerprint]]:
    findings, fingerprints = _scan_scope(tree.body, path, "module")
    for item in fingerprints:
        if item.line_count <= long_function_limit:
            continue
        findings.append(
            Finding(
                "blocker",
                "long_function",
                item.path,
                item.line,
                item.name,
                f"{item.line_count} lines exceeds {long_function_limit}",
            )
        )
    return findings, fingerprints
