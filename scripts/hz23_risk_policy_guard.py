#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

TARGET = Path("run/hz21_strict_card_dom_recover_page.py")
POLICY = Path("config/hz23_risk_policy.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    strong = [str(x) for x in policy.get("strong_signals") or [] if str(x)]
    ignored = [str(x) for x in policy.get("ignored_page_copy") or [] if str(x)]
    source = TARGET.read_text(encoding="utf-8")
    before = [x for x in ignored if x in source]
    hits: dict[str, int] = {}

    updated = source
    for text in ignored:
        count = 0
        for quote in ("'", '"'):
            for pattern in (f",{quote}{text}{quote}", f"{quote}{text}{quote},"):
                count += updated.count(pattern)
                updated = updated.replace(pattern, "")
        hits[text] = count

    changed = False
    if args.fix and updated != source:
        tmp = TARGET.with_suffix(TARGET.suffix + ".tmp")
        tmp.write_text(updated, encoding="utf-8")
        tmp.replace(TARGET)
        changed = True

    current = TARGET.read_text(encoding="utf-8")
    syntax_ok = True
    syntax_error = None
    try:
        ast.parse(current, filename=str(TARGET))
    except SyntaxError as exc:
        syntax_ok = False
        syntax_error = {"line": exc.lineno, "offset": exc.offset, "message": exc.msg}

    after = [x for x in ignored if x in current]
    missing = [x for x in strong if x not in current]
    ok = syntax_ok and not after and not missing
    result = {
        "target": str(TARGET),
        "policy": str(POLICY),
        "fix_requested": args.fix,
        "changed": changed,
        "ignored_before": before,
        "ignored_after": after,
        "strong_signals_missing": missing,
        "replacement_hits": hits,
        "python_syntax_ok": syntax_ok,
        "syntax_error": syntax_error,
        "ok": ok,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
