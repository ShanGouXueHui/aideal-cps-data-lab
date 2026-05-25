#!/usr/bin/env python3
"""HZ15 jump-pages collector v2.

Fix over v1:
- Previous STOP at page 11 was caused by the broad generic risk marker "风险".
  Normal JD Union product/list pages can contain that word in ordinary page text,
  which creates false-positive STOP_REQUIRED.
- v2 patches risk detection to explicit verification signals only:
  risk_handler / 京东验证 / 快速验证 / 安全验证 / 验证码 / 滑块 / 购物无忧.

Scope remains unchanged:
- 商品推广 / 全部商品 only.
- Cumulative latest bootstrap from historical HZ12/HZ14/HZ15 files.
- Element UI jump input navigation.
- Single bad SKU skip behavior retained through HZ14 v3/v4 dependency chain.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

V1_PATH = Path("run/hz15_jump_pages_collector.py")


def load_v1():
    if not V1_PATH.exists():
        raise RuntimeError(f"missing dependency: {V1_PATH}")
    spec = importlib.util.spec_from_file_location("hz15_v1", str(V1_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


v1 = load_v1()
base_v1 = v1.v1

STRICT_RISK_MARKERS = [
    "risk_handler",
    "京东验证",
    "快速验证",
    "安全验证",
    "验证码",
    "滑块",
    "购物无忧",
]


def strict_page_text(page) -> str:
    try:
        return page.evaluate("() => document.body ? (document.body.innerText || '') : ''")
    except Exception:
        return ""


def strict_risk_info(page) -> List[str]:
    txt = strict_page_text(page)
    url = page.url or ""
    title = ""
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    haystack = "\n".join([url, title, txt])
    return [x for x in STRICT_RISK_MARKERS if x in haystack]


def strict_check_risk(page, context: str) -> None:
    risk = strict_risk_info(page)
    if risk:
        base_v1.stop_required("jd_risk_verification_required", context=context, url=page.url, risk=risk)


def strict_page_info(page) -> Dict[str, Any]:
    info = v1.page_info(page)
    info["risk"] = strict_risk_info(page)
    return info


# Patch both HZ15 and imported HZ14 base module globals used dynamically.
base_v1.RISK_MARKERS = STRICT_RISK_MARKERS
base_v1.risk_info = strict_risk_info
base_v1.check_risk = strict_check_risk
v1.page_info = strict_page_info
v1.v1.RISK_MARKERS = STRICT_RISK_MARKERS
v1.v1.risk_info = strict_risk_info
v1.v1.check_risk = strict_check_risk

if __name__ == "__main__":
    v1.main()
