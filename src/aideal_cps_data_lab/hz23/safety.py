from __future__ import annotations

from typing import Any


def unsafe_source_reason(row: dict[str, Any]) -> str | None:
    worker = str(row.get("worker_name") or "").lower()
    menu_mode = str(row.get("menu_mode") or "").lower()
    promotion_mode = str(row.get("promotion_mode") or "").lower()
    if worker == "hz20_mouse_click":
        return "worker_name_hz20_mouse_click"
    if "hz20" in menu_mode:
        return "menu_mode_contains_hz20"
    if "hz20" in promotion_mode:
        return "promotion_mode_contains_hz20"
    return None
