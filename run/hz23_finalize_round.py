#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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
FEED_SCHEMA_VERSION = "aideal-cps-product-feed/v1"
MANIFEST_SCHEMA_VERSION = "aideal-cps-product-feed-manifest/v1"


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


def payload_hash(row: Dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_feed_row(
    sku: str,
    base: Dict[str, Any],
    catalog: Dict[str, Any],
    generated_at: str,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "schema_version": FEED_SCHEMA_VERSION,
        "source": "jd_union_datalab",
        "sku": sku,
        "title": catalog.get("title") or base.get("title"),
        "description": base.get("description"),
        "item_url": catalog.get("item_url") or base.get("item_url") or f"https://item.jd.com/{sku}.html",
        "promotion_url": base.get("short_url"),
        "short_url": base.get("short_url"),
        "long_url": base.get("long_url"),
        "qr_url": base.get("qr_url"),
        "jd_command": base.get("jd_command"),
        "image_url": catalog.get("image_url") or base.get("image_url"),
        "category_name": base.get("category_name"),
        "shop_name": base.get("shop_name"),
        "price": catalog.get("price") or base.get("price"),
        "coupon_price": base.get("coupon_price"),
        "commission_rate": catalog.get("commission_rate") or base.get("commission_rate"),
        "estimated_commission": catalog.get("estimated_income") or base.get("estimated_income"),
        "sales_volume": base.get("sales_volume"),
        "coupon_info": base.get("coupon_info"),
        "status": "active",
        "link_created_at": base.get("link_created_at"),
        "link_expire_at": base.get("link_expire_at"),
        "refresh_due_at": base.get("refresh_due_at"),
        "last_checked_at": catalog.get("last_checked_at"),
        "last_seen_at": catalog.get("last_seen_at"),
        "source_round_id": catalog.get("last_round_id") or ROUND_ID,
        "source_run_id": base.get("run_id"),
        "source_page_no": base.get("page_no"),
        "source_updated_at": catalog.get("last_checked_at") or base.get("ts") or generated_at,
        "catalog_change_count": int(catalog.get("change_count") or 0),
    }
    row["source_payload_hash"] = payload_hash(row)
    return row


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
        "missing_promotion_url": 0,
    }
    for sku, base in dedup.items():
        catalog = products.get(sku) or {}
        if catalog and catalog.get("active") is False:
            rejected["inactive"] += 1
            continue
        row = normalize_feed_row(sku, base, catalog, generated_at)
        missing = []
        for field in ["title", "item_url", "image_url", "price", "promotion_url"]:
            if not row.get(field):
                missing.append(field)
                rejected[f"missing_{field}"] += 1
        if missing:
            continue
        eligible.append(row)

    eligible.sort(key=lambda x: str(x.get("sku") or ""))
    export_text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in eligible)
    export_sha256 = hashlib.sha256(export_text.encode("utf-8")).hexdigest()
    atomic_write(EXPORT, export_text)

    round_summary: Dict[str, Any] = {}
    if SUMMARY_PATH.exists():
        try:
            round_summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "feed_schema_version": FEED_SCHEMA_VERSION,
        "feed_status": "candidate",
        "generated_at": generated_at,
        "round_id": ROUND_ID,
        "source_file": str(source) if source else None,
        "data_file": EXPORT.name,
        "candidate_file": str(EXPORT),
        "data_sha256": export_sha256,
        "row_count": len(eligible),
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
