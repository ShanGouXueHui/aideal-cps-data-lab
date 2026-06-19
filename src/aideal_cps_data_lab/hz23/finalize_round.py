from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aideal_cps_data_lab.application.candidate_validation import (
    expected_feed_schema,
    expected_manifest_schema,
)
from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.hz23.safety import unsafe_source_reason
from aideal_cps_data_lab.hz24.repository import load_json, read_jsonl
from aideal_cps_data_lab.hz24.settings import HZ24Settings, load_settings

expected_pages = set(range(1, 68))
minimum_scanned_total = 3900
minimum_successful_probes = 2
minimum_observation_hours = 48.0


@dataclass(frozen=True, slots=True)
class FinalizePaths:
    summary: Path
    index: Path
    seen: Path
    observer_state: Path
    source_candidates: tuple[Path, ...]
    export: Path
    manifest: Path


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def choose_source(paths: tuple[Path, ...]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def observation_hours(state: dict[str, Any], generated_at: str) -> float:
    started = state.get("observation_started_at") or state.get("created_at")
    if not started:
        return 0.0
    try:
        start = datetime.fromisoformat(str(started))
        end = datetime.fromisoformat(generated_at)
    except Exception:
        return 0.0
    return max(0.0, (end - start).total_seconds() / 3600.0)


def trusted_url(value: Any, settings: HZ24Settings) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return (
        parsed.scheme == settings.browser.trusted_link_scheme
        and parsed.hostname == settings.browser.trusted_link_host
    )


def update_catalog(
    index: dict[str, Any],
    seen: set[str],
    round_id: str,
    generated_at: str,
) -> dict[str, Any]:
    products = index.setdefault("products", {})
    for sku, row in products.items():
        if sku in seen:
            row["missing_rounds"] = 0
            row["active"] = True
        else:
            row["missing_rounds"] = int(row.get("missing_rounds") or 0) + 1
            if row["missing_rounds"] >= 2:
                row["active"] = False
    index["updated_at"] = generated_at
    index["last_completed_round_id"] = round_id
    return products


def deduplicate_source(
    rows: list[dict[str, Any]],
    settings: HZ24Settings,
) -> tuple[dict[str, dict[str, Any]], int, int, int]:
    dedup: dict[str, dict[str, Any]] = {}
    occurrences: dict[str, int] = {}
    unsafe_count = 0
    untrusted_count = 0
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        if not sku.isdigit() or row.get("status") != "ok" or not row.get("short_url"):
            continue
        occurrences[sku] = occurrences.get(sku, 0) + 1
        if unsafe_source_reason(row):
            unsafe_count += 1
            continue
        if not trusted_url(row.get("short_url"), settings):
            untrusted_count += 1
            continue
        dedup[sku] = row
    duplicates = sum(max(0, count - 1) for count in occurrences.values())
    return dedup, duplicates, unsafe_count, untrusted_count


def normalize_feed_row(
    sku: str,
    base: dict[str, Any],
    catalog: dict[str, Any],
    round_id: str,
    generated_at: str,
    settings: HZ24Settings,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": expected_feed_schema,
        "source": "jd_union_datalab",
        "sku": sku,
        "title": catalog.get("title") or base.get("title"),
        "description": base.get("description"),
        "item_url": catalog.get("item_url")
        or base.get("item_url")
        or f"{settings.browser.item_scheme}://{settings.browser.item_host}/{sku}.html",
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
        "commission_rate": catalog.get("commission_rate")
        or base.get("commission_rate"),
        "estimated_commission": catalog.get("estimated_income")
        or base.get("estimated_income"),
        "sales_volume": base.get("sales_volume"),
        "coupon_info": base.get("coupon_info"),
        "status": "active",
        "link_created_at": base.get("link_created_at"),
        "link_expire_at": base.get("link_expire_at"),
        "refresh_due_at": base.get("refresh_due_at"),
        "last_checked_at": catalog.get("last_checked_at"),
        "last_seen_at": catalog.get("last_seen_at"),
        "source_round_id": catalog.get("last_round_id") or round_id,
        "source_run_id": base.get("run_id"),
        "source_page_no": base.get("page_no"),
        "source_updated_at": catalog.get("last_checked_at")
        or base.get("ts")
        or generated_at,
        "catalog_change_count": int(catalog.get("change_count") or 0),
    }
    row["source_payload_hash"] = canonical_payload_hash(row)
    return row


def build_candidates(
    dedup: dict[str, dict[str, Any]],
    products: dict[str, Any],
    round_id: str,
    generated_at: str,
    settings: HZ24Settings,
    unsafe_count: int,
    untrusted_count: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rejected = {
        "inactive": 0,
        "missing_title": 0,
        "missing_item_url": 0,
        "missing_image_url": 0,
        "missing_price": 0,
        "missing_promotion_url": 0,
        "unsafe_hz20": unsafe_count,
        "untrusted_promotion_url": untrusted_count,
    }
    eligible: list[dict[str, Any]] = []
    for sku, base in dedup.items():
        catalog = products.get(sku) or {}
        if catalog and catalog.get("active") is False:
            rejected["inactive"] += 1
            continue
        row = normalize_feed_row(
            sku, base, catalog, round_id, generated_at, settings
        )
        missing = [
            field
            for field in ("title", "item_url", "image_url", "price", "promotion_url")
            if not row.get(field)
        ]
        for field in missing:
            rejected[f"missing_{field}"] += 1
        if missing:
            continue
        if not trusted_url(row.get("promotion_url"), settings):
            rejected["untrusted_promotion_url"] += 1
            continue
        eligible.append(row)
    eligible.sort(key=lambda row: str(row.get("sku") or ""))
    return eligible, rejected


def gate_state(
    summary: dict[str, Any],
    state: dict[str, Any],
    source_present: bool,
    eligible: list[dict[str, Any]],
    unsafe_count: int,
    untrusted_count: int,
    export_sha: str,
    generated_at: str,
) -> tuple[dict[str, bool], set[int], list[Any], int, int, float, int]:
    completed = {
        int(value)
        for value in summary.get("completed_pages") or []
        if str(value).isdigit()
    }
    unfinished = summary.get("unfinished_pages") or []
    scanned = int(summary.get("scanned_total") or 0)
    probes = int(state.get("successful_probes") or 0)
    hours = observation_hours(state, generated_at)
    skus = [str(row.get("sku") or "") for row in eligible]
    duplicates = len(skus) - len(set(skus))
    checks = {
        "source_present": source_present,
        "commercial_segment_complete": summary.get("commercial_segment_complete") is True,
        "all_pages_completed": completed == expected_pages,
        "unfinished_pages_empty": unfinished == [],
        "stop_reason_null": summary.get("stop_reason") in (None, ""),
        "scanned_total_minimum": scanned >= minimum_scanned_total,
        "candidate_nonempty": bool(eligible),
        "candidate_duplicate_sku_zero": duplicates == 0,
        "unsafe_hz20_zero": unsafe_count == 0,
        "untrusted_promotion_url_zero": untrusted_count == 0,
        "checksum_valid": len(export_sha) == 64,
        "successful_probes_minimum": probes >= minimum_successful_probes,
        "observation_hours_minimum": hours >= minimum_observation_hours,
    }
    return checks, completed, unfinished, scanned, probes, hours, duplicates


def build_manifest(
    round_id: str,
    generated_at: str,
    source: Path | None,
    paths: FinalizePaths,
    eligible: list[dict[str, Any]],
    dedup: dict[str, dict[str, Any]],
    source_duplicates: int,
    products: dict[str, Any],
    seen: set[str],
    rejected: dict[str, int],
    summary: dict[str, Any],
    checks: dict[str, bool],
    completed: set[int],
    unfinished: list[Any],
    scanned: int,
    probes: int,
    hours: float,
    duplicates: int,
    export_sha: str,
) -> dict[str, Any]:
    round_names = (
        "commercial_segment_complete",
        "all_pages_completed",
        "unfinished_pages_empty",
        "stop_reason_null",
        "scanned_total_minimum",
    )
    integrity_names = (
        "source_present",
        "candidate_nonempty",
        "candidate_duplicate_sku_zero",
        "unsafe_hz20_zero",
        "untrusted_promotion_url_zero",
        "checksum_valid",
    )
    return {
        "schema_version": expected_manifest_schema,
        "feed_schema_version": expected_feed_schema,
        "feed_status": "candidate",
        "generated_at": generated_at,
        "round_id": round_id,
        "source_file": str(source) if source else None,
        "data_file": paths.export.name,
        "candidate_file": str(paths.export),
        "data_sha256": export_sha,
        "row_count": len(eligible),
        "trusted_dedup_sku_count": len(dedup),
        "source_duplicate_sku_count": source_duplicates,
        "catalog_index_sku_count": len(products),
        "round_seen_sku_count": len(seen),
        "eligible_sku_count": len(eligible),
        "rejected": rejected,
        "duplicate_sku_count": duplicates,
        "commercial_segment_complete": summary.get("commercial_segment_complete"),
        "completed_pages": sorted(completed),
        "unfinished_pages": unfinished,
        "scanned_total": scanned,
        "catalog_new": summary.get("catalog_new"),
        "catalog_changed": summary.get("catalog_changed"),
        "catalog_unchanged": summary.get("catalog_unchanged"),
        "last_known_sku_count": summary.get("last_known_sku_count"),
        "stop_page": summary.get("stop_page"),
        "stop_reason": summary.get("stop_reason"),
        "round_complete": all(checks[name] for name in round_names),
        "candidate_integrity_ready": all(checks[name] for name in integrity_names),
        "successful_probes": probes,
        "minimum_successful_probes": minimum_successful_probes,
        "observation_hours": round(hours, 2),
        "minimum_observation_hours": minimum_observation_hours,
        "gate_checks": checks,
        "gate_failures": [name for name, passed in checks.items() if not passed],
        "observation_ready": all(checks.values()),
        "commercial_enabled": False,
    }


def run_finalize(
    round_id: str,
    paths: FinalizePaths,
    settings: HZ24Settings | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings()
    generated_at = timestamp()
    index = load_json(paths.index) or {"version": 1, "products": {}}
    seen = {
        str(row.get("sku"))
        for row in read_jsonl(paths.seen)
        if str(row.get("sku") or "").isdigit()
    }
    products = update_catalog(index, seen, round_id, generated_at)
    atomic_text(paths.index, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True))
    source = choose_source(paths.source_candidates)
    dedup, source_duplicates, unsafe_count, untrusted_count = deduplicate_source(
        read_jsonl(source) if source else [], settings
    )
    eligible, rejected = build_candidates(
        dedup, products, round_id, generated_at, settings, unsafe_count, untrusted_count
    )
    export_text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in eligible
    )
    export_sha = hashlib.sha256(export_text.encode("utf-8")).hexdigest()
    atomic_text(paths.export, export_text)
    summary = load_json(paths.summary)
    state = load_json(paths.observer_state)
    gate = gate_state(
        summary,
        state,
        source is not None,
        eligible,
        unsafe_count,
        untrusted_count,
        export_sha,
        generated_at,
    )
    manifest = build_manifest(
        round_id,
        generated_at,
        source,
        paths,
        eligible,
        dedup,
        source_duplicates,
        products,
        seen,
        rejected,
        summary,
        gate[0],
        gate[1],
        gate[2],
        gate[3],
        gate[4],
        gate[5],
        gate[6],
        export_sha,
    )
    atomic_text(
        paths.manifest,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("round_id")
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    paths = FinalizePaths(
        summary=args.summary,
        index=Path("data/state/hz23_catalog_index.json"),
        seen=Path(f"data/state/hz23_round_{args.round_id}_seen.jsonl"),
        observer_state=Path("run/hz23_observer_state.json"),
        source_candidates=(
            Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl"),
            Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl"),
        ),
        export=Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl"),
        manifest=Path("data/export/aideal_cps_products_commercial_candidate_manifest.json"),
    )
    manifest = run_finalize(args.round_id, paths)
    print(
        json.dumps(
            {"event": "HZ23_FINALIZE_DONE", **manifest},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if manifest.get("candidate_integrity_ready") else 1
