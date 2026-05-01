#!/usr/bin/env python3
"""Probe public JD/Jingfen/Union pages and save compact metadata.

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


DEFAULT_URLS = [
    "https://jingfen.jd.com/",
    "https://union.jd.com/",
    "https://union.jd.com/openplatform/console/openMngApi",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", default=[], help="URL to probe. Can be repeated.")
    parser.add_argument("--outdir", default="")
    parser.add_argument("--ua", default="mobile,pc", help="Comma separated UA names: mobile,pc")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--sleep", type=float, default=0.6)
    parser.add_argument("--max-bytes", type=int, default=1_200_000)
    parser.add_argument("--download-assets", action="store_true")
    parser.add_argument("--max-assets", type=int, default=40)
    args = parser.parse_args()

    urls = args.url or DEFAULT_URLS
    uas = [x.strip() for x in args.ua.split(",") if x.strip()]
    outdir = Path(args.outdir or f"run/jd_portal_public_probe_{utc_stamp()}")
    outdir.mkdir(parents=True, exist_ok=True)

    summary: list[dict[str, object]] = []
    asset_candidates: list[str] = []
    endpoint_hits: dict[str, list[str]] = {}

    idx = 0
    for url in urls:
        for ua in uas:
            idx += 1
            result = fetch_url(url, ua=ua, timeout=args.timeout, max_bytes=args.max_bytes)
            meta = write_fetch_record(outdir, idx, ua, result)
            summary.append(meta)
            print(
                f"PROBED idx={idx} ua={ua} status={meta['status']} "
                f"size={meta['body_size']} login={meta['login_hint']} product={meta['product_hint']} url={url}"
            )

            for asset in extract_assets(result.text, result.final_url or url):
                if asset not in asset_candidates:
                    asset_candidates.append(asset)

            hits = extract_endpoint_hits(result.text)
            _merge_hits(endpoint_hits, hits)

            time.sleep(args.sleep)

    if args.download_assets:
        asset_dir = outdir / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        asset_idx = 0
        for asset in asset_candidates[: args.max_assets]:
            if not _is_interesting_asset(asset):
                continue
            asset_idx += 1
            result = fetch_url(asset, ua="pc", timeout=args.timeout, max_bytes=args.max_bytes)
            write_fetch_record(asset_dir, asset_idx, "asset", result)
            _merge_hits(endpoint_hits, extract_endpoint_hits(result.text))
            print(f"ASSET idx={asset_idx} status={result.status} size={len(result.body)} url={asset}")
            time.sleep(args.sleep)

    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "asset_candidates.txt").write_text("\n".join(asset_candidates), encoding="utf-8")
    (outdir / "endpoint_hits.json").write_text(json.dumps(endpoint_hits, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OUTDIR={outdir}")
    print(f"SUMMARY={outdir / 'summary.json'}")
    print(f"ENDPOINT_HITS={outdir / 'endpoint_hits.json'}")
    return 0


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
    return lower.endswith(".js") or "union" in lower or "jingfen" in lower or "api.m.jd.com" in lower


if __name__ == "__main__":
    raise SystemExit(main())
