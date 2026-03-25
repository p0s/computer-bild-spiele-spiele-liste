from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.merge_retry_snapshot import run_merge


ISSUE_TITLE_FIELDS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "normalized_title",
    "representative_title",
    "source_kinds",
    "confidence",
    "content_kind",
]

MASTER_GAME_FIELDS = [
    "normalized_title",
    "representative_title",
    "first_seen_issue",
    "issue_count",
    "occurrence_count",
    "best_confidence",
    "source_kinds",
]

UNRESOLVED_FIELDS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "title_strategy",
    "resolution_path",
    "reason",
    "status",
]

PUBLISHED_UNRESOLVED_FIELDS = UNRESOLVED_FIELDS + ["root_cause", "retry_recommended", "suggestion"]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class MergeRetrySnapshotTests(unittest.TestCase):
    def _write_base_snapshot(self, root: Path) -> tuple[Path, Path]:
        base_dir = root / "results" / "vps-linux-full-20260324"
        published_dir = root / "results" / "published-20260324"
        write_csv(
            base_dir / "issue_titles.csv",
            ISSUE_TITLE_FIELDS,
            [
                {
                    "archive_item": "cbs-2000-09",
                    "archive_name": "2006/CBS012006DVD.7z",
                    "issue_code": "CBS012006DVD",
                    "year": "2006",
                    "variant": "DVD",
                    "normalized_title": "stable game",
                    "representative_title": "Stable Game",
                    "source_kinds": "disc-metadata-value",
                    "confidence": "high",
                    "content_kind": "unknown",
                }
            ],
        )
        write_csv(
            base_dir / "master_games.csv",
            MASTER_GAME_FIELDS,
            [
                {
                    "normalized_title": "stable game",
                    "representative_title": "Stable Game",
                    "first_seen_issue": "CBS012006DVD",
                    "issue_count": "1",
                    "occurrence_count": "1",
                    "best_confidence": "high",
                    "source_kinds": "disc-metadata-value",
                }
            ],
        )
        write_csv(
            base_dir / "unresolved_issues.csv",
            UNRESOLVED_FIELDS,
            [
                {
                    "archive_item": "cbs-2000-09",
                    "archive_name": "2007/CBS022007DVD.7z",
                    "issue_code": "CBS022007DVD",
                    "year": "2007",
                    "variant": "DVD",
                    "title_strategy": "auto",
                    "resolution_path": "none",
                    "reason": "download failed",
                    "status": "extract_failed",
                }
            ],
        )
        write_csv(
            published_dir / "final_unresolved_issues.csv",
            PUBLISHED_UNRESOLVED_FIELDS,
            [
                {
                    "archive_item": "cbs-2000-09",
                    "archive_name": "2007/CBS022007DVD.7z",
                    "issue_code": "CBS022007DVD",
                    "year": "2007",
                    "variant": "DVD",
                    "title_strategy": "auto",
                    "resolution_path": "none",
                    "reason": "download failed",
                    "status": "extract_failed",
                    "root_cause": "network/download",
                    "retry_recommended": "yes",
                    "suggestion": "retry",
                }
            ],
        )
        return base_dir, published_dir

    def test_clean_retry_overlay_replaces_unresolved_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_dir, published_dir = self._write_base_snapshot(root)
            retry_dir = root / "results" / "vps-linux-retry-20260325"
            output_dir = root / "results" / "vps-linux-merged-20260325"

            write_csv(
                retry_dir / "issue_titles.csv",
                ISSUE_TITLE_FIELDS,
                [
                    {
                        "archive_item": "cbs-2000-09",
                        "archive_name": "2007/CBS022007DVD.7z",
                        "issue_code": "CBS022007DVD",
                        "year": "2007",
                        "variant": "DVD",
                        "normalized_title": "recovered game",
                        "representative_title": "Recovered Game",
                        "source_kinds": "disc-metadata-value",
                        "confidence": "high",
                        "content_kind": "unknown",
                    }
                ],
            )
            write_csv(
                retry_dir / "master_games.csv",
                MASTER_GAME_FIELDS,
                [
                    {
                        "normalized_title": "recovered game",
                        "representative_title": "Recovered Game",
                        "first_seen_issue": "CBS022007DVD",
                        "issue_count": "1",
                        "occurrence_count": "1",
                        "best_confidence": "high",
                        "source_kinds": "disc-metadata-value",
                    }
                ],
            )
            write_csv(retry_dir / "unresolved_issues.csv", UNRESOLVED_FIELDS, [])

            rc = run_merge(
                type(
                    "Args",
                    (),
                    {
                        "base_dir": str(base_dir),
                        "retry_dir": str(retry_dir),
                        "base_published_unresolved": str(published_dir / "final_unresolved_issues.csv"),
                        "output_dir": str(output_dir),
                        "comparison_report": None,
                    },
                )()
            )

            self.assertEqual(rc, 0)
            merged_issue_rows = read_csv(output_dir / "issue_titles.csv")
            merged_master_rows = read_csv(output_dir / "master_games.csv")
            merged_unresolved_rows = read_csv(output_dir / "unresolved_issues.csv")
            report_text = (output_dir / "comparison_report.md").read_text(encoding="utf-8")

            self.assertEqual({row["archive_name"] for row in merged_issue_rows}, {"2006/CBS012006DVD.7z", "2007/CBS022007DVD.7z"})
            self.assertEqual({row["normalized_title"] for row in merged_master_rows}, {"stable game", "recovered game"})
            self.assertEqual(merged_unresolved_rows, [])
            self.assertIn("recovered: `2007/CBS022007DVD.7z`", report_text)

    def test_schema_mismatch_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_dir, published_dir = self._write_base_snapshot(root)
            retry_dir = root / "results" / "vps-linux-retry-20260325"
            write_csv(
                retry_dir / "issue_titles.csv",
                ISSUE_TITLE_FIELDS[:-1],
                [
                    {
                        "archive_item": "cbs-2000-09",
                        "archive_name": "2007/CBS022007DVD.7z",
                        "issue_code": "CBS022007DVD",
                        "year": "2007",
                        "variant": "DVD",
                        "normalized_title": "recovered game",
                        "representative_title": "Recovered Game",
                        "source_kinds": "disc-metadata-value",
                        "confidence": "high",
                    }
                ],
            )
            write_csv(retry_dir / "master_games.csv", MASTER_GAME_FIELDS, [])
            write_csv(retry_dir / "unresolved_issues.csv", UNRESOLVED_FIELDS, [])

            with self.assertRaises(SystemExit):
                run_merge(
                    type(
                        "Args",
                        (),
                        {
                            "base_dir": str(base_dir),
                            "retry_dir": str(retry_dir),
                            "base_published_unresolved": str(published_dir / "final_unresolved_issues.csv"),
                            "output_dir": str(root / "results" / "out"),
                            "comparison_report": None,
                        },
                    )()
                )

    def test_retry_archive_outside_published_unresolved_queue_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_dir, published_dir = self._write_base_snapshot(root)
            retry_dir = root / "results" / "vps-linux-retry-20260325"
            write_csv(
                retry_dir / "issue_titles.csv",
                ISSUE_TITLE_FIELDS,
                [
                    {
                        "archive_item": "cbs-2000-09",
                        "archive_name": "2008/CBS082008DVD.7z",
                        "issue_code": "CBS082008DVD",
                        "year": "2008",
                        "variant": "DVD",
                        "normalized_title": "unexpected retry",
                        "representative_title": "Unexpected Retry",
                        "source_kinds": "disc-metadata-value",
                        "confidence": "high",
                        "content_kind": "unknown",
                    }
                ],
            )
            write_csv(retry_dir / "master_games.csv", MASTER_GAME_FIELDS, [])
            write_csv(retry_dir / "unresolved_issues.csv", UNRESOLVED_FIELDS, [])

            with self.assertRaises(SystemExit):
                run_merge(
                    type(
                        "Args",
                        (),
                        {
                            "base_dir": str(base_dir),
                            "retry_dir": str(retry_dir),
                            "base_published_unresolved": str(published_dir / "final_unresolved_issues.csv"),
                            "output_dir": str(root / "results" / "out"),
                            "comparison_report": None,
                        },
                    )()
                )

    def test_rebuilt_master_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_dir, published_dir = self._write_base_snapshot(root)
            retry_dir = root / "results" / "vps-linux-retry-20260325"
            retry_issue_rows = [
                {
                    "archive_item": "cbs-2000-09",
                    "archive_name": "2007/CBS022007DVD.7z",
                    "issue_code": "CBS022007DVD",
                    "year": "2007",
                    "variant": "DVD",
                    "normalized_title": "recovered game",
                    "representative_title": "Recovered Game",
                    "source_kinds": "disc-metadata-value",
                    "confidence": "high",
                    "content_kind": "unknown",
                },
                {
                    "archive_item": "cbs-2000-09",
                    "archive_name": "2007/CBS022007DVD.7z",
                    "issue_code": "CBS022007DVD",
                    "year": "2007",
                    "variant": "DVD",
                    "normalized_title": "bonus stable",
                    "representative_title": "Bonus Stable",
                    "source_kinds": "disc-metadata-value",
                    "confidence": "medium",
                    "content_kind": "unknown",
                },
            ]
            write_csv(retry_dir / "issue_titles.csv", ISSUE_TITLE_FIELDS, retry_issue_rows)
            write_csv(retry_dir / "master_games.csv", MASTER_GAME_FIELDS, [])
            write_csv(retry_dir / "unresolved_issues.csv", UNRESOLVED_FIELDS, [])

            first_output = root / "results" / "merged-a"
            second_output = root / "results" / "merged-b"
            args_template = {
                "base_dir": str(base_dir),
                "retry_dir": str(retry_dir),
                "base_published_unresolved": str(published_dir / "final_unresolved_issues.csv"),
                "comparison_report": None,
            }

            run_merge(type("Args", (), {**args_template, "output_dir": str(first_output)})())
            run_merge(type("Args", (), {**args_template, "output_dir": str(second_output)})())

            self.assertEqual(
                (first_output / "master_games.csv").read_text(encoding="utf-8"),
                (second_output / "master_games.csv").read_text(encoding="utf-8"),
            )
