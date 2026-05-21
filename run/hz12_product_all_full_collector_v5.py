#!/usr/bin/env python3
"""HZ12 product_all v5 strict-title runner.

v4 proves UI pagination can advance, but smoke showed some records still have empty title.
For commercial-grade input, v5 enforces a strict title gate: product_all records without a
non-empty title are skipped and never written to JSONL. This prioritizes import quality over
maximum coverage. The same refresh/sleep/report behavior is inherited from v4.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

V4_PATH = Path("run/hz12_product_all_full_collector_v4.py")


def load_v4():
    if not V4_PATH.exists():
        raise RuntimeError(f"missing v4 runner: {V4_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_v4", str(V4_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v4 = load_v4()
base = v4.base
_original_collect_page_candidates = base.collect_page_candidates


def collect_page_candidates_strict_title(page) -> List[Dict[str, Any]]:
    rows = _original_collect_page_candidates(page)
    kept: List[Dict[str, Any]] = []
    skipped = []
    seen = set()
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        title = str(row.get("title") or "").strip()
        if not sku.isdigit():
            skipped.append({"sku": sku, "reason": "non_numeric", "title": title[:60]})
            continue
        if not title:
            skipped.append({"sku": sku, "reason": "missing_title", "title": ""})
            continue
        if sku in seen:
            skipped.append({"sku": sku, "reason": "duplicate", "title": title[:60]})
            continue
        seen.add(sku)
        kept.append(row)
    base.log(
        "STRICT_TITLE_CANDIDATES",
        total=len(rows),
        kept=len(kept),
        skipped=len(skipped),
        skipped_sample=skipped[:10],
        sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:80]} for x in kept[:8]],
    )
    return kept


base.collect_page_candidates = collect_page_candidates_strict_title


if __name__ == "__main__":
    base.main()
