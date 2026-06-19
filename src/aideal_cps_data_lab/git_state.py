from __future__ import annotations

import subprocess
from collections.abc import Iterable

ACTIVE_PATHS = (
    "src",
    "run",
    "scripts",
    "config",
    "tests",
    ".github",
)


def current_git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def active_paths_unchanged_since(
    base_sha: str,
    paths: Iterable[str] = ACTIVE_PATHS,
) -> bool:
    if not base_sha:
        return False
    verify = subprocess.run(
        ["git", "cat-file", "-e", f"{base_sha}^{{commit}}"],
        check=False,
        capture_output=True,
    )
    if verify.returncode != 0:
        return False
    result = subprocess.run(
        ["git", "diff", "--quiet", f"{base_sha}..HEAD", "--", *paths],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0
