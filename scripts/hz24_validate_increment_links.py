#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

QUEUE = Path("data/export/hz24_special_tab_increment_latest.jsonl")
QUEUE_MANIFEST = Path("data/export/hz24_special_tab_increment_manifest.json")
LINKS = Path("data/import/hz24_special_tab_links_latest.jsonl")
LINKS_MANIFEST = Path("data/export/hz24_special_tab_links_manifest.json")
REPORT = Path("reports/hz24_increment_validation_latest.json")
TABS = {"超补爆品", "限量高佣", "秒杀专区", "定向高佣", "粉丝爱买"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return rows, invalid
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def trusted_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname == "u.jd.com"


def record_hash(row: dict[str, Any]) -> str:
    fields = {
        key: row.get(key)
        for key in [
            "sku", "title", "item_url", "image_url", "price", "commission_rate",
            "estimated_income", "short_url", "long_url", "source_tab", "source_tabs",
        ]
    }
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    queue_manifest = load_json(QUEUE_MANIFEST)
    queue_rows, queue_invalid = read_jsonl(QUEUE)
    link_rows, link_invalid = read_jsonl(LINKS)
    queue_raw = QUEUE.read_bytes() if QUEUE.exists() else b""
    links_raw = LINKS.read_bytes() if LINKS.exists() else b""
    queue_sha = hashlib.sha256(queue_raw).hexdigest() if queue_raw else ""
    links_sha = hashlib.sha256(links_raw).hexdigest() if links_raw else ""

    queue_by_sku = {
        str(row.get("sku") or ""): row for row in queue_rows if str(row.get("sku") or "")
    }
    links_by_sku: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for row in link_rows:
        sku = str(row.get("sku") or "")
        if not sku:
            continue
        if sku in links_by_sku:
            duplicate_count += 1
        links_by_sku[sku] = row

    missing = sorted(set(queue_by_sku) - set(links_by_sku))
    extras = sorted(set(links_by_sku) - set(queue_by_sku))
    untrusted: list[str] = []
    incomplete: list[str] = []
    hash_mismatch: list[str] = []
    tab_mismatch: list[str] = []
    unsafe: list[str] = []

    required = ["title", "item_url", "price", "commission_rate", "estimated_income", "short_url"]
    for sku, row in links_by_sku.items():
        if not trusted_url(row.get("short_url")):
            untrusted.append(sku)
        if any(not str(row.get(field) or "").strip() for field in required):
            incomplete.append(sku)
        if row.get("record_sha256") != record_hash(row):
            hash_mismatch.append(sku)
        source_tab = str(row.get("source_tab") or "")
        expected_tabs = set(queue_by_sku.get(sku, {}).get("source_tabs") or [])
        if source_tab not in TABS or source_tab not in expected_tabs:
            tab_mismatch.append(sku)
        if "hz20" in str(row.get("worker_name") or "").lower() or "hz20" in str(row.get("menu_mode") or "").lower():
            unsafe.append(sku)

    checks = {
        "queue_present": QUEUE.exists(),
        "queue_manifest_present": bool(queue_manifest),
        "queue_json_valid": queue_invalid == 0,
        "queue_checksum_valid": queue_sha == str(queue_manifest.get("data_sha256") or ""),
        "queue_row_count_valid": len(queue_rows) == int(queue_manifest.get("row_count") or -1),
        "links_present": LINKS.exists(),
        "links_json_valid": link_invalid == 0,
        "all_queue_skus_linked": not missing,
        "no_extra_skus": not extras,
        "duplicate_sku_zero": duplicate_count == 0,
        "trusted_url_only": not untrusted,
        "required_fields_complete": not incomplete,
        "record_hash_valid": not hash_mismatch,
        "source_tab_valid": not tab_mismatch,
        "unsafe_hz20_zero": not unsafe,
    }
    ready = all(checks.values())
    generated_at = datetime.now().isoformat(timespec="seconds")

    manifest = {
        "schema_version": "aideal-hz24-special-tab-links-manifest/v1",
        "generated_at": generated_at,
        "status": "validated_candidate" if ready else "incomplete",
        "queue_file": str(QUEUE),
        "queue_sha256": queue_sha,
        "links_file": str(LINKS),
        "links_sha256": links_sha,
        "queue_row_count": len(queue_by_sku),
        "validated_row_count": len(links_by_sku) - len(extras),
        "missing_count": len(missing),
        "duplicate_sku_count": duplicate_count,
        "untrusted_url_count": len(untrusted),
        "incomplete_row_count": len(incomplete),
        "hash_mismatch_count": len(hash_mismatch),
        "commercial_enabled": False,
        "merge_allowed": ready,
    }
    atomic_json(LINKS_MANIFEST, manifest)

    report = {
        "ok": ready,
        "generated_at": generated_at,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "queue_count": len(queue_by_sku),
        "link_row_count": len(link_rows),
        "unique_link_sku_count": len(links_by_sku),
        "missing_count": len(missing),
        "missing_samples": missing[:30],
        "extra_count": len(extras),
        "extra_samples": extras[:30],
        "duplicate_sku_count": duplicate_count,
        "untrusted_url_count": len(untrusted),
        "untrusted_samples": untrusted[:20],
        "incomplete_row_count": len(incomplete),
        "incomplete_samples": incomplete[:20],
        "hash_mismatch_count": len(hash_mismatch),
        "hash_mismatch_samples": hash_mismatch[:20],
        "tab_mismatch_count": len(tab_mismatch),
        "unsafe_hz20_count": len(unsafe),
        "merge_allowed": ready,
    }
    atomic_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
