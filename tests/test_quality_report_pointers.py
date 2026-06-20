from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QualityReportPointerTests(unittest.TestCase):
    def test_engineering_report_paths_are_pointers(self) -> None:
        names = (
            "project_engineering_audit_latest.json",
            "project_engineering_active_audit_latest.json",
        )
        for name in names:
            path = ROOT / "reports" / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("aideal-quality-report-pointer/v1", payload["schema_version"])
            self.assertFalse(payload["authority"])


if __name__ == "__main__":
    unittest.main()
