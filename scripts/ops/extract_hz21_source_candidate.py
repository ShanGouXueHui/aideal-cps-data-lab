from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
LOCATOR = ROOT / "reports" / "hz21_collector_source_locator_latest.json"
OUTPUT = ROOT / "reports" / "hz21_source_candidate_extract_latest.json"
KEYWORDS = (
    "一键领链",
    "我要推广",
    "short_url_timeout",
    "short_url",
    "u.jd.com",
    "known_sku_count",
    "page_no",
    "page_summary",
    "HZ21_PAGE_SEQUENCE",
    "推广位",
    "所属网站",
    "dialog",
    "modal",
    "click",
    "sku",
)


def score_candidate(item: dict[str, object]) -> int:
    path = str(item.get("path") or "")
    hits = set(item.get("content_hits") or [])
    score = len(hits) * 20
    if path.endswith(".py"):
        score += 50
    if "/backups/" in path:
        score += 20
    if "hz11" in path:
        score += 10
    if item.get("has_hz21_page_sequence"):
        score += 20
    if item.get("has_short_url_timeout"):
        score += 20
    if "reports/" in path or "scripts/ops/" in path or "src/aideal_cps_data_lab/hz21/" in path:
        score -= 1000
    return score


def read_locator() -> dict[str, object]:
    if not LOCATOR.exists():
        return {}
    try:
        return json.loads(LOCATOR.read_text(encoding="utf-8"))
    except Exception:
        return {}


def collect_keyword_windows(lines: list[str]) -> list[dict[str, object]]:
    windows: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for idx, line in enumerate(lines, start=1):
        if not any(keyword in line for keyword in KEYWORDS):
            continue
        start = max(1, idx - 8)
        end = min(len(lines), idx + 12)
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        windows.append(
            {
                "match_line": idx,
                "start_line": start,
                "end_line": end,
                "lines": [
                    {"line": no, "text": lines[no - 1][:300]}
                    for no in range(start, end + 1)
                ],
            }
        )
        if len(windows) >= 30:
            break
    return windows


def collect_defs(lines: list[str]) -> list[dict[str, object]]:
    defs: list[dict[str, object]] = []
    pattern = re.compile(r"^(def|async def|class)\s+")
    for idx, line in enumerate(lines, start=1):
        if not pattern.match(line):
            continue
        start = idx
        end = min(len(lines), idx + 8)
        defs.append(
            {
                "line": idx,
                "signature": line[:300],
                "preview": [
                    {"line": no, "text": lines[no - 1][:300]}
                    for no in range(start, end + 1)
                ],
            }
        )
    return defs[:120]


def extract(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "size_bytes": path.stat().st_size,
        "line_count": len(lines),
        "first_120_lines": [
            {"line": no, "text": lines[no - 1][:300]}
            for no in range(1, min(len(lines), 120) + 1)
        ],
        "definitions": collect_defs(lines),
        "keyword_windows": collect_keyword_windows(lines),
    }


def main() -> int:
    locator = read_locator()
    candidates = [item for item in locator.get("matches") or [] if str(item.get("path") or "").endswith(".py")]
    candidates = sorted(candidates, key=score_candidate, reverse=True)
    selected = []
    for item in candidates[:5]:
        p = Path(str(item.get("path") or ""))
        if p.exists() and p.is_file():
            selected.append(extract(p))
    payload = {
        "schema_version": "hz21-source-candidate-extract/v1",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "read_only": True,
        "locator_report": str(LOCATOR.relative_to(ROOT)),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "selected": selected,
        "status": "FOUND" if selected else "NOT_FOUND",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STATUS=" + payload["status"])
    print("CANDIDATE_COUNT=" + str(payload["candidate_count"]))
    print("SELECTED_COUNT=" + str(payload["selected_count"]))
    print("REPORT=" + str(OUTPUT.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
