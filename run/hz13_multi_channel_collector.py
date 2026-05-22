#!/usr/bin/env python3
"""HZ13 multi-channel JD Union product collector.

Rationale:
- HZ12 proved link creation and field quality, but a single product_all path plateaus.
- HZ13 expands the pool by cycling validated tabs/channels:
  全部商品 / 超级补贴 / 限量高佣 / 秒杀专区 / 定向高佣 / 粉丝爱买.
- Commercial quality remains strict: only numeric SKU with non-empty title is collected.
- Promotion links are collected by visible one-key link buttons through the existing HZ12 base flow.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

V8_PATH = Path("run/hz12_product_all_full_collector_v8.py")


def load_v8():
    if not V8_PATH.exists():
        raise RuntimeError(f"missing v8 runner: {V8_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_v8", str(V8_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v8 = load_v8()
base = v8.base

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
WORKER = os.environ.get("HZ13_WORKER_NAME", "hz13_multi_channel")
TARGET_TOTAL = int(os.environ.get("HZ13_TARGET_TOTAL", os.environ.get("HZ12_TARGET_TOTAL", "4000")))
RUN_ONCE = os.environ.get("HZ13_RUN_ONCE", os.environ.get("HZ12_RUN_ONCE", "false")).lower() in {"1", "true", "yes"}
CHANNELS = [x.strip() for x in os.environ.get("HZ13_CHANNELS", "全部商品,超级补贴,限量高佣,秒杀专区,定向高佣,粉丝爱买").split(",") if x.strip()]
CHANNEL_PAGE_MAX = int(os.environ.get("HZ13_CHANNEL_PAGE_MAX", "12"))
CHANNEL_STALE_LIMIT = int(os.environ.get("HZ13_CHANNEL_STALE_LIMIT", "3"))
ITEM_SLEEP_MIN = float(os.environ.get("HZ13_ITEM_SLEEP_MIN", os.environ.get("HZ12_ITEM_SLEEP_MIN", "4")))
ITEM_SLEEP_MAX = float(os.environ.get("HZ13_ITEM_SLEEP_MAX", os.environ.get("HZ12_ITEM_SLEEP_MAX", "8")))
PAGE_SLEEP_MIN = float(os.environ.get("HZ13_PAGE_SLEEP_MIN", os.environ.get("HZ12_PAGE_SLEEP_MIN", "2")))
PAGE_SLEEP_MAX = float(os.environ.get("HZ13_PAGE_SLEEP_MAX", os.environ.get("HZ12_PAGE_SLEEP_MAX", "4")))
REFRESH_AFTER_DAYS = int(os.environ.get("HZ13_REFRESH_AFTER_DAYS", os.environ.get("HZ12_REFRESH_AFTER_DAYS", "40")))
CYCLE_SLEEP = float(os.environ.get("HZ13_CYCLE_SLEEP", "3600"))

STATE_PATH = Path("run/hz13_multi_channel_state.json")
STOP_PATH = Path("run/hz13_STOP_REQUIRED.json")
OUT = Path(f"data/import/hz_jd_union_multi_channel_links_{RUN_ID}.jsonl")
LATEST = Path("data/import/hz_jd_union_multi_channel_links_latest.jsonl")
REPORT = Path(f"run/hz13_multi_channel_report_{RUN_ID}.json")
LATEST_REPORT = Path("run/hz13_multi_channel_report_latest.json")
# Keep HZ12 product_all latest aligned for downstream check scripts.
HZ12_COMPAT_LATEST = Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl")


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(event: str, **kwargs: Any) -> None:
    payload = {"ts": now(), "worker": WORKER, "event": event}
    payload.update(kwargs)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    target = path.resolve() if path.is_symlink() else path
    for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    shutil.copyfile(path, LATEST)
    shutil.copyfile(path, HZ12_COMPAT_LATEST)


def existing_known_skus() -> List[str]:
    known: List[str] = []
    for p in [LATEST, HZ12_COMPAT_LATEST]:
        for row in read_jsonl(p):
            if row.get("status") != "ok" or not row.get("short_url"):
                continue
            sku = str(row.get("sku") or "").strip()
            if sku and sku not in known:
                known.append(sku)
    return known


def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            state = {}
    else:
        state = {}
    state.setdefault("run_id", RUN_ID)
    state.setdefault("created_at", now())
    state.setdefault("known_skus", existing_known_skus())
    state.setdefault("round_seen_skus", [])
    state.setdefault("fail_streak", 0)
    state.setdefault("target_total", TARGET_TOTAL)
    state.setdefault("current_channel", None)
    state.setdefault("current_channel_index", 0)
    state.setdefault("current_page_no", 1)
    state.setdefault("refresh_round", 0)
    state["known_sku_count"] = len(state.get("known_skus") or [])
    state["updated_at"] = now()
    return state


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = now()
    state["known_sku_count"] = len(state.get("known_skus") or [])
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def stop_required(reason: str, **kwargs: Any) -> None:
    payload = {"ts": now(), "reason": reason}
    payload.update(kwargs)
    STOP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    log("STOP_REQUIRED", **payload)
    raise SystemExit(2)


def write_report(state: Dict[str, Any], extra: Dict[str, Any] | None = None) -> None:
    rows = read_jsonl(LATEST)
    ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
    dedup = sorted({str(x.get("sku") or "") for x in ok if x.get("sku")})
    pages = sorted({int(x.get("page_no")) for x in ok if str(x.get("page_no") or "").isdigit()})
    channels: Dict[str, int] = {}
    for x in ok:
        c = str(x.get("channel") or x.get("menu_mode") or "unknown")
        channels[c] = channels.get(c, 0) + 1
    missing = {
        "title": sum(1 for x in ok if not x.get("title")),
        "image_url": sum(1 for x in ok if not x.get("image_url")),
        "item_url": sum(1 for x in ok if not x.get("item_url")),
        "price": sum(1 for x in ok if not x.get("price")),
        "commission_rate": sum(1 for x in ok if not x.get("commission_rate")),
        "estimated_income": sum(1 for x in ok if not x.get("estimated_income")),
        "short_url": sum(1 for x in ok if not x.get("short_url")),
        "long_url": sum(1 for x in ok if not x.get("long_url")),
        "qr_url": sum(1 for x in ok if not x.get("qr_url")),
        "jd_command": sum(1 for x in ok if not x.get("jd_command")),
        "refresh_due_at": sum(1 for x in ok if not x.get("refresh_due_at")),
    }
    report = {
        "ts": now(),
        "run_id": RUN_ID,
        "worker": WORKER,
        "out": str(OUT),
        "latest": str(LATEST),
        "hz12_compat_latest": str(HZ12_COMPAT_LATEST),
        "target_total": TARGET_TOTAL,
        "rows": len(rows),
        "ok_rows": len(ok),
        "dedup_sku": len(dedup),
        "progress_pct": round(len(dedup) / TARGET_TOTAL * 100, 2) if TARGET_TOTAL else None,
        "channels": channels,
        "page_count": len(pages),
        "missing": missing,
        "state": state,
    }
    if extra:
        report.update(extra)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    shutil.copyfile(REPORT, LATEST_REPORT)


def get_active_page(browser):
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    for page in reversed(pages):
        if "union.jd.com" in (page.url or ""):
            return page
    if pages:
        return pages[-1]
    raise RuntimeError("no_page")


def click_channel(page, channel: str) -> Dict[str, Any]:
    # Always start from product manager page to reset SPA state.
    page.goto(base.URL_TEMPLATE.format(page_no=1), wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)
    before = v8.current_page_skus(page)[:10]
    result: Dict[str, Any] = {"channel": channel, "ok": False, "count": 0}
    try:
        loc = page.get_by_text(channel, exact=True)
        count = loc.count()
        result["count"] = count
        if count <= 0:
            result.update({"ok": False, "reason": "channel_text_not_found"})
            return result
        loc.first.click(timeout=8000)
        page.wait_for_timeout(4000)
        after = v8.current_page_skus(page)[:10]
        result.update({"ok": True, "changed": bool(after and after != before), "before_skus": before[:5], "after_skus": after[:5]})
        return result
    except Exception as exc:
        result.update({"ok": False, "reason": "click_exception", "err": repr(exc)})
        return result


def collect_page(page, state: Dict[str, Any], channel: str, page_no: int) -> int:
    info = base.check_page(page)
    total_hint = base.extract_page_total(page)
    candidates = base.collect_page_candidates(page)
    seen = set(state.get("known_skus") or [])
    fresh: List[Dict[str, Any]] = []
    fresh_skus = set()
    for cand in candidates:
        sku = str(cand.get("sku") or "").strip()
        title = str(cand.get("title") or "").strip()
        if sku.isdigit() and title and sku not in seen and sku not in fresh_skus:
            fresh.append(cand)
            fresh_skus.add(sku)
    log("PAGE_CANDIDATES", channel=channel, page_no=page_no, total=len(candidates), fresh=len(fresh), page_info=info, total_hint=total_hint, sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:60]} for x in fresh[:6]])

    processed = 0
    for order, cand in enumerate(fresh[:base.ITEMS_PER_PAGE_LIMIT]):
        try:
            row = base.collect_one(page, cand, state, page_no, order)
            if row:
                row["channel"] = channel
                row["menu_mode"] = "hz13_multi_channel"
                row["promotion_mode"] = "hz13_multi_channel_logged_in_onekey"
                row["run_id"] = RUN_ID
                # Re-append enriched row to HZ13 output. base.collect_one also appends to its own OUT;
                # HZ13 latest is the authoritative multi-channel export.
                append_jsonl(OUT, row)
                sku = str(row.get("sku") or "").strip()
                if sku and sku not in state["known_skus"]:
                    state["known_skus"].append(sku)
                state["fail_streak"] = 0
                save_state(state)
                processed += 1
                write_report(state, {"last_channel": channel, "last_page_no": page_no, "last_cycle_processed": processed})
                log("ITEM_OK", channel=channel, page_no=page_no, sku=row.get("sku"), short_url=row.get("short_url"), known_sku_count=len(state["known_skus"]))
            time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
        except Exception as exc:
            state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
            save_state(state)
            log("ITEM_FAIL", channel=channel, page_no=page_no, sku=cand.get("sku"), err=repr(exc), fail_streak=state["fail_streak"])
            try:
                base.close_dialog(page)
            except Exception:
                pass
            if state["fail_streak"] >= base.MAX_FAIL_STREAK:
                stop_required("max_fail_streak_reached", channel=channel, page_no=page_no, sku=cand.get("sku"), fail_streak=state["fail_streak"], last_error=repr(exc))
            time.sleep(random.uniform(20, 40))
    return processed


def collect_channel(page, state: Dict[str, Any], channel: str) -> int:
    click_res = click_channel(page, channel)
    log("CHANNEL_OPEN", channel=channel, result=click_res)
    if not click_res.get("ok"):
        return 0

    channel_processed = 0
    stale = 0
    for page_no in range(1, CHANNEL_PAGE_MAX + 1):
        state["current_channel"] = channel
        state["current_page_no"] = page_no
        save_state(state)
        processed = collect_page(page, state, channel, page_no)
        channel_processed += processed
        if len(state.get("known_skus") or []) >= TARGET_TOTAL:
            log("TARGET_TOTAL_REACHED", known_sku_count=len(state["known_skus"]), target_total=TARGET_TOTAL)
            return channel_processed
        next_res = v8.click_next_by_reposition(page, state)
        log("CHANNEL_NEXT", channel=channel, page_no=page_no, result=next_res)
        write_report(state, {"last_channel": channel, "last_page_no": page_no, "last_channel_next": next_res, "channel_processed": channel_processed})
        if next_res.get("ok") and next_res.get("changed"):
            stale = 0
            time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
            continue
        stale += 1
        if stale >= CHANNEL_STALE_LIMIT:
            log("CHANNEL_STALE_LIMIT", channel=channel, page_no=page_no, stale=stale)
            break
        time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
    return channel_processed


def main() -> None:
    if STOP_PATH.exists():
        stop_required("existing_stop_file_present")
    log("HZ13_MULTI_CHANNEL_START", target_total=TARGET_TOTAL, channels=CHANNELS, channel_page_max=CHANNEL_PAGE_MAX, run_once=RUN_ONCE)
    with v8.v7.v5.base.sync_playwright() as p:  # type: ignore[attr-defined]
        # Fallback because sync_playwright is not exposed on base in some versions.
        pass


# Avoid relying on base internals for Playwright import.
from playwright.sync_api import sync_playwright


def run() -> None:
    if STOP_PATH.exists():
        stop_required("existing_stop_file_present")
    log("HZ13_MULTI_CHANNEL_START", target_total=TARGET_TOTAL, channels=CHANNELS, channel_page_max=CHANNEL_PAGE_MAX, run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = get_active_page(browser)
        page.set_default_timeout(15000)
        while True:
            state = load_state()
            if len(state.get("known_skus") or []) >= TARGET_TOTAL:
                state["last_full_cycle_finished_at"] = now()
                state["next_refresh_due_at"] = (datetime.now() + timedelta(days=REFRESH_AFTER_DAYS)).isoformat(timespec="seconds")
                save_state(state)
                write_report(state, {"sleep_reason": "target_total_reached"})
                log("SLEEP_TARGET_TOTAL", known_sku_count=len(state["known_skus"]), target_total=TARGET_TOTAL)
                if RUN_ONCE:
                    break
                time.sleep(CYCLE_SLEEP)
                continue
            total_processed = 0
            for channel in CHANNELS:
                state = load_state()
                if len(state.get("known_skus") or []) >= TARGET_TOTAL:
                    break
                n = collect_channel(page, state, channel)
                total_processed += n
                write_report(load_state(), {"last_channel": channel, "channel_processed": n, "cycle_processed": total_processed})
                time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
            state = load_state()
            state["last_full_cycle_finished_at"] = now()
            state["next_refresh_due_at"] = (datetime.now() + timedelta(days=REFRESH_AFTER_DAYS)).isoformat(timespec="seconds")
            save_state(state)
            write_report(state, {"cycle_finished": True, "cycle_processed": total_processed})
            log("CYCLE_DONE", processed=total_processed, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(CYCLE_SLEEP)


if __name__ == "__main__":
    run()
