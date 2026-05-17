#!/usr/bin/env python3
"""HZ12 product_all title-enriched runner.

This wrapper loads run/hz12_product_all_full_collector.py and overrides only the
candidate collection layer. The base collector already has the stable modal/click
flow; this wrapper enriches candidates with titles/image/itemUrl from the visible
product card DOM so commercial import does not receive empty titles.
"""

from __future__ import annotations

import importlib.util
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


def dom_product_cards(page) -> List[Dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\s+/g, ' ').trim();
          const compact = s => (s || '').replace(/\s+/g, '').trim();
          const buttons = Array.from(document.querySelectorAll('button,a,span,div'))
            .map((el, idx) => {
              const r = el.getBoundingClientRect();
              return {
                el,
                idx,
                txt: compact(el.innerText || el.textContent),
                visible: r.width > 0 && r.height > 0 && r.top >= -220 && r.left >= -60 && r.top < window.innerHeight + 900
              };
            })
            .filter(x => x.visible && x.txt === '一键领链');

          const out = [];
          const seen = new Set();
          for (const b of buttons) {
            let root = b.el;
            let best = null;
            for (let d = 0; d < 10 && root; d++, root = root.parentElement) {
              const r = root.getBoundingClientRect();
              const txt = norm(root.innerText || root.textContent || '');
              if (r.width >= 160 && r.height >= 140 && txt.includes('到手价') && txt.includes('佣金') && txt.includes('一键领链')) {
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
              raw_text: (best.innerText || best.textContent || '').slice(0, 1600),
              imageUrl: imgs[0] || '',
              itemUrl: links[0] || ''
            });
          }
          return out;
        }
        """
    )


def collect_page_candidates_title_enriched(page) -> List[Dict[str, Any]]:
    """Collect HZ9 SKU/price/commission and enrich each row by DOM card order."""
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
            title = h.get("title") or base.clean_title_from_card_text(raw_text)
            item_url = h.get("itemUrl") or dom.get("itemUrl") or (f"https://item.jd.com/{sku}.html" if sku else "")
            image_url = base.normalize_img(h.get("imageUrl") or dom.get("imageUrl"))
            card = dict(h)
            card.update({
                "sku": sku,
                "title": title,
                "itemUrl": item_url,
                "imageUrl": image_url,
                "raw_text": raw_text,
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
    base.log("TITLE_ENRICHED_CANDIDATES", total=len(out), sample=[{"sku": x.get("sku"), "title": (x.get("title") or "")[:60]} for x in out[:5]])
    return out


base.collect_page_candidates = collect_page_candidates_title_enriched


if __name__ == "__main__":
    base.main()
