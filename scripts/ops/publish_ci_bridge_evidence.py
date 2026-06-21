from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run() -> int:
    build = subprocess.run(
        [sys.executable, "scripts/ops/ci_bridge_evidence.py"],
        cwd=ROOT,
        check=False,
    )
    if build.returncode != 0:
        print(f"CI_BRIDGE_EVIDENCE_BUILD_RC={build.returncode}")
        print("STATUS=FAIL")
        return build.returncode
    publish = subprocess.run(
        [
            "bash",
            "scripts/git_publish_files_via_worktree.sh",
            "reports: update ci bridge evidence",
            "reports/ci_bridge_evidence_latest.json",
        ],
        cwd=ROOT,
        check=False,
    )
    print("CI_BRIDGE_EVIDENCE_BUILD_RC=0")
    print(f"CI_BRIDGE_EVIDENCE_PUBLISH_RC={publish.returncode}")
    print("STATUS=PASS" if publish.returncode == 0 else "STATUS=FAIL")
    return publish.returncode


if __name__ == "__main__":
    raise SystemExit(run())
