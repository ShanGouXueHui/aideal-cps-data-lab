from __future__ import annotations

import importlib.util
from typing import Any
from urllib.parse import urlparse

from .browser_contract import (
    BODY_TEXT_SCRIPT,
    CARD_COLLECTION_SCRIPT,
    COMMISSION_RATE_PATTERN,
    ESTIMATED_INCOME_PATTERN,
    PRICE_PATTERN,
    TAB_SCORE_SCRIPT,
)
from .settings import HZ24Settings


class JDPageAdapter:
    def __init__(self, settings: HZ24Settings) -> None:
        self.settings = settings
        self.hz21 = self._load_hz21()

    def _load_hz21(self):
        path = self.settings.contracts.hz21_adapter
        spec = importlib.util.spec_from_file_location("hz21_for_hz24", str(path))
        if spec is None or spec.loader is None:
            raise RuntimeError("HZ21 adapter load failed")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def connect_page(self, playwright):
        browser = playwright.chromium.connect_over_cdp(
            self.settings.browser.cdp_endpoint,
            timeout=self.settings.browser.connect_timeout_ms,
        )
        pages = [page for context in browser.contexts for page in context.pages]
        page = next(
            (
                item
                for item in reversed(pages)
                if self.settings.browser.page_host in str(item.url or "")
            ),
            pages[-1] if pages else None,
        )
        if page is None:
            return None
        page.set_default_timeout(self.settings.browser.default_timeout_ms)
        page.bring_to_front()
        return page

    def risk(self, page) -> list[str]:
        try:
            body = page.evaluate(BODY_TEXT_SCRIPT)
        except Exception:
            body = ""
        haystack = "\n".join([str(page.url or ""), str(body)])
        return [
            marker
            for marker in self.settings.browser.risk_markers
            if marker in haystack
        ]

    def trusted_short_url(self, value: Any) -> bool:
        try:
            parsed = urlparse(str(value or "").strip())
        except Exception:
            return False
        return (
            parsed.scheme == self.settings.browser.trusted_link_scheme
            and parsed.hostname == self.settings.browser.trusted_link_host
        )

    def click_tab(self, page, name: str) -> bool:
        locator = page.get_by_text(name, exact=True)
        candidates: list[tuple[int, int]] = []
        for index in range(locator.count()):
            item = locator.nth(index)
            try:
                if not item.is_visible():
                    continue
                candidates.append((int(item.evaluate(TAB_SCORE_SCRIPT)), index))
            except Exception:
                continue
        if not candidates:
            return False
        candidates.sort(reverse=True)
        target = locator.nth(candidates[0][1])
        target.scroll_into_view_if_needed(
            timeout=self.settings.browser.tab_click_timeout_ms
        )
        target.click(timeout=self.settings.browser.tab_click_timeout_ms)
        page.wait_for_timeout(self.settings.browser.tab_settle_ms)
        return True

    def collect_cards(self, page) -> list[dict[str, Any]]:
        cards = page.evaluate(CARD_COLLECTION_SCRIPT)
        result: list[dict[str, Any]] = []
        for card in cards:
            raw = str(card.get("raw_text") or "")
            card["title"] = self.hz21.extract_title(raw)
            card["price"] = self.hz21.parse_money(raw, PRICE_PATTERN)
            card["rate"] = self.hz21.parse_money(raw, COMMISSION_RATE_PATTERN)
            card["income"] = self.hz21.parse_money(
                raw,
                ESTIMATED_INCOME_PATTERN,
            )
            result.append(card)
        return result

    def close_dialog(self, page) -> None:
        try:
            self.hz21.base.close_dialog(page)
        except Exception:
            return

    def click_card(self, page, card: dict[str, Any]) -> dict[str, Any]:
        return dict(self.hz21.click_card(page, card))

    def parse_modal(self, page) -> dict[str, Any]:
        return dict(self.hz21.parse_modal(page))

    def link_dates(self):
        return self.hz21.link_dates()

    def normalize_image(self, value: Any) -> Any:
        return self.hz21.base.normalize_img(value)
