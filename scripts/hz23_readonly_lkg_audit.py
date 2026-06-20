from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from aideal_cps_data_lab.hz23.lkg_candidate_audit import build_candidate_report
from aideal_cps_data_lab.hz23.lkg_settings import load_last_known_good_settings


def git_value(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/hz23-last-known-good.toml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/hz23_lkg_readonly_audit_latest.json"),
    )
    args = parser.parse_args()
    root = Path.cwd()
    settings = load_last_known_good_settings(root / args.config)
    report = build_candidate_report(root, settings)
    status = git_value(root, "status", "--porcelain", "--untracked-files=no")
    report["git"] = {
        "head": git_value(root, "rev-parse", "HEAD"),
        "branch": git_value(root, "branch", "--show-current"),
        "tracked_worktree_clean": not bool(status),
        "tracked_change_count": len(status.splitlines()) if status else 0,
    }
    report["actions_executed"] = {
        "jd_live": False,
        "mysql": False,
        "candidate_restore": False,
        "finalize": False,
        "business_publish": False,
    }
    destination = root / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidate_count": report["candidate_count"],
                "exact_match_count": report["exact_match_count"],
                "report": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
