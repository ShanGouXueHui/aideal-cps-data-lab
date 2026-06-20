from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.hz23.lkg_candidate_audit import build_candidate_report
from aideal_cps_data_lab.hz23.lkg_settings import LastKnownGoodSettings


def candidate_bytes(*skus: str) -> bytes:
    return "".join(
        json.dumps({"sku": sku}, sort_keys=True) + "\n"
        for sku in skus
    ).encode("utf-8")


class LastKnownGoodReadonlyAuditTests(unittest.TestCase):
    def settings(self, raw: bytes) -> LastKnownGoodSettings:
        return LastKnownGoodSettings(
            schema_version="hz23-last-known-good/v1",
            expected_round_id="round-1",
            expected_row_count=2,
            expected_data_sha256=hashlib.sha256(raw).hexdigest(),
            canonical_candidate=Path("data/export/candidate.jsonl"),
            canonical_manifest=Path("data/export/manifest.json"),
            service_name="observer.service",
            search_roots=(Path("data/export"), Path("backups")),
            candidate_name_fragments=("candidate", "last_known_good"),
        )

    def test_exact_candidate_is_found_without_mutation(self) -> None:
        raw = candidate_bytes("100", "200")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "data/export/candidate.jsonl"
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(raw)
            report = build_candidate_report(root, self.settings(raw))
        self.assertEqual("FOUND_EXACT_3304", report["status"])
        self.assertEqual(1, report["exact_match_count"])
        self.assertTrue(report["read_only"])


if __name__ == "__main__":
    unittest.main()
