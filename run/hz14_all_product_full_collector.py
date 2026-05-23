#!/usr/bin/env python3
"""HZ14 commercial all-product collector for JD Union.

Scope:
- Only 商品推广 / 全部商品.
- Pagination uses Element UI paginator DOM: .el-pagination .el-pager li / button.btn-next.
- Low-frequency page turning to reduce JD risk verification triggers.
- Risk page is never bypassed. It writes STOP_REQUIRED and stops.
- Strict commercial quality: numeric SKU + title + short_url and core promotion fields.
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
from typing import Any, Dict, List, Optional, Tuple

V8_PATH = Path("run/hz12_product_all_full_collector_v8.py")


def load_v8():
    if not V8_PATH.exists():
        raise RuntimeError(f"missing dependency: {V8_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_v8", str(V8_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v8 = load_v8()
base = v8.base

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
WORKER = os.environ.get("HZ14_WORKER_NAME", "hz14_all_product_full")
TARGET_TOTAL = int(os.environ.get("HZ14_TARGET_TOTAL", "4000"))
PAGE_START = int(os.environ.get("HZ14_PAGE_START", "1"))
PAGE_MAX = int(os.environ.get("HZ14_PAGE_MAX", "67"))
RUN_ONCE = os.environ.get("HZ14_RUN_ONCE", "false").lower() in {"1", "true", "yes"}
ITEMS_PER_PAGE_LIMIT = int(os.environ.get("HZ14_ITEMS_PER_PAGE_LIMIT", "60"))
ITEM_SLEEP_MIN = float(os.environ.get("HZ14_ITEM_SLEEP_MIN", "5"))
ITEM_SLEEP_MAX = float(os.environ.get("HZ14_ITEM_SLEEP_MAX", "10"))
PAGE_SLEEP_MIN = float(os.environ.get("HZ14_PAGE_SLEEP_MIN", "55"))
PAGE_SLEEP_MAX = float(os.environ.get("HZ14_PAGE_SLEEP_MAX", "95"))
CYCLE_SLEEP = float(os.environ.get("HZ14_CYCLE_SLEEP", "3600"))
REFRESH_AFTER_DAYS = int(os.environ.get("HZ14_REFRESH_AFTER_DAYS", "40"))
MAX_FAIL_STREAK = int(os.environ.get("HZ14_MAX_FAIL_STREAK", "3"))

STATE_PATH = Path("run/hz14_all_product_full_state.json")
STOP_PATH = Path("run/hz14_STOP_REQUIRED.json")
OUT = Path(f"data/import/hz_jd_union_all_product_full_links_{RUN_ID}.jsonl")
LATEST = Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl")
# Compatibility path for existing downstream scripts/checkers.
HZ12_COMPAT_LATEST = Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl")
REPORT = Path(f"run/hz14_all_product_full_report_{RUN_ID}.json")
LATEST_REPORT = Path("run/hz14_all_product_full_report_latest.json")

RISK_MARKERS = ["快速验证", "购物无忧", "安全验证", "验证码", "滑块", "risk_handler", "风险"]


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
    for p in (LATEST, HZ12_COMPAT_LATEST):
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
            s = json.loads(STATE_PATH.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            s = {}
    else:
        s = {}
    s.setdefault("run_id", RUN_ID)
    s.setdefault("created_at", now())
    s.setdefault("known_skus", existing_known_skus())
    s.setdefault("target_total", TARGET_TOTAL)
    s.setdefault("current_page_no", PAGE_START)
    s.setdefault("fail_streak", 0)
    s.setdefault("refresh_round", 0)
    s.setdefault("pages_done", [])
    s["known_sku_count"] = len(s.get("known_skus") or [])
    s["updated_at"] = now()
    return s


def save_state(s: Dict[str, Any]) -> None:
    s["updated_at"] = now()
    s["known_sku_count"] = len(s.get("known_skus") or [])
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def stop_required(reason: str, **kwargs: Any) -> None:
    payload = {"ts": now(), "reason": reason}
    payload.update(kwargs)
    STOP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    log("STOP_REQUIRED", **payload)
    raise SystemExit(2)


def page_text(page) -> str:
    try:
        return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception:
        return ""


def risk_info(page) -> List[str]:
    txt = page_text(page)
    url = page.url or ""
    return [x for x in RISK_MARKERS if x in txt or x in url]


def check_risk(page, context: str) -> None:
    risk = risk_info(page)
    if risk:
        stop_required("jd_risk_verification_required", context=context, url=page.url, risk=risk)


def get_page_info(page) -> Dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const txt = document.body ? (document.body.innerText || '') : '';
          const skus = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const m = (a.href || '').match(/\/(\d{5,})\.html/);
            if (m && !skus.includes(m[1])) skus.push(m[1]);
          }
          const pager = document.querySelector('.el-pagination');
          const active = pager ? Array.from(pager.querySelectorAll('.el-pager li')).find(el => String(el.className || '').includes('active')) : null;
          const buttons = pager ? Array.from(pager.querySelectorAll('button')).map(el => ({cls:String(el.className || ''), disabled:!!el.disabled || el.getAttribute('disabled') !== null})) : [];
          return {
            url: location.href,
            oneKeyCount: (txt.match(/一键领链/g) || []).length,
            skuCount: skus.length,
            skus: skus.slice(0, 100),
            has4000: txt.includes('共 4000 条') || txt.includes('共4000条'),
            hasEmpty: txt.includes('抱歉，没有找到相关商品'),
            pagerText: pager ? (pager.innerText || pager.textContent || '').replace(/\s+/g, ' ').trim() : '',
            activePageText: active ? (active.innerText || active.textContent || '').replace(/\s+/g, '').trim() : null,
            buttons,
            risk: ['快速验证','购物无忧','风险','安全验证','验证码','滑块','risk_handler'].filter(x => txt.includes(x) || location.href.includes(x))
          };
        }
        """
    )


def write_report(state: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> None:
    rows = read_jsonl(LATEST)
    ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
    dedup = sorted({str(x.get("sku") or "").strip() for x in ok if x.get("sku")})
    pages = sorted({int(x.get("page_no")) for x in ok if str(x.get("page_no") or "").isdigit()})
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
    report: Dict[str, Any] = {
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
        "page_count": len(pages),
        "pages": pages,
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
        if "union.jd.com" in (page.url or "") or "jd.com" in (page.url or ""):
            return page
    if pages:
        return pages[-1]
    raise RuntimeError("no_page")


def click_product_all(page) -> Dict[str, Any]:
    try:
        loc = page.get_by_text("全部商品", exact=True)
        count = loc.count()
        if count <= 0:
            return {"ok": False, "reason": "not_found"}
        loc.nth(count - 1).click(timeout=8000)
        return {"ok": True, "count": count}
    except Exception as exc:
        return {"ok": False, "reason": "exception", "err": repr(exc)}


def reset_product_all(page) -> Dict[str, Any]:
    page.goto("https://union.jd.com/proManager/index?pageNo=1", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    check_risk(page, "after_goto_product_manager")
    click_res = click_product_all(page)
    page.wait_for_timeout(6000)
    check_risk(page, "after_click_product_all")
    page.evaluate("""() => { document.body.style.zoom='80%'; const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
    page.wait_for_timeout(1200)
    info = get_page_info(page)
    return {"click_product_all": click_res, "page_info": info}


def collect_current_page(page, state: Dict[str, Any], page_no: int) -> int:
    check_risk(page, f"before_collect_page_{page_no}")
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
    log("PAGE_CANDIDATES", page_no=page_no, total=len(candidates), fresh=len(fresh), sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:60]} for x in fresh[:6]])

    processed = 0
    for order, cand in enumerate(fresh[:ITEMS_PER_PAGE_LIMIT]):
        check_risk(page, f"before_collect_one_page_{page_no}")
        try:
            # base.collect_one validates/clicks 一键领链 and parses modal.
            row = base.collect_one(page, cand, state, page_no, order)
            if not row:
                continue
            row["source_menu"] = "商品推广/全部商品"
            row["menu_mode"] = "hz14_all_product_full"
            row["promotion_mode"] = "hz14_all_product_logged_in_onekey"
            row["run_id"] = RUN_ID
            row["page_no"] = page_no
            append_jsonl(OUT, row)
            sku = str(row.get("sku") or "").strip()
            if sku and sku not in state["known_skus"]:
                state["known_skus"].append(sku)
            state["fail_streak"] = 0
            save_state(state)
            processed += 1
            write_report(state, {"last_page_no": page_no, "last_page_processed": processed})
            log("ITEM_OK", page_no=page_no, sku=row.get("sku"), short_url=row.get("short_url"), known_sku_count=len(state["known_skus"]))
            time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
        except SystemExit:
            raise
        except Exception as exc:
            state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
            save_state(state)
            log("ITEM_FAIL", page_no=page_no, sku=cand.get("sku"), err=repr(exc), fail_streak=state["fail_streak"])
            try:
                base.close_dialog(page)
            except Exception:
                pass
            check_risk(page, f"after_item_fail_page_{page_no}")
            if state["fail_streak"] >= MAX_FAIL_STREAK:
                stop_required("max_fail_streak_reached", page_no=page_no, sku=cand.get("sku"), fail_streak=state["fail_streak"], last_error=repr(exc))
            time.sleep(random.uniform(20, 40))
    return processed


def active_page_number(page) -> Optional[int]:
    info = get_page_info(page)
    raw = info.get("activePageText")
    if raw and str(raw).isdigit():
        return int(raw)
    return None


def go_next_page(page, state: Dict[str, Any], current_page_no: int) -> Dict[str, Any]:
    check_risk(page, f"before_next_page_{current_page_no}")
    before_info = get_page_info(page)
    before_skus = before_info.get("skus") or []
    try:
        page.evaluate("""() => { const p=document.querySelector('.el-pagination'); if (p) p.scrollIntoView({block:'center'}); else window.scrollTo(0, document.body.scrollHeight); }""")
        page.wait_for_timeout(800)
        btn = page.locator(".el-pagination button.btn-next").first
        btn.scroll_into_view_if_needed(timeout=5000)
        btn.click(timeout=8000)
    except Exception as exc:
        result = {"ok": False, "changed": False, "reason": "btn_next_click_exception", "err": repr(exc), "before": before_info}
        log("PAGE_NEXT", page_no=current_page_no, result=result)
        return result

    after_info: Dict[str, Any] = {}
    changed = False
    risk: List[str] = []
    for _ in range(60):
        page.wait_for_timeout(1000)
        risk = risk_info(page)
        if risk:
            stop_required("jd_risk_verification_required", context=f"after_next_page_{current_page_no}", url=page.url, risk=risk)
        after_info = get_page_info(page)
        after_skus = after_info.get("skus") or []
        if after_skus and after_skus[:40] != before_skus[:40]:
            changed = True
            break
    result = {"ok": True, "changed": changed, "from_page_no": current_page_no, "active_page_no": after_info.get("activePageText"), "before_skus": before_skus[:8], "after_skus": (after_info.get("skus") or [])[:8], "before_url": before_info.get("url"), "after_url": after_info.get("url")}
    log("PAGE_NEXT", page_no=current_page_no, result=result)
    return result


def run_cycle(page, state: Dict[str, Any]) -> int:
    reset = reset_product_all(page)
    log("PRODUCT_ALL_RESET", result=reset)
    if reset.get("page_info", {}).get("risk"):
        stop_required("jd_risk_verification_required", context="reset_product_all", url=page.url, risk=reset["page_info"].get("risk"))
    processed_total = 0
    page_no = 1
    while page_no <= PAGE_MAX:
        state["current_page_no"] = page_no
        save_state(state)
        processed = collect_current_page(page, state, page_no)
        processed_total += processed
        pages_done = state.setdefault("pages_done", [])
        if page_no not in pages_done:
            pages_done.append(page_no)
        save_state(state)
        write_report(state, {"last_page_no": page_no, "last_page_processed": processed, "cycle_processed": processed_total})
        if len(state.get("known_skus") or []) >= TARGET_TOTAL:
            log("TARGET_TOTAL_REACHED", known_sku_count=len(state["known_skus"]), target_total=TARGET_TOTAL)
            break
        if page_no >= PAGE_MAX:
            break
        sleep_s = random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX)
        log("PAGE_SLEEP", page_no=page_no, seconds=round(sleep_s, 2))
        time.sleep(sleep_s)
        next_res = go_next_page(page, state, page_no)
        if not next_res.get("ok") or not next_res.get("changed"):
            stop_required("page_next_failed_or_unchanged", page_no=page_no, next_result=next_res)
        # Trust sequential navigation rather than URL/page active state if SKU changed.
        page_no += 1
    return processed_total


from playwright.sync_api import sync_playwright


def main() -> None:
    if STOP_PATH.exists():
        stop_required("existing_stop_file_present")
    log("HZ14_ALL_PRODUCT_FULL_START", target_total=TARGET_TOTAL, page_start=PAGE_START, page_max=PAGE_MAX, item_sleep=[ITEM_SLEEP_MIN, ITEM_SLEEP_MAX], page_sleep=[PAGE_SLEEP_MIN, PAGE_SLEEP_MAX], run_once=RUN_ONCE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{base.CDP_PORT}", timeout=15000)
        page = get_active_page(browser)
        page.set_default_timeout(20000)
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
            n = run_cycle(page, state)
            state = load_state()
            state["last_full_cycle_finished_at"] = now()
            state["next_refresh_due_at"] = (datetime.now() + timedelta(days=REFRESH_AFTER_DAYS)).isoformat(timespec="seconds")
            save_state(state)
            write_report(state, {"cycle_finished": True, "cycle_processed": n})
            log("CYCLE_DONE", processed=n, known_sku_count=len(state.get("known_skus") or []))
            if RUN_ONCE:
                break
            time.sleep(CYCLE_SLEEP)


if __name__ == "__main__":
    main()
