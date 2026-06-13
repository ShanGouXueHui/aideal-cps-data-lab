#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright

PAGE_NO = int(sys.argv[1])
ROUND_ID = sys.argv[2]
REPORT = Path(sys.argv[3])
INDEX = Path("data/state/hz23_catalog_index.json")
SEEN = Path(f"data/state/hz23_round_{ROUND_ID}_seen.jsonl")
CHANGES = Path("data/history/hz23_catalog_changes.jsonl")
STRONG_RISK = ["risk_handler", "京东验证", "快速验证", "安全验证", "验证码", "滑块"]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_money(raw: str, pattern: str) -> str:
    m = re.search(pattern, raw or "")
    return m.group(1) if m else ""


def extract_title(raw: str) -> str:
    text = compact(raw)
    m = re.search(r"佣金比例\s*\d+(?:\.\d+)?%\s*(.*?)\s*到手价", text)
    if m:
        return compact(m.group(1))[:240]
    lines = [compact(x) for x in re.split(r"[\r\n]+", raw or "") if compact(x)]
    bad = ["预估收益", "佣金比例", "到手价", "我要推广", "一键领链", "去报名", "自营", "京配"]
    for line in lines:
        if len(line) >= 6 and not any(x in line for x in bad):
            return line[:240]
    return ""


def fingerprint(row: Dict[str, Any]) -> str:
    keys = ["title", "item_url", "image_url", "price", "commission_rate", "estimated_income"]
    payload = json.dumps({k: row.get(k) or "" for k in keys}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_index() -> Dict[str, Any]:
    if not INDEX.exists():
        return {"version": 1, "products": {}}
    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        if not isinstance(data.get("products"), dict):
            data["products"] = {}
        return data
    except Exception:
        return {"version": 1, "products": {}}


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    CHANGES.parent.mkdir(parents=True, exist_ok=True)
    checked_at = now()
    report: Dict[str, Any] = {
        "ts": checked_at,
        "round_id": ROUND_ID,
        "page_no": PAGE_NO,
        "ok": False,
        "scanned": 0,
        "new": 0,
        "changed": 0,
        "unchanged": 0,
    }

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:19228", timeout=15000)
        pages = [pg for ctx in browser.contexts for pg in ctx.pages]
        page = next((pg for pg in reversed(pages) if "union.jd.com" in (pg.url or "")), pages[-1])
        page.set_default_timeout(20000)
        page.bring_to_front()
        state = page.evaluate(
            """
            () => {
              const txt=document.body?(document.body.innerText||''):'';
              const pager=Array.from(document.querySelectorAll('.el-pagination')).find(p=>(p.innerText||p.textContent||'').includes('4000')) || document.querySelector('.el-pagination');
              const active=pager?Array.from(pager.querySelectorAll('.el-pager li')).find(el=>String(el.className||'').includes('active')):null;
              return {url:location.href,title:document.title,text:txt,activePageText:active?(active.innerText||active.textContent||'').trim():null,has4000:txt.includes('共 4000 条')||txt.includes('共4000条')};
            }
            """
        )
        hay = "\n".join([state.get("url") or "", state.get("title") or "", state.get("text") or ""])
        risk = [x for x in STRONG_RISK if x in hay]
        report["page_state"] = {k: state.get(k) for k in ["url", "title", "activePageText", "has4000"]}
        report["risk"] = risk
        if risk:
            report["reason"] = "risk"
        elif not state.get("has4000") or str(state.get("activePageText") or "") != str(PAGE_NO):
            report["reason"] = "page_not_ready"
        else:
            cards: List[Dict[str, Any]] = page.evaluate(
                """
                () => {
                  const compact=s=>(s||'').replace(/\s+/g,'').trim();
                  const buttons=Array.from(document.querySelectorAll('button,a,span,div')).filter(el=>compact(el.innerText||el.textContent)==='一键领链');
                  const out=[]; const seen=new Set();
                  for (const btn of buttons) {
                    let cur=btn,root=null;
                    for (let d=0;d<16&&cur;d++,cur=cur.parentElement) {
                      const r=cur.getBoundingClientRect(); const raw=cur.innerText||cur.textContent||''; const c=compact(raw);
                      if (r.width>=160&&r.height>=100&&c.includes('一键领链')&&(c.includes('到手价')||c.includes('佣金'))) {root=cur;break;}
                    }
                    if (!root) continue;
                    const links=Array.from(root.querySelectorAll('a[href]')).map(a=>a.href||'');
                    const item=links.find(h=>/item\.jd\.com\/(\d+)\.html/.test(h));
                    const m=item&&item.match(/item\.jd\.com\/(\d+)\.html/); const sku=m?m[1]:'';
                    if (!sku||seen.has(sku)) continue; seen.add(sku);
                    const imgs=Array.from(root.querySelectorAll('img')).map(img=>img.currentSrc||img.src||'').filter(Boolean);
                    out.push({sku,item_url:item,image_url:imgs[0]||'',raw_text:root.innerText||root.textContent||''});
                  }
                  return out;
                }
                """
            )
            index = load_index()
            products = index.setdefault("products", {})
            seen_rows: List[Dict[str, Any]] = []
            change_rows: List[Dict[str, Any]] = []
            for card in cards:
                sku = str(card.get("sku") or "").strip()
                raw = str(card.get("raw_text") or "")
                if not sku.isdigit():
                    continue
                row = {
                    "sku": sku,
                    "title": extract_title(raw),
                    "item_url": card.get("item_url") or f"https://item.jd.com/{sku}.html",
                    "image_url": card.get("image_url") or "",
                    "price": parse_money(raw, r"到手价\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)"),
                    "commission_rate": parse_money(raw, r"佣金比例\s*([0-9]+(?:\.[0-9]+)?%)"),
                    "estimated_income": parse_money(raw, r"预估收益\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)"),
                    "page_no": PAGE_NO,
                    "last_checked_at": checked_at,
                    "last_seen_at": checked_at,
                    "last_round_id": ROUND_ID,
                    "missing_rounds": 0,
                    "active": True,
                }
                row["fingerprint"] = fingerprint(row)
                old = products.get(sku)
                if old is None:
                    row["first_seen_at"] = checked_at
                    row["change_count"] = 0
                    products[sku] = row
                    report["new"] += 1
                else:
                    row["first_seen_at"] = old.get("first_seen_at") or checked_at
                    changed = old.get("fingerprint") != row["fingerprint"]
                    row["change_count"] = int(old.get("change_count") or 0) + (1 if changed else 0)
                    products[sku] = row
                    if changed:
                        report["changed"] += 1
                        change_rows.append({"ts": checked_at, "round_id": ROUND_ID, "page_no": PAGE_NO, "sku": sku, "before": {k: old.get(k) for k in ["title", "price", "commission_rate", "estimated_income", "image_url"]}, "after": {k: row.get(k) for k in ["title", "price", "commission_rate", "estimated_income", "image_url"]}})
                    else:
                        report["unchanged"] += 1
                seen_rows.append({"sku": sku, "page_no": PAGE_NO, "ts": checked_at})
            report["scanned"] = len(seen_rows)
            index["updated_at"] = checked_at
            index["last_round_id"] = ROUND_ID
            atomic_write(INDEX, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True))
            with SEEN.open("a", encoding="utf-8") as f:
                for row in seen_rows:
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            if change_rows:
                with CHANGES.open("a", encoding="utf-8") as f:
                    for row in change_rows:
                        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            report["ok"] = len(seen_rows) >= 55
            report["reason"] = None if report["ok"] else "insufficient_cards"

    atomic_write(REPORT, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps({"event": "HZ23_SCAN_DONE", **report}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
