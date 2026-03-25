from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.build_enriched_release import run_build
from scripts.enrich_reference_links import Resolution


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "enrichment"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class BuildEnrichedReleaseTests(unittest.TestCase):
    def _args(self, root: Path, **overrides: object) -> SimpleNamespace:
        values = {
            "input_master": str(FIXTURE_DIR / "publishable_master_games.csv"),
            "input_issues": str(FIXTURE_DIR / "publishable_issue_titles.csv"),
            "output_dir": str(root / "results" / "enriched-20260324"),
            "cache_db": str(root / "results" / "enrichment.sqlite"),
            "resume": False,
            "refresh_cache": False,
            "limit": None,
            "only_unmatched": False,
            "only_ambiguous": False,
            "manual_alias_overrides": str(root / "data" / "manual_alias_overrides.csv"),
            "manual_entity_overrides": str(root / "data" / "manual_entity_overrides.csv"),
            "manual_url_overrides": str(root / "data" / "manual_url_overrides.csv"),
            "manual_rejections": str(root / "data" / "manual_rejections.csv"),
            "review_csv": str(root / "results" / "reference_review.csv"),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _write_override_files(self, root: Path) -> None:
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "manual_alias_overrides.csv").write_text(
            "normalized_title,canonical_slug,canonical_title,reason\n"
            "18 wheelsof steel haulin,18-wheels-of-steel-haulin,18 Wheels of Steel Haulin,spacing variant\n",
            encoding="utf-8",
        )
        (data_dir / "manual_entity_overrides.csv").write_text(
            "normalized_title,wikidata_id,wikipedia_url,canonical_title,entity_type,reason\n",
            encoding="utf-8",
        )
        (data_dir / "manual_url_overrides.csv").write_text(
            "canonical_slug,wikipedia_url,wikidata_id,source_url,reason\n",
            encoding="utf-8",
        )
        (data_dir / "manual_rejections.csv").write_text(
            "normalized_title,rejected_candidate,source,reason\n",
            encoding="utf-8",
        )

    def test_builds_enriched_outputs_and_propagates_master_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_override_files(root)

            def fake_resolution(_conn, normalized_title: str, representative_title: str) -> Resolution:
                if normalized_title in {"18 wheels of steel haulin", "18 wheelsof steel haulin"}:
                    return Resolution(
                        normalized_title=normalized_title,
                        representative_title=representative_title,
                        canonical_title="18 Wheels of Steel Haulin",
                        canonical_slug="18-wheels-of-steel-haulin",
                        reference_url="https://en.wikipedia.org/wiki/18_Wheels_of_Steel:_Haulin%27",
                        reference_source="wikipedia-en",
                        reference_lang="en",
                        reference_title="18 Wheels of Steel: Haulin'",
                        reference_confidence="high",
                        reference_status="matched",
                        match_method="wikimedia-search",
                        match_source="wikipedia-en",
                        match_source_url="https://en.wikipedia.org/wiki/18_Wheels_of_Steel:_Haulin%27",
                        wikidata_id="Q1",
                        wikidata_url="https://www.wikidata.org/wiki/Q1",
                        match_fetched_at="2026-03-24T00:00:00+00:00",
                        failure_reason="",
                        top_candidates=tuple(),
                    )
                if normalized_title == "arena wars":
                    return Resolution(
                        normalized_title=normalized_title,
                        representative_title=representative_title,
                        canonical_title="Arena Wars",
                        canonical_slug="arena-wars",
                        reference_url="https://en.wikipedia.org/wiki/Arena_Wars",
                        reference_source="wikipedia-en",
                        reference_lang="en",
                        reference_title="Arena Wars",
                        reference_confidence="high",
                        reference_status="matched",
                        match_method="wikimedia-search",
                        match_source="wikipedia-en",
                        match_source_url="https://en.wikipedia.org/wiki/Arena_Wars",
                        wikidata_id="Q2",
                        wikidata_url="https://www.wikidata.org/wiki/Q2",
                        match_fetched_at="2026-03-24T00:00:00+00:00",
                        failure_reason="",
                        top_candidates=tuple(),
                    )
                if normalized_title == "arena wars v 1 1":
                    return Resolution(
                        normalized_title=normalized_title,
                        representative_title=representative_title,
                        canonical_title="",
                        canonical_slug="",
                        reference_url="",
                        reference_source="",
                        reference_lang="",
                        reference_title="",
                        reference_confidence="",
                        reference_status="ambiguous",
                        match_method="wikimedia-search",
                        match_source="",
                        match_source_url="",
                        wikidata_id="",
                        wikidata_url="",
                        match_fetched_at="2026-03-24T00:00:00+00:00",
                        failure_reason="multiple plausible entities",
                        top_candidates=tuple(),
                    )
                return Resolution(
                    normalized_title=normalized_title,
                    representative_title=representative_title,
                    canonical_title="",
                    canonical_slug="",
                    reference_url="",
                    reference_source="",
                    reference_lang="",
                    reference_title="",
                    reference_confidence="",
                    reference_status="unmatched",
                    match_method="wikimedia-search",
                    match_source="",
                    match_source_url="",
                    wikidata_id="",
                    wikidata_url="",
                    match_fetched_at="2026-03-24T00:00:00+00:00",
                    failure_reason="no confident match",
                    top_candidates=tuple(),
                )

            def fake_entity(_conn, qid: str) -> dict[str, object]:
                entities = {
                    "Q1": {
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q7889"}}}}],
                            "P136": [{"mainsnak": {"datavalue": {"value": {"id": "Q860750"}}}}],
                            "P577": [{"mainsnak": {"datavalue": {"value": {"time": "+2006-01-01T00:00:00Z"}}}}],
                        }
                    },
                    "Q2": {
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q7889"}}}}],
                            "P136": [{"mainsnak": {"datavalue": {"value": {"id": "Q27670585"}}}}],
                            "P577": [{"mainsnak": {"datavalue": {"value": {"time": "+2004-01-01T00:00:00Z"}}}}],
                        }
                    },
                }
                return entities[qid]

            def fake_labels(_conn, ids):
                mapping = {
                    "Q7889": "video game",
                    "Q860750": "racing",
                    "Q27670585": "real-time strategy",
                }
                return {entity_id: mapping[entity_id] for entity_id in ids if entity_id in mapping}

            with mock.patch("scripts.build_enriched_release.resolve_title_reference", side_effect=fake_resolution), mock.patch(
                "scripts.build_enriched_release.fetch_entity_with_claims",
                side_effect=fake_entity,
            ), mock.patch(
                "scripts.build_enriched_release.fetch_labels",
                side_effect=fake_labels,
            ), mock.patch(
                "scripts.build_enriched_release.fetch_mobygames_metadata",
                return_value={
                    "genres": "",
                    "categories": "",
                    "themes": "",
                    "rating_value": "",
                    "rating_scale": "",
                    "rating_count": "",
                    "rating_source": "",
                    "rating_url": "",
                    "rating_fetched_at": "",
                    "rating_confidence": "",
                    "notes": "",
                },
            ):
                run_build(self._args(root))

            out_dir = root / "results" / "enriched-20260324"
            master_rows = read_csv(out_dir / "enriched_master_games.csv")
            issue_rows = read_csv(out_dir / "enriched_issue_titles.csv")
            alias_rows = read_csv(out_dir / "title_aliases.csv")
            ambiguous_rows = read_csv(out_dir / "ambiguous_matches.csv")
            unmatched_rows = read_csv(out_dir / "unmatched_titles.csv")

            self.assertIn("canonical_slug", master_rows[0])
            self.assertIn("wikipedia_url", master_rows[0])
            self.assertIn("rating_source", master_rows[0])
            haulin = next(row for row in master_rows if row["normalized_title"] == "18 wheels of steel haulin")
            self.assertEqual(haulin["canonical_slug"], "18-wheels-of-steel-haulin")
            self.assertEqual(haulin["entity_type"], "game")
            self.assertEqual(haulin["categories"], "racing")
            self.assertEqual(haulin["release_year"], "2006")

            variant_issue = next(row for row in issue_rows if row["normalized_title"] == "18 wheelsof steel haulin")
            self.assertEqual(variant_issue["canonical_slug"], "18-wheels-of-steel-haulin")
            self.assertEqual(variant_issue["match_status"], "matched")

            alias_variant = next(row for row in alias_rows if row["normalized_title"] == "18 wheelsof steel haulin")
            self.assertEqual(alias_variant["override_applied"], "true")

            self.assertEqual(len(ambiguous_rows), 1)
            self.assertEqual(ambiguous_rows[0]["normalized_title"], "arena wars v 1 1")
            self.assertEqual(len(unmatched_rows), 2)
            self.assertEqual(
                {row["normalized_title"] for row in unmatched_rows},
                {"hell copter", "4 story"},
            )

    def test_repeat_run_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_override_files(root)

            def fake_resolution(_conn, normalized_title: str, representative_title: str) -> Resolution:
                return Resolution(
                    normalized_title=normalized_title,
                    representative_title=representative_title,
                    canonical_title=representative_title if normalized_title != "4 story" else "",
                    canonical_slug=representative_title.lower().replace(" ", "-") if normalized_title != "4 story" else "",
                    reference_url="https://example.invalid/" + normalized_title.replace(" ", "-") if normalized_title != "4 story" else "",
                    reference_source="wikidata" if normalized_title != "4 story" else "",
                    reference_lang="" if normalized_title != "4 story" else "",
                    reference_title=representative_title if normalized_title != "4 story" else "",
                    reference_confidence="high" if normalized_title != "4 story" else "",
                    reference_status="matched" if normalized_title != "4 story" else "ambiguous",
                    match_method="wikimedia-search",
                    match_source="wikidata" if normalized_title != "4 story" else "",
                    match_source_url="https://example.invalid/" + normalized_title.replace(" ", "-") if normalized_title != "4 story" else "",
                    wikidata_id="QX" if normalized_title != "4 story" else "",
                    wikidata_url="https://www.wikidata.org/wiki/QX" if normalized_title != "4 story" else "",
                    match_fetched_at="2026-03-24T00:00:00+00:00",
                    failure_reason="" if normalized_title != "4 story" else "ambiguous",
                    top_candidates=tuple(),
                )

            with mock.patch("scripts.build_enriched_release.resolve_title_reference", side_effect=fake_resolution), mock.patch(
                "scripts.build_enriched_release.fetch_entity_with_claims",
                return_value={"claims": {}},
            ), mock.patch(
                "scripts.build_enriched_release.fetch_labels",
                return_value={},
            ), mock.patch(
                "scripts.build_enriched_release.fetch_mobygames_metadata",
                return_value={
                    "genres": "",
                    "categories": "",
                    "themes": "",
                    "rating_value": "",
                    "rating_scale": "",
                    "rating_count": "",
                    "rating_source": "",
                    "rating_url": "",
                    "rating_fetched_at": "",
                    "rating_confidence": "",
                    "notes": "",
                },
            ):
                run_build(self._args(root))
                first = (root / "results" / "enriched-20260324" / "enriched_master_games.csv").read_text(encoding="utf-8")
                run_build(self._args(root))
                second = (root / "results" / "enriched-20260324" / "enriched_master_games.csv").read_text(encoding="utf-8")
            self.assertEqual(first, second)
