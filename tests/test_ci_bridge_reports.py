from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.ops import archive_reports, validate_reports


class CiBridgeReportTests(unittest.TestCase):
    def write_report(self, root: Path, name: str, payload: dict[str, object]) -> None:
        target = root / "reports" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")

    def test_archive_removes_previous_latest_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_report(root, "offline_quality_latest.json", {"old": True})
            self.write_report(root, "project_engineering_audit_latest.json", {"old": True})
            moved = archive_reports(root, "stamp")
            self.assertEqual(2, len(moved))
            self.assertFalse((root / "reports/offline_quality_latest.json").exists())
            self.assertTrue(
                (root / "run/ci_bridge_previous_stamp/offline_quality_latest.json").exists()
            )

    def test_stale_head_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_report(
                root,
                "offline_quality_latest.json",
                {
                    "git_head": "old",
                    "generated_at": "now",
                    "offline_mode": True,
                    "jd_live_called": False,
                },
            )
            self.write_report(
                root,
                "project_engineering_audit_latest.json",
                {
                    "git_head": "old",
                    "generated_at": "now",
                    "full_gate_blocker_count": 1,
                },
            )
            errors = validate_reports(root, "current")
            self.assertEqual(2, sum("git_head_mismatch" in item for item in errors))

    def test_fresh_offline_reports_pass_even_when_audit_has_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_report(
                root,
                "offline_quality_latest.json",
                {
                    "git_head": "current",
                    "generated_at": "now",
                    "offline_mode": True,
                    "jd_live_called": False,
                },
            )
            self.write_report(
                root,
                "project_engineering_audit_latest.json",
                {
                    "git_head": "current",
                    "generated_at": "now",
                    "full_gate_blocker_count": 3,
                },
            )
            self.assertEqual([], validate_reports(root, "current"))


if __name__ == "__main__":
    unittest.main()
