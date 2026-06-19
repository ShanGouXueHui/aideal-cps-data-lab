from __future__ import annotations

from typing import Any

ONE_KEY_TEXT = "一键领链"


def _visible(locator) -> list[Any]:
    result: list[Any] = []
    for index in range(locator.count()):
        item = locator.nth(index)
        try:
            if item.is_visible():
                result.append(item)
        except Exception:
            continue
    return result


def _root_for_sku(page, sku: str):
    anchors = _visible(page.locator(f'a[href*="/{sku}.html"]'))
    for anchor in anchors:
        root = anchor.locator(
            "xpath=ancestor::*[.//*[normalize-space()=\"一键领链\"] "
            "and (contains(., \"到手价\") or contains(., \"佣金\"))][1]"
        )
        try:
            if root.count() and root.first.is_visible():
                return root.first
        except Exception:
            continue
    return None


def _button_metadata(button, root, sku: str) -> dict[str, Any]:
    button_box = button.bounding_box() or {}
    root_box = root.bounding_box() or {}
    try:
        root_text = root.inner_text(timeout=3000)
    except Exception:
        root_text = ""
    return {
        "method": "exact_sku_anchor_root",
        "ok": True,
        "sku": sku,
        "matched": {
            "rootText": root_text[:800],
            "rootRect": root_box,
            "buttonRect": button_box,
        },
    }


def click_card_button(page, card: dict[str, Any]) -> dict[str, Any]:
    sku = str(card.get("sku") or "")
    root = _root_for_sku(page, sku)
    if root is None:
        return {"ok": False, "sku": sku, "reason": "sku_card_not_found"}
    buttons = _visible(root.get_by_text(ONE_KEY_TEXT, exact=True))
    if not buttons:
        return {"ok": False, "sku": sku, "reason": "one_key_button_not_found"}
    button = buttons[-1]
    button.scroll_into_view_if_needed(timeout=8000)
    page.wait_for_timeout(300)
    mark = _button_metadata(button, root, sku)
    box = button.bounding_box()
    if not box:
        return {"ok": False, "sku": sku, "reason": "button_box_missing", "mark": mark}
    center = {
        "x": float(box["x"]) + float(box["width"]) / 2,
        "y": float(box["y"]) + float(box["height"]) / 2,
    }
    hit = page.evaluate(
        "point => { const element = document.elementFromPoint(point.x, point.y); "
        "return element ? {tag: element.tagName, cls: String(element.className || ''), "
        "text: String(element.innerText || element.textContent || '').trim()} : null; }",
        center,
    ) or {}
    if "card-disabled" in str(hit.get("cls") or ""):
        return {
            "ok": False,
            "sku": sku,
            "reason": "hit_test_not_target_button",
            "mark": mark,
            "hit": hit,
            "box": box,
        }
    page.mouse.move(center["x"], center["y"])
    page.mouse.click(center["x"], center["y"])
    return {"ok": True, "sku": sku, "mark": mark, "hit": hit, "box": box}
