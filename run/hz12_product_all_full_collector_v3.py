#!/usr/bin/env python3
"""HZ12 product_all v3 runner with stronger title extraction.

This wrapper keeps the stable HZ12 base collector and overrides the candidate
collection function. It extracts titles from the visible product card text using
card-level DOM text, then maps card order to the HZ9 SKU/price/commission parser.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Dict, List

BASE_PATH = Path("run/hz12_product_all_full_collector.py")


def load_base():
    if not BASE_PATH.exists():
        raise RuntimeError(f"missing base collector: {BASE_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_base", str(BASE_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


base = load_base()

BAD_TITLE_TOKENS = [
    "预估收益", "佣金比例", "佣金", "到手价", "我要推广", "一键领链",
    "自营", "京配", "券", "促销", "定向", "百亿补贴", "好评", "店铺",
]


def normalize_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def compact_text(s: Any) -> str:
    return re.sub(r"\s+", "", str(s or "")).strip()


def extract_title_from_card_text(raw: str) -> str:
    """Extract the visible product title from JD Union card text.

    Product cards sometimes collapse into one line, for example:
    预估收益 ￥1.23 | 佣金比例10% 商品标题 ... 到手价 ￥xx 我要推广 一键领链
    The base HZ9 parser can capture SKU/price but often loses title, so we recover it here.
    """
    text = normalize_text(raw)
    if not text:
        return ""

    candidates: List[str] = []

    patterns = [
        r"佣金比例\s*\d+(?:\.\d+)?\s*%?\s*(.*?)\s*到手价",
        r"预估收益\s*[¥￥]?\s*\d+(?:\.\d+)?\s*\|?\s*佣金比例\s*\d+(?:\.\d+)?\s*%?\s*(.*?)\s*到手价",
        r"预估收益.*?佣金.*?%\s*(.*?)\s*到手价",
        r"(?:券|奖励|促销|自营|京配)\s*(.*?)\s*到手价",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            candidates.append(m.group(1))

    # Line-based fallback. Works when DOM keeps visible title as separate lines.
    for line in re.split(r"[\n\r]+", str(raw or "")):
        line = normalize_text(line)
        c = compact_text(line)
        if len(c) < 6:
            continue
        if any(tok in c for tok in BAD_TITLE_TOKENS):
            continue
        if re.fullmatch(r"[¥￥]?\d+(?:\.\d+)?", c):
            continue
        candidates.append(line)

    # Broad fallback: text before 到手价, after removing money/header fragments.
    if "到手价" in text:
        prefix = text.split("到手价", 1)[0]
        prefix = re.sub(r".*?佣金比例\s*\d+(?:\.\d+)?\s*%?", "", prefix)
        prefix = re.sub(r"预估收益\s*[¥￥]?\s*\d+(?:\.\d+)?", "", prefix)
        candidates.append(prefix)

    def clean(v: str) -> str:
        v = normalize_text(v)
        v = re.sub(r"^(自营|京配|券|奖励|促销|定向|百亿补贴|秒杀|预售|拼购|京喜自营)\s*", "", v)
        v = re.sub(r"\s*(自营|京配|券|奖励|促销|定向|百亿补贴|秒杀|预售|拼购|京喜自营)\s*$", "", v)
        v = re.sub(r"[|｜]+", " ", v)
        v = normalize_text(v)
        return v[:180]

    cleaned = []
    for cand in candidates:
        t = clean(cand)
        c = compact_text(t)
        if len(c) < 6:
            continue
        if any(tok in c for tok in ["预估收益", "佣金比例", "我要推广", "一键领链"]):
            continue
        cleaned.append(t)

    # Prefer a reasonably long title but avoid the entire card blob.
    cleaned = sorted(set(cleaned), key=lambda x: (len(compact_text(x)) > 12, -abs(len(compact_text(x)) - 38), len(compact_text(x))), reverse=True)
    return cleaned[0] if cleaned else ""


def dom_product_cards(page) -> List[Dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\s+/g, ' ').trim();
          const compact = s => (s || '').replace(/\s+/g, '').trim();
          const nodes = Array.from(document.querySelectorAll('button,a,span,div'))
            .map((el, idx) => {
              const r = el.getBoundingClientRect();
              return {
                el,
                idx,
                txt: compact(el.innerText || el.textContent),
                visible: r.width > 0 && r.height > 0 && r.top >= -240 && r.left >= -80 && r.top < window.innerHeight + 1000
              };
            })
            .filter(x => x.visible && x.txt === '一键领链');

          const out = [];
          const seen = new Set();
          for (const b of nodes) {
            let root = b.el;
            let best = null;
            for (let d = 0; d < 12 && root; d++, root = root.parentElement) {
              const r = root.getBoundingClientRect();
              const txt = norm(root.innerText || root.textContent || '');
              if (r.width >= 150 && r.height >= 130 && txt.includes('到手价') && txt.includes('佣金') && txt.includes('一键领链')) {
                best = root;
                break;
              }
            }
            if (!best) continue;
            const r = best.getBoundingClientRect();
            const key = [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)].join(':');
            if (seen.has(key)) continue;
            seen.add(key);
            const imgs = Array.from(best.querySelectorAll('img')).map(img => img.currentSrc || img.src || '').filter(Boolean);
            const links = Array.from(best.querySelectorAll('a[href]')).map(a => a.href || '').filter(Boolean);
            out.push({
              button_ord: out.length,
              rect: {x:r.x, y:r.y, w:r.width, h:r.height},
              raw_text: best.innerText || best.textContent || '',
              imageUrl: imgs[0] || '',
              itemUrl: links[0] || ''
            });
          }
          return out;
        }
        """
    )


def collect_page_candidates_v3(page) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(900)
    except Exception:
        pass

    for _step in range(base.MAX_SCROLL_STEPS):
        try:
            dom_cards = dom_product_cards(page)
        except Exception as exc:
            base.log("DOM_PRODUCT_CARDS_FAIL", err=repr(exc))
            dom_cards = []

        hz9_cards = base.unique_candidates_from_hz9(page)

        for idx, h in enumerate(hz9_cards):
            sku = str(h.get("sku") or "").strip()
            if not sku or sku in merged:
                continue

            dom = dom_cards[idx] if idx < len(dom_cards) else {}
            raw_text = dom.get("raw_text") or ""
            title = h.get("title") or extract_title_from_card_text(raw_text)
            item_url = h.get("itemUrl") or dom.get("itemUrl") or (f"https://item.jd.com/{sku}.html" if sku else "")
            image_url = base.normalize_img(h.get("imageUrl") or dom.get("imageUrl"))

            card = dict(h)
            card.update({
                "sku": sku,
                "title": title,
                "itemUrl": item_url,
                "imageUrl": image_url,
                "raw_text": raw_text[:1600],
                "button_ord": dom.get("button_ord", idx),
                "rect": dom.get("rect"),
                "scroll_y": base.current_scroll_y(page),
            })
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

    out = list(merged.values())
    base.log("TITLE_ENRICHED_CANDIDATES_V3", total=len(out), missing_title=sum(1 for x in out if not x.get("title")), sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:80]} for x in out[:8]])
    return out


base.collect_page_candidates = collect_page_candidates_v3


if __name__ == "__main__":
    base.main()
