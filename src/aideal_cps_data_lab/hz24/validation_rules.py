from __future__ import annotations

from typing import Any

from .jd_page import JDPageAdapter
from .records import LINK_HASH_FIELDS, stable_hash
from .settings import HZ24Settings


REQUIRED_LINK_FIELDS = (
    "title",
    "item_url",
    "price",
    "commission_rate",
    "estimated_income",
    "short_url",
)


def validate_linked_rows(
    settings: HZ24Settings,
    adapter: JDPageAdapter,
    queue_by_sku: dict[str, dict[str, Any]],
    linked_by_sku: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    issues = {
        "untrusted": [],
        "incomplete": [],
        "hash_mismatch": [],
        "tab_mismatch": [],
        "unsafe": [],
    }
    allowed_tabs = set(settings.special_tabs)
    for sku, row in linked_by_sku.items():
        if not adapter.trusted_short_url(row.get("short_url")):
            issues["untrusted"].append(sku)
        if any(
            not str(row.get(field) or "").strip()
            for field in REQUIRED_LINK_FIELDS
        ):
            issues["incomplete"].append(sku)
        if row.get("record_sha256") != stable_hash(row, LINK_HASH_FIELDS):
            issues["hash_mismatch"].append(sku)
        expected_tabs = set(
            queue_by_sku.get(sku, {}).get("source_tabs") or []
        )
        source_tab = str(row.get("source_tab") or "")
        if source_tab not in allowed_tabs or source_tab not in expected_tabs:
            issues["tab_mismatch"].append(sku)
        source = " ".join(
            [
                str(row.get("worker_name") or ""),
                str(row.get("menu_mode") or ""),
            ]
        ).lower()
        if "hz20" in source:
            issues["unsafe"].append(sku)
    return issues


def validate_unavailable_rows(
    settings: HZ24Settings,
    queue_by_sku: dict[str, dict[str, Any]],
    unavailable_by_sku: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    issues = {
        "invalid_reason": [],
        "hash_mismatch": [],
        "tab_mismatch": [],
    }
    for sku, row in unavailable_by_sku.items():
        if str(row.get("reason") or "") not in settings.allowed_unavailable_reasons:
            issues["invalid_reason"].append(sku)
        fields = tuple(
            key
            for key in row
            if key != "record_sha256"
        )
        if row.get("record_sha256") != stable_hash(row, fields):
            issues["hash_mismatch"].append(sku)
        expected_tabs = set(
            queue_by_sku.get(sku, {}).get("source_tabs") or []
        )
        if str(row.get("source_tab") or "") not in expected_tabs:
            issues["tab_mismatch"].append(sku)
    return issues
