from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def upsert_jsonl_by_sku(path: Path, row: dict[str, Any]) -> None:
    rows = read_jsonl(path)
    indexed = {
        str(item.get("sku") or ""): item
        for item in rows
        if str(item.get("sku") or "")
    }
    indexed[str(row["sku"])] = row
    data = "".join(
        json.dumps(indexed[sku], ensure_ascii=False, sort_keys=True) + "\n"
        for sku in sorted(indexed)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(data, encoding="utf-8")
    temporary.replace(path)


def successful_skus(path: Path) -> set[str]:
    return {
        str(row.get("sku") or "")
        for row in read_jsonl(path)
        if row.get("status") == "ok" and str(row.get("sku") or "")
    }


def unavailable_skus(path: Path) -> set[str]:
    return {
        str(row.get("sku") or "")
        for row in read_jsonl(path)
        if row.get("status") == "unavailable" and str(row.get("sku") or "")
    }
