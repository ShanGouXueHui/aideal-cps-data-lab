#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

BASE_PATH = Path("scripts/hz24_validate_increment_links.py")
UNAVAILABLE = Path("data/import/hz24_special_tab_unavailable_latest.jsonl")
OUTCOME_MANIFEST = Path("data/export/hz24_special_tab_outcomes_manifest.json")
REPORT = Path("reports/hz24_increment_validation_latest.json")
ALLOWED_UNAVAILABLE = {"sold_out", "delisted", "not_promotable"}


def load_base():
    spec = importlib.util.spec_from_file_location("hz24_validate_v1", str(BASE_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()


def unavailable_hash(row: dict[str, Any]) -> str:
    fields = {key: row.get(key) for key in ["schema_version", "status", "reason", "observed_at", "worker_name", "sku", "title", "item_url", "source_tab", "source_tabs", "structure_sha256"]}
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    queue_manifest = base.load_json(base.QUEUE_MANIFEST)
    queue_rows, queue_invalid = base.read_jsonl(base.QUEUE)
    linked_rows, linked_invalid = base.read_jsonl(base.LINKS)
    unavailable_rows, unavailable_invalid = base.read_jsonl(UNAVAILABLE)
    queue_raw = base.QUEUE.read_bytes() if base.QUEUE.exists() else b""
    linked_raw = base.LINKS.read_bytes() if base.LINKS.exists() else b""
    unavailable_raw = UNAVAILABLE.read_bytes() if UNAVAILABLE.exists() else b""

    queue_by_sku = {str(row.get("sku") or ""): row for row in queue_rows if str(row.get("sku") or "")}
    linked_by_sku: dict[str, dict[str, Any]] = {}
    unavailable_by_sku: dict[str, dict[str, Any]] = {}
    linked_duplicates = 0
    unavailable_duplicates = 0
    for row in linked_rows:
        sku = str(row.get("sku") or "")
        if not sku:
            continue
        if sku in linked_by_sku:
            linked_duplicates += 1
        linked_by_sku[sku] = row
    for row in unavailable_rows:
        sku = str(row.get("sku") or "")
        if not sku:
            continue
        if sku in unavailable_by_sku:
            unavailable_duplicates += 1
        unavailable_by_sku[sku] = row

    queue_skus = set(queue_by_sku)
    linked_skus = set(linked_by_sku)
    unavailable_skus = set(unavailable_by_sku)
    overlap = sorted(linked_skus & unavailable_skus)
    extras = sorted((linked_skus | unavailable_skus) - queue_skus)
    missing = sorted(queue_skus - linked_skus - unavailable_skus)

    untrusted: list[str] = []
    incomplete: list[str] = []
    hash_mismatch: list[str] = []
    tab_mismatch: list[str] = []
    unsafe: list[str] = []
    for sku, row in linked_by_sku.items():
        if not base.trusted_url(row.get("short_url")):
            untrusted.append(sku)
        required = ["title", "item_url", "price", "commission_rate", "estimated_income", "short_url"]
        if any(not str(row.get(field) or "").strip() for field in required):
            incomplete.append(sku)
        if row.get("record_sha256") != base.record_hash(row):
            hash_mismatch.append(sku)
        expected_tabs = set(queue_by_sku.get(sku, {}).get("source_tabs") or [])
        if str(row.get("source_tab") or "") not in expected_tabs:
            tab_mismatch.append(sku)
        if "hz20" in str(row.get("worker_name") or "").lower():
            unsafe.append(sku)

    unavailable_invalid_reason: list[str] = []
    unavailable_hash_mismatch: list[str] = []
    unavailable_tab_mismatch: list[str] = []
    for sku, row in unavailable_by_sku.items():
        if str(row.get("reason") or "") not in ALLOWED_UNAVAILABLE:
            unavailable_invalid_reason.append(sku)
        if row.get("record_sha256") != unavailable_hash(row):
            unavailable_hash_mismatch.append(sku)
        expected_tabs = set(queue_by_sku.get(sku, {}).get("source_tabs") or [])
        if str(row.get("source_tab") or "") not in expected_tabs:
            unavailable_tab_mismatch.append(sku)

    queue_sha = hashlib.sha256(queue_raw).hexdigest() if queue_raw else ""
    checks = {
        "queue_present": base.QUEUE.exists(),
        "queue_manifest_present": bool(queue_manifest),
        "queue_json_valid": queue_invalid == 0,
        "queue_checksum_valid": queue_sha == str(queue_manifest.get("data_sha256") or ""),
        "queue_row_count_valid": len(queue_rows) == int(queue_manifest.get("row_count") or -1),
        "linked_json_valid": linked_invalid == 0,
        "unavailable_json_valid": unavailable_invalid == 0,
        "all_queue_skus_accounted": not missing,
        "no_extra_skus": not extras,
        "linked_unavailable_overlap_zero": not overlap,
        "duplicate_sku_zero": linked_duplicates == 0 and unavailable_duplicates == 0,
        "trusted_url_only": not untrusted,
        "linked_required_fields_complete": not incomplete,
        "linked_hash_valid": not hash_mismatch,
        "linked_source_tab_valid": not tab_mismatch,
        "unsafe_hz20_zero": not unsafe,
        "unavailable_reason_valid": not unavailable_invalid_reason,
        "unavailable_hash_valid": not unavailable_hash_mismatch,
        "unavailable_source_tab_valid": not unavailable_tab_mismatch,
    }
    ready = all(checks.values())
    generated_at = base.datetime.now().isoformat(timespec="seconds")

    manifest = {
        "schema_version": "aideal-hz24-special-tab-outcomes-manifest/v1",
        "generated_at": generated_at,
        "status": "validated_candidate" if ready else "incomplete",
        "queue_row_count": len(queue_skus),
        "linked_row_count": len(linked_skus & queue_skus),
        "unavailable_row_count": len(unavailable_skus & queue_skus),
        "accounted_row_count": len((linked_skus | unavailable_skus) & queue_skus),
        "missing_count": len(missing),
        "linked_sha256": hashlib.sha256(linked_raw).hexdigest() if linked_raw else "",
        "unavailable_sha256": hashlib.sha256(unavailable_raw).hexdigest() if unavailable_raw else "",
        "commercial_enabled": False,
        "merge_allowed": ready,
        "merge_linked_only": True,
    }
    base.atomic_json(OUTCOME_MANIFEST, manifest)

    report = {
        "ok": ready,
        "generated_at": generated_at,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "queue_count": len(queue_skus),
        "linked_count": len(linked_skus & queue_skus),
        "unavailable_count": len(unavailable_skus & queue_skus),
        "accounted_count": len((linked_skus | unavailable_skus) & queue_skus),
        "missing_count": len(missing),
        "missing_samples": missing[:30],
        "extra_count": len(extras),
        "overlap_count": len(overlap),
        "untrusted_url_count": len(untrusted),
        "incomplete_linked_count": len(incomplete),
        "linked_hash_mismatch_count": len(hash_mismatch),
        "unavailable_invalid_reason_count": len(unavailable_invalid_reason),
        "unavailable_hash_mismatch_count": len(unavailable_hash_mismatch),
        "merge_allowed": ready,
        "merge_linked_only": True,
    }
    base.atomic_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
