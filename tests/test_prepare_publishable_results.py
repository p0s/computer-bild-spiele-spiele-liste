from __future__ import annotations

import unittest

from scripts.improved_release_common import normalize_rating
from scripts.prepare_publishable_results import (
    add_publication_coverage_unresolved,
    build_source_issue_inventory,
    clean_issue_rows,
    publishable_issue_rows,
)


def archive(name: str, issue_code: str) -> dict[str, str]:
    return {
        "archive_item": "cbs-2000-09",
        "archive_name": name,
        "archive_url": f"https://archive.org/download/cbs-2000-09/{name}",
        "size_bytes": "123",
        "sha1": "a" * 40,
        "issue_code": issue_code,
        "year": "2010",
        "variant": "DVD",
    }


class SourceCoverageTests(unittest.TestCase):
    def test_rating_value_and_scale_are_separate_numeric_fields(self) -> None:
        self.assertEqual(normalize_rating("73/100", ""), ("73", "100"))
        self.assertEqual(normalize_rating("8.5", "10"), ("8.5", "10"))

    def test_manual_candidate_include_recovers_strong_manifest_evidence(self) -> None:
        row = {
            **archive("2010/CBS012010DVD.7z", "CBS012010DVD"),
            "normalized_title": "ankh",
            "representative_title": "ANKH",
            "source_kinds": "disc-manifest-path",
            "confidence": "medium",
            "content_kind": "unknown",
        }
        override = {
            (row["archive_name"], row["normalized_title"]): {
                "representative_title": "Ankh",
                "action": "include",
            }
        }

        cleaned, dropped = clean_issue_rows([row], override)

        self.assertEqual(dropped, [])
        self.assertEqual(cleaned[0]["clean_reason"], "manual-include")
        self.assertEqual(publishable_issue_rows(cleaned)[0]["representative_title"], "Ankh")

    def test_zero_output_archive_remains_visible_and_unresolved(self) -> None:
        source_archives = [
            archive("2010/CBS012010DVD.7z", "CBS012010DVD"),
            archive("2010/CBS022010DVD.7z", "CBS022010DVD"),
        ]
        raw_rows = [
            {**source_archives[0], "representative_title": "Ankh"},
            {**source_archives[1], "representative_title": "Example Game"},
        ]
        cleaned_rows = list(raw_rows)
        published_rows = [{**raw_rows[1], "game_id": "examplegame"}]

        inventory = build_source_issue_inventory(
            source_archives,
            raw_rows,
            cleaned_rows,
            published_rows,
            [],
            [],
        )

        self.assertEqual(len(inventory), 2)
        self.assertEqual(inventory[0]["publication_status"], "unresolved_no_publishable_game")
        self.assertEqual(inventory[0]["source_sha1"], "a" * 40)
        self.assertEqual(inventory[1]["publication_status"], "published")

        unresolved = add_publication_coverage_unresolved([], inventory)
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["archive_name"], "2010/CBS012010DVD.7z")
        self.assertEqual(unresolved[0]["root_cause"], "no-publishable-game")

    def test_raw_extraction_failure_is_not_duplicated(self) -> None:
        source = archive("2010/CBS032010DVD.7z", "CBS032010DVD")
        raw_unresolved = [{**source, "reason": "download timed out"}]
        inventory = build_source_issue_inventory([source], [], [], [], [], raw_unresolved)
        analyzed = [
            {
                **raw_unresolved[0],
                "title_strategy": "auto",
                "resolution_path": "download",
                "status": "failed",
                "root_cause": "network/download",
                "retry_recommended": "yes",
                "suggestion": "retry",
            }
        ]

        self.assertEqual(inventory[0]["publication_status"], "unresolved_extraction")
        self.assertEqual(add_publication_coverage_unresolved(analyzed, inventory), analyzed)


if __name__ == "__main__":
    unittest.main()
