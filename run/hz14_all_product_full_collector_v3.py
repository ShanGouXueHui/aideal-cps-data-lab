#!/usr/bin/env python3
"""HZ14 all-product collector v3.

Fix over v2:
- v2 confirmed pagination and commercial row quality, but stopped the whole job after
  three consecutive RuntimeError('short_url_not_found') on one problematic SKU.
- v3 treats short_url_not_found as a per-SKU skip, records it in state.skipped_skus,
  closes any modal, resets fail_streak, and continues with the next product.

Scope remains unchanged:
- 商品推广 / 全部商品 only.
- Element UI pagination.
- Risk verification writes STOP_REQUIRED and stops; no bypass.
"""

from __future__ import annotations

import importlib.util
import random
import time
from pathlib import Path
from typing import Any, Dict, List

V2_PATH = Path("run/hz14_all_product_full_collector_v2.py")


def load_v2():
    if not V2_PATH.exists():
        raise RuntimeError(f"missing dependency: {V2_PATH}")
    spec = importlib.util.spec_from_file_location("hz14_v2", str(V2_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v2 = load_v2()
v1 = v2.v1
base = v1.base


def ensure_skip_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state = v2.ensure_state_compat(state)
    skipped = state.get("skipped_skus")
    if not isinstance(skipped, list):
        skipped = []
    dedup = []
    for sku in skipped:
        sku = str(sku or "").strip()
        if sku and sku not in dedup:
            dedup.append(sku)
    state["skipped_skus"] = dedup
    state["skipped_sku_count"] = len(dedup)
    return state


def mark_skip(state: Dict[str, Any], sku: str, reason: str) -> None:
    state = ensure_skip_state(state)
    sku = str(sku or "").strip()
    if sku and sku not in state["skipped_skus"]:
        state["skipped_skus"].append(sku)
    state["skipped_sku_count"] = len(state["skipped_skus"])
    state["last_skipped"] = {"sku": sku, "reason": reason, "page_no": state.get("current_page_no")}
    state["fail_streak"] = 0
    v1.save_state(state)


def collect_current_page_v3(page, state: Dict[str, Any], page_no: int) -> int:
    v1.check_risk(page, f"before_collect_page_{page_no}")
    state = ensure_skip_state(state)
    candidates = base.collect_page_candidates(page)
    seen = set(state.get("known_skus") or []) | set(state.get("skipped_skus") or [])
    fresh: List[Dict[str, Any]] = []
    fresh_skus = set()
    for cand in candidates:
        sku = str(cand.get("sku") or "").strip()
        title = str(cand.get("title") or "").strip()
        if sku.isdigit() and title and sku not in seen and sku not in fresh_skus:
            fresh.append(cand)
            fresh_skus.add(sku)
    v1.log("PAGE_CANDIDATES", page_no=page_no, total=len(candidates), fresh=len(fresh), skipped_sku_count=len(state.get("skipped_skus") or []), sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:60]} for x in fresh[:6]])

    processed = 0
    for order, cand in enumerate(fresh[:v1.ITEMS_PER_PAGE_LIMIT]):
        sku = str(cand.get("sku") or "").strip()
        v1.check_risk(page, f"before_collect_one_page_{page_no}")
        try:
            row = base.collect_one(page, cand, state, page_no, order)
            if not row:
                mark_skip(state, sku, "collect_one_returned_empty")
                v1.log("ITEM_SKIP", page_no=page_no, sku=sku, reason="collect_one_returned_empty")
                continue
            row["source_menu"] = "商品推广/全部商品"
            row["menu_mode"] = "hz14_all_product_full_v3"
            row["promotion_mode"] = "hz14_all_product_logged_in_onekey"
            row["run_id"] = v1.RUN_ID
            row["page_no"] = page_no
            v1.append_jsonl(v1.OUT, row)
            if sku and sku not in state["known_skus"]:
                state["known_skus"].append(sku)
            state["fail_streak"] = 0
            v1.save_state(state)
            processed += 1
            v1.write_report(state, {"last_page_no": page_no, "last_page_processed": processed})
            v1.log("ITEM_OK", page_no=page_no, sku=row.get("sku"), short_url=row.get("short_url"), known_sku_count=len(state["known_skus"]))
            time.sleep(random.uniform(v1.ITEM_SLEEP_MIN, v1.ITEM_SLEEP_MAX))
        except SystemExit:
            raise
        except Exception as exc:
            err = repr(exc)
            try:
                base.close_dialog(page)
            except Exception:
                pass
            v1.check_risk(page, f"after_item_exception_page_{page_no}")
            if "short_url_not_found" in err or "click_failed" in err:
                mark_skip(state, sku, err)
                v1.log("ITEM_SKIP", page_no=page_no, sku=sku, reason=err, skipped_sku_count=len(state.get("skipped_skus") or []))
                time.sleep(random.uniform(8, 18))
                continue
            state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
            v1.save_state(state)
            v1.log("ITEM_FAIL", page_no=page_no, sku=sku, err=err, fail_streak=state["fail_streak"])
            if state["fail_streak"] >= v1.MAX_FAIL_STREAK:
                v1.stop_required("max_fail_streak_reached", page_no=page_no, sku=sku, fail_streak=state["fail_streak"], last_error=err)
            time.sleep(random.uniform(20, 40))
    return processed


# Patch v1 globals used by main/run_cycle.
v1.collect_current_page = collect_current_page_v3

if __name__ == "__main__":
    v1.main()
