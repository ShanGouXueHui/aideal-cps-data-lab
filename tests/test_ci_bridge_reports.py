from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.ops import archive_reports, validate_reports


def offline_report(head: str = "current") -> dict[str, object]:
    return {
        "status": "PASS",
        "git_head": head,
        "generated_at": "now",
        "offline_mode": True,
        "jd_live_called": False,
        "test_failure_count": 0,
        "test_error_count": 0,
    }


def audit_report(head: str = "current") -> dict[str, object]:
    return {
        "status": "PASS",
        "git_head": head,
        "generated_at": "now",
        "global_blocker_count": 0,
        "full_gate_blocker_count": 0,
    }


class CiBridgeReportTests(unittest.TestCase):
    def write_report(self, root: Path, name: str, payload: dict[str, object]) -> None:
        target = root / "reports" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")

    def write_pair(
        self,
        root: Path,
        offline: dict[str, object],
        audit: dict[str, object],
    ) -> None:
        self.write_report(root, "offline_quality_latest.json", offline)
        self.write_report(root, "project_engineering_audit_latest.json", audit)

    def test_archive_removes_previous_latest_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pair(root, {"old": True}, {"old": True})
            moved = archive_reports(root, "stamp")
            self.assertEqual(2, len(moved))
            self.assertFalse((root / "reports/offline_quality_latest.json").exists())
            self.assertTrue(
                (root / "run/ci_bridge_previous_stamp/offline_quality_latest.json").exists()
            )

    def test_stale_head_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pair(root, offline_report("old"), audit_report("old"))
            errors = validate_reports(root, "current")
            self.assertEqual(2, sum("git_head_mismatch" in item for item in errors))

    def test_audit_blockers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = audit_report()
            audit.update(
                status="FAIL",
                global_blocker_count=3,
                full_gate_blocker_count=3,
            )
            self.write_pair(root, offline_report(), audit)
            errors = validate_reports(root, "current")
            self.assertIn("audit_status_not_pass", errors)
            self.assertIn("global_blockers_not_zero", errors)
            self.assertIn("full_gate_blockers_not_zero", errors)

    def test_offline_failures_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            offline = offline_report()
            offline.update(status="FAIL", test_failure_count=1, test_error_count=2)
            self.write_pair(root, offline, audit_report())
            errors = validate_reports(root, "current")
            self.assertIn("offline_status_not_pass", errors)
            self.assertIn("offline_failures_not_zero", errors)
            self.assertIn("offline_errors_not_zero", errors)

    def test_clean_reports_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pair(root, offline_report(), audit_report())
            self.assertEqual([], validate_reports(root, "current"))


if __name__ == "__main__":
    unittest.main()
