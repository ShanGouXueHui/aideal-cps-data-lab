from __future__ import annotations

import hashlib
import json
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from .queue_builder import load_json, trusted_source_skus
from .settings import HZ24Settings, load_settings

STRUCTURE_PATH = Path("reports/hz24_tab_pool_structure_latest.json")
CANDIDATE_PATH = Path(
    "data/export/aideal_cps_products_commercial_candidate_latest.jsonl"
)
MANIFEST_PATH = Path(
    "data/export/aideal_cps_products_commercial_candidate_manifest.json"
)
REPORT_PATH = Path("reports/hz24_tab_overlap_analysis_latest.json")


def load_jsonl_skus(path: Path) -> set[str]:
    skus: set[str] = set()
    if not path.exists():
        return skus
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def build_tab_analysis(
    tab_map: dict[str, dict[str, Any]],
    tabs: tuple[str, ...],
    candidate_skus: set[str],
    trusted_skus: set[str],
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    tab_sets: dict[str, set[str]] = {}
    per_tab: list[dict[str, Any]] = []
    for name in tabs:
        row = tab_map.get(name) or {}
        skus = {
            str(value).strip()
            for value in row.get("skus") or []
            if str(value).strip()
        }
        tab_sets[name] = skus
        per_tab.append(
            {
                "tab_name": name,
                "pool_sku_count": len(skus),
                "tab_ok": row.get("ok") is True,
                "tab_risk": row.get("risk") or [],
                "single_page_confirmed": row.get("single_page_confirmed") is True,
                "single_page_confirmation_method": row.get(
                    "single_page_confirmation_method"
                ),
                "overlap_with_candidate_count": len(skus & candidate_skus),
                "increment_vs_candidate_count": len(skus - candidate_skus),
                "overlap_with_trusted_source_count": len(skus & trusted_skus),
                "promotion_link_required_count": len(skus - trusted_skus),
                "increment_vs_candidate_samples": sorted(skus - candidate_skus)[:20],
                "promotion_link_required_samples": sorted(skus - trusted_skus)[:20],
            }
        )
    return tab_sets, per_tab


def pairwise_analysis(
    tabs: tuple[str, ...],
    tab_sets: dict[str, set[str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for left, right in combinations(tabs, 2):
        left_set = tab_sets.get(left, set())
        right_set = tab_sets.get(right, set())
        intersection = left_set & right_set
        union = left_set | right_set
        output.append(
            {
                "left": left,
                "right": right,
                "intersection_count": len(intersection),
                "jaccard": round(len(intersection) / len(union), 4) if union else None,
                "intersection_samples": sorted(intersection)[:20],
            }
        )
    return output


def build_checks(
    structure_path: Path,
    candidate_path: Path,
    manifest: dict,
    source_path: Path,
    tab_map: dict[str, dict[str, Any]],
    tab_sets: dict[str, set[str]],
    tabs: tuple[str, ...],
    candidate_skus: set[str],
) -> dict[str, bool]:
    return {
        "structure_file_present": structure_path.exists(),
        "all_special_tabs_present": all(name in tab_map for name in tabs),
        "all_special_tabs_single_page_confirmed": all(
            (tab_map.get(name) or {}).get("single_page_confirmed") is True
            for name in tabs
        ),
        "all_special_tabs_safe": all(
            (tab_map.get(name) or {}).get("ok") is True
            and not ((tab_map.get(name) or {}).get("risk") or [])
            and bool(tab_sets.get(name))
            for name in tabs
        ),
        "candidate_file_present": candidate_path.exists(),
        "candidate_nonempty": bool(candidate_skus),
        "manifest_present": bool(manifest),
        "trusted_source_present": source_path.exists(),
    }


def recommended_step(
    ready: bool,
    union_special: set[str],
    candidate_skus: set[str],
    trusted_skus: set[str],
) -> str:
    if not ready:
        return "complete_structure_audit"
    if union_special - trusted_skus:
        return "generate_links_only_for_global_increment"
    if union_special - candidate_skus:
        return "merge_already_linked_increment"
    return "no_increment"


def run_overlap_analysis(settings: HZ24Settings | None = None) -> int:
    settings = settings or load_settings()
    structure_path = settings.root / STRUCTURE_PATH
    candidate_path = settings.root / CANDIDATE_PATH
    manifest_path = settings.root / MANIFEST_PATH
    report_path = settings.root / REPORT_PATH
    raw = structure_path.read_bytes() if structure_path.exists() else b""
    structure = load_json(structure_path)
    manifest = load_json(manifest_path)
    candidate_skus = load_jsonl_skus(candidate_path)
    source_path = settings.root / str(manifest.get("source_file") or "")
    trusted_skus = trusted_source_skus(source_path, settings)
    tab_map = {
        str(row.get("tab_name") or ""): row
        for row in structure.get("tabs") or []
        if isinstance(row, dict)
    }
    tabs = settings.special_tabs
    tab_sets, per_tab = build_tab_analysis(
        tab_map,
        tabs,
        candidate_skus,
        trusted_skus,
    )
    union_special = set().union(*tab_sets.values()) if tab_sets else set()
    checks = build_checks(
        structure_path,
        candidate_path,
        manifest,
        source_path,
        tab_map,
        tab_sets,
        tabs,
        candidate_skus,
    )
    ready = all(checks.values())
    membership_count = sum(len(value) for value in tab_sets.values())
    result = {
        "schema_version": "aideal-hz24-tab-overlap-analysis/v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "structure_generated_at": structure.get("generated_at"),
        "structure_sha256": hashlib.sha256(raw).hexdigest() if raw else "",
        "structure_global_ok": structure.get("ok") is True,
        "structure_global_risk": structure.get("risk") or [],
        "ok": ready,
        "analysis_ready": ready,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "candidate_sku_count": len(candidate_skus),
        "trusted_source_sku_count": len(trusted_skus),
        "source_file": str(source_path),
        "special_tab_membership_count": membership_count,
        "special_tab_union_sku_count": len(union_special),
        "cross_tab_duplicate_membership_count": membership_count - len(union_special),
        "special_union_overlap_with_candidate_count": len(
            union_special & candidate_skus
        ),
        "special_union_increment_vs_candidate_count": len(
            union_special - candidate_skus
        ),
        "special_union_overlap_with_trusted_source_count": len(
            union_special & trusted_skus
        ),
        "special_union_promotion_link_required_count": len(
            union_special - trusted_skus
        ),
        "special_union_already_linked_not_candidate_count": len(
            (union_special & trusted_skus) - candidate_skus
        ),
        "special_union_increment_vs_candidate_samples": sorted(
            union_special - candidate_skus
        )[:50],
        "special_union_promotion_link_required_samples": sorted(
            union_special - trusted_skus
        )[:50],
        "per_tab": per_tab,
        "pairwise": pairwise_analysis(tabs, tab_sets),
        "recommended_next_step": recommended_step(
            ready,
            union_special,
            candidate_skus,
            trusted_skus,
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(report_path)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if ready else 1
