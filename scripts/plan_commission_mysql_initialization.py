#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

STATUS = Path("reports/hz23_commercial_status_v2_latest.json")
UPGRADE = Path("migrations/mysql/0001_commission_data_v1.up.sql")
ROLLBACK = Path("migrations/mysql/0001_commission_data_v1.down.sql")
CANDIDATE = Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl")
MANIFEST = Path("data/export/aideal_cps_products_commercial_candidate_manifest.json")
REPORT = Path("reports/commission_mysql_initialization_plan_latest.json")


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> int:
    status = load(STATUS)
    manifest = load(MANIFEST)
    checks = {
        "status_present": bool(status),
        "service_active": ((status.get("service") or {}).get("state") == "active"),
        "observation_ready": status.get("observation_ready") is True,
        "mysql_initialization_allowed": status.get("mysql_initialization_allowed") is True,
        "full_round_complete": ((status.get("checks") or {}).get("full_round_complete") is True),
        "candidate_integrity_ready": ((status.get("checks") or {}).get("candidate_integrity_ready") is True),
        "candidate_file_present": CANDIDATE.exists(),
        "candidate_manifest_present": bool(manifest),
        "upgrade_file_present": UPGRADE.exists(),
        "rollback_file_present": ROLLBACK.exists(),
        "commercial_switch_off": manifest.get("commercial_enabled") is False,
    }
    status_round = str(((status.get("latest_round") or {}).get("round_id")) or "")
    manifest_round = str(manifest.get("round_id") or "")
    checks["round_id_present"] = bool(status_round and manifest_round)
    checks["round_id_consistent"] = bool(status_round and status_round == manifest_round)

    result = {
        "schema_version": "aideal-commission-mysql-initialization-plan/v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "database_name": "aideal_cps_data_lab",
        "database_bind": "127.0.0.1:3306",
        "upgrade_file": str(UPGRADE),
        "upgrade_sha256": digest(UPGRADE),
        "rollback_file": str(ROLLBACK),
        "rollback_sha256": digest(ROLLBACK),
        "candidate_file": str(CANDIDATE),
        "candidate_sha256": digest(CANDIDATE),
        "candidate_rows": manifest.get("row_count"),
        "round_id": manifest_round or None,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "ready_for_database_initialization": all(checks.values()),
        "execution_performed": False,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(REPORT.suffix + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(REPORT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
