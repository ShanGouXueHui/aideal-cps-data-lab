#!/usr/bin/env python3
"""HZ14 all-product collector v2.

Fix over v1:
- HZ14 v1 reused the HZ12 collect_one helper, which expects HZ12-style
  state keys such as round_seen_skus. v1 did not initialize those keys,
  causing KeyError('round_seen_skus') before rows could be written.
- v2 monkey-patches HZ14 v1 load_state/save_state to always maintain the
  compatibility keys required by HZ12 helpers.

Scope remains unchanged:
- 商品推广 / 全部商品 only.
- Element UI paginator.
- Risk verification writes STOP_REQUIRED and stops; no bypass.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

V1_PATH = Path("run/hz14_all_product_full_collector.py")


def load_v1():
    if not V1_PATH.exists():
        raise RuntimeError(f"missing dependency: {V1_PATH}")
    spec = importlib.util.spec_from_file_location("hz14_v1", str(V1_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v1 = load_v1()
_orig_load_state = v1.load_state
_orig_save_state = v1.save_state


def ensure_state_compat(s: Dict[str, Any]) -> Dict[str, Any]:
    known = s.get("known_skus") or []
    if not isinstance(known, list):
        known = list(known)
    # Deduplicate while preserving order.
    dedup_known = []
    for sku in known:
        sku = str(sku or "").strip()
        if sku and sku not in dedup_known:
            dedup_known.append(sku)
    s["known_skus"] = dedup_known
    s["known_sku_count"] = len(dedup_known)

    round_seen = s.get("round_seen_skus")
    if not isinstance(round_seen, list):
        # The HZ12 helper appends to round_seen_skus during collect_one.
        # Initializing from known_skus prevents duplicate work inside a cycle.
        round_seen = dedup_known[:]
    s["round_seen_skus"] = round_seen
    s["round_seen_sku_count"] = len(round_seen)

    # HZ12 helper/reporting code expects these soft state fields to exist.
    s.setdefault("seen_skus", dedup_known[:])
    s.setdefault("seen_short_urls", [])
    s.setdefault("fail_streak", 0)
    s.setdefault("refresh_round", 0)
    s.setdefault("current_page_no", 1)
    s.setdefault("pages_done", [])
    return s


def load_state_v2() -> Dict[str, Any]:
    return ensure_state_compat(_orig_load_state())


def save_state_v2(s: Dict[str, Any]) -> None:
    return _orig_save_state(ensure_state_compat(s))


v1.load_state = load_state_v2
v1.save_state = save_state_v2

# Patch module-level functions which reference save_state/load_state through v1 globals.
# Python global lookups are dynamic, so assigning here is sufficient.

if __name__ == "__main__":
    v1.main()
