#!/usr/bin/env python3
"""HZ12 product_all official full collector.

Official source: JD Union 商品推广 / 全部商品.
Design goals:
- Use visible product cards on product_all pages as the official commercial data source.
- Reuse the locally validated HZ9 modal parser/click helpers when available.
- Avoid unstable stored DOM ids; always re-read current DOM before clicking.
- Only persist records with numeric SKU and complete union links.
- Stop on login/risk/captcha/continuous failures by writing STOP_REQUIRED.
- Data Lab only: writes JSONL and reports; does not write production DB.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import re
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

WORKER_NAME = os.environ.get("HZ12_WORKER_NAME", "product_all_full")
CDP_PORT = int(os.environ.get("HZ12_CDP_PORT", "19228"))
URL_TEMPLATE = os.environ.get("HZ12_URL_TEMPLATE", "https://union.jd.com/proManager/index?pageNo={page_no}")

PAGE_START = int(os.environ.get("HZ12_PAGE_START", "1"))
PAGE_MAX = int(os.environ.get("HZ12_PAGE_MAX", "260"))
TARGET_TOTAL = int(os.environ.get("HZ12_TARGET_TOTAL", "4000"))
ITEMS_PER_PAGE_LIMIT = int(os.environ.get("HZ12_ITEMS_PER_PAGE_LIMIT", "20"))

ITEM_SLEEP_MIN = float(os.environ.get("HZ12_ITEM_SLEEP_MIN", "7"))
ITEM_SLEEP_MAX = float(os.environ.get("HZ12_ITEM_SLEEP_MAX", "16"))
PAGE_SLEEP_MIN = float(os.environ.get("HZ12_PAGE_SLEEP_MIN", "5"))
PAGE_SLEEP_MAX = float(os.environ.get("HZ12_PAGE_SLEEP_MAX", "12"))

LINK_EXPIRE_DAYS = int(os.environ.get("HZ12_LINK_EXPIRE_DAYS", "60"))
REFRESH_AFTER_DAYS = int(os.environ.get("HZ12_REFRESH_AFTER_DAYS", "40"))
SLEEP_CHECK_SECONDS = int(os.environ.get("HZ12_SLEEP_CHECK_SECONDS", "1800"))

MAX_FAIL_STREAK = int(os.environ.get("HZ12_MAX_FAIL_STREAK", "3"))
EMPTY_PAGE_LIMIT = int(os.environ.get("HZ12_EMPTY_PAGE_LIMIT", "8"))
MAX_SCROLL_STEPS = int(os.environ.get("HZ12_MAX_SCROLL_STEPS", "6"))
RUN_ONCE = os.environ.get("HZ12_RUN_ONCE", "false").lower() in {"1", "true", "yes", "y"}

OUT_PREFIX = os.environ.get("HZ12_OUT_PREFIX", "hz_jd_union_product_all_full_links")

STATE_PATH = Path("run/hz12_product_all_full_state.json")
STOP_PATH = Path("run/hz12_product_all_STOP_REQUIRED.json")
REPORT = Path(f"run/hz12_product_all_full_report_{RUN_ID}.json")
LATEST_REPORT = Path("run/hz12_product_all_full_report_latest.json")
OUT = Path(f"data/import/{OUT_PREFIX}_{RUN_ID}.jsonl")
LATEST = Path(f"data/import/{OUT_PREFIX}_latest.jsonl")

HZ9_PATH = Path("run/hz9_union_guarded_daemon.py")

STOP_MARKERS = [
    "验证码", "安全验证", "扫码登录", "请登录", "滑块", "身份验证",
    "风险提示", "账号异常", "登录注册"
]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(event: str, **kwargs: Any) -> None:
    print(json.dumps({"ts": now(), "worker": WORKER_NAME, "event": event, **kwargs}, ensure_ascii=False, sort_keys=True), flush=True)


def load_hz9():
    if not HZ9_PATH.exists():
        raise RuntimeError(f"missing local dependency: {HZ9_PATH}")
    spec = importlib.util.spec_from_file_location("hz9_reused", str(HZ9_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


hz9 = load_hz9()


def atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    target = path.resolve() if path.is_symlink() else path
    rows: List[Dict[str, Any]] = []
    if target.exists():
        for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    target = path.resolve() if path.is_symlink() else path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_latest_link() -> None:
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    if LATEST.exists() or LATEST.is_symlink():
        try:
            LATEST.unlink()
        except Exception:
            pass
    try:
        LATEST.symlink_to(OUT.name)
    except Exception:
        if OUT.exists():
            shutil.copyfile(OUT, LATEST)


def dedup_latest_by_sku() -> List[Dict[str, Any]]:
    rows = load_jsonl(LATEST)
    by_sku: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        if not sku.isdigit():
            continue
        old = by_sku.get(sku)
        new_key = str(row.get("link_created_at") or row.get("ts") or "")
        old_key = str(old.get("link_created_at") or old.get("ts") or "") if old else ""
        if old is None or new_key >= old_key:
            by_sku[sku] = row
    merged = list(by_sku.values())
    merged.sort(key=lambda x: str(x.get("sku")))
    write_jsonl(LATEST, merged)
    return merged


def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    else:
        state = {}
    state.setdefault("created_at", now())
    state.setdefault("run_id", RUN_ID)
    state.setdefault("current_page_no", PAGE_START)
    state.setdefault("refresh_round", 0)
    state.setdefault("known_skus", [])
    state.setdefault("round_seen_skus", [])
    state.setdefault("fail_streak", 0)
    state.setdefault("empty_page_streak", 0)
    state.setdefault("last_full_cycle_finished_at", None)
    state.setdefault("next_refresh_due_at", None)
    state.setdefault("page_total_hint", None)
    state.setdefault("target_total", TARGET_TOTAL)
    return state


def save_state(state: Dict[str, Any]) -> None:
    for key in ("known_skus", "round_seen_skus"):
        seen: List[str] = []
        for item in state.get(key) or []:
            value = str(item or "").strip()
            if value and value not in seen:
                seen.append(value)
        state[key] = seen
    state["known_sku_count"] = len(state.get("known_skus") or [])
    state["round_seen_sku_count"] = len(state.get("round_seen_skus") or [])
    state["updated_at"] = now()
    atomic_write_json(STATE_PATH, state)


def stop_required(reason: str, **kwargs: Any) -> None:
    payload = {"ts": now(), "reason": reason, **kwargs}
    atomic_write_json(STOP_PATH, payload)
    log("STOP_REQUIRED", **payload)
    raise SystemExit(2)


def body_text(page) -> str:
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:
        return ""


def check_page(page) -> Dict[str, Any]:
    txt = body_text(page)
    risk = [x for x in STOP_MARKERS if x in txt]
    url = page.url or ""
    if "union.jd.com" not in url:
        stop_required("not_jd_union_page", url=url, sample=txt[:300])
    if risk and "一键领链" not in txt:
        stop_required("risk_marker_detected", url=url, risk=risk, sample=txt[:500])
    return {
        "url": url,
        "one_key_count": txt.count("一键领链"),
        "has_product": "商品推广" in txt or "我要推广" in txt,
        "risk": risk,
        "text_len": len(txt),
    }


def extract_page_total(page) -> Optional[int]:
    txt = body_text(page)
    for pat in (r"共\s*(\d+)\s*条", r"共\s*(\d+)\s*个商品", r"全部商品\s*\(?\s*(\d+)\s*\)?"):
        m = re.search(pat, txt)
        if m:
            return int(m.group(1))
    return None


def normalize_img(url: Any) -> str:
    s = str(url or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("jfs/") or s.startswith("/jfs/"):
        return "https://img14.360buyimg.com/n1/" + s.lstrip("/")
    return s


def clean_title_from_card_text(txt: str) -> str:
    lines = [x.strip() for x in re.split(r"[\n\r]+", txt or "") if x.strip()]
    bad = ["预估收益", "佣金比例", "佣金", "到手价", "我要推广", "一键领链", "自营", "京配", "券", "促销", "定向", "百亿补贴", "好评"]
    candidates: List[str] = []
    for line in lines:
        compact = re.sub(r"\s+", "", line)
        if len(compact) < 6:
            continue
        if any(b in compact for b in bad):
            continue
        if re.search(r"^[¥￥]?\d+(\.\d+)?$", compact):
            continue
        candidates.append(line)
    return (candidates[0] if candidates else "")[:180]


def current_scroll_y(page) -> int:
    try:
        return int(page.evaluate("() => Math.round(window.scrollY || document.documentElement.scrollTop || 0)"))
    except Exception:
        return 0


def unique_candidates_from_hz9(page) -> List[Dict[str, Any]]:
    try:
        raw = hz9.get_candidates(page)
    except Exception as exc:
        log("HZ9_GET_CANDIDATES_FAIL", err=repr(exc))
        raw = []
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw):
        sku = str(item.get("sku") or "").strip()
        if not sku or not sku.isdigit() or sku in seen:
            continue
        seen.add(sku)
        card = dict(item)
        card["hz9_index"] = idx
        card["scroll_y"] = current_scroll_y(page)
        card["title"] = card.get("title") or ""
        card["imageUrl"] = normalize_img(card.get("imageUrl"))
        card["itemUrl"] = card.get("itemUrl") or f"https://item.jd.com/{sku}.html"
        out.append(card)
    return out


def collect_page_candidates(page) -> List[Dict[str, Any]]:
    """Scroll the product_all page and collect unique numeric-SKU candidates."""
    merged: Dict[str, Dict[str, Any]] = {}
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)
    except Exception:
        pass
    for step in range(MAX_SCROLL_STEPS):
        for card in unique_candidates_from_hz9(page):
            sku = str(card.get("sku") or "").strip()
            if sku and sku not in merged:
                merged[sku] = card
        at_bottom = False
        try:
            at_bottom = bool(page.evaluate("() => (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 20)"))
        except Exception:
            pass
        if at_bottom:
            break
        try:
            page.evaluate("() => window.scrollBy(0, Math.floor(window.innerHeight * 0.75))")
            page.wait_for_timeout(1200)
        except Exception:
            break
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(600)
    except Exception:
        pass
    return list(merged.values())


def find_current_candidate(page, sku: str, preferred_scroll_y: Optional[int]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    scroll_positions: List[int] = []
    if preferred_scroll_y is not None:
        scroll_positions.append(max(0, int(preferred_scroll_y)))
    scroll_positions.extend([0, 350, 700, 1050, 1400, 1750, 2100])
    seen_pos: set[int] = set()
    last_candidates: List[Dict[str, Any]] = []
    for pos in scroll_positions:
        if pos in seen_pos:
            continue
        seen_pos.add(pos)
        try:
            page.evaluate("(y) => window.scrollTo(0, y)", pos)
            page.wait_for_timeout(900)
        except Exception:
            pass
        current = unique_candidates_from_hz9(page)
        last_candidates = current
        for cand in current:
            if str(cand.get("sku") or "") == sku:
                return cand, current
    return None, last_candidates


def fallback_click_visible_onekey_by_index(page, index: int) -> Dict[str, Any]:
    return page.evaluate(
        """
        (index) => {
          const norm = s => (s || '').replace(/\s+/g, '').trim();
          const nodes = Array.from(document.querySelectorAll('button,a,span,div'))
            .map((el, idx) => {
              const r = el.getBoundingClientRect();
              return {el, idx, txt:norm(el.innerText || el.textContent), visible:r.width>0 && r.height>0 && r.top>=-100 && r.left>=-50 && r.top<=window.innerHeight+500};
            })
            .filter(x => x.visible && x.txt === '一键领链');
          if (!nodes.length) return {ok:false, reason:'no_visible_onekey', count:0};
          const i = Math.max(0, Math.min(index, nodes.length - 1));
          nodes[i].el.scrollIntoView({block:'center', inline:'center'});
          nodes[i].el.click();
          return {ok:true, method:'visible_button_index', requested:index, used:i, dom_index:nodes[i].idx, count:nodes.length};
        }
        """,
        index,
    )


def click_candidate(page, candidate: Dict[str, Any], page_order: int) -> Dict[str, Any]:
    try:
        ok = hz9.click_candidate(page, candidate)
        if ok:
            return {"ok": True, "method": "hz9_click_candidate"}
    except Exception as exc:
        log("HZ9_CLICK_CANDIDATE_FAIL", sku=candidate.get("sku"), err=repr(exc))
    return fallback_click_visible_onekey_by_index(page, page_order)


def close_dialog(page) -> bool:
    try:
        return bool(hz9.close_dialog(page))
    except Exception:
        return False


def parse_modal(page) -> Dict[str, Any]:
    try:
        return dict(hz9.parse_modal(page))
    except Exception:
        return {}


def link_dates() -> Tuple[str, str, str]:
    created = datetime.now()
    return (
        created.isoformat(timespec="seconds"),
        (created + timedelta(days=LINK_EXPIRE_DAYS)).isoformat(timespec="seconds"),
        (created + timedelta(days=REFRESH_AFTER_DAYS)).isoformat(timespec="seconds"),
    )


def collect_one(page, original_candidate: Dict[str, Any], state: Dict[str, Any], page_no: int, page_order: int) -> Optional[Dict[str, Any]]:
    sku = str(original_candidate.get("sku") or "").strip()
    if not sku.isdigit():
        log("ITEM_SKIP_NO_NUMERIC_SKU", page_no=page_no, sku=sku, title=(original_candidate.get("title") or "")[:80])
        return None
    current_candidate, current_candidates = find_current_candidate(page, sku, original_candidate.get("scroll_y"))
    if current_candidate is None:
        raise RuntimeError(f"candidate_not_visible_for_sku:{sku};visible={[x.get('sku') for x in current_candidates[:8]]}")
    close_dialog(page)
    click_result = click_candidate(page, current_candidate, min(page_order, max(0, len(current_candidates) - 1)))
    if not click_result.get("ok"):
        raise RuntimeError("click_failed:" + repr(click_result))
    result: Dict[str, Any] = {}
    for _ in range(60):
        page.wait_for_timeout(1000)
        result = parse_modal(page)
        if result.get("short_url"):
            break
    close_dialog(page)
    if not result.get("short_url"):
        raise RuntimeError("short_url_not_found")
    created_at, expire_at, refresh_due_at = link_dates()
    row = {
        "status": "ok",
        "ts": now(),
        "worker_name": WORKER_NAME,
        "menu_mode": "product_all_full",
        "page_no": page_no,
        "page_order": page_order,
        "sku": sku,
        "sku_source": "product_all_hz9",
        "title": current_candidate.get("title") or original_candidate.get("title"),
        "item_url": current_candidate.get("itemUrl") or original_candidate.get("itemUrl") or f"https://item.jd.com/{sku}.html",
        "image_url": normalize_img(current_candidate.get("imageUrl") or original_candidate.get("imageUrl")),
        "price": current_candidate.get("price") or original_candidate.get("price"),
        "commission_rate": current_candidate.get("rate") or original_candidate.get("rate"),
        "estimated_income": current_candidate.get("income") or original_candidate.get("income"),
        "short_url": result.get("short_url"),
        "long_url": result.get("long_url"),
        "qr_url": result.get("qr_url"),
        "jd_command": result.get("jd_command"),
        "promotion_mode": "hz_jd_union_product_all_full_onekey",
        "link_created_at": created_at,
        "link_expire_at": expire_at,
        "link_expire_days": LINK_EXPIRE_DAYS,
        "refresh_due_at": refresh_due_at,
        "refresh_after_days": REFRESH_AFTER_DAYS,
        "refresh_before_expiry_days": LINK_EXPIRE_DAYS - REFRESH_AFTER_DAYS,
        "refresh_round": state.get("refresh_round", 0),
        "run_id": RUN_ID,
        "click_result": click_result,
    }
    append_jsonl(OUT, row)
    ensure_latest_link()
    if sku not in state["known_skus"]:
        state["known_skus"].append(sku)
    if sku not in state["round_seen_skus"]:
        state["round_seen_skus"].append(sku)
    state["fail_streak"] = 0
    state["empty_page_streak"] = 0
    state["last_event"] = {"event": "ITEM_OK", "ts": now(), "sku": sku, "page_no": page_no, "short_url": row["short_url"]}
    save_state(state)
    log("ITEM_OK", page_no=page_no, sku=sku, short_url=row["short_url"], title=(row.get("title") or "")[:60], known_sku_count=len(state["known_skus"]))
    return row


def write_report(state: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> None:
    rows = load_jsonl(LATEST)
    ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
    skus = {str(x.get("sku")) for x in ok if x.get("sku")}
    non_numeric = [x for x in ok if not str(x.get("sku") or "").isdigit()]
    missing = {
        "title": sum(1 for x in ok if not x.get("title")),
        "image_url": sum(1 for x in ok if not x.get("image_url")),
        "item_url": sum(1 for x in ok if not x.get("item_url")),
        "price": sum(1 for x in ok if not x.get("price")),
        "commission_rate": sum(1 for x in ok if not x.get("commission_rate")),
        "estimated_income": sum(1 for x in ok if not x.get("estimated_income")),
        "long_url": sum(1 for x in ok if not x.get("long_url")),
        "qr_url": sum(1 for x in ok if not x.get("qr_url")),
        "jd_command": sum(1 for x in ok if not x.get("jd_command")),
        "refresh_due_at": sum(1 for x in ok if not x.get("refresh_due_at")),
    }
    report: Dict[str, Any] = {
        "ts": now(),
        "run_id": RUN_ID,
        "latest": str(LATEST),
        "out": str(OUT),
        "rows": len(rows),
        "ok": len(ok),
        "dedup_sku": len(skus),
        "non_numeric_sku": len(non_numeric),
        "missing": missing,
        "target_total": TARGET_TOTAL,
        "state": state,
    }
    if extra:
        report.update(extra)
    atomic_write_json(REPORT, report)
    shutil.copyfile(REPORT, LATEST_REPORT)


def full_cycle(page, state: Dict[str, Any]) -> int:
    processed = 0
    empty_pages = 0
    for page_no in range(int(state.get("current_page_no") or PAGE_START), PAGE_MAX + 1):
        state["current_page_no"] = page_no
        save_state(state)
        url = URL_TEMPLATE.format(page_no=page_no)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        info = check_page(page)
        total_hint = extract_page_total(page)
        if total_hint:
            state["page_total_hint"] = total_hint
            save_state(state)
        candidates = collect_page_candidates(page)
        seen = set(state.get("known_skus") or [])
        fresh: List[Dict[str, Any]] = []
        for cand in candidates:
            sku = str(cand.get("sku") or "").strip()
            if sku.isdigit() and sku not in seen and sku not in {str(x.get("sku")) for x in fresh}:
                fresh.append(cand)
        log("PAGE_CANDIDATES", page_no=page_no, total=len(candidates), fresh=len(fresh), processed=processed, page_info=info, total_hint=total_hint, sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:50]} for x in fresh[:5]])
        if not candidates:
            empty_pages += 1
            if empty_pages >= EMPTY_PAGE_LIMIT:
                log("EMPTY_PAGE_LIMIT_REACHED", page_no=page_no, empty_pages=empty_pages)
                break
            continue
        if not fresh:
            empty_pages += 1
            if empty_pages >= EMPTY_PAGE_LIMIT and len(state.get("known_skus") or []) >= min(TARGET_TOTAL, int((total_hint or TARGET_TOTAL) * 0.95)):
                break
            time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
            continue
        empty_pages = 0
        for order, cand in enumerate(fresh[:ITEMS_PER_PAGE_LIMIT]):
            try:
                row = collect_one(page, cand, state, page_no, order)
                if row:
                    processed += 1
                    write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no})
                time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
            except Exception as exc:
                state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
                state["last_event"] = {"event": "ITEM_FAIL", "ts": now(), "page_no": page_no, "sku": cand.get("sku"), "error": repr(exc)}
                save_state(state)
                log("ITEM_FAIL", page_no=page_no, sku=cand.get("sku"), err=repr(exc), fail_streak=state["fail_streak"])
                close_dialog(page)
                if state["fail_streak"] >= MAX_FAIL_STREAK:
                    stop_required("max_fail_streak_reached", page_no=page_no, sku=cand.get("sku"), fail_streak=state["fail_streak"], last_error=repr(exc))
                time.sleep(random.uniform(20, 40))
        write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no})
        time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
        if len(state.get("known_skus") or []) >= TARGET_TOTAL:
            log("TARGET_TOTAL_REACHED", known_sku_count=len(state["known_skus"]), target_total=TARGET_TOTAL)
            break
    state["last_full_cycle_finished_at"] = now()
    state["next_refresh_due_at"] = (datetime.now() + timedelta(days=REFRESH_AFTER_DAYS)).isoformat(timespec="seconds")
    state["current_page_no"] = PAGE_START
    state["round_seen_skus"] = []
    save_state(state)
    merged = dedup_latest_by_sku()
    write_report(state, {"cycle_finished": True, "cycle_processed": processed, "dedup_after_cycle": len(merged)})
    return processed


def should_sleep_until_refresh(state: Dict[str, Any]) -> Tuple[bool, Optional[datetime]]:
    next_due = state.get("next_refresh_due_at")
    if not next_due:
        return False, None
    try:
        due = datetime.fromisoformat(next_due)
    except Exception:
        return False, None
    return datetime.now() < due, due


def get_active_page(browser):
    return hz9.get_active_page(browser)


def main() -> None:
    log("HZ12_PRODUCT_ALL_FULL_START", cdp_port=CDP_PORT, target_total=TARGET_TOTAL, page_max=PAGE_MAX)
    if STOP_PATH.exists():
        stop_required("existing_stop_file_present", stop_path=str(STOP_PATH))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}", timeout=15000)
        page = get_active_page(browser)
        page.set_default_timeout(15000)
        while True:
            state = load_state()
            sleeping, _ = should_sleep_until_refresh(state)
            if sleeping:
                write_report(state, {"sleep_reason": "refresh_not_due", "next_refresh_due_at": state.get("next_refresh_due_at")})
                log("SLEEP_REFRESH_NOT_DUE", next_refresh_due_at=state.get("next_refresh_due_at"), sleep_seconds=SLEEP_CHECK_SECONDS)
                if RUN_ONCE:
                    break
                time.sleep(SLEEP_CHECK_SECONDS)
                continue
            state["refresh_round"] = int(state.get("refresh_round") or 0)
            state["current_page_no"] = PAGE_START
            state["round_seen_skus"] = []
            save_state(state)
            processed = full_cycle(page, state)
            log("FULL_CYCLE_DONE", processed=processed)
            if RUN_ONCE:
                break


if __name__ == "__main__":
    main()
