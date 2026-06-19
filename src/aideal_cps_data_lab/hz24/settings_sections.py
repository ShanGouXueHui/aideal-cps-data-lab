from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlunsplit

from .settings_models import (
    BrowserSettings,
    CollectionSettings,
    ContractSettings,
)


def _env_number(name: str, value: object, value_type):
    return value_type(os.environ.get(name, str(value)))


def browser_settings(data: dict[str, object]) -> BrowserSettings:
    cdp_scheme = os.environ.get(
        "AIDEAL_HZ24_CDP_SCHEME",
        str(data["cdp_scheme"]),
    )
    cdp_host = os.environ.get(
        "AIDEAL_HZ24_CDP_HOST",
        str(data["cdp_host"]),
    )
    cdp_port = _env_number(
        "AIDEAL_HZ24_CDP_PORT",
        data["cdp_port"],
        int,
    )
    endpoint = urlunsplit(
        (cdp_scheme, f"{cdp_host}:{cdp_port}", "", "", "")
    )
    return BrowserSettings(
        cdp_endpoint=endpoint,
        page_scheme=str(data["page_scheme"]),
        page_host=str(data["page_host"]),
        trusted_link_scheme=str(data["trusted_link_scheme"]),
        trusted_link_host=str(data["trusted_link_host"]),
        item_scheme=str(data["item_scheme"]),
        item_host=str(data["item_host"]),
        default_timeout_ms=int(data["default_timeout_ms"]),
        connect_timeout_ms=int(data["connect_timeout_ms"]),
        tab_click_timeout_ms=int(data["tab_click_timeout_ms"]),
        tab_settle_ms=int(data["tab_settle_ms"]),
        modal_poll_ms=int(data["modal_poll_ms"]),
        risk_markers=tuple(str(value) for value in data["risk_markers"]),
        tab_role_selector=str(data["tab_role_selector"]),
        tab_class_pattern=str(data["tab_class_pattern"]),
    )


def collection_settings(data: dict[str, object]) -> CollectionSettings:
    return CollectionSettings(
        batch_limit=_env_number("HZ24_BATCH_LIMIT", data["batch_limit"], int),
        wait_seconds=_env_number("HZ24_WAIT_SECONDS", data["wait_seconds"], int),
        item_sleep_min_seconds=_env_number(
            "HZ24_ITEM_SLEEP_MIN", data["item_sleep_min_seconds"], float
        ),
        item_sleep_max_seconds=_env_number(
            "HZ24_ITEM_SLEEP_MAX", data["item_sleep_max_seconds"], float
        ),
        tab_sleep_min_seconds=_env_number(
            "HZ24_TAB_SLEEP_MIN", data["tab_sleep_min_seconds"], float
        ),
        tab_sleep_max_seconds=_env_number(
            "HZ24_TAB_SLEEP_MAX", data["tab_sleep_max_seconds"], float
        ),
        failure_fuse=_env_number("HZ24_FAIL_FUSE", data["failure_fuse"], int),
        link_expire_days=int(data["link_expire_days"]),
        refresh_after_days=int(data["refresh_after_days"]),
        refresh_before_expiry_days=int(data["refresh_before_expiry_days"]),
    )


def _path(root: Path, value: object) -> Path:
    return root / str(value)


def contract_settings(
    root: Path,
    data: dict[str, object],
) -> ContractSettings:
    return ContractSettings(
        observer_service=str(data["observer_service"]),
        hz21_adapter=_path(root, data["hz21_adapter"]),
        queue_file=_path(root, data["queue_file"]),
        queue_manifest_file=_path(root, data["queue_manifest_file"]),
        linked_file=_path(root, data["linked_file"]),
        unavailable_file=_path(root, data["unavailable_file"]),
        state_file=_path(root, data["state_file"]),
        collection_report_file=_path(root, data["collection_report_file"]),
        validation_report_file=_path(root, data["validation_report_file"]),
        linked_manifest_file=_path(root, data["linked_manifest_file"]),
        outcome_manifest_file=_path(root, data["outcome_manifest_file"]),
        linked_schema=str(data["linked_schema"]),
        unavailable_schema=str(data["unavailable_schema"]),
        state_schema=str(data["state_schema"]),
        collection_schema=str(data["collection_schema"]),
        worker_name=str(data["worker_name"]),
        menu_mode=str(data["menu_mode"]),
        promotion_mode=str(data["promotion_mode"]),
    )
