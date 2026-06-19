from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .settings import HZ24Settings, load_settings

STRUCTURE_PATH = Path("reports/hz24_tab_pool_structure_special_verified_latest.json")
ANALYSIS_PATH = Path("reports/hz24_tab_overlap_analysis_latest.json")
BASE_MANIFEST_PATH = Path(
    "data/export/aideal_cps_products_commercial_candidate_manifest.json"
)
REPORT_PATH = Path("reports/hz24_increment_queue_build_latest.json")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def trusted_source_skus(path: Path, settings: HZ24Settings) -> set[str]:
    result: set[str] = set()
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict) or str(row.get("status") or "").lower() != "ok":
            continue
        value = str(row.get("short_url") or row.get("promotion_url") or "").strip()
        parsed = urlparse(value)
        if (
            parsed.scheme != settings.browser.trusted_link_scheme
            or parsed.hostname != settings.browser.trusted_link_host
        ):
            continue
        sku = str(row.get("sku") or row.get("jd_sku_id") or "").strip()
        if sku:
            result.add(sku)
    return result


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def index_sku_tabs(structure: dict, tabs: tuple[str, ...]) -> tuple[dict, dict]:
    rows_by_tab = {
        str(row.get("tab_name") or ""): row
        for row in structure.get("tabs") or []
        if isinstance(row, dict)
    }
    sku_tabs: dict[str, set[str]] = {}
    for tab in tabs:
        for value in (rows_by_tab.get(tab) or {}).get("skus") or []:
            sku = str(value).strip()
            if sku:
                sku_tabs.setdefault(sku, set()).add(tab)
    return rows_by_tab, sku_tabs


def build_checks(
    structure: dict,
    analysis: dict,
    rows_by_tab: dict,
    tabs: tuple[str, ...],
    source_path: Path,
    pending_count: int,
) -> dict[str, bool]:
    return {
        "structure_present": bool(structure),
        "analysis_ready": analysis.get("analysis_ready") is True,
        "all_tabs_present": all(tab in rows_by_tab for tab in tabs),
        "all_tabs_single_page_confirmed": all(
            (rows_by_tab.get(tab) or {}).get("single_page_confirmed") is True
            for tab in tabs
        ),
        "all_tabs_safe": all(
            (rows_by_tab.get(tab) or {}).get("ok") is True
            and not ((rows_by_tab.get(tab) or {}).get("risk") or [])
            for tab in tabs
        ),
        "trusted_source_present": source_path.exists(),
        "analysis_increment_matches": int(
            analysis.get("special_union_promotion_link_required_count") or -1
        )
        == pending_count,
    }


def queue_rows(
    pending: list[str],
    sku_tabs: dict[str, set[str]],
    structure: dict,
    structure_sha256: str,
) -> list[dict]:
    return [
        {
            "schema_version": "aideal-hz24-increment-sku/v1",
            "sku": sku,
            "source_tabs": sorted(sku_tabs[sku]),
            "status": "pending_link",
            "structure_generated_at": structure.get("generated_at"),
            "structure_sha256": structure_sha256,
        }
        for sku in pending
    ]


def run_queue_builder(settings: HZ24Settings | None = None) -> int:
    settings = settings or load_settings()
    structure_path = settings.root / STRUCTURE_PATH
    analysis_path = settings.root / ANALYSIS_PATH
    base_manifest_path = settings.root / BASE_MANIFEST_PATH
    report_path = settings.root / REPORT_PATH
    structure_raw = structure_path.read_bytes() if structure_path.exists() else b""
    structure = load_json(structure_path)
    analysis = load_json(analysis_path)
    base_manifest = load_json(base_manifest_path)
    source_path = settings.root / str(base_manifest.get("source_file") or "")
    trusted = trusted_source_skus(source_path, settings)
    tabs = settings.special_tabs
    rows_by_tab, sku_tabs = index_sku_tabs(structure, tabs)
    pending = sorted(set(sku_tabs) - trusted)
    structure_sha = hashlib.sha256(structure_raw).hexdigest() if structure_raw else ""
    checks = build_checks(
        structure,
        analysis,
        rows_by_tab,
        tabs,
        source_path,
        len(pending),
    )
    ready = all(checks.values())
    generated_at = datetime.now().isoformat(timespec="seconds")
    rows = queue_rows(pending, sku_tabs, structure, structure_sha)
    queue_data = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    ).encode("utf-8")
    queue_sha = hashlib.sha256(queue_data).hexdigest()
    if ready:
        atomic_write(settings.contracts.queue_file, queue_data)
        manifest = {
            "schema_version": "aideal-hz24-increment-manifest/v1",
            "generated_at": generated_at,
            "structure_file": str(structure_path),
            "structure_generated_at": structure.get("generated_at"),
            "structure_sha256": structure_sha,
            "analysis_file": str(analysis_path),
            "source_file": str(source_path),
            "row_count": len(rows),
            "data_sha256": queue_sha,
            "source_tabs": list(tabs),
            "commercial_enabled": False,
        }
        atomic_write(
            settings.contracts.queue_manifest_file,
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode(),
        )
    report = {
        "ok": ready,
        "generated_at": generated_at,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "structure_sha256": structure_sha,
        "special_union_sku_count": len(sku_tabs),
        "trusted_source_sku_count": len(trusted),
        "queue_row_count": len(rows),
        "queue_sha256": queue_sha,
        "queue_file": str(settings.contracts.queue_file) if ready else None,
        "queue_manifest": str(settings.contracts.queue_manifest_file) if ready else None,
    }
    atomic_write(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode(),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if ready else 1
