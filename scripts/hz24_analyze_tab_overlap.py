#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

STRUCTURE = Path("reports/hz24_tab_pool_structure_latest.json")
CANDIDATE = Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl")
MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
REPORT = Path("reports/hz24_tab_overlap_analysis_latest.json")
SPECIAL_TABS = ["超补爆品", "限量高佣", "秒杀专区", "定向高佣", "粉丝爱买"]


def load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def load_jsonl_skus(path: Path) -> set[str]:
    skus: set[str] = set()
    if not path.exists():
        return skus
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        sku = str(row.get("sku") or row.get("jd_sku_id") or "").strip()
        if sku:
            skus.add(sku)
    return skus


def trusted_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname == "u.jd.com"


def load_trusted_source_skus(path: Path) -> set[str]:
    skus: set[str] = set()
    if not path.exists():
        return skus
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").lower() != "ok":
            continue
        url = row.get("short_url") or row.get("promotion_url")
        if not trusted_url(url):
            continue
        sku = str(row.get("sku") or row.get("jd_sku_id") or "").strip()
        if sku:
            skus.add(sku)
    return skus


def main() -> int:
    structure_raw = STRUCTURE.read_bytes() if STRUCTURE.exists() else b""
    structure_sha256 = hashlib.sha256(structure_raw).hexdigest() if structure_raw else ""
    structure = load_object(STRUCTURE)
    manifest = load_object(MANIFEST)
    candidate_skus = load_jsonl_skus(CANDIDATE)
    source_path = Path(str(manifest.get("source_file") or ""))
    trusted_skus = load_trusted_source_skus(source_path)

    tab_map = {
        str(row.get("tab_name") or ""): row
        for row in structure.get("tabs") or []
        if isinstance(row, dict)
    }
    tab_sets: dict[str, set[str]] = {}
    per_tab: list[dict[str, Any]] = []
    for name in SPECIAL_TABS:
        row = tab_map.get(name) or {}
        skus = {str(value).strip() for value in row.get("skus") or [] if str(value).strip()}
        tab_sets[name] = skus
        per_tab.append(
            {
                "tab_name": name,
                "pool_sku_count": len(skus),
                "tab_ok": row.get("ok") is True,
                "tab_risk": row.get("risk") or [],
                "single_page_confirmed": row.get("single_page_confirmed") is True,
                "single_page_confirmation_method": row.get("single_page_confirmation_method"),
                "overlap_with_candidate_count": len(skus & candidate_skus),
                "increment_vs_candidate_count": len(skus - candidate_skus),
                "overlap_with_trusted_source_count": len(skus & trusted_skus),
                "promotion_link_required_count": len(skus - trusted_skus),
                "increment_vs_candidate_samples": sorted(skus - candidate_skus)[:20],
                "promotion_link_required_samples": sorted(skus - trusted_skus)[:20],
            }
        )

    union_special: set[str] = set().union(*tab_sets.values()) if tab_sets else set()
    pairwise = []
    for left, right in combinations(SPECIAL_TABS, 2):
        left_set = tab_sets.get(left, set())
        right_set = tab_sets.get(right, set())
        intersection = left_set & right_set
        union = left_set | right_set
        pairwise.append(
            {
                "left": left,
                "right": right,
                "intersection_count": len(intersection),
                "jaccard": round(len(intersection) / len(union), 4) if union else None,
                "intersection_samples": sorted(intersection)[:20],
            }
        )

    all_special_present = all(name in tab_map for name in SPECIAL_TABS)
    all_special_complete = all(
        (tab_map.get(name) or {}).get("single_page_confirmed") is True
        for name in SPECIAL_TABS
    )
    all_special_safe = all(
        (tab_map.get(name) or {}).get("ok") is True
        and not ((tab_map.get(name) or {}).get("risk") or [])
        and bool(tab_sets.get(name))
        for name in SPECIAL_TABS
    )
    checks = {
        "structure_file_present": STRUCTURE.exists(),
        "all_special_tabs_present": all_special_present,
        "all_special_tabs_single_page_confirmed": all_special_complete,
        "all_special_tabs_safe": all_special_safe,
        "candidate_file_present": CANDIDATE.exists(),
        "candidate_nonempty": len(candidate_skus) > 0,
        "manifest_present": bool(manifest),
        "trusted_source_present": source_path.exists(),
    }
    ready = all(checks.values())

    result = {
        "schema_version": "aideal-hz24-tab-overlap-analysis/v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "structure_generated_at": structure.get("generated_at"),
        "structure_sha256": structure_sha256,
        "structure_global_ok": structure.get("ok") is True,
        "structure_global_risk": structure.get("risk") or [],
        "ok": ready,
        "analysis_ready": ready,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "candidate_sku_count": len(candidate_skus),
        "trusted_source_sku_count": len(trusted_skus),
        "source_file": str(source_path),
        "special_tab_membership_count": sum(len(value) for value in tab_sets.values()),
        "special_tab_union_sku_count": len(union_special),
        "cross_tab_duplicate_membership_count": sum(len(value) for value in tab_sets.values()) - len(union_special),
        "special_union_overlap_with_candidate_count": len(union_special & candidate_skus),
        "special_union_increment_vs_candidate_count": len(union_special - candidate_skus),
        "special_union_overlap_with_trusted_source_count": len(union_special & trusted_skus),
        "special_union_promotion_link_required_count": len(union_special - trusted_skus),
        "special_union_already_linked_not_candidate_count": len((union_special & trusted_skus) - candidate_skus),
        "special_union_increment_vs_candidate_samples": sorted(union_special - candidate_skus)[:50],
        "special_union_promotion_link_required_samples": sorted(union_special - trusted_skus)[:50],
        "per_tab": per_tab,
        "pairwise": pairwise,
        "recommended_next_step": (
            "generate_links_only_for_global_increment"
            if ready and len(union_special - trusted_skus) > 0
            else "merge_already_linked_increment"
            if ready and len(union_special - candidate_skus) > 0
            else "no_increment"
            if ready
            else "complete_structure_audit"
        ),
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(REPORT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
