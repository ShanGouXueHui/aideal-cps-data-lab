#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
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
]


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def as_bool(value: str | int | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_text(page: Any, limit: int = 1200) -> str:
    try:
        body = page.locator("body")
        text = body.inner_text(timeout=2500)
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
    low = text.lower()
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "url": url,
        "title": title,
        "text_head": text[:500],
        "login_text_hit": any(x in text for x in ["登录", "扫码", "二维码", "账户登录", "请登录"]),
        "portal_text_hit": any(x in text for x in ["京东联盟", "京粉", "商品推广", "我的API", "数据报表", "佣金", "账户"]),
        "product_text_hit": any(x in text for x in ["商品", "推广", "佣金", "转链", "京粉精选", "赚"]),
        "cookie": cookie_summary(context),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URLS[0])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=8)
    parser.add_argument("--headless", default="1")
    parser.add_argument("--profile", default=".secrets/jingfen_profile")
    parser.add_argument("--storage", default=".secrets/jingfen_storage_state.json")
    parser.add_argument("--outdir", default="")
    parser.add_argument("--stop-on-auth", default="1")
    args = parser.parse_args()

    outdir = Path(args.outdir or f"run/jingfen_login_capture_{now_tag()}")
    outdir.mkdir(parents=True, exist_ok=True)

    profile_dir = Path(args.profile)
    profile_dir.mkdir(parents=True, exist_ok=True)

    storage_path = Path(args.storage)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    headless = as_bool(args.headless)
    stop_on_auth = as_bool(args.stop_on_auth)

    print("outdir=" + str(outdir))
    print("profile=" + str(profile_dir))
    print("storage=" + str(storage_path))
    print("headless=" + str(headless))
    print("start_url=" + args.url)

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
        page.set_default_timeout(15000)

        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            print("initial_goto_error=" + repr(exc))

        started = time.time()
        idx = 0
        last_meta: dict[str, Any] = {}

        while True:
            idx += 1
            try:
                page.wait_for_timeout(1500)
            except Exception:
                pass

            meta = page_snapshot(page, context)
            last_meta = meta

            png = outdir / "latest.png"
            html = outdir / "latest.html"
            meta_file = outdir / "latest.meta.json"

            try:
                page.screenshot(path=str(png), full_page=True)
            except Exception as exc:
                meta["screenshot_error"] = repr(exc)

            try:
                html.write_text(page.content(), encoding="utf-8")
            except Exception as exc:
                meta["html_error"] = repr(exc)

            try:
                context.storage_state(path=str(storage_path))
                meta["storage_saved"] = True
            except Exception as exc:
                meta["storage_saved"] = False
                meta["storage_error"] = repr(exc)

            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            print(
                "tick={tick} elapsed={elapsed:.1f}s title={title!r} auth_cookie_count={auth} url={url} screenshot={png}".format(
                    tick=idx,
                    elapsed=time.time() - started,
                    title=meta.get("title", "")[:60],
                    auth=meta.get("cookie", {}).get("auth_cookie_count", 0),
                    url=meta.get("url", ""),
                    png=png,
                ),
                flush=True,
            )

            if stop_on_auth and meta.get("cookie", {}).get("auth_cookie_count", 0) > 0:
                print("AUTH_COOKIE_DETECTED")
                break

            if time.time() - started >= args.timeout:
                print("TIMEOUT_REACHED")
                break

            time.sleep(max(2, args.interval))

        final_file = outdir / "final.meta.json"
        final_file.write_text(json.dumps(last_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            context.storage_state(path=str(storage_path))
        except Exception:
            pass
        context.close()

    print("DONE")
    print("outdir=" + str(outdir))
    print("latest_png=" + str(outdir / "latest.png"))
    print("storage=" + str(storage_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
