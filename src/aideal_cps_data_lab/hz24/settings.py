from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlunsplit


@dataclass(frozen=True, slots=True)
class BrowserSettings:
    cdp_endpoint: str
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


def _read(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _path(root: Path, value: object) -> Path:
    return root / str(value)


def _env_number(name: str, value: object, value_type):
    return value_type(os.environ.get(name, str(value)))


def load_settings() -> HZ24Settings:
    root = Path(__file__).resolve().parents[3]
    config_dir = Path(
        os.environ.get("AIDEAL_HZ24_CONFIG_DIR", str(root / "config"))
    )
    domain = _read(config_dir / "hz24-domain.toml")
    browser_data = _read(config_dir / "hz24-browser.toml")
    collection_data = _read(config_dir / "hz24-collection.toml")
    contracts_data = _read(config_dir / "hz24-contracts.toml")

    cdp_scheme = os.environ.get(
        "AIDEAL_HZ24_CDP_SCHEME",
        str(browser_data["cdp_scheme"]),
    )
    cdp_host = os.environ.get(
        "AIDEAL_HZ24_CDP_HOST",
        str(browser_data["cdp_host"]),
    )
    cdp_port = _env_number(
        "AIDEAL_HZ24_CDP_PORT",
        browser_data["cdp_port"],
        int,
    )
    browser = BrowserSettings(
        cdp_endpoint=urlunsplit(
            (cdp_scheme, f"{cdp_host}:{cdp_port}", "", "", "")
        ),
        page_host=str(browser_data["page_host"]),
        trusted_link_scheme=str(browser_data["trusted_link_scheme"]),
        trusted_link_host=str(browser_data["trusted_link_host"]),
        item_scheme=str(browser_data["item_scheme"]),
        item_host=str(browser_data["item_host"]),
        default_timeout_ms=int(browser_data["default_timeout_ms"]),
        connect_timeout_ms=int(browser_data["connect_timeout_ms"]),
        tab_click_timeout_ms=int(browser_data["tab_click_timeout_ms"]),
        tab_settle_ms=int(browser_data["tab_settle_ms"]),
        modal_poll_ms=int(browser_data["modal_poll_ms"]),
        risk_markers=tuple(str(value) for value in browser_data["risk_markers"]),
    )
    collection = CollectionSettings(
        batch_limit=_env_number("HZ24_BATCH_LIMIT", collection_data["batch_limit"], int),
        wait_seconds=_env_number("HZ24_WAIT_SECONDS", collection_data["wait_seconds"], int),
        item_sleep_min_seconds=_env_number("HZ24_ITEM_SLEEP_MIN", collection_data["item_sleep_min_seconds"], float),
        item_sleep_max_seconds=_env_number("HZ24_ITEM_SLEEP_MAX", collection_data["item_sleep_max_seconds"], float),
        tab_sleep_min_seconds=_env_number("HZ24_TAB_SLEEP_MIN", collection_data["tab_sleep_min_seconds"], float),
        tab_sleep_max_seconds=_env_number("HZ24_TAB_SLEEP_MAX", collection_data["tab_sleep_max_seconds"], float),
        failure_fuse=_env_number("HZ24_FAIL_FUSE", collection_data["failure_fuse"], int),
        link_expire_days=int(collection_data["link_expire_days"]),
        refresh_after_days=int(collection_data["refresh_after_days"]),
        refresh_before_expiry_days=int(collection_data["refresh_before_expiry_days"]),
    )
    contracts = ContractSettings(
        observer_service=str(contracts_data["observer_service"]),
        hz21_adapter=_path(root, contracts_data["hz21_adapter"]),
        queue_file=_path(root, contracts_data["queue_file"]),
        queue_manifest_file=_path(root, contracts_data["queue_manifest_file"]),
        linked_file=_path(root, contracts_data["linked_file"]),
        unavailable_file=_path(root, contracts_data["unavailable_file"]),
        state_file=_path(root, contracts_data["state_file"]),
        collection_report_file=_path(root, contracts_data["collection_report_file"]),
        validation_report_file=_path(root, contracts_data["validation_report_file"]),
        linked_manifest_file=_path(root, contracts_data["linked_manifest_file"]),
        outcome_manifest_file=_path(root, contracts_data["outcome_manifest_file"]),
        linked_schema=str(contracts_data["linked_schema"]),
        unavailable_schema=str(contracts_data["unavailable_schema"]),
        state_schema=str(contracts_data["state_schema"]),
        collection_schema=str(contracts_data["collection_schema"]),
        worker_name=str(contracts_data["worker_name"]),
        menu_mode=str(contracts_data["menu_mode"]),
        promotion_mode=str(contracts_data["promotion_mode"]),
    )
    return HZ24Settings(
        root=root,
        special_tabs=tuple(str(value) for value in domain["special_tabs"]),
        allowed_unavailable_reasons=frozenset(
            str(value) for value in domain["allowed_unavailable_reasons"]
        ),
        browser=browser,
        collection=collection,
        contracts=contracts,
    )
