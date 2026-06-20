from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from .models import Finding

_CONFIG_NAMES = {"config", "configs", "settings", "defaults", "options", "params"}
_DEFAULT_NAMES = {"default", "defaults", "default_config", "default_settings"}
_RUNTIME_SCOPE_NODES = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith, ast.Try, ast.Match)


def _assigned_names(node: ast.stmt) -> tuple[str, ...]:
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    else:
        return ()
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return tuple(names)


def _literal_dict_keys(node: ast.stmt) -> tuple[tuple[str, int], ...]:
    value: ast.AST | None = None
    if isinstance(node, ast.Assign):
        value = node.value
    elif isinstance(node, ast.AnnAssign):
        value = node.value
    if not isinstance(value, ast.Dict):
        return ()
    keys: list[tuple[str, int]] = []
    for key in value.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.append((key.value, int(key.lineno)))
    return tuple(keys)


def _assignment_category(name: str, scope: str) -> str | None:
    lower = name.lower()
    if name.isupper():
        return "duplicate_constant_assignment"
    if scope in {"module", "class"}:
        return "duplicate_assignment"
    if lower in _DEFAULT_NAMES:
        return "duplicate_default_source"
    return None


def _scan_assignment_scope(
    body: list[ast.stmt],
    path: Path,
    scope_name: str,
    scope_kind: str,
) -> list[Finding]:
    findings: list[Finding] = []
    assignments: dict[str, list[int]] = defaultdict(list)
    dict_keys: dict[str, list[int]] = defaultdict(list)
    default_sources: dict[str, list[int]] = defaultdict(list)

    for node in body:
        if isinstance(node, _RUNTIME_SCOPE_NODES):
            continue
        names = _assigned_names(node)
        for name in names:
            assignments[name].append(int(node.lineno))
            if name.lower() in _DEFAULT_NAMES:
                default_sources[name].append(int(node.lineno))
        if any(name.lower() in _CONFIG_NAMES for name in names):
            for key, line in _literal_dict_keys(node):
                dict_keys[key].append(line)

    for name, lines in assignments.items():
        category = _assignment_category(name, scope_kind)
        if category is None or len(lines) <= 1:
            continue
        for line in lines[1:]:
            findings.append(
                Finding(
                    "blocker",
                    category,
                    str(path),
                    line,
                    f"{scope_name}.{name}",
                    f"same {scope_kind} scope assigns {name!r} {len(lines)} times",
                )
            )

    for key, lines in dict_keys.items():
        if len(lines) <= 1:
            continue
        for line in lines[1:]:
            findings.append(
                Finding(
                    "blocker",
                    "duplicate_config_key",
                    str(path),
                    line,
                    f"{scope_name}.{key}",
                    f"same config literal defines key {key!r} {len(lines)} times",
                )
            )

    for name, lines in default_sources.items():
        if len(lines) <= 1:
            continue
        for line in lines[1:]:
            findings.append(
                Finding(
                    "blocker",
                    "duplicate_default_source",
                    str(path),
                    line,
                    f"{scope_name}.{name}",
                    f"same scope defines default source {name!r} {len(lines)} times",
                )
            )
    return findings


def assignment_findings(tree: ast.Module, path: Path) -> list[Finding]:
    findings = _scan_assignment_scope(tree.body, path, "module", "module")
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            findings.extend(_scan_assignment_scope(node.body, path, node.name, "class"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_scan_assignment_scope(node.body, path, node.name, "function"))
    return findings
