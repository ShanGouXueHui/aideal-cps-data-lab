import os
import json
import time
import shutil
import random
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

WORKER_NAME = os.environ.get("HZ11_WORKER_NAME", "worker")
MENU_MODE = os.environ.get("HZ11_MENU_MODE", "product_all")
CDP_PORT = int(os.environ.get("HZ11_CDP_PORT", "19228"))

TARGET_TOTAL = int(os.environ.get("HZ11_WORKER_TARGET_TOTAL", "60000"))
PAGE_START = int(os.environ.get("HZ11_PAGE_START", "1"))
PAGE_MAX = int(os.environ.get("HZ11_PAGE_MAX", "5000"))
MAX_ITEMS_PER_CYCLE = int(os.environ.get("HZ11_MAX_ITEMS_PER_CYCLE", "30"))
MAX_PAGES_PER_CYCLE = int(os.environ.get("HZ11_MAX_PAGES_PER_CYCLE", "5"))
MAX_HOVER_POINTS_PER_CYCLE = int(os.environ.get("HZ11_MAX_HOVER_POINTS_PER_CYCLE", "18"))

ITEM_SLEEP_MIN = float(os.environ.get("HZ11_ITEM_SLEEP_MIN", "7"))
ITEM_SLEEP_MAX = float(os.environ.get("HZ11_ITEM_SLEEP_MAX", "16"))
PAGE_SLEEP_MIN = float(os.environ.get("HZ11_PAGE_SLEEP_MIN", "6"))
PAGE_SLEEP_MAX = float(os.environ.get("HZ11_PAGE_SLEEP_MAX", "16"))
CYCLE_SLEEP = float(os.environ.get("HZ11_CYCLE_SLEEP", "90"))

MAX_FAIL_STREAK = int(os.environ.get("HZ11_MAX_FAIL_STREAK", "3"))
EMPTY_STREAK_LIMIT = int(os.environ.get("HZ11_EMPTY_STREAK_LIMIT", "40"))
RUN_ONCE = os.environ.get("HZ11_RUN_ONCE", "false").lower() in ("1", "true", "yes", "y")

LINK_EXPIRE_DAYS = int(os.environ.get("HZ11_LINK_EXPIRE_DAYS", "60"))
REFRESH_AFTER_DAYS = int(os.environ.get("HZ11_REFRESH_AFTER_DAYS", "40"))
REFRESH_BEFORE_EXPIRY_DAYS = int(os.environ.get("HZ11_REFRESH_BEFORE_EXPIRY_DAYS", str(max(1, LINK_EXPIRE_DAYS - REFRESH_AFTER_DAYS))))

OUT_PREFIX = os.environ.get("HZ11_OUT_PREFIX", f"hz_jd_union_{WORKER_NAME}")
STATE_PATH = Path(os.environ.get("HZ11_STATE_PATH", f"run/hz11_{WORKER_NAME}_state.json"))
STOP_PATH = Path(os.environ.get("HZ11_STOP_PATH", f"run/hz11_{WORKER_NAME}_STOP_REQUIRED.json"))
OUT = Path(f"data/import/{OUT_PREFIX}_{RUN_ID}.jsonl")
LATEST = Path(f"data/import/{OUT_PREFIX}_latest.jsonl")
REPORT = Path(f"run/hz11_{WORKER_NAME}_report_{RUN_ID}.json")
LATEST_REPORT = Path(f"run/hz11_{WORKER_NAME}_report_latest.json")

SEED_FILES = [x.strip() for x in os.environ.get("HZ11_SEED_FILES", "").split(",") if x.strip()]

PRODUCT_ALL_URL = "https://union.jd.com/proManager/index?pageNo={page_no}"
REALTIME_URL = "https://union.jd.com/proManager/realTimeRankings"
HIGH_COMMISSION_TAB_TEXT = os.environ.get("HZ11_HIGH_COMMISSION_TAB_TEXT", "高佣榜")

HZ9_PATH = Path("run/hz9_union_guarded_daemon.py")

STOP_MARKERS = ["验证码", "安全验证", "扫码登录", "请登录", "滑块", "身份验证", "风险提示", "账号异常"]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(event, **kwargs):
    payload = {"ts": now(), "worker": WORKER_NAME, "mode": MENU_MODE, "event": event, **kwargs}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def load_hz9():
    if not HZ9_PATH.exists():
        raise RuntimeError(f"missing {HZ9_PATH}")
    spec = importlib.util.spec_from_file_location("hz9_reused", str(HZ9_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hz9 = load_hz9()


def atomic_write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def ensure_latest_link():
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


def load_seed_skus():
    skus = []
    for name in SEED_FILES:
        p = Path(name)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                x = json.loads(line)
            except Exception:
                continue
            sku = str(x.get("sku") or "").strip()
            if sku and sku not in skus:
                skus.append(sku)
    return skus


def load_state():
    if STATE_PATH.exists():
        try:
            s = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            s = {}
    else:
        s = {}

    seed = load_seed_skus() if not s else []
    s.setdefault("created_at", now())
    s.setdefault("run_id", RUN_ID)
    s.setdefault("worker_name", WORKER_NAME)
    s.setdefault("menu_mode", MENU_MODE)
    s.setdefault("target_total", TARGET_TOTAL)
    s.setdefault("current_page_no", PAGE_START)
    s.setdefault("scroll_round", 0)
    s.setdefault("known_skus", seed)
    s.setdefault("round_seen_skus", [])
    s.setdefault("seen_short_urls", [])
    s.setdefault("refresh_round", 0)
    s.setdefault("refresh_started_at", None)
    s.setdefault("fail_streak", 0)
    s.setdefault("empty_streak", 0)
    s.setdefault("last_event", None)
    return s


def save_state(s):
    s["updated_at"] = now()
    for key in ("known_skus", "round_seen_skus", "seen_short_urls"):
        vals = []
        for x in s.get(key) or []:
            v = str(x or "").strip()
            if v and v not in vals:
                vals.append(v)
        s[key] = vals
    s["known_sku_count"] = len(s.get("known_skus") or [])
    s["round_seen_sku_count"] = len(s.get("round_seen_skus") or [])
    atomic_write_json(STATE_PATH, s)


def stop_required(reason, **kwargs):
    payload = {"ts": now(), "worker": WORKER_NAME, "mode": MENU_MODE, "reason": reason, **kwargs}
    atomic_write_json(STOP_PATH, payload)
    log("STOP_REQUIRED", **payload)
    raise SystemExit(2)


def append_jsonl(path: Path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def get_active_page(browser):
    return hz9.get_active_page(browser)


def close_dialog(page):
    try:
        return hz9.close_dialog(page)
    except Exception:
        return False


def body_text(page):
    try:
        return page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:
        return ""


def check_page(page):
    txt = body_text(page)
    risk = [x for x in STOP_MARKERS if x in txt]
    url = page.url or ""
    if "union.jd.com" not in url:
        stop_required("not_jd_union_page", url=url, sample=txt[:300])
    if risk:
        stop_required("risk_marker_detected", url=url, risk=risk, sample=txt[:500])
    return {
        "url": url,
        "one_key_count": txt.count("一键领链"),
        "promo_hit": ("商品推广" in txt or "实时榜单" in txt or "我要推广" in txt),
        "risk": risk,
    }


def click_text(page, text):
    return page.evaluate(
        """
        (text) => {
          const norm = s => (s || '').replace(/\\s+/g, '').trim();
          const target = norm(text);
          const nodes = Array.from(document.querySelectorAll('button,a,span,div,li'));
          const matched = nodes
            .map((el, idx) => ({el, idx, txt: norm(el.innerText || el.textContent)}))
            .filter(x => (x.txt === target || x.txt.includes(target)) && x.txt.length <= 40)
            .filter(x => {
              const r = x.el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && r.top >= 0 && r.top < window.innerHeight;
            })
            .sort((a, b) => {
              const ae = a.txt === target ? 0 : 1;
              const be = b.txt === target ? 0 : 1;
              if (ae !== be) return ae - be;
              return a.txt.length - b.txt.length;
            });
          if (!matched.length) return {ok:false, reason:'not_found', text};
          matched[0].el.click();
          return {ok:true, text, clicked:matched[0].txt, index:matched[0].idx};
        }
        """,
        text,
    )


def open_product_all(page, state):
    page_no = int(state.get("current_page_no") or PAGE_START)
    if page_no > PAGE_MAX:
        page_no = PAGE_START
        state["current_page_no"] = page_no
        save_state(state)
    page.goto(PRODUCT_ALL_URL.format(page_no=page_no), wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3500)
    close_dialog(page)
    info = check_page(page)
    return page_no, info


def open_high_commission(page, state):
    if "realTimeRankings" not in (page.url or ""):
        page.goto(REALTIME_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
    close_dialog(page)
    res = click_text(page, HIGH_COMMISSION_TAB_TEXT)
    page.wait_for_timeout(2500)
    close_dialog(page)
    info = check_page(page)
    return int(state.get("scroll_round") or 0), {"tab_click": res, **info}


def get_candidates_basic(page):
    try:
        candidates = hz9.get_candidates(page)
    except Exception as e:
        log("GET_CANDIDATES_FAIL", err=repr(e))
        return []
    out = []
    for c in candidates:
        sku = str(c.get("sku") or "").strip()
        if sku:
            out.append(c)
    return out


def hover_points():
    xs = [360, 820, 1260]
    ys = [560, 735, 910]
    return [(x, y) for y in ys for x in xs]


def move_scroll(page, state):
    page.evaluate("() => window.scrollBy(0, Math.floor(window.innerHeight * 0.75))")
    page.wait_for_timeout(1800)
    state["scroll_round"] = int(state.get("scroll_round") or 0) + 1
    save_state(state)


def at_bottom(page):
    try:
        return bool(page.evaluate("() => (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 10)"))
    except Exception:
        return False


def reset_scroll(page, state):
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(2000)
    state["scroll_round"] = 0
    save_state(state)


def skip_sku(state, sku):
    if sku in set(state.get("round_seen_skus") or []):
        return True
    if int(state.get("refresh_round") or 0) <= 0 and sku in set(state.get("known_skus") or []):
        return True
    return False


def link_dates():
    created = datetime.now()
    expire = created + timedelta(days=LINK_EXPIRE_DAYS)
    refresh_due = created + timedelta(days=REFRESH_AFTER_DAYS)
    return (
        created.isoformat(timespec="seconds"),
        expire.isoformat(timespec="seconds"),
        refresh_due.isoformat(timespec="seconds"),
    )


def collect_one(page, candidate, state, location):
    close_dialog(page)
    if not hz9.click_candidate(page, candidate):
        raise RuntimeError("click_failed")

    result = {}
    for _ in range(60):
        page.wait_for_timeout(1000)
        result = hz9.parse_modal(page)
        if result.get("short_url"):
            break

    close_dialog(page)

    if not result.get("short_url"):
        raise RuntimeError("short_url_not_found")

    created_at, expire_at, refresh_due_at = link_dates()
    sku = str(candidate.get("sku") or "").strip()
    short = str(result.get("short_url") or "").strip()

    row = {
        "status": "ok",
        "ts": now(),
        "worker_name": WORKER_NAME,
        "menu_mode": MENU_MODE,
        "location": location,
        "sku": sku,
        "title": candidate.get("title"),
        "item_url": candidate.get("itemUrl"),
        "image_url": candidate.get("imageUrl"),
        "price": candidate.get("price"),
        "commission_rate": candidate.get("rate"),
        "estimated_income": candidate.get("income"),
        "short_url": result.get("short_url"),
        "long_url": result.get("long_url"),
        "qr_url": result.get("qr_url"),
        "jd_command": result.get("jd_command"),
        "promotion_mode": f"hz_jd_union_{MENU_MODE}_onekey",
        "link_created_at": created_at,
        "link_expire_at": expire_at,
        "link_expire_days": LINK_EXPIRE_DAYS,
        "refresh_due_at": refresh_due_at,
        "refresh_after_days": REFRESH_AFTER_DAYS,
        "refresh_before_expiry_days": REFRESH_BEFORE_EXPIRY_DAYS,
        "refresh_round": state.get("refresh_round", 0),
        "run_id": RUN_ID,
    }

    append_jsonl(OUT, row)
    ensure_latest_link()

    if sku and sku not in state["known_skus"]:
        state["known_skus"].append(sku)
    if sku and sku not in state["round_seen_skus"]:
        state["round_seen_skus"].append(sku)
    if short and short not in state["seen_short_urls"]:
        state["seen_short_urls"].append(short)

    state["fail_streak"] = 0
    state["empty_streak"] = 0
    state["last_event"] = {"event": "ITEM_OK", "ts": now(), "sku": sku, "short_url": short, "location": location}
    save_state(state)

    log(
        "ITEM_OK",
        sku=sku,
        short_url=short,
        location=location,
        known_sku_count=len(state.get("known_skus") or []),
        round_seen_sku_count=len(state.get("round_seen_skus") or []),
        refresh_round=state.get("refresh_round", 0),
    )
    return row


def maybe_start_refresh_round(state):
    known = len(set(state.get("known_skus") or []))
    if known < TARGET_TOTAL:
        return False
    state["refresh_round"] = int(state.get("refresh_round") or 0) + 1
    state["refresh_started_at"] = now()
    state["round_seen_skus"] = []
    state["current_page_no"] = PAGE_START
    state["scroll_round"] = 0
    state["last_event"] = {"event": "REFRESH_ROUND_START", "ts": now(), "known_sku_count": known}
    save_state(state)
    log("REFRESH_ROUND_START", known_sku_count=known, target_total=TARGET_TOTAL, refresh_round=state["refresh_round"])
    return True


def read_rows(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def write_report(state, extra=None):
    rows = read_rows(OUT)
    ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
    skus = {str(x.get("sku")) for x in ok if x.get("sku")}
    started_at = state.get("created_at") or now()
    try:
        elapsed_hours = max((datetime.now() - datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600, 0.01)
    except Exception:
        elapsed_hours = 0.01
    per_hour = len(ok) / elapsed_hours
    per_day = per_hour * 24
    target_days = (TARGET_TOTAL / per_day) if per_day > 0 else None
    required_daily_for_40d = TARGET_TOTAL / max(1, REFRESH_AFTER_DAYS)

    report = {
        "ts": now(),
        "worker_name": WORKER_NAME,
        "menu_mode": MENU_MODE,
        "run_id": RUN_ID,
        "out": str(OUT),
        "latest": str(LATEST),
        "rows_this_run": len(rows),
        "ok_rows_this_run": len(ok),
        "dedup_sku_this_run": len(skus),
        "known_sku_count": len(set(state.get("known_skus") or [])),
        "round_seen_sku_count": len(set(state.get("round_seen_skus") or [])),
        "target_total": TARGET_TOTAL,
        "estimated_per_hour_this_worker": round(per_hour, 2),
        "estimated_per_day_this_worker": round(per_day, 2),
        "estimated_days_to_worker_target": round(target_days, 2) if target_days else None,
        "required_daily_for_40d_refresh": round(required_daily_for_40d, 2),
        "state": state,
    }
    if extra:
        report.update(extra)
    atomic_write_json(REPORT, report)
    shutil.copyfile(REPORT, LATEST_REPORT)


def cycle_product_all(page, state):
    processed = 0
    pages = 0
    while pages < MAX_PAGES_PER_CYCLE and processed < MAX_ITEMS_PER_CYCLE:
        maybe_start_refresh_round(state)
        page_no, info = open_product_all(page, state)
        candidates = get_candidates_basic(page)
        fresh = []
        fresh_skus = set()
        for c in candidates:
            sku = str(c.get("sku") or "").strip()
            if sku and sku not in fresh_skus and not skip_sku(state, sku):
                fresh.append(c)
                fresh_skus.add(sku)
        log("PAGE_CANDIDATES", page_no=page_no, total=len(candidates), fresh=len(fresh), processed=processed, page_info=info)

        if not fresh:
            state["empty_streak"] = int(state.get("empty_streak") or 0) + 1
            state["current_page_no"] = page_no + 1
            save_state(state)
            if state["empty_streak"] >= EMPTY_STREAK_LIMIT:
                stop_required("empty_streak_limit", empty_streak=state["empty_streak"], page_no=page_no)
            pages += 1
            time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
            continue

        for c in fresh:
            if processed >= MAX_ITEMS_PER_CYCLE:
                break
            loop_sku = str(c.get("sku") or "").strip()
            if loop_sku and skip_sku(state, loop_sku):
                log("SKIP_ALREADY_SEEN_IN_LOOP", sku=loop_sku)
                continue
            try:
                collect_one(page, c, state, {"page_no": page_no})
                processed += 1
                write_report(state, {"last_cycle_processed": processed, "last_page_no": page_no})
                time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
            except Exception as e:
                state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
                state["last_event"] = {"event": "ITEM_FAIL", "ts": now(), "err": repr(e), "page_no": page_no}
                save_state(state)
                log("ITEM_FAIL", err=repr(e), page_no=page_no, fail_streak=state["fail_streak"])
                close_dialog(page)
                if state["fail_streak"] >= MAX_FAIL_STREAK:
                    stop_required("max_fail_streak_reached", fail_streak=state["fail_streak"], last_error=repr(e))
                time.sleep(random.uniform(20, 40))

        state["current_page_no"] = page_no + 1
        save_state(state)
        pages += 1
        time.sleep(random.uniform(PAGE_SLEEP_MIN, PAGE_SLEEP_MAX))
    return processed, pages


def cycle_high_commission(page, state):
    processed = 0
    hover_checked = 0
    maybe_start_refresh_round(state)
    scroll_round, info = open_high_commission(page, state)

    for x, y in hover_points():
        if processed >= MAX_ITEMS_PER_CYCLE or hover_checked >= MAX_HOVER_POINTS_PER_CYCLE:
            break
        try:
            page.mouse.move(x, y)
            page.wait_for_timeout(700)
        except Exception:
            continue

        candidates = get_candidates_basic(page)
        fresh = []
        fresh_skus = set()
        for c in candidates:
            sku = str(c.get("sku") or "").strip()
            if sku and sku not in fresh_skus and not skip_sku(state, sku):
                fresh.append(c)
                fresh_skus.add(sku)

        hover_checked += 1
        log(
            "HOVER_CANDIDATES",
            x=x,
            y=y,
            scroll_round=scroll_round,
            total=len(candidates),
            fresh=len(fresh),
            processed=processed,
            page_info=info,
        )

        if not fresh:
            continue

        try:
            collect_one(page, fresh[0], state, {"scroll_round": scroll_round, "x": x, "y": y})
            processed += 1
            write_report(state, {"last_cycle_processed": processed, "last_scroll_round": scroll_round})
            time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
        except Exception as e:
            state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
            state["last_event"] = {"event": "ITEM_FAIL", "ts": now(), "err": repr(e), "scroll_round": scroll_round, "x": x, "y": y}
            save_state(state)
            log("ITEM_FAIL", err=repr(e), scroll_round=scroll_round, x=x, y=y, fail_streak=state["fail_streak"])
            close_dialog(page)
            if state["fail_streak"] >= MAX_FAIL_STREAK:
                stop_required("max_fail_streak_reached", fail_streak=state["fail_streak"], last_error=repr(e))
            time.sleep(random.uniform(20, 40))

    if processed <= 0:
        state["empty_streak"] = int(state.get("empty_streak") or 0) + 1
    else:
        state["empty_streak"] = 0
    save_state(state)

    if at_bottom(page):
        log("SCROLL_BOTTOM_RESET", scroll_round=state.get("scroll_round"))
        reset_scroll(page, state)
    else:
        move_scroll(page, state)

    if state["empty_streak"] >= EMPTY_STREAK_LIMIT:
        stop_required("empty_streak_limit", empty_streak=state["empty_streak"], scroll_round=state.get("scroll_round"))

    return processed, hover_checked


def main():
    log(
        "HZ11_RANK_WORKER_START",
        worker_name=WORKER_NAME,
        menu_mode=MENU_MODE,
        cdp_port=CDP_PORT,
        target_total=TARGET_TOTAL,
        out=str(OUT),
        latest=str(LATEST),
        link_expire_days=LINK_EXPIRE_DAYS,
        refresh_after_days=REFRESH_AFTER_DAYS,
    )

    if STOP_PATH.exists():
        stop_required("existing_stop_file_present", stop_path=str(STOP_PATH))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ensure_latest_link()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}", timeout=15000)
        page = get_active_page(browser)
        page.set_default_timeout(15000)
        log("ATTACHED", url=page.url, title=page.title())

        while True:
            state = load_state()
            if MENU_MODE == "product_all":
                processed, units = cycle_product_all(page, state)
            elif MENU_MODE == "high_commission":
                processed, units = cycle_high_commission(page, state)
            else:
                stop_required("unknown_menu_mode", menu_mode=MENU_MODE)

            state = load_state()
            write_report(state, {"last_cycle_processed": processed, "last_cycle_units": units, "sleep_seconds": CYCLE_SLEEP})
            log(
                "CYCLE_DONE",
                processed=processed,
                units=units,
                known_sku_count=len(set(state.get("known_skus") or [])),
                round_seen_sku_count=len(set(state.get("round_seen_skus") or [])),
                refresh_round=state.get("refresh_round", 0),
            )

            if RUN_ONCE:
                break
            time.sleep(CYCLE_SLEEP)


if __name__ == "__main__":
    main()
