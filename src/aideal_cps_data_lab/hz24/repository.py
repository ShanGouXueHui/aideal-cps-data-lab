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


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
    )


def encode_jsonl_by_sku(rows: list[dict[str, Any]]) -> str:
    indexed = {
        str(row.get("sku") or ""): row
        for row in rows
        if str(row.get("sku") or "")
    }
    return "".join(
        json.dumps(indexed[sku], ensure_ascii=False, sort_keys=True) + "\n"
        for sku in sorted(indexed)
    )


def upsert_jsonl_rows_by_sku(
    path: Path,
    new_rows: list[dict[str, Any]],
) -> None:
    indexed = {
        str(row.get("sku") or ""): row
        for row in read_jsonl(path)
        if str(row.get("sku") or "")
    }
    for row in new_rows:
        sku = str(row.get("sku") or "")
        if not sku:
            raise ValueError("missing SKU in JSONL upsert")
        indexed[sku] = row
    atomic_text(path, encode_jsonl_by_sku(list(indexed.values())))


def upsert_jsonl_by_sku(path: Path, row: dict[str, Any]) -> None:
    upsert_jsonl_rows_by_sku(path, [row])


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
