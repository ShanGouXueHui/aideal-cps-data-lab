from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .settings import HZ24Settings


@dataclass(frozen=True, slots=True)
class AuditSettings:
    structure_schema: str
    overlap_schema: str
    mode: str
    structure_report: Path
    overlap_report: Path
    candidate_file: Path
    candidate_manifest: Path
    product_page_path: str
    product_page_query: str
    page_wait_until: str
    page_navigation_timeout_ms: int
    page_navigation_settle_ms: int
    scroll_iterations: int
    scroll_settle_ms: int
    scroll_reset_settle_ms: int
    minimum_sku_count: int
    sample_limit: int

    def product_page_url(self, settings: HZ24Settings) -> str:
        query = f"?{self.product_page_query}" if self.product_page_query else ""
        return (
            f"{settings.browser.item_scheme}://"
            f"{settings.browser.page_host}"
            f"{self.product_page_path}{query}"
        )


def load_audit_settings(settings: HZ24Settings) -> AuditSettings:
    path = settings.root / "config/hz24-audit.toml"
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    root = settings.root
    return AuditSettings(
        structure_schema=str(data["structure_schema"]),
        overlap_schema=str(data["overlap_schema"]),
        mode=str(data["mode"]),
        structure_report=root / str(data["structure_report"]),
        overlap_report=root / str(data["overlap_report"]),
        candidate_file=root / str(data["candidate_file"]),
        candidate_manifest=root / str(data["candidate_manifest"]),
        product_page_path=str(data["product_page_path"]),
        product_page_query=str(data["product_page_query"]),
        page_wait_until=str(data["page_wait_until"]),
        page_navigation_timeout_ms=int(data["page_navigation_timeout_ms"]),
        page_navigation_settle_ms=int(data["page_navigation_settle_ms"]),
        scroll_iterations=int(data["scroll_iterations"]),
        scroll_settle_ms=int(data["scroll_settle_ms"]),
        scroll_reset_settle_ms=int(data["scroll_reset_settle_ms"]),
        minimum_sku_count=int(data["minimum_sku_count"]),
        sample_limit=int(data["sample_limit"]),
    )
