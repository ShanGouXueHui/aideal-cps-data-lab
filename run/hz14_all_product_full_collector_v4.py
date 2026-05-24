#!/usr/bin/env python3
"""HZ14 all-product collector v4.

Fix over v3:
- Previous restarts created a new per-run OUT file and copied it to latest on the
  first new row, making latest represent only the current run. v4 bootstraps the
  new OUT from all historical HZ14/HZ12 all-product JSONL files before collecting.
- Keeps v3 behavior: skip single bad SKUs on short_url_not_found/click_failed.

Scope:
- 商品推广 / 全部商品 only.
- Element UI pagination.
- Risk verification writes STOP_REQUIRED and stops; no bypass.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

V3_PATH = Path("run/hz14_all_product_full_collector_v3.py")


def load_v3():
    if not V3_PATH.exists():
        raise RuntimeError(f"missing dependency: {V3_PATH}")
    spec = importlib.util.spec_from_file_location("hz14_v3", str(V3_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v3 = load_v3()
v1 = v3.v1


def parse_dt(value: Any) -> datetime:
    s = str(value or "").strip()
    for fmt in (None, "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
        except Exception:
            pass
    return datetime.min


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists() or path.is_dir():
        return []
    rows: List[Dict[str, Any]] = []
    target = path.resolve() if path.is_symlink() else path
    try:
        for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows


def historical_paths() -> List[Path]:
    pats = [
        "data/import/hz_jd_union_all_product_full_links_*.jsonl",
        "data/import/hz_jd_union_all_product_full_links_latest.jsonl",
        "data/import/hz_jd_union_product_all_full_links_*.jsonl",
        "data/import/hz_jd_union_product_all_full_links_latest.jsonl",
    ]
    paths: List[Path] = []
    for pat in pats:
        for p in Path(".").glob(pat):
            if p not in paths:
                paths.append(p)
    # Read older files first; latest/current later can override by timestamp.
    return sorted(paths, key=lambda p: str(p))


def merge_existing_rows() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    by_sku: Dict[str, Dict[str, Any]] = {}
    chosen_dt: Dict[str, datetime] = {}
    raw_ok = 0
    sources: Dict[str, int] = {}
    for path in historical_paths():
        rows = list(iter_jsonl(path))
        sources[str(path)] = len(rows)
        for row in rows:
            if row.get("status") != "ok" or not row.get("short_url"):
                continue
            sku = str(row.get("sku") or "").strip()
            if not sku or not sku.isdigit():
                continue
            raw_ok += 1
            dt = parse_dt(row.get("link_created_at") or row.get("ts"))
            if sku not in by_sku or dt >= chosen_dt.get(sku, datetime.min):
                row.setdefault("source_menu", "商品推广/全部商品")
                row.setdefault("menu_mode", "hz14_all_product_full_merged")
                by_sku[sku] = row
                chosen_dt[sku] = dt
    merged = sorted(by_sku.values(), key=lambda r: (int(r.get("page_no") or 9999), str(r.get("sku") or "")))
    summary = {"sources": sources, "raw_ok": raw_ok, "merged_dedup_sku": len(merged)}
    return merged, summary


def bootstrap_out_from_history() -> None:
    merged, summary = merge_existing_rows()
    v1.OUT.parent.mkdir(parents=True, exist_ok=True)
    with v1.OUT.open("w", encoding="utf-8") as f:
        for row in merged:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    shutil.copyfile(v1.OUT, v1.LATEST)
    shutil.copyfile(v1.OUT, v1.HZ12_COMPAT_LATEST)
    v1.log("HZ14_V4_BOOTSTRAP_MERGE", out=str(v1.OUT), latest=str(v1.LATEST), **summary)


if __name__ == "__main__":
    bootstrap_out_from_history()
    v1.main()
