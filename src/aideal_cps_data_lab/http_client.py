"""Small standard-library HTTP helpers for authorized JD/Jingfen portal probes.

This module deliberately avoids browser automation and external dependencies.
It only fetches URLs that the operator is allowed to access, optionally with a
user-provided Cookie header stored outside git under .secrets/.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
import json
import re
import socket


DEFAULT_USER_AGENTS: dict[str, str] = {
    "mobile": (
        "Mozilla/5.0 (Linux; Android 12; M2007J3SC) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Mobile Safari/537.36"
    ),
    "pc": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
}


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes
    text: str
    error: str = ""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_slug(value: str, max_len: int = 120) -> str:
    parsed = urlparse(value)
    raw = "_".join(x for x in [parsed.netloc, parsed.path.replace("/", "_")] if x)
    raw = raw or value
    raw = re.sub(r"[^0-9A-Za-z._-]+", "_", raw).strip("._-")
    return (raw[:max_len] or "url").lower()


def load_cookie_header(path: str | Path | None) -> str | None:
    """Load a Cookie header from a raw cookie file or Netscape cookie jar.

    Accepted formats:
    - One-line raw header: "pt_key=...; pt_pin=..."
    - Header prefixed with "Cookie:"
    - Netscape cookie format exported by browser tools.
    """

    if not path:
        return None

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"cookie file not found: {p}")

    text = p.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None

    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line.lower().startswith("cookie:"):
        return first_line.split(":", 1)[1].strip()

    if ";" in text and "=" in text and "\n" not in text:
        return text.strip()

    pairs: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            name = parts[-2].strip()
            value = parts[-1].strip()
            if name:
                pairs.append(f"{name}={value}")

    if pairs:
        return "; ".join(pairs)

    if "=" in first_line:
        return first_line

    return None


def redact_cookie_header(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for item in value.split(";"):
        key = item.split("=", 1)[0].strip()
        if key:
            parts.append(f"{key}=***")
    return "; ".join(parts)


def fetch_url(
    url: str,
    *,
    ua: str = "mobile",
    cookie_header: str | None = None,
    timeout: float = 20.0,
    max_bytes: int = 1_200_000,
) -> FetchResult:
    headers = {
        "User-Agent": DEFAULT_USER_AGENTS.get(ua, DEFAULT_USER_AGENTS["mobile"]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    req = Request(url, headers=headers, method="GET")
    opener = build_opener()

    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            hdrs = {str(k): str(v) for k, v in resp.headers.items()}
            charset = _charset_from_headers(hdrs) or "utf-8"
            text = raw.decode(charset, errors="replace")
            return FetchResult(
                url=url,
                final_url=resp.geturl(),
                status=int(getattr(resp, "status", 200) or 200),
                headers=hdrs,
                body=raw,
                text=text,
            )
    except HTTPError as exc:
        raw = exc.read(max_bytes)
        hdrs = {str(k): str(v) for k, v in exc.headers.items()} if exc.headers else {}
        charset = _charset_from_headers(hdrs) or "utf-8"
        return FetchResult(
            url=url,
            final_url=exc.geturl() if hasattr(exc, "geturl") else url,
            status=int(exc.code),
            headers=hdrs,
            body=raw,
            text=raw.decode(charset, errors="replace"),
            error=str(exc),
        )
    except (URLError, TimeoutError, socket.timeout) as exc:
        return FetchResult(
            url=url,
            final_url=url,
            status=0,
            headers={},
            body=b"",
            text="",
            error=repr(exc),
        )


def _charset_from_headers(headers: dict[str, str]) -> str | None:
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    m = re.search(r"charset=([A-Za-z0-9._-]+)", content_type)
    return m.group(1) if m else None


def extract_assets(html: str, base_url: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, flags=re.I):
        value = unescape(m.group(1).strip())
        if not value or value.startswith(("javascript:", "data:", "mailto:")):
            continue
        full = urljoin(base_url, value)
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def extract_endpoint_hits(text: str) -> dict[str, list[str]]:
    """Find high-value endpoint and functionId hints from HTML/JS text."""

    patterns: dict[str, str] = {
        "function_id": r"""functionId["']?\s*[:=]\s*["']([^"']+)["']""",
        "api_m_jd": r"""https?://api\.m\.jd\.com[^"'\\\s<>()]+""",
        "union_domain": r"""https?://[^"'\\\s<>()]*union[^"'\\\s<>()]+""",
        "jingfen_domain": r"""https?://[^"'\\\s<>()]*jingfen[^"'\\\s<>()]+""",
        "route_path": r"""["'](/(?:api|open|union|jingfen|mall|gw|rest)[^"']{3,160})["']""",
    }
    result: dict[str, list[str]] = {}
    for key, pattern in patterns.items():
        vals: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(pattern, text, flags=re.I):
            value = match.group(1) if match.groups() else match.group(0)
            value = value.strip()
            if value and value not in seen:
                seen.add(value)
                vals.append(value)
        result[key] = vals[:200]
    return result


def login_hint(text: str) -> bool:
    hay = text.lower()
    markers = ["登录", "passport", "plogin", "请登录", "login", "二维码"]
    return any(x.lower() in hay for x in markers)


def product_hint(text: str) -> bool:
    markers = ["到手价", "佣金", "赚￥", "赚¥", "热销", "商品", "sku", "京喜自营"]
    return any(x in text for x in markers)


def write_fetch_record(outdir: Path, index: int, ua: str, result: FetchResult) -> dict[str, object]:
    outdir.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(result.url)
    prefix = f"{index:03d}_{ua}_{slug}"
    body_path = outdir / f"{prefix}.html"
    headers_path = outdir / f"{prefix}.headers.json"
    meta_path = outdir / f"{prefix}.meta.json"

    body_path.write_bytes(result.body)
    headers_path.write_text(json.dumps(result.headers, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = {
        "url": result.url,
        "final_url": result.final_url,
        "status": result.status,
        "error": result.error,
        "body_size": len(result.body),
        "login_hint": login_hint(result.text),
        "product_hint": product_hint(result.text),
        "assets_count": len(extract_assets(result.text, result.final_url or result.url)),
        "body_file": str(body_path),
        "headers_file": str(headers_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["meta_file"] = str(meta_path)
    return meta
