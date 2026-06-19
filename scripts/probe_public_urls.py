#!/usr/bin/env python3
"""Probe configured public JD pages and save compact metadata.

No login, no cookies, no production database writes.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from aideal_cps_data_lab.http_client import (
    extract_assets,
    extract_endpoint_hits,
    fetch_url,
    utc_stamp,
    write_fetch_record,
)
from aideal_cps_data_lab.jingfen.settings import load_jingfen_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--outdir", default="")
    parser.add_argument("--ua", default="mobile,pc")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--sleep", type=float, default=0.6)
    parser.add_argument("--max-bytes", type=int, default=1_200_000)
    parser.add_argument("--download-assets", action="store_true")
    parser.add_argument("--max-assets", type=int, default=40)
    args = parser.parse_args()

    settings = load_jingfen_settings()
    urls = tuple(args.url) or settings.public_probe_urls
    uas = [value.strip() for value in args.ua.split(",") if value.strip()]
    outdir = Path(args.outdir or f"run/jd_portal_public_probe_{utc_stamp()}")
    outdir.mkdir(parents=True, exist_ok=True)

    summary: list[dict[str, object]] = []
    assets: list[str] = []
    endpoint_hits: dict[str, list[str]] = {}
    index = 0
    for url in urls:
        for user_agent in uas:
            index += 1
            result = fetch_url(
                url,
                ua=user_agent,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
            )
            meta = write_fetch_record(outdir, index, user_agent, result)
            summary.append(meta)
            print(
                f"PROBED idx={index} ua={user_agent} status={meta['status']} "
                f"size={meta['body_size']} login={meta['login_hint']} "
                f"product={meta['product_hint']} url={url}"
            )
            for asset in extract_assets(result.text, result.final_url or url):
                if asset not in assets:
                    assets.append(asset)
            _merge_hits(endpoint_hits, extract_endpoint_hits(result.text))
            time.sleep(args.sleep)

    if args.download_assets:
        _download_assets(
            outdir,
            assets[: args.max_assets],
            endpoint_hits,
            args.timeout,
            args.max_bytes,
            args.sleep,
        )
    (outdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "asset_candidates.txt").write_text("\n".join(assets), encoding="utf-8")
    (outdir / "endpoint_hits.json").write_text(
        json.dumps(endpoint_hits, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OUTDIR={outdir}")
    print(f"SUMMARY={outdir / 'summary.json'}")
    print(f"ENDPOINT_HITS={outdir / 'endpoint_hits.json'}")
    return 0


def _download_assets(
    outdir: Path,
    assets: list[str],
    endpoint_hits: dict[str, list[str]],
    timeout: float,
    max_bytes: int,
    sleep_seconds: float,
) -> None:
    asset_dir = outdir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset_index = 0
    for asset in assets:
        if not _is_interesting_asset(asset):
            continue
        asset_index += 1
        result = fetch_url(asset, ua="pc", timeout=timeout, max_bytes=max_bytes)
        write_fetch_record(asset_dir, asset_index, "asset", result)
        _merge_hits(endpoint_hits, extract_endpoint_hits(result.text))
        print(
            f"ASSET idx={asset_index} status={result.status} "
            f"size={len(result.body)} url={asset}"
        )
        time.sleep(sleep_seconds)


def _merge_hits(base: dict[str, list[str]], new: dict[str, list[str]]) -> None:
    for key, values in new.items():
        bucket = base.setdefault(key, [])
        seen = set(bucket)
        for value in values:
            if value not in seen:
                bucket.append(value)
                seen.add(value)


def _is_interesting_asset(url: str) -> bool:
    lower = url.lower()
    return (
        lower.endswith(".js")
        or "union" in lower
        or "jingfen" in lower
        or "api.m.jd.com" in lower
    )


if __name__ == "__main__":
    raise SystemExit(main())
