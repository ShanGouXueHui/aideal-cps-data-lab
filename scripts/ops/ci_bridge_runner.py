#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from aideal_cps_data_lab.ops.ci_bridge_runner import run_bridge


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "validate-publish"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    return run_bridge(args.root, args.action)


if __name__ == "__main__":
    raise SystemExit(main())
