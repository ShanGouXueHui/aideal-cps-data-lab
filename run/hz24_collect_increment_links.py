#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HZ21_PATH = Path("run/hz21_strict_card_dom_recover_page.py")
QUEUE = Path("data/export/hz24_special_tab_increment_latest.jsonl")
QUEUE_MANIFEST = Path("data/export/hz24_special_tab_increment_manifest.json")
OUTPUT = Path("data/import/hz24_special_tab_links_latest.jsonl")
STATE = Path("run/hz24_increment_collection_state.json")
REPORT = Path("reports/hz24_increment_collection_latest.json")
TABS = ["超补爆品", "限量高佣", "秒杀专区", "定向高佣", "粉丝爱买"]
RISK_MARKERS = ["risk_handler", "京东验证", "快速验证", "安全验证", "验证码", "滑块"]
BATCH_LIMIT = int(os.environ.get("HZ24_BATCH_LIMIT", "35"))
WAIT_SECONDS = int(os.environ.get("HZ24_WAIT_SECONDS", "12"))
ITEM_SLEEP_MIN = float(os.environ.get("HZ24_ITEM_SLEEP_MIN", "4"))
ITEM_SLEEP_MAX = float(os.environ.get("HZ24_ITEM_SLEEP_MAX", "8"))
TAB_SLEEP_MIN = float(os.environ.get("HZ24_TAB_SLEEP_MIN", "120"))
TAB_SLEEP_MAX = float(os.environ.get("HZ24_TAB_SLEEP_MAX", "240"))
FAIL_FUSE = int(os.environ.get("HZ24_FAIL_FUSE", "5"))


def load_hz21():
    spec = importlib.util.spec_from_file_location("hz21_for_hz24", str(HZ21_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hz21 = load_hz21()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(event: str, **data: Any) -> None:
    print(json.dumps({"ts": now(), "worker": "hz24_increment", "event": event, **data}, ensure_ascii=False, sort_keys=True), flush=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def upsert_output(row: dict[str, Any]) -> None:
    rows = read_jsonl(OUTPUT)
    by_sku = {str(item.get("sku") or ""): item for item in rows if str(item.get("sku") or "")}
    by_sku[str(row["sku"])] = row
    data = "".join(json.dumps(by_sku[sku], ensure_ascii=False, sort_keys=True) + "\n" for sku in sorted(by_sku))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(OUTPUT)


def risk(page) -> list[str]:
    try:
        body = page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception:
        body = ""
    haystack = "\n".join([str(page.url or ""), str(body)])
    return [marker for marker in RISK_MARKERS if marker in haystack]


def trusted_short_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname == "u.jd.com"


def click_tab(page, name: str) -> bool:
    locator = page.get_by_text(name, exact=True)
    candidates: list[tuple[int, int]] = []
    for index in range(locator.count()):
        item = locator.nth(index)
        try:
            if not item.is_visible():
                continue
            score = item.evaluate("""
                el => {
                  const cls = typeof el.className === 'string' ? el.className : '';
                  let score = 0;
                  if (el.matches('[role="radio"], label.el-radio-button, [role="tab"]')) score += 30;
                  if (/radio|tab/i.test(cls)) score += 20;
                  if (getComputedStyle(el).cursor === 'pointer') score += 10;
                  return score;
                }
            """)
            candidates.append((int(score), index))
        except Exception:
            continue
    if not candidates:
        return False
    candidates.sort(reverse=True)
    target = locator.nth(candidates[0][1])
    target.scroll_into_view_if_needed(timeout=5000)
    target.click(timeout=8000)
    page.wait_for_timeout(5000)
    return True


def collect_cards(page) -> list[dict[str, Any]]:
    cards = page.evaluate("""
        () => {
          const compact = s => (s || '').replace(/\s+/g, '').trim();
          const buttons = Array.from(document.querySelectorAll('button,a,span,div'))
            .filter(el => compact(el.innerText || el.textContent) === '一键领链');
          const out = [], seen = new Set();
          for (const button of buttons) {
            let current = button, root = null;
            for (let depth = 0; depth < 16 && current; depth += 1, current = current.parentElement) {
              const rect = current.getBoundingClientRect();
              const raw = current.innerText || current.textContent || '';
              const text = compact(raw);
              if (rect.width >= 160 && rect.height >= 100 && text.includes('一键领链') && (text.includes('到手价') || text.includes('佣金'))) {
                root = current; break;
              }
            }
            if (!root) continue;
            const links = Array.from(root.querySelectorAll('a[href]')).map(a => a.href || '');
            const itemUrl = links.find(href => /item\.jd\.com\/(\d+)\.html/.test(href));
            const match = itemUrl && itemUrl.match(/item\.jd\.com\/(\d+)\.html/);
            const sku = match ? match[1] : '';
            if (!sku || seen.has(sku)) continue;
            seen.add(sku);
            const images = Array.from(root.querySelectorAll('img')).map(img => img.currentSrc || img.src || '').filter(Boolean);
            out.push({sku, itemUrl, imageUrl: images[0] || '', raw_text: root.innerText || root.textContent || ''});
          }
          return out;
        }
    """)
    result: list[dict[str, Any]] = []
    for card in cards:
        raw = str(card.get("raw_text") or "")
        card["title"] = hz21.extract_title(raw)
        card["price"] = hz21.parse_money(raw, r"到手价\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)")
        card["rate"] = hz21.parse_money(raw, r"佣金比例\s*([0-9]+(?:\.[0-9]+)?%)")
        card["income"] = hz21.parse_money(raw, r"预估收益\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)")
        result.append(card)
    return result


def record_hash(row: dict[str, Any]) -> str:
    fields = {
        key: row.get(key)
        for key in [
            "sku", "title", "item_url", "image_url", "price", "commission_rate",
            "estimated_income", "short_url", "long_url", "source_tab", "source_tabs",
        ]
    }
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def collect_one(page, card: dict[str, Any], queue_row: dict[str, Any], tab: str) -> dict[str, Any]:
    sku = str(card.get("sku") or "")
    if risk(page):
        return {"ok": False, "sku": sku, "reason": "risk_before", "risk": risk(page)}
    try:
        try:
            hz21.base.close_dialog(page)
        except Exception:
            pass
        click = hz21.click_card(page, card)
        if not click.get("ok"):
            return {"ok": False, "sku": sku, "reason": "click_failed", "click": click}
        modal: dict[str, Any] = {}
        for _ in range(WAIT_SECONDS):
            page.wait_for_timeout(1000)
            if risk(page):
                return {"ok": False, "sku": sku, "reason": "risk_after_click", "risk": risk(page)}
            modal = dict(hz21.parse_modal(page))
            if modal.get("short_url"):
                break
        try:
            hz21.base.close_dialog(page)
        except Exception:
            pass
        if not trusted_short_url(modal.get("short_url")):
            return {"ok": False, "sku": sku, "reason": "trusted_short_url_missing"}
        created, expire, refresh = hz21.link_dates()
        row: dict[str, Any] = {
            "schema_version": "aideal-hz24-special-tab-link/v1",
            "status": "ok",
            "ts": now(),
            "worker_name": "hz24_special_tab_increment",
            "source_menu": f"商品推广/{tab}",
            "source_tab": tab,
            "source_tabs": queue_row.get("source_tabs") or [tab],
            "menu_mode": "hz24_special_tab_increment",
            "promotion_mode": "hz24_exact_sku_mouse_onekey",
            "sku": sku,
            "title": card.get("title"),
            "item_url": card.get("itemUrl") or f"https://item.jd.com/{sku}.html",
            "image_url": hz21.base.normalize_img(card.get("imageUrl")),
            "price": card.get("price"),
            "commission_rate": card.get("rate"),
            "estimated_income": card.get("income"),
            "short_url": modal.get("short_url"),
            "long_url": modal.get("long_url"),
            "qr_url": modal.get("qr_url"),
            "jd_command": modal.get("jd_command"),
            "link_created_at": created,
            "link_expire_at": expire,
            "link_expire_days": 60,
            "refresh_due_at": refresh,
            "refresh_after_days": 40,
            "refresh_before_expiry_days": 20,
            "structure_sha256": queue_row.get("structure_sha256"),
            "click_result": click,
        }
        row["record_sha256"] = record_hash(row)
        upsert_output(row)
        return {"ok": True, "sku": sku, "short_url": row["short_url"], "record_sha256": row["record_sha256"]}
    except Exception as exc:
        try:
            hz21.base.close_dialog(page)
        except Exception:
            pass
        return {"ok": False, "sku": sku, "reason": "exception", "error": repr(exc)}


def main() -> int:
    queue_manifest = load_json(QUEUE_MANIFEST)
    queue_raw = QUEUE.read_bytes() if QUEUE.exists() else b""
    queue_rows = read_jsonl(QUEUE)
    queue_by_sku = {str(row.get("sku") or ""): row for row in queue_rows if str(row.get("sku") or "")}
    queue_sha256 = hashlib.sha256(queue_raw).hexdigest() if queue_raw else ""
    if not queue_rows or queue_sha256 != str(queue_manifest.get("data_sha256") or ""):
        report = {"ok": False, "reason": "queue_integrity_failed", "queue_rows": len(queue_rows), "queue_sha256": queue_sha256}
        atomic_json(REPORT, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 2

    existing = {str(row.get("sku") or ""): row for row in read_jsonl(OUTPUT) if row.get("status") == "ok"}
    pending = set(queue_by_sku) - set(existing)
    state = load_json(STATE)
    state.update({
        "schema_version": "aideal-hz24-increment-state/v1",
        "queue_sha256": queue_sha256,
        "queue_count": len(queue_by_sku),
        "started_at": state.get("started_at") or now(),
        "updated_at": now(),
        "stop_reason": None,
    })
    atomic_json(STATE, state)

    batch_success = 0
    batch_fail = 0
    processed = 0
    failures: list[dict[str, Any]] = []
    stop_reason: str | None = None
    stop_risk: list[str] = []

    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:19228", timeout=15000)
        pages = [page for context in browser.contexts for page in context.pages]
        page = next((item for item in reversed(pages) if "union.jd.com" in str(item.url or "")), pages[-1] if pages else None)
        if page is None:
            stop_reason = "browser_page_missing"
        else:
            page.set_default_timeout(20000)
            page.bring_to_front()
            initial_risk = risk(page)
            if initial_risk:
                stop_reason = "risk_initial"
                stop_risk = initial_risk
            else:
                consecutive_failures = 0
                for tab_index, tab in enumerate(TABS):
                    if processed >= BATCH_LIMIT or not pending or stop_reason:
                        break
                    tab_targets = {sku for sku in pending if tab in (queue_by_sku[sku].get("source_tabs") or [])}
                    if not tab_targets:
                        continue
                    if not click_tab(page, tab):
                        stop_reason = f"tab_not_found:{tab}"
                        break
                    tab_risk = risk(page)
                    if tab_risk:
                        stop_reason = "risk_after_tab"
                        stop_risk = tab_risk
                        break
                    cards = collect_cards(page)
                    cards_by_sku = {str(card.get("sku") or ""): card for card in cards}
                    ordered = [card for card in cards if str(card.get("sku") or "") in tab_targets]
                    log("TAB_READY", tab=tab, target_count=len(tab_targets), card_count=len(cards), matched_count=len(ordered))
                    for card in ordered:
                        if processed >= BATCH_LIMIT or stop_reason:
                            break
                        sku = str(card.get("sku") or "")
                        result = collect_one(page, card, queue_by_sku[sku], tab)
                        processed += 1
                        if result.get("ok"):
                            batch_success += 1
                            consecutive_failures = 0
                            pending.discard(sku)
                        else:
                            batch_fail += 1
                            consecutive_failures += 1
                            failures.append({"tab": tab, **result})
                            if str(result.get("reason") or "").startswith("risk_"):
                                stop_reason = str(result.get("reason"))
                                stop_risk = result.get("risk") or []
                            elif consecutive_failures >= FAIL_FUSE:
                                stop_reason = "item_fail_fuse"
                        state.update({
                            "updated_at": now(),
                            "last_tab": tab,
                            "last_sku": sku,
                            "success_count": len(queue_by_sku) - len(pending),
                            "pending_count": len(pending),
                            "stop_reason": stop_reason,
                        })
                        atomic_json(STATE, state)
                        log("ITEM_RESULT", tab=tab, sku=sku, ok=result.get("ok"), reason=result.get("reason"), pending_count=len(pending))
                        if stop_reason:
                            break
                        time.sleep(random.uniform(ITEM_SLEEP_MIN, ITEM_SLEEP_MAX))
                    if tab_index < len(TABS) - 1 and pending and processed < BATCH_LIMIT and not stop_reason:
                        time.sleep(random.uniform(TAB_SLEEP_MIN, TAB_SLEEP_MAX))

    output_rows = read_jsonl(OUTPUT)
    success_skus = {str(row.get("sku") or "") for row in output_rows if row.get("status") == "ok"}
    pending_after = sorted(set(queue_by_sku) - success_skus)
    complete = not pending_after
    state.update({
        "updated_at": now(),
        "success_count": len(success_skus & set(queue_by_sku)),
        "pending_count": len(pending_after),
        "complete": complete,
        "stop_reason": stop_reason,
    })
    atomic_json(STATE, state)
    report = {
        "schema_version": "aideal-hz24-increment-collection/v1",
        "generated_at": now(),
        "ok": stop_reason is None,
        "complete": complete,
        "queue_count": len(queue_by_sku),
        "success_count": len(success_skus & set(queue_by_sku)),
        "pending_count": len(pending_after),
        "pending_samples": pending_after[:30],
        "batch_limit": BATCH_LIMIT,
        "batch_processed": processed,
        "batch_success": batch_success,
        "batch_fail": batch_fail,
        "failures": failures[-30:],
        "stop_reason": stop_reason,
        "risk": stop_risk,
        "output_file": str(OUTPUT),
        "state_file": str(STATE),
    }
    atomic_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if stop_reason and str(stop_reason).startswith("risk_"):
        return 88
    if stop_reason:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
