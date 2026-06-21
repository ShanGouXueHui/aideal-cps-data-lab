from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = ROOT / "run" / "ci_bridge_latest.env"
REPORT_PATH = ROOT / "reports" / "ci_bridge_evidence_latest.json"


def read_summary() -> dict[str, str]:
    values: dict[str, str] = {}
    if not SUMMARY_PATH.exists():
        return values
    for raw in SUMMARY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key] = value
    return values


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def read_tail(path: str, limit: int = 160) -> list[str]:
    log_path = Path(path)
    if not log_path.is_absolute():
        log_path = ROOT / log_path
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]


def main() -> int:
    summary = read_summary()
    payload = {
        "schema_version": "ci-bridge-evidence/v1",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_head": git_head(),
        "summary": summary,
        "log_tail": read_tail(summary.get("LOG_FILE", "")),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(REPORT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
