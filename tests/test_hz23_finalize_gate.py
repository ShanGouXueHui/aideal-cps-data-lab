from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.testing import FIXTURES


class Hz23FinalizeGateTest(unittest.TestCase):
    round_id = "test_round"

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def catalog(self) -> dict[str, Any]:
        return {
            "version": 1,
            "products": {
                FIXTURES.sku: {
                    "title": "测试商品",
                    "item_url": FIXTURES.item_url,
                    "image_url": FIXTURES.image_url,
                    "price": "99.90",
                    "commission_rate": "12.5%",
                    "estimated_income": "12.49",
                    "last_checked_at": FIXTURES.timestamp,
                    "last_seen_at": FIXTURES.timestamp,
                    "last_round_id": self.round_id,
                    "change_count": 0,
                    "missing_rounds": 0,
                    "active": True,
                }
            },
        }

    def trusted_row(self, worker_name: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "sku": FIXTURES.sku,
            "title": "测试商品",
            "item_url": FIXTURES.item_url,
            "image_url": FIXTURES.image_url,
            "price": "99.90",
            "commission_rate": "12.5%",
            "estimated_income": "12.49",
            "short_url": FIXTURES.promotion_url,
            "worker_name": worker_name,
            "page_no": 1,
            "run_id": "run-1",
        }

    def prepare_runtime(self, root: Path, worker_name: str, probes: int, hours: float) -> Path:
        self.write_json(root / "data/state/hz23_catalog_index.json", self.catalog())
        seen = root / f"data/state/hz23_round_{self.round_id}_seen.jsonl"
        seen.parent.mkdir(parents=True, exist_ok=True)
        seen.write_text(json.dumps({"sku": FIXTURES.sku, "page_no": 1}) + "\n")
        source = root / "data/import/hz_jd_union_all_product_full_links_latest.jsonl"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps(self.trusted_row(worker_name), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary = {
            "commercial_segment_complete": True,
            "completed_pages": list(range(1, 68)),
            "unfinished_pages": [],
            "scanned_total": 3900,
            "catalog_new": 100,
            "catalog_changed": 10,
            "catalog_unchanged": 3790,
            "last_known_sku_count": 4000,
            "stop_page": None,
            "stop_reason": None,
        }
        summary_path = root / "reports/round.json"
        self.write_json(summary_path, summary)
        started = datetime.now() - timedelta(hours=hours)
        self.write_json(
            root / "run/hz23_observer_state.json",
            {
                "created_at": started.isoformat(timespec="seconds"),
                "observation_started_at": started.isoformat(timespec="seconds"),
                "successful_probes": probes,
            },
        )
        return summary_path

    def run_finalize(
        self,
        *,
        worker_name: str = "hz21_strict_card_dom",
        successful_probes: int = 2,
        observed_hours: float = 49.0,
        expect_promoted: bool = True,
    ) -> dict[str, object]:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "run" / "hz23_finalize_round.py"
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            summary = self.prepare_runtime(
                root,
                worker_name,
                successful_probes,
                observed_hours,
            )
            completed = subprocess.run(
                [sys.executable, str(script), self.round_id, str(summary)],
                cwd=root,
                env=dict(os.environ),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0 if expect_promoted else 1, completed.stderr)
            report = (
                root / "data/export/aideal_cps_products_commercial_candidate_manifest.json"
                if expect_promoted
                else root / "reports/hz23_finalize_attempt_latest.json"
            )
            return json.loads(report.read_text(encoding="utf-8"))

    def test_complete_observation_is_ready(self) -> None:
        manifest = self.run_finalize()
        self.assertTrue(manifest["round_complete"])
        self.assertTrue(manifest["candidate_integrity_ready"])
        self.assertTrue(manifest["observation_ready"])
        self.assertEqual(manifest["duplicate_sku_count"], 0)
        self.assertEqual(manifest["rejected"]["unsafe_hz20"], 0)

    def test_hz20_contamination_blocks_candidate(self) -> None:
        manifest = self.run_finalize(worker_name="hz20_mouse_click", expect_promoted=False)
        self.assertFalse(manifest["candidate_integrity_ready"])
        self.assertFalse(manifest["observation_ready"])
        self.assertEqual(manifest["rejected"]["unsafe_hz20"], 1)
        self.assertIn("unsafe_hz20_zero", manifest["gate_failures"])
        self.assertFalse(manifest["promoted"])

    def test_probe_and_time_gates_are_enforced(self) -> None:
        manifest = self.run_finalize(
            successful_probes=1,
            observed_hours=24,
            expect_promoted=False,
        )
        self.assertFalse(manifest["observation_ready"])
        self.assertIn("successful_probes_minimum", manifest["gate_failures"])
        self.assertIn("observation_hours_minimum", manifest["gate_failures"])


if __name__ == "__main__":
    unittest.main()
