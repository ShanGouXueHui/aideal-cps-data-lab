#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from aideal_cps_data_lab.hz24.audit_settings import load_audit_settings
from aideal_cps_data_lab.hz24.settings import load_settings
from aideal_cps_data_lab.hz24.structure_inspection import run_structure_inspection


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only structure audit for JD promotion tabs."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cdp")
    args = parser.parse_args()

    settings = load_settings()
    if args.cdp:
        settings = replace(
            settings,
            browser=replace(settings.browser, cdp_endpoint=args.cdp),
        )
    audit = load_audit_settings(settings)
    if args.output:
        audit = replace(audit, structure_report=args.output)
    return run_structure_inspection(settings, audit)


if __name__ == "__main__":
    raise SystemExit(main())
