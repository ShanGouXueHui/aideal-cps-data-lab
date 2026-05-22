#!/usr/bin/env python3
"""HZ12 product_all v8 runner.

Purpose:
- Keep v7 strict-title commercial quality.
- Re-locate the 下一页 control immediately before every page turn.
- Scroll to the bottom, re-query exact text elements, choose the visible bottom-most
  small control, and click its fresh coordinates. This avoids stale/shifted button
  positions after SPA pagination and page re-layout.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

V7_PATH = Path("run/hz12_product_all_full_collector_v7.py")


def load_v7():
    if not V7_PATH.exists():
        raise RuntimeError(f"missing v7 runner: {V7_PATH}")
    spec = importlib.util.spec_from_file_location("hz12_v7", str(V7_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v7 = load_v7()
base = v7.base


def current_page_skus(page) -> List[str]:
    try:
        cards = base.collect_page_candidates(page)
    except Exception:
        cards = []
    out: List[str] = []
    for card in cards:
        sku = str(card.get("sku") or "").strip()
        if sku and sku not in out:
            out.append(sku)
    return out[:20]


def fresh_next_controls(page) -> List[Dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\s+/g, '').trim();
          const pathOf = el => {
            const parts = [];
            let cur = el;
            for (let i = 0; cur && cur.nodeType === 1 && i < 7; i++, cur = cur.parentElement) {
              let part = cur.tagName.toLowerCase();
              if (cur.id) part += '#' + cur.id;
              const cls = String(cur.className || '').trim().split(/\s+/).filter(Boolean).slice(0, 4).join('.');
              if (cls) part += '.' + cls;
              parts.push(part);
            }
            return parts.join(' < ');
          };
          const controls = Array.from(document.querySelectorAll('button,a,span,div,li'))
            .map((el, idx) => {
              const r = el.getBoundingClientRect();
              const txt = norm(el.innerText || el.textContent);
              const cls = String(el.className || '');
              const aria = String(el.getAttribute('aria-label') || '');
              const disabled = !!el.disabled || el.getAttribute('disabled') !== null || cls.includes('disabled') || cls.includes('is-disabled') || el.getAttribute('aria-disabled') === 'true';
              const visible = r.width > 0 && r.height > 0 && r.top >= -80 && r.left >= -80 && r.top <= window.innerHeight + 120;
              const small = r.width <= 160 && r.height <= 90;
              return {
                idx, text: txt, tag: el.tagName.toLowerCase(), cls: cls.slice(0,160), aria,
                disabled, visible, small,
                rect: {x:r.x, y:r.y, w:r.width, h:r.height, cx:r.x + r.width/2, cy:r.y + r.height/2},
                path: pathOf(el)
              };
            })
            .filter(x => x.visible && x.small && !x.disabled && x.text === '下一页')
            .sort((a,b) => (b.rect.y - a.rect.y) || (b.rect.x - a.rect.x));
          return controls;
        }
        """
    )


def click_next_by_reposition(page, state: Dict[str, Any]) -> Dict[str, Any]:
    before = current_page_skus(page)[:8]
    attempts: List[Dict[str, Any]] = []

    for attempt in range(1, 4):
        try:
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(800 + 250 * attempt)
        except Exception:
            pass

        controls = []
        try:
            controls = fresh_next_controls(page)
        except Exception as exc:
            attempts.append({"attempt": attempt, "ok": False, "stage": "fresh_next_controls", "err": repr(exc)})

        if controls:
            target = controls[0]
            try:
                page.mouse.move(float(target["rect"]["cx"]), float(target["rect"]["cy"]))
                page.wait_for_timeout(150)
                page.mouse.click(float(target["rect"]["cx"]), float(target["rect"]["cy"]))
                attempts.append({"attempt": attempt, "ok": True, "method": "fresh_bbox_mouse_click", "target": target})
            except Exception as exc:
                attempts.append({"attempt": attempt, "ok": False, "method": "fresh_bbox_mouse_click", "target": target, "err": repr(exc)})
                continue
        else:
            # Fallback to Playwright exact text last, but after re-scrolling and re-locating.
            try:
                locator = page.get_by_text("下一页", exact=True)
                count = locator.count()
                if count <= 0:
                    attempts.append({"attempt": attempt, "ok": False, "method": "exact_text_last", "reason": "count_zero"})
                    continue
                locator.last.scroll_into_view_if_needed(timeout=4000)
                page.wait_for_timeout(200)
                locator.last.click(timeout=8000)
                attempts.append({"attempt": attempt, "ok": True, "method": "exact_text_last", "count": count})
            except Exception as exc:
                attempts.append({"attempt": attempt, "ok": False, "method": "exact_text_last", "err": repr(exc)})
                continue

        changed = False
        after: List[str] = []
        for _ in range(24):
            page.wait_for_timeout(1000)
            after = current_page_skus(page)[:8]
            if after and after != before:
                changed = True
                break
        if changed:
            state["current_page_no"] = int(state.get("current_page_no") or 1) + 1
            base.save_state(state)
            result = {
                "ok": True,
                "changed": True,
                "page_no": state.get("current_page_no"),
                "before_skus": before[:5],
                "after_skus": after[:5],
                "attempts": attempts,
            }
            base.log("PRODUCT_NEXT_REPOSITION", result=result)
            return result
        attempts[-1]["changed"] = False
        attempts[-1]["after_skus"] = after[:5]

    result = {
        "ok": True,
        "changed": False,
        "page_no": state.get("current_page_no"),
        "before_skus": before[:5],
        "attempts": attempts,
    }
    base.log("PRODUCT_NEXT_REPOSITION", result=result)
    return result


# Monkey-patch v7 full_cycle dependency. full_cycle_v7 resolves the global name from v7 module.
v7.click_next_by_exact_text = click_next_by_reposition
base.full_cycle = v7.full_cycle_v7


if __name__ == "__main__":
    base.main()
