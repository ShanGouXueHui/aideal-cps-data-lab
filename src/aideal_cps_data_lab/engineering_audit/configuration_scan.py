from __future__ import annotations

import configparser
import json
import re
import tomli
from collections import defaultdict
from pathlib import Path
from typing import Callable

from .default_sources import config_default_source
from .models import DefaultSource, Finding

_TOML_SECTION_RE = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(?:#.*)?$")
_TOML_KEY_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=")
_INI_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$")
_INI_KEY_RE = re.compile(r"^\s*([^#;\s][^:=]*?)\s*[:=]")
_YAML_KEY_RE = re.compile(
    r"^(\s*)(-\s+)?(?:['\"]([^'\"]+)['\"]|([^:#][^:]*?))\s*:\s*(?:[^|>].*)?$"
)


def _finding(
    path: Path,
    line: int,
    symbol: str,
    detail: str,
    category: str = "duplicate_config_key",
) -> Finding:
    return Finding("blocker", category, str(path), line, symbol, detail)


def _record_key(
    seen: dict[tuple[str, str], int],
    findings: list[Finding],
    path: Path,
    section: str,
    key: str,
    line: int,
) -> None:
    normalized = (section.casefold(), key.casefold())
    if normalized in seen:
        findings.append(
            _finding(
                path,
                line,
                f"{section}.{key}" if section else key,
                f"configuration key {key!r} repeats in scope {section or '<root>'!r}; first defined at line {seen[normalized]}",
            )
        )
    else:
        seen[normalized] = line


def _scan_toml(text: str, path: Path) -> tuple[list[Finding], list[DefaultSource]]:
    findings: list[Finding] = []
    defaults: list[DefaultSource] = []
    seen: dict[tuple[str, str], int] = {}
    section = ""
    for line_number, line in enumerate(text.splitlines(), start=1):
        section_match = _TOML_SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip().strip('"\'')
            continue
        key_match = _TOML_KEY_RE.match(line)
        if not key_match:
            continue
        key = key_match.group(1).strip().strip('"\'')
        _record_key(seen, findings, path, section, key, line_number)
        source = config_default_source(section, key, path, line_number)
        if source:
            defaults.append(source)
    try:
        tomli.loads(text)
    except (tomli.TOMLDecodeError, ValueError) as exc:
        findings.append(_finding(path, 1, "", str(exc), "config_syntax"))
    return findings, defaults


def _scan_ini(text: str, path: Path) -> tuple[list[Finding], list[DefaultSource]]:
    findings: list[Finding] = []
    defaults: list[DefaultSource] = []
    seen: dict[tuple[str, str], int] = {}
    section = "DEFAULT"
    for line_number, line in enumerate(text.splitlines(), start=1):
        section_match = _INI_SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip()
            continue
        key_match = _INI_KEY_RE.match(line)
        if not key_match:
            continue
        key = key_match.group(1).strip()
        _record_key(seen, findings, path, section, key, line_number)
        source = config_default_source(section, key, path, line_number)
        if source:
            defaults.append(source)
    parser = configparser.ConfigParser(strict=True)
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        findings.append(_finding(path, 1, "", str(exc), "config_syntax"))
    return findings, defaults


def _yaml_parent(scopes: list[tuple[int, str]], indent: int) -> str:
    while scopes[-1][0] >= indent:
        scopes.pop()
    return scopes[-1][1]


def _scan_yaml(text: str, path: Path) -> tuple[list[Finding], list[DefaultSource]]:
    findings: list[Finding] = []
    defaults: list[DefaultSource] = []
    scopes: list[tuple[int, str]] = [(-1, "")]
    sequence_counts: dict[tuple[int, str], int] = defaultdict(int)
    seen: dict[tuple[str, str], int] = {}
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = _YAML_KEY_RE.match(raw)
        if not match:
            continue
        indent = len(match.group(1).replace("\t", "    "))
        is_sequence_item = bool(match.group(2))
        key = (match.group(3) or match.group(4) or "").strip()
        parent = _yaml_parent(scopes, indent)
        if is_sequence_item:
            sequence_key = (indent, parent)
            index = sequence_counts[sequence_key]
            sequence_counts[sequence_key] += 1
            section = f"{parent}[{index}]" if parent else f"[{index}]"
            scopes.append((indent, section))
        else:
            section = parent
        _record_key(seen, findings, path, section, key, line_number)
        source = config_default_source(section, key, path, line_number)
        if source:
            defaults.append(source)
        value_text = raw.split(":", 1)[1].strip()
        if not value_text or value_text.startswith(("#", "|", ">")):
            nested = f"{section}.{key}" if section else key
            scopes.append((indent, nested))
    return findings, defaults


class _JSONObject(list):
    pass


def _scan_json(text: str, path: Path) -> tuple[list[Finding], list[DefaultSource]]:
    findings: list[Finding] = []
    defaults: list[DefaultSource] = []

    def hook(pairs: list[tuple[str, object]]) -> _JSONObject:
        return _JSONObject(pairs)

    try:
        root = json.loads(text, object_pairs_hook=hook)
    except json.JSONDecodeError as exc:
        return [_finding(path, int(exc.lineno), "", exc.msg, "config_syntax")], defaults

    def visit(value: object, section: str) -> None:
        if isinstance(value, _JSONObject):
            seen: set[str] = set()
            for key, child in value:
                normalized = key.casefold()
                if normalized in seen:
                    findings.append(
                        _finding(
                            path,
                            1,
                            f"{section}.{key}" if section else key,
                            f"JSON object repeats key {key!r}",
                        )
                    )
                seen.add(normalized)
                source = config_default_source(section, key, path, 1)
                if source:
                    defaults.append(source)
                nested = f"{section}.{key}" if section else key
                visit(child, nested)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{section}[{index}]")

    visit(root, "")
    return findings, defaults


_SCANNERS: dict[str, Callable[[str, Path], tuple[list[Finding], list[DefaultSource]]]] = {
    ".toml": _scan_toml,
    ".ini": _scan_ini,
    ".cfg": _scan_ini,
    ".yaml": _scan_yaml,
    ".yml": _scan_yaml,
    ".json": _scan_json,
}


def scan_configuration(
    root: Path,
    path: Path,
) -> tuple[list[Finding], list[DefaultSource]]:
    scanner = _SCANNERS.get(path.suffix.lower())
    if scanner is None:
        return [], []
    text = (root / path).read_text(encoding="utf-8", errors="replace")
    return scanner(text, path)
