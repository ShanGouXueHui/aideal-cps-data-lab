from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.contracts import canonical_payload_hash
from aideal_cps_data_lab.testing import FIXTURES


class BackfillExecutionGateTest(unittest.TestCase):
    def build_fixture(
        self,
        *,
        observation_ready: bool,
    ) -> tuple[Path, Path, Path, Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        candidate = root / "candidate.jsonl"
        manifest = root / "manifest.json"
        status = root / "status.json"
        report = root / "report.json"

        row: dict[str, object] = {
            "schema_version": "aideal-cps-product-feed/v1",
            "source": "jd_union_datalab",
            "sku": FIXTURES.sku,
            "title": "测试商品",
            "item_url": FIXTURES.item_url,
            "promotion_url": FIXTURES.promotion_url,
            "short_url": FIXTURES.promotion_url,
            "image_url": FIXTURES.image_url,
            "price": "99.90",
            "commission_rate": "12.5000",
            "estimated_commission": "12.49",
            "status": "active",
            "source_round_id": "round-1",
            "source_page_no": 1,
            "catalog_change_count": 0,
        }
        row["source_payload_hash"] = canonical_payload_hash(row)
        candidate_text = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        candidate.write_text(candidate_text, encoding="utf-8")
        manifest_payload = {
            "schema_version": "aideal-cps-product-feed-manifest/v1",
            "feed_schema_version": "aideal-cps-product-feed/v1",
            "feed_status": "candidate",
            "round_id": "round-1",
            "data_sha256": hashlib.sha256(candidate_text.encode("utf-8")).hexdigest(),
            "row_count": 1,
            "eligible_sku_count": 1,
            "duplicate_sku_count": 0,
            "rejected": {"unsafe_hz20": 0, "untrusted_promotion_url": 0},
            "commercial_enabled": False,
        }
        manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
        status.write_text(
            json.dumps(
                {
                    "service": {"state": "active"},
                    "observation_ready": observation_ready,
                    "mysql_initialization_allowed": observation_ready,
                    "latest_round": {"round_id": "round-1"},
                    "candidate_manifest": {"round_id": "round-1"},
                }
            ),
            encoding="utf-8",
        )
        return candidate, manifest, status, report, tmp

    def run_command(
        self,
        candidate: Path,
        manifest: Path,
        status: Path,
        report: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "backfill_commission_products_mysql.py"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root / "src")
        env.pop("DATA_LAB_DB_WRITE_ENABLED", None)
        env.pop("DATA_LAB_DATABASE_URL", None)
        env.pop("DATA_LAB_MYSQL_DEFAULT_FILE", None)
        return subprocess.run(
            [
                sys.executable,
                str(script),
                str(candidate),
                "--manifest",
                str(manifest),
                "--commercial-status",
                str(status),
                "--report",
                str(report),
                *extra,
            ],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dry_run_validates_without_requiring_observation_gate(self) -> None:
        candidate, manifest, status, report, tmp = self.build_fixture(
            observation_ready=False
        )
        self.addCleanup(tmp.cleanup)
        completed = self.run_command(candidate, manifest, status, report)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertFalse(result["ready_for_execute"])
        self.assertIn("observation_ready", result["gate_failures"])

    def test_execute_is_blocked_before_database_settings_when_observation_not_ready(self) -> None:
        candidate, manifest, status, report, tmp = self.build_fixture(
            observation_ready=False
        )
        self.addCleanup(tmp.cleanup)
        completed = self.run_command(
            candidate,
            manifest,
            status,
            report,
            "--execute",
            "--run-id",
            "backfill-test",
        )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(result["error"], "commercial_backfill_gate_not_ready")
        self.assertIn("observation_ready", result["gate_failures"])
        self.assertIn("mysql_initialization_allowed", result["gate_failures"])

    def test_execute_reaches_write_feature_flag_only_after_commercial_gate(self) -> None:
        candidate, manifest, status, report, tmp = self.build_fixture(
            observation_ready=True
        )
        self.addCleanup(tmp.cleanup)
        completed = self.run_command(
            candidate,
            manifest,
            status,
            report,
            "--execute",
            "--run-id",
            "backfill-test",
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("DATA_LAB_DB_WRITE_ENABLED is false", completed.stderr)


if __name__ == "__main__":
    unittest.main()
