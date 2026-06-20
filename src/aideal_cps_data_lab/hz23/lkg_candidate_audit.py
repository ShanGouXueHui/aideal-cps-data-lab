from __future__ import annotations

import hashlib
import json
from datetime import datetime
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


def find_candidates(root: Path, settings: LastKnownGoodSettings) -> list[Path]:
    found: set[Path] = set()
    canonical = root / settings.canonical_candidate
    if canonical.is_file():
        found.add(canonical)
    for relative_root in settings.search_roots:
        search_root = root / relative_root
        if not search_root.is_dir():
            continue
        for path in search_root.rglob("*.jsonl"):
            name = path.name.lower()
            if any(fragment in name for fragment in settings.candidate_name_fragments):
                found.add(path)
    return sorted(found)


def manifest_summary(path: Path, root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path.relative_to(root)),
        "present": path.is_file(),
    }
    if not path.is_file():
        return result
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        result["valid_json"] = False
        return result
    result["valid_json"] = isinstance(value, dict)
    if isinstance(value, dict):
        for key in (
            "round_id",
            "row_count",
            "data_sha256",
            "candidate_integrity_ready",
            "observation_ready",
            "gate_failures",
        ):
            result[key] = value.get(key)
    return result


def build_candidate_report(root: Path, settings: LastKnownGoodSettings) -> dict[str, Any]:
    candidates = [inspect_candidate(path, root) for path in find_candidates(root, settings)]
    exact = [item for item in candidates if is_exact_match(item, settings)]
    status = "FOUND_EXACT_3304" if exact else (
        "FOUND_CANDIDATE_MISMATCH" if candidates else "NOT_FOUND"
    )
    return {
        "schema_version": settings.schema_version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "read_only": True,
        "expected": {
            "round_id": settings.expected_round_id,
            "row_count": settings.expected_row_count,
            "data_sha256": settings.expected_data_sha256,
        },
        "canonical_manifest": manifest_summary(
            root / settings.canonical_manifest,
            root,
        ),
        "candidate_count": len(candidates),
        "exact_match_count": len(exact),
        "candidates": candidates,
    }
