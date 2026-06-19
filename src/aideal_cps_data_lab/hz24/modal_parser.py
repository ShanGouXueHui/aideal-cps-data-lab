from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

DIALOG_SELECTOR = ".el-dialog:visible, .ant-modal:visible, [role=dialog]:visible"
CLOSE_SELECTOR = ".el-dialog__close, .ant-modal-close, [aria-label=Close], [aria-label=关闭]"
URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+")


def _visible_dialog(page):
    dialogs = page.locator(DIALOG_SELECTOR)
    for index in range(dialogs.count() - 1, -1, -1):
        dialog = dialogs.nth(index)
        try:
            if dialog.is_visible():
                return dialog
        except Exception:
            continue
    return None


def close_dialog(page) -> bool:
    dialog = _visible_dialog(page)
    if dialog is None:
        return False
    buttons = dialog.locator(CLOSE_SELECTOR)
    for index in range(buttons.count()):
        button = buttons.nth(index)
        try:
            if button.is_visible():
                button.click(timeout=4000)
                return True
        except Exception:
            continue
    try:
        page.keyboard.press("Escape")
        return True
    except Exception:
        return False


def _field_values(dialog) -> list[str]:
    values: list[str] = []
    fields = dialog.locator("input, textarea")
    for index in range(fields.count()):
        field = fields.nth(index)
        try:
            value = str(field.input_value(timeout=2000) or "").strip()
        except Exception:
            value = ""
        if value and value not in values:
            values.append(value)
    return values


def _anchor_urls(dialog) -> list[str]:
    urls: list[str] = []
    anchors = dialog.locator("a[href]")
    for index in range(anchors.count()):
        try:
            value = str(anchors.nth(index).get_attribute("href") or "").strip()
        except Exception:
            value = ""
        if value and value not in urls:
            urls.append(value)
    return urls


def _image_urls(dialog) -> list[str]:
    urls: list[str] = []
    images = dialog.locator("img")
    for index in range(images.count()):
        try:
            value = str(images.nth(index).get_attribute("src") or "").strip()
        except Exception:
            value = ""
        if value and value not in urls:
            urls.append(value)
    return urls


def _trusted_url(values: list[str], scheme: str, host: str) -> str | None:
    for value in values:
        parsed = urlparse(value)
        if parsed.scheme == scheme and parsed.hostname == host:
            return value
    return None


def parse_modal(page, trusted_scheme: str, trusted_host: str) -> dict[str, Any]:
    dialog = _visible_dialog(page)
    if dialog is None:
        return {}
    try:
        text = str(dialog.inner_text(timeout=3000) or "")
    except Exception:
        text = ""
    values = _field_values(dialog)
    discovered = values + _anchor_urls(dialog) + URL_PATTERN.findall(text)
    short_url = _trusted_url(discovered, trusted_scheme, trusted_host)
    long_url = next(
        (
            value
            for value in discovered
            if value.startswith(("http://", "https://")) and value != short_url
        ),
        None,
    )
    qr_url = next(
        (value for value in _image_urls(dialog) if "qr" in value.lower()),
        None,
    )
    commands = [value for value in values if not value.startswith(("http://", "https://"))]
    return {
        "short_url": short_url,
        "long_url": long_url,
        "qr_url": qr_url,
        "jd_command": commands[0] if commands else None,
        "dialog_text": text[:1000],
    }
