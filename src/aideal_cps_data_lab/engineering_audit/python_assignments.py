from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from .default_sources import is_default_name
from .models import Finding

_CONFIG_TOKENS = {"config", "configs", "setting", "settings", "option", "options", "param", "params"}
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_ASSIGNMENT_NODES = (ast.Assign, ast.AnnAssign)


def _target_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return tuple(names)
    return ()


def _assigned_names(node: ast.stmt) -> tuple[str, ...]:
    if isinstance(node, ast.Assign):
        names: list[str] = []
        for target in node.targets:
            names.extend(_target_names(target))
        return tuple(names)
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return _target_names(node.target)
    return ()


def _name_tokens(name: str) -> set[str]:
    return {part for part in name.lower().split("_") if part}


def _is_config_name(name: str) -> bool:
    return bool(_name_tokens(name) & _CONFIG_TOKENS)


def _assignment_category(name: str, scope_kind: str) -> str | None:
    if is_default_name(name):
        return "duplicate_default_source"
    if name.isupper():
        return "duplicate_constant_assignment"
    if scope_kind in {"module", "class"} or _is_config_name(name):
        return "duplicate_assignment"
    return None


class _ScopeAssignmentVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.assignments: dict[str, list[int]] = defaultdict(list)

    def visit_Assign(self, node: ast.Assign) -> None:
        for name in _assigned_names(node):
            self.assignments[name].append(int(node.lineno))
        self.generic_visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for name in _assigned_names(node):
            self.assignments[name].append(int(node.lineno))
        if node.value is not None:
            self.generic_visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return None


def _scope_assignments(body: list[ast.stmt]) -> dict[str, list[int]]:
    visitor = _ScopeAssignmentVisitor()
    for node in body:
        if not isinstance(node, _SCOPE_NODES):
            visitor.visit(node)
    return visitor.assignments


def _duplicate_assignments(
    body: list[ast.stmt],
    path: Path,
    scope_name: str,
    scope_kind: str,
) -> list[Finding]:
    assignments = _scope_assignments(body)
    findings: list[Finding] = []
    for name, lines in assignments.items():
        category = _assignment_category(name, scope_kind)
        if category is None or len(lines) < 2:
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
    return findings


def _dict_key(node: ast.AST | None) -> str | None:
    if not isinstance(node, ast.Constant):
        return None
    if not isinstance(node.value, (str, int, float, bool)):
        return None
    return repr(node.value)


def _duplicate_dict_keys(tree: ast.Module, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        locations: dict[str, list[int]] = defaultdict(list)
        for key in node.keys:
            normalized = _dict_key(key)
            if normalized is not None:
                locations[normalized].append(int(getattr(key, "lineno", node.lineno)))
        for key, lines in locations.items():
            for line in lines[1:]:
                findings.append(
                    Finding(
                        "blocker",
                        "duplicate_config_key",
                        str(path),
                        line,
                        key,
                        f"same dictionary literal defines key {key} {len(lines)} times",
                    )
                )
    return findings


def _scan_scopes(
    body: list[ast.stmt],
    path: Path,
    scope_name: str,
    scope_kind: str,
) -> list[Finding]:
    findings = _duplicate_assignments(body, path, scope_name, scope_kind)
    for node in body:
        if not isinstance(node, _SCOPE_NODES):
            continue
        nested_kind = "class" if isinstance(node, ast.ClassDef) else "function"
        findings.extend(
            _scan_scopes(
                node.body,
                path,
                f"{scope_name}.{node.name}",
                nested_kind,
            )
        )
    return findings


def assignment_findings(tree: ast.Module, path: Path) -> list[Finding]:
    findings = _scan_scopes(tree.body, path, "module", "module")
    findings.extend(_duplicate_dict_keys(tree, path))
    return findings
