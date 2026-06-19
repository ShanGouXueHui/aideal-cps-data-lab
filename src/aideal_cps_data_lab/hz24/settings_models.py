from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BrowserSettings:
    cdp_endpoint: str
    page_scheme: str
    page_host: str
    trusted_link_scheme: str
    trusted_link_host: str
    item_scheme: str
    item_host: str
    default_timeout_ms: int
    connect_timeout_ms: int
    tab_click_timeout_ms: int
    tab_settle_ms: int
    modal_poll_ms: int
    risk_markers: tuple[str, ...]
    tab_role_selector: str = '[role="radio"], label.el-radio-button, [role="tab"]'
    tab_class_pattern: str = "radio|tab"


@dataclass(frozen=True, slots=True)
class CollectionSettings:
    batch_limit: int
    wait_seconds: int
    item_sleep_min_seconds: float
    item_sleep_max_seconds: float
    tab_sleep_min_seconds: float
    tab_sleep_max_seconds: float
    failure_fuse: int
    link_expire_days: int
    refresh_after_days: int
    refresh_before_expiry_days: int


@dataclass(frozen=True, slots=True)
class ContractSettings:
    observer_service: str
    hz21_adapter: Path
    queue_file: Path
    queue_manifest_file: Path
    linked_file: Path
    unavailable_file: Path
    state_file: Path
    collection_report_file: Path
    validation_report_file: Path
    linked_manifest_file: Path
    outcome_manifest_file: Path
    linked_schema: str
    unavailable_schema: str
    state_schema: str
    collection_schema: str
    worker_name: str
    menu_mode: str
    promotion_mode: str


@dataclass(frozen=True, slots=True)
class HZ24Settings:
    root: Path
    special_tabs: tuple[str, ...]
    allowed_unavailable_reasons: frozenset[str]
    browser: BrowserSettings
    collection: CollectionSettings
    contracts: ContractSettings
