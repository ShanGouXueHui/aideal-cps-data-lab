from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
TARGET = ROOT / "run" / "hz21_strict_card_dom_recover_page.py"
OUTPUT = ROOT / "reports" / "hz21_runtime_inspection_latest.json"
PATTERNS = (
    "HZ21_PAGE_SEQUENCE",
    "PAGE_SEQUENCE",
    "pageNo",
    "short_url_timeout",
    "所属网站",
    "推广位",
    "modal_keys",
    "known_sku_count",
)


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def grep_context(lines: list[str], pattern: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for index, line in enumerate(lines, start=1):
        if pattern in line:
            start = max(1, index - 3)
            end = min(len(lines), index + 3)
            out.append(
                {
                    "line": index,
                    "pattern": pattern,
                    "context": [
                        {"line": number, "text": lines[number - 1][:240]}
                        for number in range(start, end + 1)
                    ],
                }
            )
    return out[:20]


def main() -> int:
    payload: dict[str, object] = {
        "schema_version": "hz21-runtime-inspection/v1",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_head": git_head(),
        "target": str(TARGET.relative_to(ROOT)),
        "target_exists": TARGET.is_file(),
        "read_only": True,
    }
    if TARGET.is_file():
        text = TARGET.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        payload.update(
            {
                "line_count": len(lines),
                "sha256": sha256_text(text),
                "uses_hz21_page_sequence": "HZ21_PAGE_SEQUENCE" in text,
                "uses_page_sequence": "PAGE_SEQUENCE" in text,
                "mentions_short_url_timeout": "short_url_timeout" in text,
                "mentions_media_site": "所属网站" in text,
                "mentions_promotion_slot": "推广位" in text,
                "contexts": [item for pattern in PATTERNS for item in grep_context(lines, pattern)],
            }
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("REPORT=" + str(OUTPUT.relative_to(ROOT)))
    print("TARGET_EXISTS=" + str(payload.get("target_exists")))
    print("USES_HZ21_PAGE_SEQUENCE=" + str(payload.get("uses_hz21_page_sequence")))
    print("MENTIONS_SHORT_URL_TIMEOUT=" + str(payload.get("mentions_short_url_timeout")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
