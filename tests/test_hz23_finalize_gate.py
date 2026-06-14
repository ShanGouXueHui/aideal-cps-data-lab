from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


class Hz23FinalizeGateTest(unittest.TestCase):
    def run_finalize(
        self,
        *,
        worker_name: str = "hz21_strict_card_dom",
        successful_probes: int = 2,
        observed_hours: float = 49.0,
    ) -> dict[str, object]:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "run" / "hz23_finalize_round.py"
        round_id = "test_round"

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data/state").mkdir(parents=True)
            (root / "data/import").mkdir(parents=True)
            (root / "reports").mkdir(parents=True)
            (root / "run").mkdir(parents=True)

            sku = "100012345678"
            catalog = {
                "version": 1,
                "products": {
                    sku: {
                        "title": "测试商品",
                        "item_url": f"https://item.jd.com/{sku}.html",
                        "image_url": "https://img.example.invalid/product.jpg",
                        "price": "99.90",
                        "commission_rate": "12.5%",
                        "estimated_income": "12.49",
                        "last_checked_at": "2026-06-14T10:00:00",
                        "last_seen_at": "2026-06-14T10:00:00",
                        "last_round_id": round_id,
                        "change_count": 0,
                        "missing_rounds": 0,
                        "active": True,
                    }
                },
            }
            (root / "data/state/hz23_catalog_index.json").write_text(
                json.dumps(catalog, ensure_ascii=False),
                encoding="utf-8",
            )
            (root / f"data/state/hz23_round_{round_id}_seen.jsonl").write_text(
                json.dumps({"sku": sku, "page_no": 1}) + "\n",
                encoding="utf-8",
            )
            trusted = {
                "status": "ok",
                "sku": sku,
                "title": "测试商品",
                "item_url": f"https://item.jd.com/{sku}.html",
                "image_url": "https://img.example.invalid/product.jpg",
                "price": "99.90",
                "commission_rate": "12.5%",
                "estimated_income": "12.49",
                "short_url": "https://u.jd.com/example",
                "worker_name": worker_name,
                "page_no": 1,
                "run_id": "run-1",
            }
            (root / "data/import/hz_jd_union_all_product_full_links_latest.jsonl").write_text(
                json.dumps(trusted, ensure_ascii=False) + "\n",
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
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            state = {
                "created_at": (datetime.now() - timedelta(hours=observed_hours)).isoformat(timespec="seconds"),
                "observation_started_at": (datetime.now() - timedelta(hours=observed_hours)).isoformat(timespec="seconds"),
                "successful_probes": successful_probes,
            }
            (root / "run/hz23_observer_state.json").write_text(
                json.dumps(state),
                encoding="utf-8",
            )

            env = dict(os.environ)
            completed = subprocess.run(
                [sys.executable, str(script), round_id, str(summary_path)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest_path = root / "data/export/aideal_cps_products_commercial_candidate_manifest.json"
            return json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_complete_observation_is_ready(self) -> None:
        manifest = self.run_finalize()
        self.assertTrue(manifest["round_complete"])
        self.assertTrue(manifest["candidate_integrity_ready"])
        self.assertTrue(manifest["observation_ready"])
        self.assertEqual(manifest["duplicate_sku_count"], 0)
        self.assertEqual(manifest["rejected"]["unsafe_hz20"], 0)

    def test_hz20_contamination_blocks_candidate(self) -> None:
        manifest = self.run_finalize(worker_name="hz20_mouse_click")
        self.assertFalse(manifest["candidate_integrity_ready"])
        self.assertFalse(manifest["observation_ready"])
        self.assertEqual(manifest["rejected"]["unsafe_hz20"], 1)
        self.assertIn("unsafe_hz20_zero", manifest["gate_failures"])

    def test_probe_and_time_gates_are_enforced(self) -> None:
        manifest = self.run_finalize(successful_probes=1, observed_hours=24)
        self.assertFalse(manifest["observation_ready"])
        self.assertIn("successful_probes_minimum", manifest["gate_failures"])
        self.assertIn("observation_hours_minimum", manifest["gate_failures"])


if __name__ == "__main__":
    unittest.main()
