from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from .browser_helpers import as_bool, cookie_summary, now_tag, page_snapshot, safe_name
from .settings import JingfenSettings, load_jingfen_settings


@dataclass(frozen=True, slots=True)
class ProbeRequest:
    profile: Path
    outdir: Path
    headless: bool
    timeout_ms: int
    urls: tuple[str, ...]


def inspect_target(page: Any, context: Any, url: str) -> dict[str, Any]:
    snapshot = page_snapshot(page, context)
    snapshot["requested_url"] = url
    snapshot["final_url"] = snapshot.pop("url", "")
    snapshot["text_head"] = str(snapshot.get("text_head") or "")[:800]
    return snapshot


def capture_target(
    page: Any,
    context: Any,
    request: ProbeRequest,
    index: int,
    url: str,
) -> dict[str, Any]:
    key = f"{index:02d}_" + safe_name(url)
    result: dict[str, Any] = {"requested_url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=request.timeout_ms)
        page.wait_for_timeout(3000)
        result.update(inspect_target(page, context, url))
        try:
            page.screenshot(path=str(request.outdir / f"{key}.png"), full_page=True)
        except Exception as error:
            result["screenshot_error"] = repr(error)
        try:
            (request.outdir / f"{key}.html").write_text(
                page.content(),
                encoding="utf-8",
            )
        except Exception as error:
            result["html_error"] = repr(error)
    except Exception as error:
        result["error"] = repr(error)
    (request.outdir / f"{key}.meta.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def launch_context(playwright, request: ProbeRequest, settings: JingfenSettings):
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(request.profile),
        headless=request.headless,
        viewport={
            "width": settings.viewport_width,
            "height": settings.viewport_height,
        },
        locale=settings.locale,
        timezone_id=settings.timezone_id,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )


def run_probe(
    request: ProbeRequest,
    settings: JingfenSettings | None = None,
) -> int:
    settings = settings or load_jingfen_settings()
    request.outdir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    print("outdir=" + str(request.outdir))
    print("profile=" + str(request.profile))
    print("headless=" + str(request.headless))
    with sync_playwright() as playwright:
        context = launch_context(playwright, request, settings)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(request.timeout_ms)
        for index, url in enumerate(request.urls, start=1):
            result = capture_target(page, context, request, index, url)
            results.append(result)
            print(
                json.dumps(
                    {
                        "idx": index,
                        "title": result.get("title", ""),
                        "final_url": result.get("final_url", ""),
                        "login_text_hit": result.get("login_text_hit"),
                        "portal_text_hit": result.get("portal_text_hit"),
                        "product_text_hit": result.get("product_text_hit"),
                        "auth_cookie_count": (result.get("cookie") or {}).get(
                            "auth_cookie_count", 0
                        ),
                        "error": result.get("error", ""),
                    },
                    ensure_ascii=False,
                )
            )
        summary = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "profile": str(request.profile),
            "outdir": str(request.outdir),
            "cookie": cookie_summary(context),
            "results": results,
        }
        (request.outdir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        context.close()
    print("AUTH_PROBE_DONE")
    print("summary=" + str(request.outdir / "summary.json"))
    return 0


def parse_request(settings: JingfenSettings) -> ProbeRequest:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=str(settings.profile_path))
    parser.add_argument("--outdir", default="")
    parser.add_argument("--headless", default="1")
    parser.add_argument("--timeout-ms", type=int, default=45000)
    parser.add_argument("--url", action="append", default=[])
    args = parser.parse_args()
    return ProbeRequest(
        profile=Path(args.profile),
        outdir=Path(args.outdir or f"run/jingfen_auth_probe_{now_tag()}"),
        headless=as_bool(args.headless),
        timeout_ms=args.timeout_ms,
        urls=tuple(args.url) or settings.auth_probe_urls,
    )


def main() -> int:
    settings = load_jingfen_settings()
    return run_probe(parse_request(settings), settings)
