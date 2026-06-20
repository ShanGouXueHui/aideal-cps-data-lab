from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import ABS_PATH_RE, IP_RE, URL_RE, is_configuration_file, iter_engineering_files
from .configuration_scan import scan_configuration
from .default_sources import duplicate_default_source_findings
from .models import DefaultSource, Finding, FunctionFingerprint
from .python_scan import scan_python
from .shell_scan import scan_shell

AUDIT_GATE_CATEGORIES = (
    "duplicate_definition",
    "duplicate_assignment",
    "duplicate_constant_assignment",
    "duplicate_config_key",
    "duplicate_default_source",
    "duplicate_implementation",
    "large_file",
    "long_function",
    "python_syntax",
    "shell_syntax",
    "config_syntax",
)


def _merge_literals(target: dict[str, set[str]], source: dict[str, set[str]]) -> None:
    for value, paths in source.items():
        target[value].update(paths)


def _scan_generic(root: Path, path: Path, settings: dict[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    text = (root / path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > int(settings["large_file_line_limit"]):
        findings.append(
            Finding("blocker", "large_file", str(path), 1, "", f"{len(lines)} lines exceeds {settings['large_file_line_limit']}")
        )
    if is_configuration_file(path, settings):
        return findings
    for line_number, line in enumerate(lines, start=1):
        for category, pattern in (
            ("hardcoded_url", URL_RE),
            ("hardcoded_ip", IP_RE),
            ("hardcoded_absolute_path", ABS_PATH_RE),
        ):
            match = pattern.search(line)
            if match:
                findings.append(Finding("blocker", category, str(path), line_number, "", match.group(0)[:240]))
    return findings


def _duplicate_implementation_findings(
    fingerprints: list[FunctionFingerprint], settings: dict[str, object]
) -> list[Finding]:
    ignored = {str(value) for value in settings["ignored_function_names"]}
    minimum = int(settings["duplicate_function_min_lines"])
    groups: dict[tuple[str, str], list[FunctionFingerprint]] = defaultdict(list)
    for item in fingerprints:
        if item.name not in ignored and item.line_count >= minimum:
            groups[(item.name, item.digest)].append(item)
    findings: list[Finding] = []
    for (name, _), group in groups.items():
        if len({item.path for item in group}) < 2:
            continue
        detail = ", ".join(f"{item.path}:{item.line}" for item in group)
        findings.extend(
            Finding("blocker", "duplicate_implementation", item.path, item.line, name, detail)
            for item in group
        )
    return findings


def _matches(path: str, settings: dict[str, object], key: str) -> bool:
    return any(re.search(str(pattern), path) for pattern in settings.get(key, []))


def _scope(path: str, settings: dict[str, object]) -> str:
    for scope, key in (
        ("historical", "historical_path_patterns"),
        ("compatibility", "compatibility_path_patterns"),
        ("support", "support_path_patterns"),
    ):
        if _matches(path, settings, key):
            return scope
    return "active"


def _summary(findings: list[Finding], scoped: list[dict[str, Any]]) -> dict[str, object]:
    category_counts = Counter(item.category for item in findings)
    blocker_files = Counter(item.path for item in findings if item.severity == "blocker")
    scope_counts = Counter(item["scope"] for item in scoped if item["severity"] == "blocker")
    return {
        "category_counts": dict(sorted(category_counts.items())),
        "blocker_scope_counts": dict(sorted(scope_counts.items())),
        "top_blocker_files": [
            {"path": path, "count": count} for path, count in blocker_files.most_common(30)
        ],
        "blocker_file_count": len(blocker_files),
    }


def _repeated_literal_findings(
    literals: dict[str, set[str]], settings: dict[str, object]
) -> list[Finding]:
    minimum_files = int(settings["repeated_literal_min_files"])
    return [
        Finding(
            "warning",
            "repeated_literal",
            sorted(paths)[0],
            0,
            "",
            f"{value[:160]!r} repeated in {len(paths)} files: {', '.join(sorted(paths))}",
        )
        for value, paths in literals.items()
        if len(paths) >= minimum_files
    ]


def _deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    unique: dict[tuple[str, str, int], Finding] = {}
    for item in findings:
        key = (item.category, item.path, item.line)
        unique.setdefault(key, item)
    return list(unique.values())


def _scan_file(
    root: Path,
    path: Path,
    settings: dict[str, object],
) -> tuple[list[Finding], list[FunctionFingerprint], dict[str, set[str]], list[DefaultSource]]:
    if path.suffix == ".py":
        return scan_python(root, path, settings)
    if path.suffix == ".sh":
        findings, literals, defaults = scan_shell(root, path, settings)
        return findings, [], literals, defaults
    findings = _scan_generic(root, path, settings)
    config_findings, defaults = scan_configuration(root, path)
    findings.extend(config_findings)
    return findings, [], {}, defaults


def _count_fields(findings: list[Finding]) -> dict[str, object]:
    blocker_categories = Counter(
        item.category for item in findings if item.severity == "blocker"
    )
    quality_gate_counts = {
        category: blocker_categories.get(category, 0)
        for category in AUDIT_GATE_CATEGORIES
    }
    fields: dict[str, object] = {"quality_gate_counts": quality_gate_counts}
    fields.update({f"{category}_count": count for category, count in quality_gate_counts.items()})
    fields["python_shell_syntax"] = (
        "PASS"
        if quality_gate_counts["python_syntax"] == 0
        and quality_gate_counts["shell_syntax"] == 0
        else "FAIL"
    )
    return fields


def run_audit(root: Path, settings: dict[str, object]) -> dict[str, Any]:
    findings: list[Finding] = []
    fingerprints: list[FunctionFingerprint] = []
    default_sources: list[DefaultSource] = []
    literals: dict[str, set[str]] = defaultdict(set)
    files = list(iter_engineering_files(root, settings))
    for path in files:
        file_findings, file_fingerprints, file_literals, file_defaults = _scan_file(
            root, path, settings
        )
        findings.extend(file_findings)
        fingerprints.extend(file_fingerprints)
        default_sources.extend(file_defaults)
        _merge_literals(literals, file_literals)
    findings.extend(_duplicate_implementation_findings(fingerprints, settings))
    findings.extend(duplicate_default_source_findings(default_sources))
    findings.extend(_repeated_literal_findings(literals, settings))
    findings = _deduplicate_findings(findings)
    findings.sort(
        key=lambda item: (
            item.severity != "blocker",
            _scope(item.path, settings),
            item.path,
            item.line,
            item.category,
        )
    )
    scoped_findings: list[dict[str, Any]] = []
    for item in findings:
        payload = asdict(item)
        payload["scope"] = _scope(item.path, settings)
        scoped_findings.append(payload)
    blocker_count = sum(item.severity == "blocker" for item in findings)
    warning_count = sum(item.severity == "warning" for item in findings)
    scope_blockers = Counter(
        item["scope"] for item in scoped_findings if item["severity"] == "blocker"
    )
    gate_blocker_count = scope_blockers.get("active", 0) + scope_blockers.get("compatibility", 0)
    report: dict[str, Any] = {
        "schema_version": str(settings["schema_version"]),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if blocker_count == 0 else "FAIL",
        "files_scanned": len(files),
        "blocker_count": blocker_count,
        "global_blocker_count": blocker_count,
        "full_gate_blocker_count": blocker_count,
        "active_blocker_count": scope_blockers.get("active", 0),
        "compatibility_blocker_count": scope_blockers.get("compatibility", 0),
        "historical_blocker_count": scope_blockers.get("historical", 0),
        "support_blocker_count": scope_blockers.get("support", 0),
        "gate_blocker_count": gate_blocker_count,
        "warning_count": warning_count,
        "summary": _summary(findings, scoped_findings),
        "findings": scoped_findings,
    }
    report.update(_count_fields(findings))
    return report
