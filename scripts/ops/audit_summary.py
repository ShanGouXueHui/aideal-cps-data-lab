from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
src = root / "reports" / "project_engineering_audit_latest.json"
out = root / "reports" / "audit_blocker_evidence_latest.json"
data = json.loads(src.read_text(encoding="utf-8"))
items = [x for x in data.get("findings", []) if x.get("severity") == "blocker"]
result = {
    "schema_version": "audit-blocker-evidence/v1",
    "git_head": data.get("git_head"),
    "status": data.get("status"),
    "blocker_count": data.get("blocker_count"),
    "quality_gate_counts": data.get("quality_gate_counts"),
    "blockers": items,
}
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out.relative_to(root))
