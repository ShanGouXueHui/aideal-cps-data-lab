#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aideal_cps_data_lab.contracts import canonical_payload_hash

ROUND_ID = sys.argv[1]
SUMMARY_PATH = Path(sys.argv[2])
INDEX = Path("data/state/hz23_catalog_index.json")
SEEN = Path(f"data/state/hz23_round_{ROUND_ID}_seen.jsonl")
OBSERVER_STATE = Path("run/hz23_observer_state.json")
LATEST_CANDIDATES = [
    Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl"),
    Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl"),
]
EXPORT = Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl")
MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
FEED_SCHEMA_VERSION = "aideal-cps-product-feed/v1"
MANIFEST_SCHEMA_VERSION = "aideal-cps-product-feed-manifest/v1"
MIN_SCANNED_TOTAL = 3900
MIN_SUCCESSFUL_PROBES = 2
MIN_OBSERVATION_HOURS = 48.0
EXPECTED_PAGES = set(range(1, 68))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


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


def stable_payload_hash(row: Dict[str, Any]) -> str:
    return canonical_payload_hash(row)


def trusted_promotion_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname == "u.jd.com"


def is_hz20_unsafe(row: Dict[str, Any]) -> bool:
    worker = str(row.get("worker_name") or "").lower()
    mode = str(row.get("menu_mode") or "").lower()
    promotion_mode = str(row.get("promotion_mode") or "").lower()
    return worker == "hz20_mouse_click" or "hz20" in mode or "hz20" in promotion_mode


def observation_hours(state: Dict[str, Any], generated_at: str) -> float:
    started = state.get("observation_started_at") or state.get("created_at")
    if not started:
        return 0.0
    try:
        start_dt = datetime.fromisoformat(str(started))
        end_dt = datetime.fromisoformat(generated_at)
        return max(0.0, (end_dt - start_dt).total_seconds() / 3600.0)
    except Exception:
        return 0.0


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
    row["source_payload_hash"] = stable_payload_hash(row)
    return row


def main() -> None:
    generated_at = now()
    index = read_json(INDEX) or {"version": 1, "products": {}}
    products: Dict[str, Any] = index.setdefault("products", {})
    seen_rows = read_jsonl(SEEN)
    seen = {str(x.get("sku")) for x in seen_rows if str(x.get("sku") or "").isdigit()}

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
    occurrence_count: Dict[str, int] = {}
    unsafe_hz20_count = 0
    untrusted_promotion_url_count = 0

    for row in trusted_rows:
        sku = str(row.get("sku") or "").strip()
        if not sku.isdigit() or row.get("status") != "ok" or not row.get("short_url"):
            continue
        occurrence_count[sku] = occurrence_count.get(sku, 0) + 1
        if is_hz20_unsafe(row):
            unsafe_hz20_count += 1
            continue
        if not trusted_promotion_url(row.get("short_url")):
            untrusted_promotion_url_count += 1
            continue
        dedup[sku] = row

    source_duplicate_sku_count = sum(max(0, count - 1) for count in occurrence_count.values())
    eligible: List[Dict[str, Any]] = []
    rejected: Dict[str, int] = {
        "inactive": 0,
        "missing_title": 0,
        "missing_item_url": 0,
        "missing_image_url": 0,
        "missing_price": 0,
        "missing_promotion_url": 0,
        "unsafe_hz20": unsafe_hz20_count,
        "untrusted_promotion_url": untrusted_promotion_url_count,
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
        if not trusted_promotion_url(row.get("promotion_url")):
            rejected["untrusted_promotion_url"] += 1
            continue
        eligible.append(row)

    eligible.sort(key=lambda x: str(x.get("sku") or ""))
    candidate_skus = [str(row.get("sku") or "") for row in eligible]
    duplicate_sku_count = len(candidate_skus) - len(set(candidate_skus))
    export_text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in eligible
    )
    export_sha256 = hashlib.sha256(export_text.encode("utf-8")).hexdigest()
    atomic_write(EXPORT, export_text)

    round_summary = read_json(SUMMARY_PATH)
    observer_state = read_json(OBSERVER_STATE)
    completed_pages = {int(x) for x in round_summary.get("completed_pages") or [] if str(x).isdigit()}
    unfinished_pages = round_summary.get("unfinished_pages") or []
    scanned_total = int(round_summary.get("scanned_total") or 0)
    successful_probes = int(observer_state.get("successful_probes") or 0)
    observed_hours = observation_hours(observer_state, generated_at)

    gate_checks = {
        "source_present": source is not None,
        "commercial_segment_complete": round_summary.get("commercial_segment_complete") is True,
        "all_pages_completed": completed_pages == EXPECTED_PAGES,
        "unfinished_pages_empty": unfinished_pages == [],
        "stop_reason_null": round_summary.get("stop_reason") in (None, ""),
        "scanned_total_minimum": scanned_total >= MIN_SCANNED_TOTAL,
        "candidate_nonempty": len(eligible) > 0,
        "candidate_duplicate_sku_zero": duplicate_sku_count == 0,
        "unsafe_hz20_zero": unsafe_hz20_count == 0,
        "untrusted_promotion_url_zero": untrusted_promotion_url_count == 0,
        "checksum_valid": len(export_sha256) == 64,
        "successful_probes_minimum": successful_probes >= MIN_SUCCESSFUL_PROBES,
        "observation_hours_minimum": observed_hours >= MIN_OBSERVATION_HOURS,
    }
    gate_failures = [name for name, passed in gate_checks.items() if not passed]
    round_complete = all(
        gate_checks[name]
        for name in [
            "commercial_segment_complete",
            "all_pages_completed",
            "unfinished_pages_empty",
            "stop_reason_null",
            "scanned_total_minimum",
        ]
    )
    candidate_integrity_ready = all(
        gate_checks[name]
        for name in [
            "source_present",
            "candidate_nonempty",
            "candidate_duplicate_sku_zero",
            "unsafe_hz20_zero",
            "untrusted_promotion_url_zero",
            "checksum_valid",
        ]
    )
    observation_ready = all(gate_checks.values())

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
        "source_duplicate_sku_count": source_duplicate_sku_count,
        "catalog_index_sku_count": len(products),
        "round_seen_sku_count": len(seen),
        "eligible_sku_count": len(eligible),
        "rejected": rejected,
        "duplicate_sku_count": duplicate_sku_count,
        "commercial_segment_complete": round_summary.get("commercial_segment_complete"),
        "completed_pages": sorted(completed_pages),
        "unfinished_pages": unfinished_pages,
        "scanned_total": scanned_total,
        "catalog_new": round_summary.get("catalog_new"),
        "catalog_changed": round_summary.get("catalog_changed"),
        "catalog_unchanged": round_summary.get("catalog_unchanged"),
        "last_known_sku_count": round_summary.get("last_known_sku_count"),
        "stop_page": round_summary.get("stop_page"),
        "stop_reason": round_summary.get("stop_reason"),
        "round_complete": round_complete,
        "candidate_integrity_ready": candidate_integrity_ready,
        "successful_probes": successful_probes,
        "minimum_successful_probes": MIN_SUCCESSFUL_PROBES,
        "observation_hours": round(observed_hours, 2),
        "minimum_observation_hours": MIN_OBSERVATION_HOURS,
        "gate_checks": gate_checks,
        "gate_failures": gate_failures,
        "observation_ready": observation_ready,
        "commercial_enabled": False,
    }
    atomic_write(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps({"event": "HZ23_FINALIZE_DONE", **manifest}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
