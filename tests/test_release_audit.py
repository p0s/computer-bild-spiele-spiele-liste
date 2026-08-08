from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.release_audit import (
    build_paths,
    classify_sample,
    compare_output_files,
    enrichment_quality,
    parse_args,
    readme_snapshot_counts,
    run_audit,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class ReleaseAuditCliTests(unittest.TestCase):
    def test_readme_snapshot_counts_accepts_current_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text(
                "- publishable master rows: `1711`\n- publishable issue/title rows: `2183`\n- unresolved issues: `0`\n",
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

            for name in ["issue_titles.csv", "master_games.csv", "unresolved_issues.csv", "source_archives.csv"]:
                shutil.copy2(REPO_ROOT / "results" / "raw-candidates-20260325" / name, raw_dir / name)
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "prepare_publishable_results.py"),
                    "--input-dir",
                    str(raw_dir),
                    "--output-dir",
                    str(published_dir),
                    "--baseline-enriched-master",
                    str(REPO_ROOT / "results" / "enriched-20260325" / "enriched_master_games.csv"),
                ],
                cwd=REPO_ROOT,
                check=True,
            )
            for name in [
                "README.md",
                "ambiguous_matches.csv",
                "enriched_issue_titles.csv",
                "enriched_master_games.csv",
                "enrichment_audit.md",
                "match_demotions.csv",
                "pending_lookups.csv",
                "source_attribution.csv",
                "title_aliases.csv",
                "unmatched_titles.csv",
            ]:
                shutil.copy2(REPO_ROOT / "results" / "enriched-20260808" / name, enriched_dir / name)

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

            self.assertTrue(report_path.exists())
            self.assertTrue(sample_path.exists())
            report_text = report_path.read_text(encoding="utf-8")
            expected_rc = 1 if "Verdict: **not ready**" in report_text else 0
            self.assertEqual(rc, expected_rc)
            self.assertIn(f"Published dir: `{published_dir.resolve()}`", report_text)

    def test_compare_output_files_detects_canonical_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "generated"
            canonical = root / "canonical"
            generated.mkdir()
            canonical.mkdir()
            (generated / "example.csv").write_text("value\n1\n", encoding="utf-8")
            (canonical / "example.csv").write_text("value\n2\n", encoding="utf-8")

            self.assertEqual(
                compare_output_files(generated, canonical, ("example.csv",)),
                {"example.csv": "mismatch"},
            )

    def test_enrichment_quality_rejects_unreviewable_and_shared_entities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            enriched = Path(temp_dir)
            (enriched / "enriched_master_games.csv").write_text(
                "game_id,match_status,wikidata_id\na,ambiguous,Q1\nb,matched,Q1\nc,unmatched,\nd,pending,\n",
                encoding="utf-8",
            )
            (enriched / "ambiguous_matches.csv").write_text(
                "game_id,candidate_1_title,candidate_1_url\na,,\n",
                encoding="utf-8",
            )
            (enriched / "unmatched_titles.csv").write_text(
                "game_id,failure_reason\nc,reference_lookup_failed\n",
                encoding="utf-8",
            )
            (enriched / "pending_lookups.csv").write_text("game_id\nd\n", encoding="utf-8")

            problems, counts = enrichment_quality(enriched)

            self.assertEqual(counts, {"matched": 1, "ambiguous": 1, "unmatched": 1, "pending": 1})
            self.assertTrue(any("Wikidata IDs" in problem for problem in problems))
            self.assertTrue(any("candidate evidence" in problem for problem in problems))
            self.assertTrue(any("operational lookup failures" in problem for problem in problems))
