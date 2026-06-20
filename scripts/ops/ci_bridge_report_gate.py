#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from aideal_cps_data_lab.ops import archive_reports, validate_reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stamp", default="manual")
    parser.add_argument("--expected-head", default="")
    args = parser.parse_args()

    if args.action == "prepare":
        moved = archive_reports(args.root, args.stamp)
        print("REPORT_ARCHIVE_COUNT=" + str(len(moved)))
        for path in moved:
            print("REPORT_ARCHIVED=" + path)
        return 0

    errors = validate_reports(args.root, args.expected_head)
    print("REPORT_GATE_ERROR_COUNT=" + str(len(errors)))
    for error in errors:
        print("REPORT_GATE_ERROR=" + error)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
