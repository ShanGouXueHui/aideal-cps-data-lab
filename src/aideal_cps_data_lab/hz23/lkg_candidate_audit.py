from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .lkg_settings import LastKnownGoodSettings


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inspect_candidate(path: Path, root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    skus: list[str] = []
    invalid_json = 0
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid_json += 1
            continue
        if isinstance(value, dict):
            skus.append(str(value.get("sku") or value.get("jd_sku_id") or ""))
        else:
            invalid_json += 1
    unique_count = len(set(skus))
    return {
        "path": str(path.relative_to(root)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_bytes(raw),
        "row_count": len(skus),
        "unique_sku_count": unique_count,
        "duplicate_sku_count": len(skus) - unique_count,
        "invalid_row_count": invalid_json,
        "non_numeric_sku_count": sum(not sku.isdigit() for sku in skus),
    }


def is_exact_match(item: dict[str, Any], settings: LastKnownGoodSettings) -> bool:
    return bool(
        item["sha256"] == settings.expected_data_sha256
        and item["row_count"] == settings.expected_row_count
        and item["duplicate_sku_count"] == 0
        and item["invalid_row_count"] == 0
        and item["non_numeric_sku_count"] == 0
    )
