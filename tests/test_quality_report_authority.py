from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QualityReportAuthorityTests(unittest.TestCase):
    def test_main_contains_pointers_not_quality_snapshots(self) -> None:
        for name in (
            "project_engineering_audit_latest.json",
            "project_engineering_active_audit_latest.json",
        ):
            payload = json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))
            self.assertEqual("aideal-quality-report-pointer/v1", payload["schema_version"])
            self.assertFalse(payload["authority"])

    def test_ci_bridge_cannot_publish_quality_reports_to_main(self) -> None:
        source = (
            ROOT / "src/aideal_cps_data_lab/ops/ci_bridge_runner.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("git_publish_files_via_worktree.sh", source)
        self.assertNotIn("HEAD:main", source)
        self.assertIn("github_actions_quality_reports", source)

    def test_obsolete_engineering_audit_publisher_is_absent(self) -> None:
        self.assertFalse((ROOT / "scripts/run_engineering_scan_and_publish.sh").exists())

    def test_github_actions_publish_only_to_quality_reports(self) -> None:
        workflow = (ROOT / ".github/workflows/offline-quality.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("HEAD:quality-reports", workflow)
        self.assertNotIn("HEAD:main", workflow)


if __name__ == "__main__":
    unittest.main()
