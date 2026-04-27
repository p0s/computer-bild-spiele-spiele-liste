from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.release_audit import build_paths, classify_sample, parse_args, readme_snapshot_counts, run_audit


REPO_ROOT = Path(__file__).resolve().parent.parent


class ReleaseAuditCliTests(unittest.TestCase):
    def test_readme_snapshot_counts_accepts_current_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text(
                "- publishable master rows: `1711`\n"
                "- publishable issue/title rows: `2183`\n"
                "- unresolved issues: `0`\n",
                encoding="utf-8",
            )

            self.assertEqual(
                readme_snapshot_counts(root),
                {"master_titles": 1711, "issue_rows": 2183, "unresolved": 0},
            )

    def test_classify_sample_keeps_known_knights_title(self) -> None:
        self.assertEqual(classify_sample("Knights of Honor"), ("keep", "known valid game title"))

    def test_build_paths_respects_explicit_arguments(self) -> None:
        args = parse_args(
            [
                "--raw-dir",
                "/tmp/raw",
                "--published-dir",
                "/tmp/published",
                "--enriched-dir",
                "/tmp/enriched",
                "--report-path",
                "/tmp/report.md",
                "--sample-path",
                "/tmp/sample.csv",
            ]
        )
        paths = build_paths(args, root=REPO_ROOT)
        self.assertEqual(paths.raw_dir, Path("/tmp/raw").resolve())
        self.assertEqual(paths.published_dir, Path("/tmp/published").resolve())
        self.assertEqual(paths.enriched_dir, Path("/tmp/enriched").resolve())
        self.assertEqual(paths.report_path, Path("/tmp/report.md").resolve())
        self.assertEqual(paths.sample_path, Path("/tmp/sample.csv").resolve())

    def test_run_audit_accepts_absolute_snapshot_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_dir = root / "raw"
            published_dir = root / "published"
            enriched_dir = root / "enriched"
            raw_dir.mkdir()
            published_dir.mkdir()
            enriched_dir.mkdir()

            for name in ["issue_titles.csv", "master_games.csv", "unresolved_issues.csv"]:
                shutil.copy2(REPO_ROOT / "results" / "vps-linux-full-rerun-20260325" / name, raw_dir / name)
            for name in [
                "publishable_master_games.csv",
                "publishable_issue_titles.csv",
                "excluded_non_game_titles.csv",
                "final_unresolved_issues.csv",
                "README.md",
                "audit_summary.md",
                "unresolved_summary.md",
            ]:
                shutil.copy2(REPO_ROOT / "results" / "published-20260326" / name, published_dir / name)
            for name in [
                "README.md",
                "ambiguous_matches.csv",
                "enriched_issue_titles.csv",
                "enriched_master_games.csv",
                "enrichment_audit.md",
                "match_demotions.csv",
                "source_attribution.csv",
                "title_aliases.csv",
                "unmatched_titles.csv",
            ]:
                shutil.copy2(REPO_ROOT / "results" / "enriched-20260326" / name, enriched_dir / name)

            report_path = root / "audit.md"
            sample_path = root / "sample.csv"
            args = parse_args(
                [
                    "--raw-dir",
                    str(raw_dir),
                    "--published-dir",
                    str(published_dir),
                    "--enriched-dir",
                    str(enriched_dir),
                    "--report-path",
                    str(report_path),
                    "--sample-path",
                    str(sample_path),
                    "--skip-git-fetch",
                ]
            )

            rc = run_audit(args, root=REPO_ROOT)

            self.assertEqual(rc, 0)
            self.assertTrue(report_path.exists())
            self.assertTrue(sample_path.exists())
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn(f"Published dir: `{published_dir.resolve()}`", report_text)
