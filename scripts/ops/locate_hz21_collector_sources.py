from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
OUTPUT = ROOT / "reports" / "hz21_collector_source_locator_latest.json"
NAME_HINTS = (
    "hz21_strict_card_dom_recover_page.py",
    "hz21_strong",
    "strict_card_dom_recover",
    "card_dom_recover",
)
CONTENT_HINTS = (
    "一键领链",
    "short_url_timeout",
    "HZ21_PAGE_SEQUENCE",
    "known_sku_count",
    "hz21_exact_sku_locator_safe_mouse_click",
    "所属网站",
    "推广位",
)
SKIP_DIRS = {".git", ".venv", ".venv-browser", "node_modules", "__pycache__"}


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def should_skip(path: Path) -> bool:
    return bool(set(path.parts) & SKIP_DIRS)


def inspect_file(path: Path) -> dict[str, object] | None:
    name_hit = any(hint in path.name for hint in NAME_HINTS)
    if path.suffix != ".py" and not name_hit:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    content_hits = [hint for hint in CONTENT_HINTS if hint in text]
    if not name_hit and not content_hits:
        return None
    lines = text.splitlines()
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "line_count": len(lines),
        "name_hit": name_hit,
        "content_hits": content_hits,
        "has_hz21_page_sequence": "HZ21_PAGE_SEQUENCE" in text,
        "has_short_url_timeout": "short_url_timeout" in text,
        "has_media_site_text": "所属网站" in text,
        "has_promotion_slot_text": "推广位" in text,
        "first_lines": lines[:8],
    }


def main() -> int:
    roots = [ROOT, Path.home(), Path("/home/cpsdata/projects"), Path("/home/cpsdata/backups")]
    seen: set[Path] = set()
    matches: list[dict[str, object]] = []
    scanned = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            scanned += 1
            item = inspect_file(resolved)
            if item:
                matches.append(item)
    matches.sort(key=lambda item: (not item["name_hit"], -len(item["content_hits"]), str(item["path"])))
    payload = {
        "schema_version": "hz21-collector-source-locator/v1",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_head": git_head(),
        "read_only": True,
        "roots": [str(root) for root in roots],
        "scanned_file_count": scanned,
        "match_count": len(matches),
        "status": "FOUND" if matches else "NOT_FOUND",
        "matches": matches[:100],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STATUS=" + payload["status"])
    print("SCANNED_FILE_COUNT=" + str(scanned))
    print("MATCH_COUNT=" + str(len(matches)))
    print("REPORT=" + str(OUTPUT.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
