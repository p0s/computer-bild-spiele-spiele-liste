from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.enrich_reference_links import (
    build_search_variants,
    connect_cache,
    fetch_json_cached,
    pick_wikimedia_link,
    resolve_title_reference,
)


class VariantTests(unittest.TestCase):
    def test_build_search_variants_strips_version_suffix(self) -> None:
        variants = build_search_variants("Arena Wars v 1 1")
        self.assertIn("Arena Wars", variants)
        self.assertEqual(variants[0], "Arena Wars v 1 1")


class WikimediaSelectionTests(unittest.TestCase):
    def test_pick_wikimedia_link_prefers_english_then_german(self) -> None:
        entity = {
            "id": "Q1",
            "sitelinks": {
                "dewiki": {"title": "Mystery Island"},
                "enwiki": {"title": "Mystery Island"},
            },
        }
        url, source, lang, title = pick_wikimedia_link(entity)
        self.assertEqual(source, "wikipedia-en")
        self.assertEqual(lang, "en")
        self.assertIn("/Mystery_Island", url)
        self.assertEqual(title, "Mystery Island")

    def test_pick_wikimedia_link_falls_back_to_wikidata(self) -> None:
        entity = {"id": "Q42", "sitelinks": {}}
        url, source, lang, title = pick_wikimedia_link(entity)
        self.assertEqual(source, "wikidata")
        self.assertEqual(lang, "")
        self.assertEqual(title, "Q42")
        self.assertTrue(url.endswith("/Q42"))


class CacheTests(unittest.TestCase):
    def test_fetch_json_cached_reuses_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_cache(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch(
                    "scripts.enrich_reference_links.http_get_json",
                    return_value={"ok": True},
                ) as get_json:
                    first = fetch_json_cached(conn, "k1", "https://example.invalid/1")
                    second = fetch_json_cached(conn, "k1", "https://example.invalid/1")
                self.assertEqual(first, {"ok": True})
                self.assertEqual(second, {"ok": True})
                self.assertEqual(get_json.call_count, 1)
            finally:
                conn.close()


class ResolutionTests(unittest.TestCase):
    def test_resolve_title_reference_exact_english_hit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_cache(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch(
                    "scripts.enrich_reference_links.wikidata_search",
                    return_value=[{"id": "Q1"}],
                ), mock.patch(
                    "scripts.enrich_reference_links.wikidata_entities",
                    return_value={
                        "Q1": {
                            "id": "Q1",
                            "labels": {"en": {"value": "Mystery Island"}},
                            "aliases": {"en": [{"value": "Mystery Island"}]},
                            "sitelinks": {"enwiki": {"title": "Mystery Island"}},
                        }
                    },
                ), mock.patch(
                    "scripts.enrich_reference_links.wikipedia_search",
                    return_value=[],
                ):
                    result = resolve_title_reference(conn, "mystery island", "Mystery Island")
                self.assertEqual(result.reference_status, "matched")
                self.assertEqual(result.reference_source, "wikipedia-en")
                self.assertEqual(result.reference_title, "Mystery Island")
            finally:
                conn.close()

    def test_resolve_title_reference_uses_german_when_no_english(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_cache(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch(
                    "scripts.enrich_reference_links.wikidata_search",
                    return_value=[{"id": "Q2"}],
                ), mock.patch(
                    "scripts.enrich_reference_links.wikidata_entities",
                    return_value={
                        "Q2": {
                            "id": "Q2",
                            "labels": {"de": {"value": "Die Siedler"}},
                            "aliases": {"de": [{"value": "Die Siedler"}]},
                            "sitelinks": {"dewiki": {"title": "Die Siedler"}},
                        }
                    },
                ), mock.patch(
                    "scripts.enrich_reference_links.wikipedia_search",
                    return_value=[],
                ):
                    result = resolve_title_reference(conn, "die siedler", "Die Siedler")
                self.assertEqual(result.reference_status, "matched")
                self.assertEqual(result.reference_source, "wikipedia-de")
                self.assertEqual(result.reference_lang, "de")
            finally:
                conn.close()

    def test_resolve_title_reference_wikidata_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_cache(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch(
                    "scripts.enrich_reference_links.wikidata_search",
                    return_value=[{"id": "Q3"}],
                ), mock.patch(
                    "scripts.enrich_reference_links.wikidata_entities",
                    return_value={
                        "Q3": {
                            "id": "Q3",
                            "labels": {"en": {"value": "Absolute Blue"}},
                            "aliases": {"en": [{"value": "Absolute Blue"}]},
                            "sitelinks": {},
                        }
                    },
                ), mock.patch(
                    "scripts.enrich_reference_links.wikipedia_search",
                    return_value=[],
                ):
                    result = resolve_title_reference(conn, "absolute blue", "Absolute Blue")
                self.assertEqual(result.reference_status, "matched")
                self.assertEqual(result.reference_source, "wikidata")
            finally:
                conn.close()

    def test_resolve_title_reference_marks_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_cache(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch(
                    "scripts.enrich_reference_links.wikidata_search",
                    return_value=[{"id": "Q4"}, {"id": "Q5"}],
                ), mock.patch(
                    "scripts.enrich_reference_links.wikidata_entities",
                    return_value={
                        "Q4": {
                            "id": "Q4",
                            "labels": {"en": {"value": "4 Story"}},
                            "aliases": {"en": [{"value": "Four Story"}]},
                            "sitelinks": {"enwiki": {"title": "4Story"}},
                        },
                        "Q5": {
                            "id": "Q5",
                            "labels": {"en": {"value": "Story 4"}},
                            "aliases": {"en": [{"value": "4 Story"}]},
                            "sitelinks": {"enwiki": {"title": "Story_4"}},
                        },
                    },
                ), mock.patch(
                    "scripts.enrich_reference_links.wikipedia_search",
                    return_value=[],
                ):
                    result = resolve_title_reference(conn, "4 story", "4 Story")
                self.assertEqual(result.reference_status, "ambiguous")
                self.assertEqual(result.reference_url, "")
            finally:
                conn.close()

    def test_resolve_title_reference_prefers_video_game_description(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_cache(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch(
                    "scripts.enrich_reference_links.wikidata_search",
                    return_value=[
                        {"id": "Q10", "description": "2008 video game"},
                        {"id": "Q11", "description": "2008 film"},
                    ],
                ), mock.patch(
                    "scripts.enrich_reference_links.wikidata_entities",
                    return_value={
                        "Q10": {
                            "id": "Q10",
                            "labels": {"en": {"value": "007: Quantum of Solace"}},
                            "aliases": {"en": [{"value": "007 Ein Quantum Trost"}]},
                            "sitelinks": {"enwiki": {"title": "007: Quantum of Solace (video game)"}},
                        },
                        "Q11": {
                            "id": "Q11",
                            "labels": {"en": {"value": "Quantum of Solace"}},
                            "aliases": {"en": [{"value": "007 Ein Quantum Trost"}]},
                            "sitelinks": {"enwiki": {"title": "Quantum of Solace"}},
                        },
                    },
                ), mock.patch(
                    "scripts.enrich_reference_links.wikipedia_search",
                    return_value=[],
                ):
                    result = resolve_title_reference(conn, "007 ein quantum trost", "007 Ein Quantum Trost")
                self.assertEqual(result.reference_status, "matched")
                self.assertEqual(result.reference_source, "wikipedia-en")
                self.assertIn("video_game", result.reference_url)
            finally:
                conn.close()
