from __future__ import annotations

import re
from datetime import datetime, timedelta
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
from .card_actions import click_card_button
from .modal_parser import close_dialog, parse_modal
from .settings import HZ24Settings

BAD_TITLE_TOKENS = (
    "预估收益",
    "佣金比例",
    "佣金",
    "到手价",
    "我要推广",
    "一键领链",
    "自营",
    "京配",
    "券",
    "促销",
    "定向",
    "百亿补贴",
    "好评",
)


class JDPageAdapter:
    def __init__(self, settings: HZ24Settings) -> None:
        self.settings = settings

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
        score_options = {
            "roleSelector": self.settings.browser.tab_role_selector,
            "classPattern": self.settings.browser.tab_class_pattern,
        }
        for index in range(locator.count()):
            item = locator.nth(index)
            try:
                if not item.is_visible():
                    continue
                score = int(item.evaluate(TAB_SCORE_SCRIPT, score_options))
                candidates.append((score, index))
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

    @staticmethod
    def _title(raw: str) -> str:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in lines:
            compact = re.sub(r"\s+", "", line)
            if len(compact) < 6 or any(token in compact for token in BAD_TITLE_TOKENS):
                continue
            if re.fullmatch(r"[¥￥]?\d+(?:\.\d+)?", compact):
                continue
            return line[:180]
        return ""

    @staticmethod
    def _money(raw: str, pattern: str) -> str:
        match = re.search(pattern, raw)
        return str(match.group(1)) if match else ""

    def collect_cards(self, page) -> list[dict[str, Any]]:
        cards = page.evaluate(CARD_COLLECTION_SCRIPT)
        result: list[dict[str, Any]] = []
        for card in cards:
            raw = str(card.get("raw_text") or "")
            card["title"] = self._title(raw)
            card["price"] = self._money(raw, PRICE_PATTERN)
            card["rate"] = self._money(raw, COMMISSION_RATE_PATTERN)
            card["income"] = self._money(raw, ESTIMATED_INCOME_PATTERN)
            result.append(card)
        return result

    def close_dialog(self, page) -> None:
        close_dialog(page)

    def click_card(self, page, card: dict[str, Any]) -> dict[str, Any]:
        return click_card_button(page, card)

    def parse_modal(self, page) -> dict[str, Any]:
        return parse_modal(
            page,
            self.settings.browser.trusted_link_scheme,
            self.settings.browser.trusted_link_host,
        )

    def link_dates(self) -> tuple[str, str, str]:
        created = datetime.now()
        collection = self.settings.collection
        return (
            created.isoformat(timespec="seconds"),
            (created + timedelta(days=collection.link_expire_days)).isoformat(
                timespec="seconds"
            ),
            (created + timedelta(days=collection.refresh_after_days)).isoformat(
                timespec="seconds"
            ),
        )

    def normalize_image(self, value: Any) -> str:
        image = str(value or "").strip()
        if not image:
            return ""
        if image.startswith(("http://", "https://")):
            return image
        if image.startswith("//"):
            return f"{self.settings.browser.image_scheme}:{image}"
        if image.startswith(("jfs/", "/jfs/")):
            browser = self.settings.browser
            return (
                f"{browser.image_scheme}://{browser.image_host}"
                f"{browser.image_path_prefix}{image.lstrip('/')}"
            )
        return image
