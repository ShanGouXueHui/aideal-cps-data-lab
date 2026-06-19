from __future__ import annotations

import random
import time

from playwright.sync_api import sync_playwright

from .batch import BatchState
from .jd_page import JDPageAdapter
from .settings import HZ24Settings
from .tab_runner import run_tab


def run_session(
    settings: HZ24Settings,
    queue: dict,
    queue_sha: str,
    linked: set[str],
    unavailable: set[str],
    pending: set[str],
    batch: BatchState,
) -> None:
    adapter = JDPageAdapter(settings)
    with sync_playwright() as playwright:
        page = adapter.connect_page(playwright)
        if page is None:
            batch.stop_reason = "browser_page_missing"
            return
        initial_risk = adapter.risk(page)
        if initial_risk:
            batch.stop_reason = "risk_initial"
            batch.stop_risk = initial_risk
            return
        for index, tab in enumerate(settings.special_tabs):
            if batch.processed >= settings.collection.batch_limit:
                break
            if not pending or batch.stop_reason:
                break
            run_tab(
                settings,
                adapter,
                page,
                tab,
                queue,
                linked,
                unavailable,
                pending,
                queue_sha,
                batch,
            )
            if index >= len(settings.special_tabs) - 1:
                continue
            if not pending or batch.stop_reason:
                continue
            time.sleep(
                random.uniform(
                    settings.collection.tab_sleep_min_seconds,
                    settings.collection.tab_sleep_max_seconds,
                )
            )
