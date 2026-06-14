#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

TARGET = Path("run/hz21_strict_card_dom_recover_page.py")
ORDINARY_COPY = "购物无忧"
REPLACEMENTS = {
    "RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']":
        "RISK=['risk_handler','京东验证','快速验证','安全验证','验证码','滑块']",
    "risk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块','购物无忧']":
        "risk:['risk_handler','京东验证','快速验证','安全验证','验证码','滑块']",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or repair the HZ23/HZ21 strong-risk keyword policy without running browser automation."
    )
    parser.add_argument("--fix", action="store_true", help="Apply the two known safe replacements.")
    args = parser.parse_args()

    result: dict[str, object] = {
        "target": str(TARGET),
        "exists": TARGET.exists(),
        "fix_requested": args.fix,
        "changed": False,
        "ordinary_copy_present_before": None,
        "ordinary_copy_present_after": None,
        "python_syntax_ok": False,
        "replacement_hits": {},
        "ok": False,
    }

    if not TARGET.exists():
        result["error"] = "target_missing"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    original = TARGET.read_text(encoding="utf-8")
    result["ordinary_copy_present_before"] = ORDINARY_COPY in original
    updated = original

    hits: dict[str, int] = {}
    if args.fix:
        for old, new in REPLACEMENTS.items():
            count = updated.count(old)
            hits[old] = count
            updated = updated.replace(old, new)
        if updated != original:
            tmp = TARGET.with_suffix(TARGET.suffix + ".tmp")
            tmp.write_text(updated, encoding="utf-8")
            tmp.replace(TARGET)
            result["changed"] = True
    result["replacement_hits"] = hits

    current = TARGET.read_text(encoding="utf-8")
    result["ordinary_copy_present_after"] = ORDINARY_COPY in current

    try:
        ast.parse(current, filename=str(TARGET))
        result["python_syntax_ok"] = True
    except SyntaxError as exc:
        result["syntax_error"] = {
            "line": exc.lineno,
            "offset": exc.offset,
            "message": exc.msg,
        }

    result["ok"] = bool(
        result["python_syntax_ok"]
        and result["ordinary_copy_present_after"] is False
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
