from __future__ import annotations

import subprocess
from pathlib import Path


REPORT_PATHS = (
    "reports/project_engineering_audit_latest.json",
    "reports/offline_quality_latest.json",
    "reports/hz24_sold_out_migration_latest.json",
    "reports/hz24_terminal_repair_latest.json",
    "reports/hz24_resume_gate_latest.json",
)
OPTIONAL_PATH = "data/export/hz24_special_tab_outcomes_manifest.json"


def existing_paths(root: Path) -> list[str]:
    paths = [path for path in REPORT_PATHS if (root / path).is_file()]
    if (root / OPTIONAL_PATH).is_file():
        paths.append(OPTIONAL_PATH)
    return paths


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    files = existing_paths(root)
    command = [
        "bash",
        str(root / "scripts/git_publish_files_via_worktree.sh"),
        "reports: publish HZ24 terminal repair evidence",
        *files,
    ]
    completed = subprocess.run(command, cwd=root, check=False)
    status = "PASS" if completed.returncode == 0 else "FAIL"
    print("===== SUMMARY =====")
    print(f"STATUS={status}")
    print(f"PUBLISH_RC={completed.returncode}")
    print("JSONL_PUBLISHED=false")
    print("SECRETS_PUBLISHED=false")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
