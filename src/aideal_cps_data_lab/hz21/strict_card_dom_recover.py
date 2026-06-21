from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

REPORT = Path("reports/hz21_strict_card_dom_recover_latest.json")


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": False,
        "reason": "hz21_collector_not_mainlined",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "controlled_entrypoint": True,
        "page_sequence": os.environ.get("HZ21_PAGE_SEQUENCE"),
        "limit": os.environ.get("HZ21_LIMIT"),
        "remediation": "mainline_hz21_browser_collector_before_hz23_new_candidate_generation",
    }
    REPORT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 66


if __name__ == "__main__":
    raise SystemExit(main())
