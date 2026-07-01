from __future__ import annotations

import json
from json import JSONDecoder
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _append_object(rows: list[dict[str, Any]], value: Any) -> None:
    if isinstance(value, dict):
        rows.append(value)


def _skip_legacy_separators(text: str, index: int) -> int:
    length = len(text)
    while index < length:
        if text[index].isspace() or text[index] == ",":
            index += 1
            continue
        if text[index] == "\\" and index + 1 < length and text[index + 1] in {"n", "r", "t"}:
            index += 2
            continue
        break
    return index


def _read_json_objects_from_text(text: str) -> list[dict[str, Any]]:
    """Read one JSON object, JSONL, or legacy concatenated object streams.

    Some historical collector outputs were written as many JSON objects appended to
    one physical line.  The old variants include `{...}{...}`, `{...},{...}` and
    `{...}\\n{...}` where the separator is the literal two-character string
    backslash+n instead of a real newline.  The commercial finalizer must treat
    those formats as valid input instead of silently dropping every row.
    """

    rows: list[dict[str, Any]] = []
    decoder = JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        index = _skip_legacy_separators(text, index)
        if index >= length:
            break
        try:
            value, end = decoder.raw_decode(text, index)
        except Exception:
            break
        _append_object(rows, value)
        if end <= index:
            break
        index = end
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            rows.extend(_read_json_objects_from_text(line))
            continue
        if isinstance(value, list):
            for item in value:
                _append_object(rows, item)
        else:
            _append_object(rows, value)
    if not rows and text.strip():
        rows.extend(_read_json_objects_from_text(text))
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
