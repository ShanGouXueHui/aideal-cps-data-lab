#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

BASE_PATH = Path("run/hz24_collect_increment_links.py")
UNAVAILABLE = Path("data/import/hz24_special_tab_unavailable_latest.jsonl")


def load_base():
    spec = importlib.util.spec_from_file_location("hz24_v1", str(BASE_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


base = load_base()


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    rows = base.read_jsonl(path)
    by_sku = {str(item.get("sku") or ""): item for item in rows if str(item.get("sku") or "")}
    by_sku[str(row["sku"])] = row
    data = "".join(json.dumps(by_sku[sku], ensure_ascii=False, sort_keys=True) + "\n" for sku in sorted(by_sku))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def unavailable_reason(card: dict[str, Any], result: dict[str, Any] | None = None) -> str | None:
    raw = str(card.get("raw_text") or "")
    if "已抢光" in raw:
        return "sold_out"
    if "已下架" in raw:
        return "delisted"
    if "暂不支持推广" in raw or "不可推广" in raw:
        return "not_promotable"
    if result:
        click = result.get("click") or {}
        hit = click.get("hit") or {}
        mark = click.get("mark") or {}
        matched = mark.get("matched") or {}
        root_text = str(matched.get("rootText") or "")
        if hit.get("cls") == "card-disabled" and "已抢光" in root_text:
            return "sold_out"
    return None


def save_unavailable(card: dict[str, Any], queue_row: dict[str, Any], tab: str, reason: str) -> None:
    sku = str(card.get("sku") or "")
    row = {
        "schema_version": "aideal-hz24-unavailable-sku/v1",
        "status": "unavailable",
        "reason": reason,
        "observed_at": base.now(),
        "worker_name": "hz24_special_tab_increment_v2",
        "sku": sku,
        "title": card.get("title"),
        "item_url": card.get("itemUrl") or f"https://item.jd.com/{sku}.html",
        "source_tab": tab,
        "source_tabs": queue_row.get("source_tabs") or [tab],
        "structure_sha256": queue_row.get("structure_sha256"),
    }
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    row["record_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    upsert_jsonl(UNAVAILABLE, row)


def main() -> int:
    queue_manifest = base.load_json(base.QUEUE_MANIFEST)
    queue_raw = base.QUEUE.read_bytes() if base.QUEUE.exists() else b""
    queue_rows = base.read_jsonl(base.QUEUE)
    queue_by_sku = {str(row.get("sku") or ""): row for row in queue_rows if str(row.get("sku") or "")}
    queue_sha = hashlib.sha256(queue_raw).hexdigest() if queue_raw else ""
    if not queue_rows or queue_sha != str(queue_manifest.get("data_sha256") or ""):
        report = {"ok": False, "reason": "queue_integrity_failed", "queue_count": len(queue_rows)}
        base.atomic_json(base.REPORT, report)
        return 2

    linked = {str(row.get("sku") or "") for row in base.read_jsonl(base.OUTPUT) if row.get("status") == "ok"}
    unavailable = {str(row.get("sku") or "") for row in base.read_jsonl(UNAVAILABLE) if row.get("status") == "unavailable"}
    pending = set(queue_by_sku) - linked - unavailable
    state = base.load_json(base.STATE)
    state.update({"queue_sha256": queue_sha, "queue_count": len(queue_by_sku), "updated_at": base.now(), "stop_reason": None})
    base.atomic_json(base.STATE, state)

    processed = success = unavailable_batch = failed = 0
    failures: list[dict[str, Any]] = []
    stop_reason: str | None = None
    stop_risk: list[str] = []
    consecutive_failures = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:19228", timeout=15000)
        pages = [page for context in browser.contexts for page in context.pages]
        page = next((item for item in reversed(pages) if "union.jd.com" in str(item.url or "")), pages[-1] if pages else None)
        if page is None:
            stop_reason = "browser_page_missing"
        else:
            page.set_default_timeout(20000)
            page.bring_to_front()
            initial_risk = base.risk(page)
            if initial_risk:
                stop_reason = "risk_initial"
                stop_risk = initial_risk
            else:
                for tab_index, tab in enumerate(base.TABS):
                    if processed >= base.BATCH_LIMIT or not pending or stop_reason:
                        break
                    targets = {sku for sku in pending if tab in (queue_by_sku[sku].get("source_tabs") or [])}
                    if not targets:
                        continue
                    if not base.click_tab(page, tab):
                        stop_reason = f"tab_not_found:{tab}"
                        break
                    found_risk = base.risk(page)
                    if found_risk:
                        stop_reason = "risk_after_tab"
                        stop_risk = found_risk
                        break
                    cards = base.collect_cards(page)
                    ordered = [card for card in cards if str(card.get("sku") or "") in targets]
                    base.log("TAB_READY", tab=tab, target_count=len(targets), card_count=len(cards), matched_count=len(ordered))
                    for card in ordered:
                        if processed >= base.BATCH_LIMIT or stop_reason:
                            break
                        sku = str(card.get("sku") or "")
                        reason = unavailable_reason(card)
                        if reason:
                            save_unavailable(card, queue_by_sku[sku], tab, reason)
                            pending.discard(sku)
                            unavailable.add(sku)
                            unavailable_batch += 1
                            consecutive_failures = 0
                            result = {"ok": False, "terminal": True, "reason": reason, "sku": sku}
                        else:
                            result = base.collect_one(page, card, queue_by_sku[sku], tab)
                            if result.get("ok"):
                                linked.add(sku)
                                pending.discard(sku)
                                success += 1
                                consecutive_failures = 0
                            else:
                                terminal = unavailable_reason(card, result)
                                if terminal:
                                    save_unavailable(card, queue_by_sku[sku], tab, terminal)
                                    pending.discard(sku)
                                    unavailable.add(sku)
                                    unavailable_batch += 1
                                    consecutive_failures = 0
                                    result = {"ok": False, "terminal": True, "reason": terminal, "sku": sku}
                                else:
                                    failed += 1
                                    consecutive_failures += 1
                                    failures.append({"tab": tab, **result})
                                    if str(result.get("reason") or "").startswith("risk_"):
                                        stop_reason = str(result.get("reason"))
                                        stop_risk = result.get("risk") or []
                                    elif consecutive_failures >= base.FAIL_FUSE:
                                        stop_reason = "item_fail_fuse"
                        processed += 1
                        state.update({
                            "updated_at": base.now(),
                            "last_tab": tab,
                            "last_sku": sku,
                            "linked_count": len(linked),
                            "unavailable_count": len(unavailable),
                            "pending_count": len(pending),
                            "stop_reason": stop_reason,
                        })
                        base.atomic_json(base.STATE, state)
                        base.log("ITEM_RESULT", tab=tab, sku=sku, ok=result.get("ok"), terminal=result.get("terminal"), reason=result.get("reason"), pending_count=len(pending))
                        if stop_reason:
                            break
                        time.sleep(random.uniform(base.ITEM_SLEEP_MIN, base.ITEM_SLEEP_MAX))
                    if tab_index < len(base.TABS) - 1 and pending and processed < base.BATCH_LIMIT and not stop_reason:
                        time.sleep(random.uniform(base.TAB_SLEEP_MIN, base.TAB_SLEEP_MAX))

    linked = {str(row.get("sku") or "") for row in base.read_jsonl(base.OUTPUT) if row.get("status") == "ok"}
    unavailable = {str(row.get("sku") or "") for row in base.read_jsonl(UNAVAILABLE) if row.get("status") == "unavailable"}
    pending_after = sorted(set(queue_by_sku) - linked - unavailable)
    complete = not pending_after
    state.update({"updated_at": base.now(), "linked_count": len(linked), "unavailable_count": len(unavailable), "pending_count": len(pending_after), "complete": complete, "stop_reason": stop_reason})
    base.atomic_json(base.STATE, state)
    report = {
        "schema_version": "aideal-hz24-increment-collection/v2",
        "generated_at": base.now(),
        "ok": stop_reason is None,
        "complete": complete,
        "queue_count": len(queue_by_sku),
        "success_count": len(linked & set(queue_by_sku)),
        "unavailable_count": len(unavailable & set(queue_by_sku)),
        "accounted_count": len((linked | unavailable) & set(queue_by_sku)),
        "pending_count": len(pending_after),
        "pending_samples": pending_after[:30],
        "batch_processed": processed,
        "batch_success": success,
        "batch_unavailable": unavailable_batch,
        "batch_fail": failed,
        "failures": failures[-30:],
        "stop_reason": stop_reason,
        "risk": stop_risk,
        "output_file": str(base.OUTPUT),
        "unavailable_file": str(UNAVAILABLE),
    }
    base.atomic_json(base.REPORT, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if stop_reason and str(stop_reason).startswith("risk_"):
        return 88
    return 1 if stop_reason else 0


if __name__ == "__main__":
    raise SystemExit(main())
