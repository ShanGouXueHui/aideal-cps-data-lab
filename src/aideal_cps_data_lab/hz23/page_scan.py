from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from aideal_cps_data_lab.hz24.jd_page import JDPageAdapter
from aideal_cps_data_lab.hz24.settings import HZ24Settings, load_settings

PAGE_STATE_SCRIPT = """
() => {
  const text = document.body ? (document.body.innerText || '') : '';
  const pagers = Array.from(document.querySelectorAll('.el-pagination'));
  const pager = pagers.find(item => (item.innerText || item.textContent || '').includes('4000'))
    || document.querySelector('.el-pagination');
  const active = pager
    ? Array.from(pager.querySelectorAll('.el-pager li')).find(
        item => String(item.className || '').includes('active')
      )
    : null;
  return {
    url: location.href,
    title: document.title,
    text,
    activePageText: active ? (active.innerText || active.textContent || '').trim() : null,
    has4000: text.includes('共 4000 条') || text.includes('共4000条')
  };
}
"""


@dataclass(frozen=True, slots=True)
class ScanPaths:
    report: Path
    index: Path
    seen: Path
    changes: Path


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fingerprint(row: dict[str, Any]) -> str:
    keys = (
        "title",
        "item_url",
        "image_url",
        "price",
        "commission_rate",
        "estimated_income",
    )
    payload = json.dumps(
        {key: row.get(key) or "" for key in keys},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "products": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "products": {}}
    if not isinstance(value, dict):
        return {"version": 1, "products": {}}
    if not isinstance(value.get("products"), dict):
        value["products"] = {}
    return value


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def initial_report(round_id: str, page_no: int, checked_at: str) -> dict[str, Any]:
    return {
        "ts": checked_at,
        "round_id": round_id,
        "page_no": page_no,
        "ok": False,
        "scanned": 0,
        "new": 0,
        "changed": 0,
        "unchanged": 0,
    }


def page_ready(
    page,
    adapter: JDPageAdapter,
    page_no: int,
    report: dict[str, Any],
) -> bool:
    state = page.evaluate(PAGE_STATE_SCRIPT)
    risk = adapter.risk(page)
    report["page_state"] = {
        key: state.get(key)
        for key in ("url", "title", "activePageText", "has4000")
    }
    report["risk"] = risk
    if risk:
        report["reason"] = "risk"
        return False
    if not state.get("has4000"):
        report["reason"] = "page_not_ready"
        return False
    if str(state.get("activePageText") or "") != str(page_no):
        report["reason"] = "page_not_ready"
        return False
    return True


def product_row(
    card: dict[str, Any],
    page_no: int,
    round_id: str,
    checked_at: str,
    settings: HZ24Settings,
) -> dict[str, Any] | None:
    sku = str(card.get("sku") or "").strip()
    if not sku.isdigit():
        return None
    row = {
        "sku": sku,
        "title": card.get("title") or "",
        "item_url": card.get("itemUrl")
        or f"{settings.browser.item_scheme}://{settings.browser.item_host}/{sku}.html",
        "image_url": card.get("imageUrl") or "",
        "price": card.get("price") or "",
        "commission_rate": card.get("rate") or "",
        "estimated_income": card.get("income") or "",
        "page_no": page_no,
        "last_checked_at": checked_at,
        "last_seen_at": checked_at,
        "last_round_id": round_id,
        "missing_rounds": 0,
        "active": True,
    }
    row["fingerprint"] = fingerprint(row)
    return row


def apply_card(
    row: dict[str, Any],
    products: dict[str, Any],
    report: dict[str, Any],
    round_id: str,
    page_no: int,
    checked_at: str,
) -> dict[str, Any] | None:
    sku = str(row["sku"])
    old = products.get(sku)
    if old is None:
        row["first_seen_at"] = checked_at
        row["change_count"] = 0
        products[sku] = row
        report["new"] += 1
        return None
    row["first_seen_at"] = old.get("first_seen_at") or checked_at
    changed = old.get("fingerprint") != row["fingerprint"]
    row["change_count"] = int(old.get("change_count") or 0) + int(changed)
    products[sku] = row
    if not changed:
        report["unchanged"] += 1
        return None
    report["changed"] += 1
    fields = ("title", "price", "commission_rate", "estimated_income", "image_url")
    return {
        "ts": checked_at,
        "round_id": round_id,
        "page_no": page_no,
        "sku": sku,
        "before": {key: old.get(key) for key in fields},
        "after": {key: row.get(key) for key in fields},
    }


def persist_cards(
    cards: list[dict[str, Any]],
    paths: ScanPaths,
    page_no: int,
    round_id: str,
    checked_at: str,
    settings: HZ24Settings,
    report: dict[str, Any],
) -> None:
    index = load_index(paths.index)
    products = index.setdefault("products", {})
    seen_rows: list[dict[str, Any]] = []
    change_rows: list[dict[str, Any]] = []
    for card in cards:
        row = product_row(card, page_no, round_id, checked_at, settings)
        if row is None:
            continue
        change = apply_card(row, products, report, round_id, page_no, checked_at)
        if change:
            change_rows.append(change)
        seen_rows.append({"sku": row["sku"], "page_no": page_no, "ts": checked_at})
    report["scanned"] = len(seen_rows)
    report["ok"] = len(seen_rows) >= 55
    report["reason"] = None if report["ok"] else "insufficient_cards"
    index["updated_at"] = checked_at
    index["last_round_id"] = round_id
    atomic_text(
        paths.index,
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
    )
    append_jsonl(paths.seen, seen_rows)
    append_jsonl(paths.changes, change_rows)


def run_scan(
    page_no: int,
    round_id: str,
    paths: ScanPaths,
    settings: HZ24Settings | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings()
    checked_at = timestamp()
    report = initial_report(round_id, page_no, checked_at)
    adapter = JDPageAdapter(settings)
    with sync_playwright() as playwright:
        page = adapter.connect_page(playwright)
        if page is None:
            report["reason"] = "browser_page_missing"
        elif page_ready(page, adapter, page_no, report):
            persist_cards(
                adapter.collect_cards(page),
                paths,
                page_no,
                round_id,
                checked_at,
                settings,
                report,
            )
    atomic_text(
        paths.report,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("page_no", type=int)
    parser.add_argument("round_id")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    paths = ScanPaths(
        report=args.report,
        index=Path("data/state/hz23_catalog_index.json"),
        seen=Path(f"data/state/hz23_round_{args.round_id}_seen.jsonl"),
        changes=Path("data/history/hz23_catalog_changes.jsonl"),
    )
    report = run_scan(args.page_no, args.round_id, paths)
    print(
        json.dumps(
            {"event": "HZ23_SCAN_DONE", **report},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("ok") else 1
