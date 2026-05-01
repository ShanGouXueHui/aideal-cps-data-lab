#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from aideal_cps_data_lab.io_utils import read_jsonl
from aideal_cps_data_lab.schema import ProductSnapshot


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=src python3 scripts/validate_export_jsonl.py data/import/file.jsonl")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"missing_file={path}")
        return 1

    rows = read_jsonl(path)
    ok = 0
    bad = 0
    for idx, row in enumerate(rows, start=1):
        try:
            item = ProductSnapshot.from_dict(row)
            if not item.title.strip():
                raise ValueError("empty title")
            ok += 1
        except Exception as exc:
            bad += 1
            print(f"bad_row line={idx} error={exc}")

    print(f"validated_file={path}")
    print(f"ok={ok}")
    print(f"bad={bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
