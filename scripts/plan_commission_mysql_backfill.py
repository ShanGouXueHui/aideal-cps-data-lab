#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aideal_cps_data_lab.application import build_backfill_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and deduplicate a commission candidate JSONL before MySQL backfill."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/commission_mysql_backfill_plan_latest.json"))
    args = parser.parse_args()

    if not args.input.exists():
        result = {"ok": False, "error": "input_missing", "input": str(args.input)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    plan = build_backfill_plan(args.input)
    result = {"ok": True, "mode": "dry_run", **plan.summary()}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.report.with_suffix(args.report.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(args.report)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ready_for_write"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
