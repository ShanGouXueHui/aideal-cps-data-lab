from __future__ import annotations

from collections import defaultdict
from typing import Any


def blocker_files_by_scope(
    findings: list[dict[str, Any]],
) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for item in findings:
        if item.get("severity") != "blocker":
            continue
        grouped[str(item.get("scope") or "active")].add(str(item.get("path") or ""))
    return {
        scope: sorted(path for path in paths if path)
        for scope, paths in sorted(grouped.items())
    }
