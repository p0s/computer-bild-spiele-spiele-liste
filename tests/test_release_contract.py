from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.release_contract import ROOT, check_contract, release_metadata, validate_redirects, validate_table


class ReleaseContractTests(unittest.TestCase):
    def test_release_metadata_is_derived_from_snapshot_directory(self) -> None:
        self.assertEqual(
            release_metadata(ROOT / "results" / "published-20260808"),
            ("20260808", "2026-08-08", "2026.8.8"),
        )

    def test_checked_in_release_satisfies_contract(self) -> None:
        self.assertEqual(
            check_contract(
                raw_dir=ROOT / "results" / "raw-candidates-20260325",
                published_dir=ROOT / "results" / "published-20260808",
                enriched_dir=ROOT / "results" / "enriched-20260808",
            ),
            [],
        )

    def test_table_validator_rejects_duplicate_and_malformed_ids(self) -> None:
        schema = {
            "fields": [
                {
                    "name": "game_id",
                    "type": "string",
                    "constraints": {"required": True, "pattern": "^[a-z0-9]+$"},
                },
                {"name": "data_quality_score", "type": "integer", "constraints": {"minimum": 0, "maximum": 100}},
            ],
            "primaryKey": "game_id",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "games.csv"
            path.write_text("game_id,data_quality_score\nbad-id,101\nbad-id,not-a-number\n", encoding="utf-8")

            _, problems = validate_table(path, schema)

        self.assertTrue(any("pattern" in problem for problem in problems))
        self.assertTrue(any("maximum" in problem for problem in problems))
        self.assertTrue(any("duplicate" in problem for problem in problems))
        self.assertTrue(any("not integer" in problem for problem in problems))

    def test_redirect_validator_rejects_missing_targets_and_cycles(self) -> None:
        problems = validate_redirects(
            {"active"},
            [
                {"source_game_id": "old-a", "target_game_id": "old-b"},
                {"source_game_id": "old-b", "target_game_id": "old-a"},
            ],
        )
        self.assertTrue(any("not active" in problem for problem in problems))
        self.assertTrue(any("cycle" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
