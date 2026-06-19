from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from .auth_probe import launch_context
from .browser_helpers import as_bool, now_tag, page_snapshot
from .settings import JingfenSettings, load_jingfen_settings


@dataclass(frozen=True, slots=True)
class LoginRequest:
    url: str
    timeout_seconds: int
    interval_seconds: int
    headless: bool
    profile: Path
    storage: Path
    outdir: Path
    stop_on_auth: bool


def save_capture(
    page: Any,
    context: Any,
    request: LoginRequest,
) -> dict[str, Any]:
    result = page_snapshot(page, context)
    try:
        page.screenshot(path=str(request.outdir / "latest.png"), full_page=True)
    except Exception as error:
        result["screenshot_error"] = repr(error)
    try:
        (request.outdir / "latest.html").write_text(
            page.content(),
            encoding="utf-8",
        )
    except Exception as error:
        result["html_error"] = repr(error)
    try:
        context.storage_state(path=str(request.storage))
        result["storage_saved"] = True
    except Exception as error:
        result["storage_saved"] = False
        result["storage_error"] = repr(error)
    (request.outdir / "latest.meta.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def should_stop(
    result: dict[str, Any],
    request: LoginRequest,
    elapsed: float,
) -> str | None:
    auth_count = int((result.get("cookie") or {}).get("auth_cookie_count") or 0)
    if request.stop_on_auth and auth_count > 0:
        return "AUTH_COOKIE_DETECTED"
    if elapsed >= request.timeout_seconds:
        return "TIMEOUT_REACHED"
    return None


def capture_loop(page: Any, context: Any, request: LoginRequest) -> dict[str, Any]:
    started = time.time()
    tick = 0
    last_result: dict[str, Any] = {}
    while True:
        tick += 1
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass
        last_result = save_capture(page, context, request)
        elapsed = time.time() - started
        print(
            "tick={tick} elapsed={elapsed:.1f}s title={title!r} "
            "auth_cookie_count={auth} url={url} screenshot={png}".format(
                tick=tick,
                elapsed=elapsed,
                title=str(last_result.get("title", ""))[:60],
                auth=(last_result.get("cookie") or {}).get("auth_cookie_count", 0),
                url=last_result.get("url", ""),
                png=request.outdir / "latest.png",
            ),
            flush=True,
        )
        stop_reason = should_stop(last_result, request, elapsed)
        if stop_reason:
            print(stop_reason)
            break
        time.sleep(max(2, request.interval_seconds))
    return last_result


def run_capture(
    request: LoginRequest,
    settings: JingfenSettings | None = None,
) -> int:
    settings = settings or load_jingfen_settings()
    request.outdir.mkdir(parents=True, exist_ok=True)
    request.profile.mkdir(parents=True, exist_ok=True)
    request.storage.parent.mkdir(parents=True, exist_ok=True)
    print("outdir=" + str(request.outdir))
    print("profile=" + str(request.profile))
    print("storage=" + str(request.storage))
    print("headless=" + str(request.headless))
    print("start_url=" + request.url)
    with sync_playwright() as playwright:
        probe_request = type(
            "ProbeContextRequest",
            (),
            {"profile": request.profile, "headless": request.headless},
        )()
        context = launch_context(playwright, probe_request, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(15000)
        try:
            page.goto(request.url, wait_until="domcontentloaded", timeout=60000)
        except Exception as error:
            print("initial_goto_error=" + repr(error))
        last_result = capture_loop(page, context, request)
        (request.outdir / "final.meta.json").write_text(
            json.dumps(last_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            context.storage_state(path=str(request.storage))
        except Exception:
            pass
        context.close()
    print("DONE")
    print("outdir=" + str(request.outdir))
    print("latest_png=" + str(request.outdir / "latest.png"))
    print("storage=" + str(request.storage))
    return 0


def parse_request(settings: JingfenSettings) -> LoginRequest:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=settings.login_start_url)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=8)
    parser.add_argument("--headless", default="1")
    parser.add_argument("--profile", default=str(settings.profile_path))
    parser.add_argument("--storage", default=str(settings.storage_path))
    parser.add_argument("--outdir", default="")
    parser.add_argument("--stop-on-auth", default="1")
    args = parser.parse_args()
    return LoginRequest(
        url=args.url,
        timeout_seconds=args.timeout,
        interval_seconds=args.interval,
        headless=as_bool(args.headless),
        profile=Path(args.profile),
        storage=Path(args.storage),
        outdir=Path(args.outdir or f"run/jingfen_login_capture_{now_tag()}"),
        stop_on_auth=as_bool(args.stop_on_auth),
    )


def main() -> int:
    settings = load_jingfen_settings()
    return run_capture(parse_request(settings), settings)
