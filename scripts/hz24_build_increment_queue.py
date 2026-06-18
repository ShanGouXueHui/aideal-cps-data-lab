#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

STRUCTURE = Path("reports/hz24_tab_pool_structure_special_verified_latest.json")
ANALYSIS = Path("reports/hz24_tab_overlap_analysis_latest.json")
BASE_MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
QUEUE = Path("data/export/hz24_special_tab_increment_latest.jsonl")
QUEUE_MANIFEST = Path("data/export/hz24_special_tab_increment_manifest.json")
REPORT = Path("reports/hz24_increment_queue_build_latest.json")
TABS = ["超补爆品", "限量高佣", "秒杀专区", "定向高佣", "粉丝爱买"]


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def trusted_source_skus(path: Path) -> set[str]:
    result: set[str] = set()
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict) or str(row.get("status") or "").lower() != "ok":
            continue
        url = str(row.get("short_url") or row.get("promotion_url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "u.jd.com":
            continue
        sku = str(row.get("sku") or row.get("jd_sku_id") or "").strip()
        if sku:
            result.add(sku)
    return result


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def main() -> int:
    structure_raw = STRUCTURE.read_bytes() if STRUCTURE.exists() else b""
    structure = load_json(STRUCTURE)
    analysis = load_json(ANALYSIS)
    base_manifest = load_json(BASE_MANIFEST)
    source_path = Path(str(base_manifest.get("source_file") or ""))
    trusted = trusted_source_skus(source_path)

    rows_by_tab = {
        str(row.get("tab_name") or ""): row
        for row in structure.get("tabs") or []
        if isinstance(row, dict)
    }
    sku_tabs: dict[str, set[str]] = {}
    for tab in TABS:
        for value in (rows_by_tab.get(tab) or {}).get("skus") or []:
            sku = str(value).strip()
            if sku:
                sku_tabs.setdefault(sku, set()).add(tab)

    pending = sorted(set(sku_tabs) - trusted)
    structure_sha256 = hashlib.sha256(structure_raw).hexdigest() if structure_raw else ""
    checks = {
        "structure_present": bool(structure),
        "analysis_ready": analysis.get("analysis_ready") is True,
        "all_tabs_present": all(tab in rows_by_tab for tab in TABS),
        "all_tabs_single_page_confirmed": all(
            (rows_by_tab.get(tab) or {}).get("single_page_confirmed") is True for tab in TABS
        ),
        "all_tabs_safe": all(
            (rows_by_tab.get(tab) or {}).get("ok") is True
            and not ((rows_by_tab.get(tab) or {}).get("risk") or [])
            for tab in TABS
        ),
        "trusted_source_present": source_path.exists(),
        "analysis_increment_matches": int(
            analysis.get("special_union_promotion_link_required_count") or -1
        ) == len(pending),
    }
    ready = all(checks.values())
    generated_at = datetime.now().isoformat(timespec="seconds")
    queue_rows = [
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
    queue_bytes = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in queue_rows
    ).encode("utf-8")
    queue_sha256 = hashlib.sha256(queue_bytes).hexdigest()

    if ready:
        atomic_write(QUEUE, queue_bytes)
        atomic_write(
            QUEUE_MANIFEST,
            json.dumps(
                {
                    "schema_version": "aideal-hz24-increment-manifest/v1",
                    "generated_at": generated_at,
                    "structure_file": str(STRUCTURE),
                    "structure_generated_at": structure.get("generated_at"),
                    "structure_sha256": structure_sha256,
                    "analysis_file": str(ANALYSIS),
                    "source_file": str(source_path),
                    "row_count": len(queue_rows),
                    "data_sha256": queue_sha256,
                    "source_tabs": TABS,
                    "commercial_enabled": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8"),
        )

    report = {
        "ok": ready,
        "generated_at": generated_at,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "structure_sha256": structure_sha256,
        "special_union_sku_count": len(sku_tabs),
        "trusted_source_sku_count": len(trusted),
        "queue_row_count": len(queue_rows),
        "queue_sha256": queue_sha256,
        "queue_file": str(QUEUE) if ready else None,
        "queue_manifest": str(QUEUE_MANIFEST) if ready else None,
    }
    atomic_write(
        REPORT,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
