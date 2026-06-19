from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl_checked(
    path: Path,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return rows, invalid
    for line in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            invalid += 1
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            invalid += 1
    return rows, invalid


def index_by_sku(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int]:
    indexed: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        sku = str(row.get("sku") or "")
        if not sku:
            continue
        if sku in indexed:
            duplicates += 1
        indexed[sku] = row
    return indexed, duplicates
