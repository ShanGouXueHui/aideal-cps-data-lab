from __future__ import annotations

from datetime import datetime
from typing import Any

AUTH_COOKIE_NAMES = {
    "pt_key",
    "pt_pin",
    "thor",
    "pin",
    "pinId",
    "unick",
    "ceshi3.com",
}


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def as_bool(value: str | int | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_name(value: str) -> str:
    result = [character if character.isalnum() else "_" for character in value]
    return "".join(result).strip("_")[:90] or "page"


def safe_text(page: Any, limit: int = 2000) -> str:
    try:
        text = page.locator("body").inner_text(timeout=4000)
    except Exception:
        text = ""
    return " ".join(str(text or "").split())[:limit]


def cookie_summary(context: Any) -> dict[str, Any]:
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    jd_cookies = [
        cookie
        for cookie in cookies
        if "jd.com" in str(cookie.get("domain", ""))
        or "360buy" in str(cookie.get("domain", ""))
    ]
    auth_names = sorted(
        {
            str(cookie.get("name", ""))
            for cookie in jd_cookies
            if str(cookie.get("name", "")) in AUTH_COOKIE_NAMES
        }
    )
    return {
        "total_cookie_count": len(cookies),
        "jd_cookie_count": len(jd_cookies),
        "auth_cookie_names": auth_names,
        "auth_cookie_count": len(auth_names),
    }


def page_snapshot(page: Any, context: Any) -> dict[str, Any]:
    try:
        title = page.title()
    except Exception:
        title = ""
    try:
        url = page.url
    except Exception:
        url = ""
    text = safe_text(page)
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "url": url,
        "title": title,
        "text_head": text[:500],
        "login_text_hit": any(
            value in text for value in ["登录", "扫码", "二维码", "账户登录", "请登录"]
        ),
        "portal_text_hit": any(
            value in text
            for value in ["京东联盟", "京粉", "商品推广", "我的API", "数据报表", "佣金", "账户"]
        ),
        "product_text_hit": any(
            value in text for value in ["商品", "推广", "佣金", "转链", "京粉精选", "赚"]
        ),
        "cookie": cookie_summary(context),
    }
