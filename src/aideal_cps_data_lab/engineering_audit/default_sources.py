from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

from .models import DefaultSource, Finding

_DEFAULT_NAME_RE = re.compile(r"(?:^default(?:s)?$|^default_|_default$)", re.IGNORECASE)
_SHELL_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):[-=][^}]+\}")
_CONFIG_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def is_default_name(name: str) -> bool:
    return bool(_DEFAULT_NAME_RE.search(name))


def _literal_present(node: ast.AST | None) -> bool:
    return node is not None and not (
        isinstance(node, ast.Constant) and node.value is None
    )


def _assigned_names(node: ast.stmt) -> tuple[str, ...]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
    else:
        return ()
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return tuple(names)


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        parts = [function.attr]
        value = function.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def _constant_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def python_default_sources(tree: ast.Module, path: Path) -> list[DefaultSource]:
    sources: list[DefaultSource] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        for name in _assigned_names(node):
            if is_default_name(name):
                sources.append(DefaultSource(name.lower(), str(path), int(node.lineno), name, "python_assignment"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in {"os.getenv", "os.environ.get", "environ.get"}:
            key = _constant_string(node.args[0]) if node.args else None
            default = node.args[1] if len(node.args) > 1 else None
            if key and _literal_present(default):
                sources.append(DefaultSource(f"env:{key}", str(path), int(node.lineno), key, "python_env_default"))
            continue
        if name.endswith("add_argument"):
            default = next((item.value for item in node.keywords if item.arg == "default"), None)
            option = next((_constant_string(arg) for arg in node.args if _constant_string(arg)), None)
            if option and _literal_present(default):
                canonical = option.lstrip("-").replace("-", "_")
                sources.append(DefaultSource(f"arg:{canonical}", str(path), int(node.lineno), option, "python_argument_default"))
    return sources


def shell_default_sources(lines: list[str], path: Path) -> list[DefaultSource]:
    sources: list[DefaultSource] = []
    for line_number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            continue
        for name in _SHELL_DEFAULT_RE.findall(line):
            sources.append(DefaultSource(f"env:{name}", str(path), line_number, name, "shell_parameter_default"))
    return sources


def config_default_source(section: str, key: str, path: Path, line: int) -> DefaultSource | None:
    normalized_section = section.strip().lower()
    normalized_key = key.strip().lower()
    if not _CONFIG_KEY_RE.fullmatch(normalized_key):
        return None
    if normalized_section in {"default", "defaults"} or is_default_name(normalized_key):
        canonical = f"config:{normalized_section}:{normalized_key}"
        return DefaultSource(canonical, str(path), line, key, "configuration_default")
    return None


def duplicate_default_source_findings(sources: list[DefaultSource]) -> list[Finding]:
    groups: dict[str, list[DefaultSource]] = defaultdict(list)
    for source in sources:
        groups[source.key].append(source)
    findings: list[Finding] = []
    for key, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda item: (item.path, item.line, item.symbol))
        authority = ordered[0]
        detail = ", ".join(f"{item.path}:{item.line} ({item.source_kind})" for item in ordered)
        for item in ordered[1:]:
            findings.append(
                Finding(
                    "blocker",
                    "duplicate_default_source",
                    item.path,
                    item.line,
                    item.symbol,
                    f"default {key!r} has multiple sources; authority candidate {authority.path}:{authority.line}; sources: {detail}",
                )
            )
    return findings
