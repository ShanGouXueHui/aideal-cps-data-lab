#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROUND_ID = sys.argv[1]
SUMMARY_PATH = Path(sys.argv[2])
INDEX = Path("data/state/hz23_catalog_index.json")
SEEN = Path(f"data/state/hz23_round_{ROUND_ID}_seen.jsonl")
LATEST_CANDIDATES = [
    Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl"),
    Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl"),
]
EXPORT = Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl")
MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def choose_source() -> Path | None:
    for path in LATEST_CANDIDATES:
        if path.exists():
            return path
    return None


def main() -> None:
    generated_at = now()
    index: Dict[str, Any] = {"version": 1, "products": {}}
    if INDEX.exists():
        try:
            index = json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            pass
    products: Dict[str, Any] = index.setdefault("products", {})
    seen = {str(x.get("sku")) for x in read_jsonl(SEEN) if str(x.get("sku") or "").isdigit()}

    for sku, row in products.items():
        if sku in seen:
            row["missing_rounds"] = 0
            row["active"] = True
        else:
            row["missing_rounds"] = int(row.get("missing_rounds") or 0) + 1
            if row["missing_rounds"] >= 2:
                row["active"] = False
    index["updated_at"] = generated_at
    index["last_completed_round_id"] = ROUND_ID
    atomic_write(INDEX, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True))

    source = choose_source()
    trusted_rows = read_jsonl(source) if source else []
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in trusted_rows:
        sku = str(row.get("sku") or "").strip()
        if not sku.isdigit() or row.get("status") != "ok" or not row.get("short_url"):
            continue
        dedup[sku] = row

    eligible: List[Dict[str, Any]] = []
    rejected: Dict[str, int] = {
        "inactive": 0,
        "missing_title": 0,
        "missing_item_url": 0,
        "missing_image_url": 0,
        "missing_price": 0,
        "missing_short_url": 0,
    }
    for sku, base in dedup.items():
        catalog = products.get(sku) or {}
        if catalog and catalog.get("active") is False:
            rejected["inactive"] += 1
            continue
        row = dict(base)
        for key in ["title", "item_url", "image_url", "price", "commission_rate", "estimated_income"]:
            if catalog.get(key):
                row[key] = catalog[key]
        row["last_checked_at"] = catalog.get("last_checked_at")
        row["last_seen_at"] = catalog.get("last_seen_at")
        row["catalog_round_id"] = catalog.get("last_round_id")
        row["catalog_change_count"] = int(catalog.get("change_count") or 0)
        missing = []
        for field in ["title", "item_url", "image_url", "price", "short_url"]:
            if not row.get(field):
                missing.append(field)
                rejected[f"missing_{field}"] += 1
        if missing:
            continue
        eligible.append(row)

    eligible.sort(key=lambda x: str(x.get("sku") or ""))
    export_text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in eligible)
    atomic_write(EXPORT, export_text)

    round_summary: Dict[str, Any] = {}
    if SUMMARY_PATH.exists():
        try:
            round_summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    manifest = {
        "generated_at": generated_at,
        "round_id": ROUND_ID,
        "source_file": str(source) if source else None,
        "candidate_file": str(EXPORT),
        "trusted_dedup_sku_count": len(dedup),
        "catalog_index_sku_count": len(products),
        "round_seen_sku_count": len(seen),
        "eligible_sku_count": len(eligible),
        "rejected": rejected,
        "duplicate_sku_count": len(eligible) - len({str(x.get("sku")) for x in eligible}),
        "round_complete": bool(round_summary.get("commercial_segment_complete")),
        "round_total_ok": round_summary.get("total_ok"),
        "round_total_fail": round_summary.get("total_fail"),
        "observation_ready": bool(round_summary.get("commercial_segment_complete")) and len(eligible) > 0,
        "commercial_enabled": False,
    }
    atomic_write(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps({"event": "HZ23_FINALIZE_DONE", **manifest}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
