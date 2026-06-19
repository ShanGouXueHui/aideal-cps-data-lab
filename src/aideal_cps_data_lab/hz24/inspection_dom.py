from __future__ import annotations

from typing import Any


SNAPSHOT_SCRIPT = """
() => {
  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
  const visible = element => {
    if (!(element instanceof Element)) return false;
    const style = getComputedStyle(element);
    const rectangle = element.getBoundingClientRect();
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      rectangle.width > 2 && rectangle.height > 2;
  };
  const body = document.body ? (document.body.innerText || '') : '';
  const skus = [];
  for (const anchor of Array.from(document.querySelectorAll('a[href]'))) {
    const match = String(anchor.href || '').match(/\/(\d{5,})\.html/);
    if (match && !skus.includes(match[1])) skus.push(match[1]);
  }
  const activeTabs = Array.from(document.querySelectorAll(
    '.el-radio-button.is-active, [role="radio"][aria-checked="true"], [role="tab"][aria-selected="true"]'
  )).filter(visible).map(element => normalize(element.textContent)).filter(Boolean);
  const paginations = Array.from(document.querySelectorAll('.el-pagination'))
    .filter(visible)
    .map(root => {
      const next = root.querySelector('.btn-next');
      const previous = root.querySelector('.btn-prev');
      const numbers = Array.from(root.querySelectorAll('.el-pager .number'))
        .filter(visible)
        .map(element => ({
          text: normalize(element.textContent),
          active: element.classList.contains('active'),
        }));
      const disabled = element => !element ||
        element.hasAttribute('disabled') ||
        element.classList.contains('disabled') ||
        element.getAttribute('aria-disabled') === 'true';
      return {
        text: normalize(root.textContent),
        page_numbers: numbers,
        active_page: (numbers.find(value => value.active) || {}).text || null,
        previous_disabled: disabled(previous),
        next_disabled: disabled(next),
        next_present: Boolean(next),
        previous_present: Boolean(previous),
      };
    });
  return {
    url: location.href,
    title: document.title,
    body_text: body,
    active_tabs: activeTabs,
    sku_count: skus.length,
    skus,
    one_key_count: (body.match(/一键领链/g) || []).length,
    paginations,
    document_height: Math.max(
      document.body ? document.body.scrollHeight : 0,
      document.documentElement ? document.documentElement.scrollHeight : 0
    ),
    viewport_height: innerHeight,
    scroll_y: scrollY,
  };
}
"""

SCROLL_TO_END_SCRIPT = """
() => {
  window.scrollTo(
    0,
    Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
  );
  for (const element of Array.from(document.querySelectorAll('body *'))) {
    if (!(element instanceof HTMLElement)) continue;
    const style = getComputedStyle(element);
    if (!['auto', 'scroll'].includes(style.overflowY)) continue;
    if (element.scrollHeight <= element.clientHeight + 20) continue;
    element.scrollTop = element.scrollHeight;
  }
}
"""

RESET_SCROLL_SCRIPT = "window.scrollTo(0, 0)"


def snapshot(page) -> dict[str, Any]:
    return dict(page.evaluate(SNAPSHOT_SCRIPT))


def pagination_is_single_page(
    paginations: list[dict[str, Any]],
) -> bool:
    if not paginations:
        return False
    for item in paginations:
        numbers = [
            int(value.get("text"))
            for value in item.get("page_numbers") or []
            if str(value.get("text") or "").isdigit()
        ]
        if not bool(item.get("next_disabled")):
            return False
        if numbers and max(numbers) > 1:
            return False
    return True
