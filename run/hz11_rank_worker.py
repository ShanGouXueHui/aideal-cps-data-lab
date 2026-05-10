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
    setup_high_commission_rank_api_capture(page)

    current_url = page.url or ""
    initialized = bool(getattr(page, "_hz11_high_commission_initialized", False))

    if "realTimeRankings" not in current_url or not initialized:
        page.goto(REALTIME_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        close_dialog(page)
        res = click_text(page, HIGH_COMMISSION_TAB_TEXT)
        page.wait_for_timeout(6000)
        close_dialog(page)
        page._hz11_high_commission_initialized = True
    else:
        # HZ11O: 不要每轮重新 goto/click tab，否则会回到第一页，分页永远扩不出去。
        res = {"ok": True, "skipped": "already_on_high_commission_page"}
        close_dialog(page)
        page.wait_for_timeout(1200)

    info = check_page(page)
    info["rank_api_count"] = len(getattr(page, "_hz11_rank_skus", []) or [])
    info["rank_api_last_error"] = getattr(page, "_hz11_rank_api_last_error", "")
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



def extract_sku_from_texts(*vals):
    import re
    patterns = [
        r'(?:skuId|sku_id|sku|wareId|ware_id|materialId|material_id|itemId|item_id)[=:/%3D]+(\d{5,})',
        r'item\.jd\.com/(\d{5,})\.html',
        r'jd\.com/(\d{5,})\.html',
        r'wareId["\\\']?\s*[:=]\s*["\\\']?(\d{5,})',
        r'skuId["\\\']?\s*[:=]\s*["\\\']?(\d{5,})',
    ]
    blob = " ".join(str(v or "") for v in vals)
    for pat in patterns:
        m = re.search(pat, blob, flags=re.I)
        if m:
            return m.group(1), pat
    return "", ""



def normalize_jd_image_url(v):
    s = str(v or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("jfs/") or s.startswith("/jfs/"):
        return "https://img14.360buyimg.com/n1/" + s.lstrip("/")
    return s


def setup_high_commission_rank_api_capture(page):
    """
    监听高佣榜列表接口 union_search_rank_api，缓存 result.rankSkuList。
    不保存 cookies/header/h5st/sign，只在 worker 内使用商品字段。
    """
    if getattr(page, "_hz11_rank_api_capture_ready", False):
        return

    page._hz11_rank_api_capture_ready = True
    page._hz11_rank_skus = []
    page._hz11_rank_api_last_error = ""

    def on_response(resp):
        try:
            url = resp.url or ""
            if "functionId=union_search_rank_api" not in url:
                return
            text = resp.text()
            payload = json.loads(text)
            items = (((payload or {}).get("result") or {}).get("rankSkuList") or [])
            clean = []
            for idx, x in enumerate(items):
                if not isinstance(x, dict):
                    continue
                sku = str(x.get("skuId") or "").strip()
                name = str(x.get("skuName") or "").strip()
                if not sku and not name:
                    continue
                image = normalize_jd_image_url(x.get("imageUrl"))
                item_url = f"https://item.jd.com/{sku}.html" if sku else ""
                clean.append({
                    "api_index": idx,
                    "sku": sku,
                    "skuId": sku,
                    "skuName": name,
                    "title": name,
                    "itemUrl": item_url,
                    "imageUrl": image,
                    "price": str(x.get("wlprice") or ""),
                    "rate": (str(x.get("commissionShare")) + "%") if x.get("commissionShare") not in (None, "") else "",
                    "income": str(x.get("commission") or ""),
                    "commission": str(x.get("commission") or ""),
                    "commissionShare": str(x.get("commissionShare") or ""),
                    "rank_index": str(x.get("rankPos") or idx + 1),
                    "raw_keys": sorted(list(x.keys()))[:80],
                })
            if clean:
                page._hz11_rank_skus = clean
                log("HC_RANK_API_CAPTURED", count=len(clean), sample=[
                    {
                        "api_index": z.get("api_index"),
                        "sku": z.get("sku"),
                        "title": (z.get("title") or "")[:60],
                        "price": z.get("price"),
                        "rate": z.get("rate"),
                        "income": z.get("income"),
                    }
                    for z in clean[:5]
                ])
        except Exception as e:
            page._hz11_rank_api_last_error = repr(e)
            log("HC_RANK_API_CAPTURE_FAIL", err=repr(e))

    page.on("response", on_response)


def title_score(a, b):
    aa = str(a or "")
    bb = str(b or "")
    if not aa or not bb:
        return 0
    aa_c = "".join(ch for ch in aa if not ch.isspace())
    bb_c = "".join(ch for ch in bb if not ch.isspace())
    if aa_c and bb_c and (aa_c in bb_c or bb_c in aa_c):
        return min(len(aa_c), len(bb_c)) + 1000
    aset = set(aa_c)
    bset = set(bb_c)
    if not aset or not bset:
        return 0
    return len(aset & bset)


def attach_rank_api_items_to_cards(page, cards):
    api_items = list(getattr(page, "_hz11_rank_skus", []) or [])
    if not cards or not api_items:
        return cards

    used = set()
    enriched = []

    for i, c in enumerate(cards):
        title = c.get("title") or c.get("raw_text") or ""
        best_j = None
        best_score = -1

        # 优先标题匹配；分数太低时按顺序兜底。
        for j, item in enumerate(api_items):
            if j in used:
                continue
            s = title_score(title, item.get("title"))
            if s > best_score:
                best_score = s
                best_j = j

        if best_j is None:
            enriched.append(c)
            continue

        # 标题分数低也接受同序兜底，避免 DOM 文本截断导致无法匹配。
        if best_score < 6 and i < len(api_items) and i not in used:
            best_j = i
            best_score = title_score(title, api_items[i].get("title"))

        item = api_items[best_j]
        used.add(best_j)

        cc = dict(c)
        cc["sku"] = item.get("sku") or cc.get("sku")
        cc["sku_source"] = "api_rank_title_match" if best_score >= 6 else "api_rank_order"
        cc["api_match_score"] = best_score
        cc["api_index"] = item.get("api_index")
        cc["rank_index"] = item.get("rank_index") or cc.get("rank_index")
        cc["title"] = item.get("title") or cc.get("title")
        cc["itemUrl"] = item.get("itemUrl") or cc.get("itemUrl")
        cc["imageUrl"] = item.get("imageUrl") or cc.get("imageUrl")
        cc["price"] = item.get("price") or cc.get("price")
        cc["rate"] = item.get("rate") or cc.get("rate")
        cc["income"] = item.get("income") or cc.get("income")
        enriched.append(cc)

    return enriched

def get_high_commission_cards(page):
    """
    realTimeRankings / 高佣榜 专用 parser。
    HZ9 get_candidates 适配商品推广页，不适配实时榜单页。
    这里从可见卡片 DOM 中解析 rank/title/price/commission，并给卡片打 data-hz11-card-id。
    """
    cards = page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
          const compact = s => (s || '').replace(/\\s+/g, '').trim();

          const skuFromUrl = (u) => {
            if (!u) return '';
            const patterns = [
              /item\\.jd\\.com\\/(\\d{5,})\\.html/i,
              /jd\\.com\\/(\\d{5,})\\.html/i,
              /(?:skuId|sku_id|sku|wareId|ware_id|materialId|material_id|itemId|item_id)[=:/%3D]+(\\d{5,})/i
            ];
            for (const p of patterns) {
              const m = String(u).match(p);
              if (m) return m[1];
            }
            return '';
          };

          const parseMoney = (txt, label) => {
            const re = new RegExp(label + '\\\\s*¥?\\\\s*([0-9]+(?:\\\\.[0-9]+)?)', 'i');
            const m = txt.match(re);
            return m ? m[1] : '';
          };

          const parseRate = (txt) => {
            const m = txt.match(/佣金率\\s*([0-9]+(?:\\.[0-9]+)?%)/);
            return m ? m[1] : '';
          };

          let raw = Array.from(document.querySelectorAll('div')).map((el, idx) => {
            const r = el.getBoundingClientRect();
            const txt = norm(el.innerText || el.textContent || '');
            return {el, idx, txt, rect:{x:r.x,y:r.y,w:r.width,h:r.height}, area:r.width*r.height};
          }).filter(x =>
            x.rect.w >= 240 &&
            x.rect.w <= 520 &&
            x.rect.h >= 120 &&
            x.rect.h <= 520 &&
            x.rect.x >= 180 &&
            x.rect.y >= -80 &&
            x.rect.y <= window.innerHeight + 360 &&
            /到手价/.test(x.txt) &&
            /佣金/.test(x.txt) &&
            x.txt.length >= 40 &&
            x.txt.length <= 1000 &&
            !/选择页面全部商品/.test(x.txt) &&
            !/批量推广/.test(x.txt)
          );

          // 保留更小的卡片容器，去掉包含其它候选卡的大容器。
          raw = raw.filter(a => !raw.some(b => a.el !== b.el && a.el.contains(b.el) && b.area < a.area * 0.82));

          raw.sort((a,b) => (a.rect.y - b.rect.y) || (a.rect.x - b.rect.x));

          const seenText = new Set();
          const out = [];

          for (const x of raw) {
            const key = compact(x.txt).slice(0, 120);
            if (seenText.has(key)) continue;
            seenText.add(key);

            const cardId = 'hc_' + out.length + '_' + Date.now();
            x.el.setAttribute('data-hz11-card-id', cardId);

            const txt = x.txt;
            const links = Array.from(x.el.querySelectorAll('a[href]')).map(a => a.href || '').filter(Boolean);
            const imgs = Array.from(x.el.querySelectorAll('img')).map(img => img.currentSrc || img.src || '').filter(Boolean);
            const hrefBlob = links.join(' ');
            let sku = skuFromUrl(hrefBlob);

            let rank = '';
            let rankMatch = txt.match(/^\\s*(\\d{1,3})\\s+/);
            if (rankMatch) rank = rankMatch[1];

            let titlePart = txt;
            titlePart = titlePart.replace(/^\\s*\\d{1,3}\\s+/, '');
            const pricePos = titlePart.search(/到手价/);
            let title = pricePos > 0 ? titlePart.slice(0, pricePos) : titlePart;
            title = title
              .replace(/精品推荐/g, ' ')
              .replace(/京喜自营/g, ' ')
              .replace(/自营/g, ' ')
              .replace(/奖励/g, ' ')
              .replace(/券/g, ' ')
              .replace(/\\s+/g, ' ')
              .trim()
              .slice(0, 180);

            const price = parseMoney(txt, '到手价');
            const income = parseMoney(txt, '佣金');
            const rate = parseRate(txt);

            out.push({
              card_id: cardId,
              rank_index: rank,
              sku: sku,
              sku_source: sku ? 'card_link' : '',
              title: title,
              itemUrl: links[0] || '',
              imageUrl: imgs[0] || '',
              price: price,
              rate: rate,
              income: income,
              raw_text: txt.slice(0, 900),
              rect: x.rect,
              center: {x: x.rect.x + x.rect.w / 2, y: x.rect.y + Math.min(x.rect.h / 2, 180)}
            });
          }

          return out;
        }
        """
    )
    return attach_rank_api_items_to_cards(page, cards)


def click_high_commission_card(page, card):
    """
    高佣榜专用点击：
    1. scroll card into center
    2. hover card center
    3. 找可见的一键领链按钮
    4. 用 mouse.click 点击按钮中心点
    """
    cid = card.get("card_id")
    center = card.get("center") or {}

    prep = page.evaluate(
        """
        (cid) => {
          const root = document.querySelector(`[data-hz11-card-id="${cid}"]`);
          if (!root) return {ok:false, reason:'card_not_found', cid};
          root.scrollIntoView({block:'center', inline:'center'});
          const r = root.getBoundingClientRect();
          return {
            ok:true,
            cid,
            rootRect:{x:r.x,y:r.y,w:r.width,h:r.height},
            center:{x:r.x + r.width / 2, y:r.y + Math.min(r.height / 2, 160)}
          };
        }
        """,
        cid,
    )

    if not prep.get("ok"):
        return prep

    page.wait_for_timeout(800)

    cx = float(prep.get("center", {}).get("x") or center.get("x") or 0)
    cy = float(prep.get("center", {}).get("y") or center.get("y") or 0)

    if cx > 0 and cy > 0:
        page.mouse.move(cx, cy)
        page.wait_for_timeout(1200)
        page.mouse.move(cx + 8, cy + 8)
        page.wait_for_timeout(700)

    # 先找可见按钮；如果没有，找卡片附近按钮。
    found = page.evaluate(
        """
        (cid) => {
          const norm = s => (s || '').replace(/\\s+/g, '').trim();
          const root = document.querySelector(`[data-hz11-card-id="${cid}"]`);
          if (!root) return {ok:false, reason:'card_not_found_after_hover', cid};

          const rr = root.getBoundingClientRect();
          const rootCx = rr.x + rr.width / 2;
          const rootCy = rr.y + rr.height / 2;

          const all = Array.from(document.querySelectorAll('button,a,span,div')).map((el, idx) => {
            const r = el.getBoundingClientRect();
            const txt = norm(el.innerText || el.textContent);
            const visible = r.width > 0 && r.height > 0 && r.top >= 0 && r.left >= 0 && r.top <= window.innerHeight && r.left <= window.innerWidth;
            const bx = r.x + r.width / 2;
            const by = r.y + r.height / 2;
            const insideX = bx >= rr.x - 80 && bx <= rr.x + rr.width + 80;
            const nearY = by >= rr.y - 120 && by <= rr.y + rr.height + 320;
            const dist = Math.abs(bx - rootCx) + Math.abs(by - rootCy);
            return {
              idx,
              tag: el.tagName,
              txt,
              visible,
              insideX,
              nearY,
              dist,
              rect:{x:r.x,y:r.y,w:r.width,h:r.height,cx:bx,cy:by},
              cls:String(el.className || '').slice(0,120)
            };
          }).filter(x => x.txt === '一键领链' || x.txt.includes('一键领链'));

          const exactVisible = all.filter(x => x.visible && x.txt === '一键领链' && x.insideX && x.nearY);
          const anyVisible = all.filter(x => x.visible && x.insideX && x.nearY);
          const nearAny = all.filter(x => x.insideX && x.nearY);

          let candidates = exactVisible.length ? exactVisible : (anyVisible.length ? anyVisible : nearAny);
          candidates.sort((a,b) => {
            const av = a.visible ? 0 : 1;
            const bv = b.visible ? 0 : 1;
            if (av !== bv) return av - bv;
            const ae = a.txt === '一键领链' ? 0 : 1;
            const be = b.txt === '一键领链' ? 0 : 1;
            if (ae !== be) return ae - be;
            return a.dist - b.dist;
          });

          if (!candidates.length) {
            return {
              ok:false,
              reason:'onekey_button_not_found',
              cid,
              rootRect:{x:rr.x,y:rr.y,w:rr.width,h:rr.height},
              allSample:all.slice(0,12)
            };
          }

          return {
            ok:true,
            cid,
            rootRect:{x:rr.x,y:rr.y,w:rr.width,h:rr.height},
            button:candidates[0],
            allCount:all.length,
            visibleCount:all.filter(x => x.visible).length
          };
        }
        """,
        cid,
    )

    if not found.get("ok"):
        return found

    btn = found.get("button") or {}
    rect = btn.get("rect") or {}
    bx = float(rect.get("cx") or 0)
    by = float(rect.get("cy") or 0)

    if bx <= 0 or by <= 0:
        return {"ok": False, "reason": "button_center_invalid", "found": found}

    page.mouse.move(bx, by)
    page.wait_for_timeout(400)
    page.mouse.click(bx, by)
    page.wait_for_timeout(1500)

    # 点击后检查是否出现弹窗/短链相关文本
    after = page.evaluate(
        """
        () => {
          const txt = document.body ? document.body.innerText || '' : '';
          return {
            has_short_hint: /短链|推广链接|复制链接|京口令|二维码/.test(txt),
            short_url_count: (txt.match(/u\\.jd\\.com/g) || []).length,
            body_sample: txt.slice(0, 800)
          };
        }
        """
    )

    return {"ok": True, "clicked_by": "mouse_coordinate", "button": btn, "after": after, "found": found}


def click_modal_tab(page, tab_text):
    """
    在“生成推广链接”弹窗中切换 短链接 / 长链接 / 二维码 / 京口令。
    """
    try:
        return page.evaluate(
            """
            (tabText) => {
              const norm = s => (s || '').replace(/\\s+/g, '').trim();
              const target = norm(tabText);
              const nodes = Array.from(document.querySelectorAll('button,a,span,div,li'));
              const matched = nodes
                .map((el, idx) => {
                  const r = el.getBoundingClientRect();
                  return {
                    el,
                    idx,
                    txt: norm(el.innerText || el.textContent),
                    visible: r.width > 0 && r.height > 0 && r.top >= 0 && r.left >= 0 && r.top <= window.innerHeight && r.left <= window.innerWidth,
                    rect: {x:r.x,y:r.y,w:r.width,h:r.height}
                  };
                })
                .filter(x => x.visible && (x.txt === target || x.txt.includes(target)) && x.txt.length <= 20)
                .sort((a,b) => a.txt.length - b.txt.length);
              if (!matched.length) return {ok:false, reason:'tab_not_found', tabText};
              matched[0].el.click();
              return {ok:true, tabText, clicked:matched[0].txt, index:matched[0].idx, rect:matched[0].rect};
            }
            """,
            tab_text,
        )
    except Exception as e:
        return {"ok": False, "reason": repr(e), "tabText": tab_text}


def parse_modal_all_tabs(page):
    """
    高佣榜弹窗中，短链 tab 默认只展示短链接。
    为了提取真实 SKU，需要切换到“长链接”tab 后再解析。
    """
    merged = {}
    tab_results = {}

    for tab in ("短链接", "长链接", "京口令", "二维码"):
        tab_res = click_modal_tab(page, tab)
        tab_results[tab] = tab_res
        page.wait_for_timeout(800)

        try:
            r = hz9.parse_modal(page)
        except Exception as e:
            r = {"_parse_error": repr(e)}

        for k, v in r.items():
            if v and not merged.get(k):
                merged[k] = v

    # 再补一份弹窗整体文本和输入框 value，便于后续诊断，但只保存短样本。
    try:
        extra = page.evaluate(
            """
            () => {
              const txt = document.body ? document.body.innerText || '' : '';
              const values = Array.from(document.querySelectorAll('input,textarea'))
                .map(x => x.value || x.getAttribute('value') || '')
                .filter(Boolean)
                .slice(0, 20);
              const hrefs = Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href || '')
                .filter(Boolean)
                .slice(0, 80);
              return {
                text_sample: txt.slice(0, 1200),
                input_values: values,
                hrefs: hrefs
              };
            }
            """
        )
    except Exception as e:
        extra = {"_extra_error": repr(e)}

    # 从 input/href 兜底补 URL
    blobs = []
    blobs.extend(extra.get("input_values") or [])
    blobs.extend(extra.get("hrefs") or [])

    for v in blobs:
        s = str(v or "")
        if "u.jd.com" in s and not merged.get("short_url"):
            merged["short_url"] = s
        if ("union-click.jd.com" in s or "jd.com" in s) and not merged.get("long_url"):
            merged["long_url"] = s

    merged["_tab_results"] = tab_results
    merged["_extra_sample"] = {
        "input_values": [str(x)[:300] for x in (extra.get("input_values") or [])[:8]],
        "hrefs": [str(x)[:300] for x in (extra.get("hrefs") or [])[:8]],
        "text_sample": str(extra.get("text_sample") or "")[:500],
    }
    return merged

def collect_high_commission_one(page, candidate, state, location):
    close_dialog(page)

    click_res = click_high_commission_card(page, candidate)
    if not click_res.get("ok"):
        raise RuntimeError("high_commission_click_failed:" + repr(click_res))
    log("HC_CLICK_RESULT", title=(candidate.get("title") or "")[:80], click_result=click_res)

    result = {}
    for _ in range(60):
        page.wait_for_timeout(1000)
        result = parse_modal_all_tabs(page)
        if result.get("short_url"):
            break

    if not result.get("short_url"):
        close_dialog(page)
        raise RuntimeError("short_url_not_found")

    sku_from_result, sku_pat = extract_sku_from_texts(
        candidate.get("sku"),
        candidate.get("itemUrl"),
        result.get("long_url"),
        result.get("short_url"),
        result.get("qr_url"),
        result.get("jd_command"),
        json.dumps(result.get("_extra_sample") or {}, ensure_ascii=False),
    )

    close_dialog(page)

    candidate_key = "hc_title_" + str(abs(hash((candidate.get("title") or "")[:120])))
    sku = sku_from_result or str(candidate.get("sku") or "").strip() or candidate_key
    sku_source = "modal_or_url" if sku_from_result else (candidate.get("sku_source") or "generated_title_key")

    created_at, expire_at, refresh_due_at = link_dates()

    row = {
        "status": "ok",
        "ts": now(),
        "worker_name": WORKER_NAME,
        "menu_mode": MENU_MODE,
        "location": location,
        "rank_index": candidate.get("rank_index"),
        "sku": sku,
        "sku_source": sku_source,
        "sku_extract_pattern": sku_pat,
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
        "promotion_mode": "hz_jd_union_high_commission_hover_onekey",
        "link_created_at": created_at,
        "link_expire_at": expire_at,
        "link_expire_days": LINK_EXPIRE_DAYS,
        "refresh_due_at": refresh_due_at,
        "refresh_after_days": REFRESH_AFTER_DAYS,
        "refresh_before_expiry_days": REFRESH_BEFORE_EXPIRY_DAYS,
        "refresh_round": state.get("refresh_round", 0),
        "run_id": RUN_ID,
        "click_result": click_res,
        "modal_tab_results": result.get("_tab_results"),
        "modal_extra_sample": result.get("_extra_sample"),
    }

    append_jsonl(OUT, row)
    ensure_latest_link()

    if sku and sku not in state["known_skus"]:
        state["known_skus"].append(sku)
    if sku and sku not in state["round_seen_skus"]:
        state["round_seen_skus"].append(sku)
    short = str(result.get("short_url") or "").strip()
    if short and short not in state["seen_short_urls"]:
        state["seen_short_urls"].append(short)

    state["fail_streak"] = 0
    state["empty_streak"] = 0
    state["last_event"] = {
        "event": "ITEM_OK",
        "ts": now(),
        "sku": sku,
        "short_url": short,
        "location": location,
        "sku_source": sku_source,
    }
    save_state(state)

    log(
        "ITEM_OK",
        sku=sku,
        sku_source=sku_source,
        short_url=short,
        location=location,
        known_sku_count=len(state.get("known_skus") or []),
        round_seen_sku_count=len(state.get("round_seen_skus") or []),
        refresh_round=state.get("refresh_round", 0),
    )
    return row




def click_high_commission_next_page(page, state):
    """
    HZ11O:
    - 不再依赖 mouse.click 屏幕坐标；
    - 直接对 DOM 中可用“下一页”节点执行 el.click()；
    - 等待 union_search_rank_api 捕获到新的 rankSkuList；
    - 只有 rank API 前后 SKU 变化时才认为翻页成功。
    """
    before_skus = [str(x.get("sku") or "") for x in (getattr(page, "_hz11_rank_skus", []) or [])[:8]]

    try:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
    except Exception:
        pass

    click_res = page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\\s+/g, '').trim();
          const nodes = Array.from(document.querySelectorAll('button,a,span,div,li'));
          const candidates = nodes.map((el, idx) => {
            const r = el.getBoundingClientRect();
            const txt = norm(el.innerText || el.textContent);
            const cls = String(el.className || '');
            const disabled =
              el.disabled ||
              el.getAttribute('disabled') !== null ||
              cls.includes('disabled') ||
              cls.includes('is-disabled') ||
              el.getAttribute('aria-disabled') === 'true';
            return {
              el,
              idx,
              txt,
              disabled,
              cls: cls.slice(0, 160),
              visible: r.width > 0 && r.height > 0 && r.top >= -120 && r.left >= -50 && r.top <= window.innerHeight + 180,
              rect: {x:r.x, y:r.y, w:r.width, h:r.height, cx:r.x + r.width/2, cy:r.y + r.height/2}
            };
          }).filter(x =>
            x.visible &&
            !x.disabled &&
            (x.txt === '下一页' || x.txt.includes('下一页')) &&
            x.txt.length <= 20
          ).sort((a,b) => {
            const ae = a.txt === '下一页' ? 0 : 1;
            const be = b.txt === '下一页' ? 0 : 1;
            if (ae !== be) return ae - be;
            return b.rect.y - a.rect.y;
          });

          if (!candidates.length) {
            return {
              ok:false,
              reason:'next_button_not_found',
              samples: nodes.map((el, idx) => {
                const r = el.getBoundingClientRect();
                const txt = norm(el.innerText || el.textContent);
                return {
                  idx,
                  txt,
                  cls:String(el.className || '').slice(0,100),
                  visible:r.width>0 && r.height>0 && r.top>=-150 && r.top<=window.innerHeight+200,
                  rect:{x:r.x,y:r.y,w:r.width,h:r.height}
                };
              }).filter(x => x.txt.includes('上一页') || x.txt.includes('下一页')).slice(-30)
            };
          }

          const target = candidates[0].el;
          const meta = {
            idx:candidates[0].idx,
            txt:candidates[0].txt,
            cls:candidates[0].cls,
            rect:candidates[0].rect
          };

          target.scrollIntoView({block:'center', inline:'center'});
          target.dispatchEvent(new MouseEvent('mouseover', {bubbles:true, cancelable:true, view:window}));
          target.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, view:window}));
          target.click();
          target.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, view:window}));

          return {ok:true, clicked:meta};
        }
        """
    )

    if not click_res.get("ok"):
        log("HC_NEXT_PAGE_NOT_FOUND", result=click_res)
        return click_res

    changed = False
    after_skus = []
    for _ in range(16):
        page.wait_for_timeout(1000)
        after_skus = [str(x.get("sku") or "") for x in (getattr(page, "_hz11_rank_skus", []) or [])[:8]]
        if after_skus and after_skus != before_skus:
            changed = True
            break

    if changed:
        state["high_commission_page_no"] = int(state.get("high_commission_page_no") or 1) + 1

    state["scroll_round"] = 0
    state["last_event"] = {
        "event": "HC_NEXT_PAGE",
        "ts": now(),
        "page_no": state.get("high_commission_page_no", 1),
        "changed": changed,
        "before_skus": before_skus[:5],
        "after_skus": after_skus[:5],
    }
    save_state(state)

    res = {
        "ok": True,
        "clicked": click_res.get("clicked"),
        "changed": changed,
        "page_no": state.get("high_commission_page_no", 1),
        "before_skus": before_skus[:5],
        "after_skus": after_skus[:5],
    }
    log("HC_NEXT_PAGE", result=res)
    return res

def cycle_high_commission(page, state):
    processed = 0
    units = 0

    maybe_start_refresh_round(state)
    scroll_round, info = open_high_commission(page, state)

    cards = get_high_commission_cards(page)
    fresh = []
    fresh_keys = set()

    for c in cards:
        key = str(c.get("sku") or c.get("title") or c.get("raw_text") or "").strip()
        if not key:
            continue
        key_for_state = str(c.get("sku") or ("hc_title_" + str(abs(hash(key[:120])))))
        if key_for_state in fresh_keys:
            continue
        if skip_sku(state, key_for_state):
            continue
        c["_state_key"] = key_for_state
        fresh.append(c)
        fresh_keys.add(key_for_state)

    log(
        "HC_CARDS",
        scroll_round=scroll_round,
        high_commission_page_no=state.get("high_commission_page_no", 1),
        total=len(cards),
        fresh=len(fresh),
        processed=processed,
        page_info=info,
        sample=[
            {
                "rank_index": x.get("rank_index"),
                "sku": x.get("sku"),
                "title": (x.get("title") or "")[:60],
                "price": x.get("price"),
                "rate": x.get("rate"),
                "income": x.get("income"),
            }
            for x in fresh[:5]
        ],
    )

    if not fresh:
        state["empty_streak"] = int(state.get("empty_streak") or 0) + 1
        save_state(state)

        # 关键修复：当前页没有新 SKU 时，直接点击下一页扩池，而不是反复刷新同一页。
        next_res = click_high_commission_next_page(page, state)
        write_report(state, {"last_cycle_processed": 0, "last_high_commission_next": next_res})

        if not next_res.get("ok"):
            if state["empty_streak"] >= EMPTY_STREAK_LIMIT:
                stop_required("empty_streak_limit", empty_streak=state["empty_streak"], next_result=next_res)
        return 0, len(cards)

    for c in fresh:
        if processed >= MAX_ITEMS_PER_CYCLE:
            break
        try:
            collect_high_commission_one(
                page,
                c,
                state,
                {
                    "scroll_round": scroll_round,
                    "high_commission_page_no": state.get("high_commission_page_no", 1),
                    "rank_index": c.get("rank_index"),
                    "card_id": c.get("card_id"),
                    "rect": c.get("rect"),
                },
            )
            processed += 1
            units += 1
            write_report(state, {"last_cycle_processed": processed, "last_scroll_round": scroll_round})
            time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
        except Exception as e:
            state["fail_streak"] = int(state.get("fail_streak") or 0) + 1
            state["last_event"] = {
                "event": "ITEM_FAIL",
                "ts": now(),
                "err": repr(e),
                "scroll_round": scroll_round,
                "rank_index": c.get("rank_index"),
                "title": (c.get("title") or "")[:80],
            }
            save_state(state)
            log(
                "ITEM_FAIL",
                err=repr(e),
                scroll_round=scroll_round,
                rank_index=c.get("rank_index"),
                title=(c.get("title") or "")[:80],
                fail_streak=state["fail_streak"],
            )
            close_dialog(page)
            if state["fail_streak"] >= MAX_FAIL_STREAK:
                stop_required("max_fail_streak_reached", fail_streak=state["fail_streak"], last_error=repr(e))
            time.sleep(random.uniform(20, 40))

    if processed <= 0:
        state["empty_streak"] = int(state.get("empty_streak") or 0) + 1
    else:
        state["empty_streak"] = 0
    save_state(state)

    # 当前页处理过新 SKU 后，也尝试进入下一页，避免后续 cycle 再撞同一页已见 SKU。
    next_res = click_high_commission_next_page(page, state)
    write_report(state, {"last_cycle_processed": processed, "last_high_commission_next": next_res})

    if state["empty_streak"] >= EMPTY_STREAK_LIMIT:
        stop_required("empty_streak_limit", empty_streak=state["empty_streak"], scroll_round=state.get("scroll_round"))

    return processed, max(units, len(cards))

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
    if OUT.exists() and OUT.stat().st_size > 0:
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
