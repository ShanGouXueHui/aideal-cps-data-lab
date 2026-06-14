#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aideal_cps_data_lab.application import validate_candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the commercial candidate JSONL and manifest before MySQL backfill."
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/export/aideal_cps_products_commercial_candidate_manifest.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/commercial_candidate_validation_latest.json"),
    )
    args = parser.parse_args()

    result = validate_candidate(args.candidate, args.manifest).as_dict()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.report.with_suffix(args.report.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(args.report)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
