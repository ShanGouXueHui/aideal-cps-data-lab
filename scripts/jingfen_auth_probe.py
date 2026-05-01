#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

AUTH_COOKIE_NAMES = {
    "pt_key",
    "pt_pin",
    "thor",
    "pin",
    "pinId",
    "unick",
    "ceshi3.com",
}

DEFAULT_URLS = [
    "https://union.jd.com/openplatform/console/openMngApi",
    "https://union.jd.com/",
    "https://jingfen.jd.com/",
    "https://prodev.m.jd.com/mall/active/2LifKZwNDLSJwL2QLhY9ub4Jv6ah/index.html",
]


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def as_bool(value: str | int | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_name(value: str) -> str:
    out = []
    for ch in value:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_")[:90] or "page"


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
        c for c in cookies
        if "jd.com" in str(c.get("domain", "")) or "360buy" in str(c.get("domain", ""))
    ]
    auth_names = sorted({
        str(c.get("name", ""))
        for c in jd_cookies
        if str(c.get("name", "")) in AUTH_COOKIE_NAMES
    })
    return {
        "total_cookie_count": len(cookies),
        "jd_cookie_count": len(jd_cookies),
        "auth_cookie_names": auth_names,
        "auth_cookie_count": len(auth_names),
    }


def inspect_page(page: Any, context: Any, url: str) -> dict[str, Any]:
    try:
        title = page.title()
    except Exception:
        title = ""
    try:
        final_url = page.url
    except Exception:
        final_url = ""
    text = safe_text(page)
    return {
        "requested_url": url,
        "final_url": final_url,
        "title": title,
        "text_head": text[:800],
        "login_text_hit": any(x in text for x in ["登录", "扫码", "二维码", "账户登录", "请登录"]),
        "portal_text_hit": any(x in text for x in ["京东联盟", "京粉", "商品推广", "我的API", "数据报表", "佣金", "账户"]),
        "product_text_hit": any(x in text for x in ["商品", "推广", "佣金", "转链", "京粉精选", "赚"]),
        "cookie": cookie_summary(context),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=".secrets/jingfen_profile")
    parser.add_argument("--outdir", default="")
    parser.add_argument("--headless", default="1")
    parser.add_argument("--timeout-ms", type=int, default=45000)
    parser.add_argument("--url", action="append", default=[])
    args = parser.parse_args()

    outdir = Path(args.outdir or f"run/jingfen_auth_probe_{now_tag()}")
    outdir.mkdir(parents=True, exist_ok=True)

    profile_dir = Path(args.profile)
    headless = as_bool(args.headless)
    urls = args.url or DEFAULT_URLS

    print("outdir=" + str(outdir))
    print("profile=" + str(profile_dir))
    print("headless=" + str(headless))

    results = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1365, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(args.timeout_ms)

        for idx, url in enumerate(urls, start=1):
            key = f"{idx:02d}_" + safe_name(url)
            meta: dict[str, Any] = {"requested_url": url}
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                page.wait_for_timeout(3000)
                meta.update(inspect_page(page, context, url))
                try:
                    page.screenshot(path=str(outdir / f"{key}.png"), full_page=True)
                except Exception as exc:
                    meta["screenshot_error"] = repr(exc)
                try:
                    (outdir / f"{key}.html").write_text(page.content(), encoding="utf-8")
                except Exception as exc:
                    meta["html_error"] = repr(exc)
            except Exception as exc:
                meta["error"] = repr(exc)

            (outdir / f"{key}.meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            results.append(meta)
            print(json.dumps({
                "idx": idx,
                "title": meta.get("title", ""),
                "final_url": meta.get("final_url", ""),
                "login_text_hit": meta.get("login_text_hit"),
                "portal_text_hit": meta.get("portal_text_hit"),
                "product_text_hit": meta.get("product_text_hit"),
                "auth_cookie_count": meta.get("cookie", {}).get("auth_cookie_count", 0),
                "error": meta.get("error", ""),
            }, ensure_ascii=False))

        summary = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "profile": str(profile_dir),
            "outdir": str(outdir),
            "cookie": cookie_summary(context),
            "results": results,
        }
        (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        context.close()

    print("AUTH_PROBE_DONE")
    print("summary=" + str(outdir / "summary.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
