from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aideal_cps_data_lab.hz23.finalize_io import FinalizePaths
from aideal_cps_data_lab.hz23.finalize_publish import persist_outcome
from aideal_cps_data_lab.hz23.finalize_source import select_source
from aideal_cps_data_lab.hz24.settings import load_settings


class HZ23SourceSelectionTests(unittest.TestCase):
    def test_empty_primary_falls_back_to_usable_secondary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "primary.jsonl"
            secondary = root / "secondary.jsonl"
            primary.write_text("", encoding="utf-8")
            secondary.write_text(
                json.dumps(
                    {
                        "sku": "100012345678",
                        "status": "ok",
                        "short_url": "https://u.jd.com/example",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            selected = select_source((primary, secondary), load_settings())
            self.assertEqual(secondary, selected.path)
            self.assertEqual(1, selected.source_row_count)
            self.assertEqual({"100012345678"}, set(selected.dedup))
            self.assertEqual(2, len(selected.evaluated))


class HZ23CandidatePromotionTests(unittest.TestCase):
    def paths(self, root: Path) -> FinalizePaths:
        return FinalizePaths(
            summary=root / "summary.json",
            index=root / "index.json",
            seen=root / "seen.jsonl",
            observer_state=root / "observer.json",
            source_candidates=(root / "source.jsonl",),
            export=root / "candidate.jsonl",
            manifest=root / "manifest.json",
        )

    def test_rejected_attempt_preserves_canonical_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.paths(root)
            attempt = root / "attempt.json"
            paths.export.write_text("old-candidate\n", encoding="utf-8")
            paths.manifest.write_text(
                json.dumps(
                    {
                        "round_id": "old-round",
                        "row_count": 3304,
                        "data_sha256": "old-hash",
                        "candidate_integrity_ready": True,
                        "observation_ready": True,
                    }
                ),
                encoding="utf-8",
            )
            old_manifest = paths.manifest.read_bytes()
            with patch(
                "aideal_cps_data_lab.hz23.finalize_publish.attempt_report_path",
                attempt,
            ):
                outcome = persist_outcome(
                    paths,
                    "",
                    {
                        "round_id": "failed-round",
                        "round_complete": True,
                        "candidate_integrity_ready": False,
                        "row_count": 0,
                        "candidate_file": str(paths.export),
                        "data_file": paths.export.name,
                    },
                )
            self.assertFalse(outcome["promoted"])
            self.assertEqual(b"old-candidate\n", paths.export.read_bytes())
            self.assertEqual(old_manifest, paths.manifest.read_bytes())
            self.assertTrue(outcome["canonical_candidate_preserved"])
            self.assertEqual("old-round", outcome["previous_manifest"]["round_id"])
            self.assertTrue(attempt.exists())

    def test_valid_attempt_promotes_candidate_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.paths(root)
            attempt = root / "attempt.json"
            with patch(
                "aideal_cps_data_lab.hz23.finalize_publish.attempt_report_path",
                attempt,
            ):
                outcome = persist_outcome(
                    paths,
                    '{"sku":"100"}\n',
                    {
                        "round_id": "valid-round",
                        "round_complete": True,
                        "candidate_integrity_ready": True,
                        "row_count": 1,
                        "candidate_file": str(paths.export),
                        "data_file": paths.export.name,
                    },
                )
            self.assertTrue(outcome["promoted"])
            self.assertEqual('{"sku":"100"}\n', paths.export.read_text(encoding="utf-8"))
            stored = json.loads(paths.manifest.read_text(encoding="utf-8"))
            self.assertEqual("valid-round", stored["round_id"])
            self.assertTrue(stored["promoted"])
            self.assertTrue(attempt.exists())


if __name__ == "__main__":
    unittest.main()
