from __future__ import annotations

import shutil
import tempfile
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.index_cbs_exes import (
    ArchiveRecord,
    AttachedImage,
    CommandError,
    StrategyRunResult,
    build_benchmark_rows,
    connect_database,
    convert_cue_to_iso,
    download_record_archive,
    ensure_required_tools,
    export_csvs,
    fetch_cached_text,
    find_mount_candidates,
    insert_title_row,
    iter_executable_paths,
    normalize_title,
    parse_archive_name,
    parse_archiveorg_metadata_payload,
    parse_vollversion_issue_html,
    parse_text_candidates,
    process_downloaded_archive,
    process_title_issue,
    run_archive_metadata_strategy,
    run_vollversion_strategy,
    title_candidates_from_exe_path,
    title_candidates_from_metadata_file,
)
from scripts.prepare_publishable_results import publishable_issue_rows, repair_issue_row


def candidate(source_kind: str, source_path: str, title: str, normalized: str, confidence: str = "high") -> tuple:
    from scripts.index_cbs_exes import TitleCandidate

    return TitleCandidate(
        source_kind=source_kind,
        source_path=source_path,
        candidate_title=title,
        normalized_title=normalized,
        confidence=confidence,
    )


class ParseArchiveNameTests(unittest.TestCase):
    def test_parse_old_cd_issue(self) -> None:
        self.assertEqual(parse_archive_name("2000/CBS092000.7z"), (2000, "CBS092000", "CD"))

    def test_parse_old_dvd_gold_issue(self) -> None:
        self.assertEqual(
            parse_archive_name("2010/CBS062010DVDGold.7z"),
            (2010, "CBS062010DVDGold", "DVDGold"),
        )

    def test_parse_new_standard_issue(self) -> None:
        self.assertEqual(parse_archive_name("2011/CBS0111.7z"), (2011, "CBS0111", "Standard"))

    def test_parse_new_gold_issue(self) -> None:
        self.assertEqual(parse_archive_name("2011/CBS0111Gold.7z"), (2011, "CBS0111Gold", "Gold"))

    def test_parse_new_platin_issue(self) -> None:
        self.assertEqual(parse_archive_name("2017/CBS0917Platin.7z"), (2017, "CBS0917Platin", "Platin"))


class TitleParsingTests(unittest.TestCase):
    def test_extracts_titles_from_vollversion_issue_page(self) -> None:
        html = """
        <html><head><title>Computer Bild Spiele 04/2000 | Die beste Software auf vollversion.de</title></head>
        <body>
        <p class="mb5 cg">Enthaltene Vollversionen:</p>
        <table class="list wp100 mb20">
          <tr><th>Programm</th></tr>
          <tr><td><a href="/programm/mystery-island.html">Mystery Island </a></td></tr>
          <tr><td><a href="/programm/anno-1602.html">Anno 1602</a></td></tr>
        </table>
        </body></html>
        """
        candidates, structured = parse_vollversion_issue_html(
            html,
            source_path="https://www.vollversion.de/ausgabe/computer-bild-spiele-04-2000.html",
        )
        normalized = {candidate.normalized_title for candidate in candidates}
        self.assertEqual(structured, True)
        self.assertIn("mystery island", normalized)
        self.assertIn("anno1602", normalized)

    def test_extracts_subject_titles(self) -> None:
        candidates, structured = parse_archiveorg_metadata_payload(
            "issue-item",
            {
                "metadata": {
                    "subject": ["Anno 1602", "Computer Bild Spiele", "Prince of Persia 3D"],
                }
            },
        )
        normalized = {candidate.normalized_title for candidate in candidates}
        self.assertEqual(structured, True)
        self.assertIn("anno1602", normalized)
        self.assertIn("prince of persia 3d", normalized)
        self.assertNotIn("computer bild spiele", normalized)

    def test_extracts_description_bullet_titles(self) -> None:
        candidates, structured = parse_archiveorg_metadata_payload(
            "issue-item",
            {
                "metadata": {
                    "description": (
                        "Vollversion:\n"
                        "- Anno 1602\n"
                        "Demos:\n"
                        "- Prince of Persia 3D\n"
                        "- RollerCoaster Tycoon"
                    )
                }
            },
        )
        normalized = {candidate.normalized_title for candidate in candidates}
        self.assertEqual(structured, True)
        self.assertEqual(
            normalized,
            {"anno1602", "prince of persia 3d", "roller coaster tycoon"},
        )

    def test_extracts_titles_from_ocr_text(self) -> None:
        candidates, structured = parse_text_candidates(
            "CD-Inhalt\nVollversion:\n* Anno 1602\nDemos:\n* Prince of Persia 3D\n",
            source_kind="archiveorg-ocr",
            source_path="ocr.txt",
            confidence="high",
        )
        normalized = {candidate.normalized_title for candidate in candidates}
        self.assertEqual(structured, True)
        self.assertEqual(normalized, {"anno1602", "prince of persia 3d"})

    def test_filters_generic_metadata_terms(self) -> None:
        self.assertIsNone(normalize_title("setup"))
        candidates, _ = parse_text_candidates(
            "Computer Bild Spiele\nGold\nCD-Inhalt",
            source_kind="archiveorg-title",
            source_path="title",
            confidence="low",
        )
        self.assertEqual(candidates, [])


class ToolAndCacheTests(unittest.TestCase):
    def test_strategy_aware_tool_requirements(self) -> None:
        def fake_which(tool: str) -> str | None:
            return "/usr/bin/curl" if tool == "curl" else None

        with mock.patch("scripts.index_cbs_exes.shutil.which", side_effect=fake_which):
            ensure_required_tools(mode="titles", title_strategy="external-only")
            with self.assertRaises(SystemExit):
                ensure_required_tools(mode="exes", title_strategy="auto")

    def test_fetch_cached_text_uses_persistent_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_database(Path(temp_dir) / "cache.sqlite")
            try:
                with mock.patch("scripts.index_cbs_exes.http_get_text", return_value="payload") as get_text:
                    first = fetch_cached_text(
                        conn,
                        cache_kind="search",
                        cache_key="search:key",
                        url="https://example.invalid/search",
                    )
                    second = fetch_cached_text(
                        conn,
                        cache_kind="search",
                        cache_key="search:key",
                        url="https://example.invalid/search",
                    )
                self.assertEqual(first, "payload")
                self.assertEqual(second, "payload")
                self.assertEqual(get_text.call_count, 1)
            finally:
                conn.close()

    def test_strategy_cache_reuses_archive_metadata_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_database(Path(temp_dir) / "cache.sqlite")
            record = ArchiveRecord(
                archive_item="cbs-2000-09",
                archive_name="2000/CBS092000.7z",
                archive_url="https://example.invalid/CBS092000.7z",
                size_bytes=1,
                year=2000,
                issue_code="CBS092000",
                variant="CD",
            )
            try:
                with mock.patch(
                    "scripts.index_cbs_exes.archiveorg_search_candidates",
                    return_value=[{"identifier": "issue-item"}],
                ) as search_candidates, mock.patch(
                    "scripts.index_cbs_exes.archiveorg_metadata_json",
                    return_value={"metadata": {"subject": ["Anno 1602"]}},
                ) as metadata_json:
                    first = run_archive_metadata_strategy(conn, record, issue_search_limit=5)
                    second = run_archive_metadata_strategy(conn, record, issue_search_limit=5)
                self.assertEqual({candidate.normalized_title for candidate in first.candidates}, {"anno1602"})
                self.assertEqual({candidate.normalized_title for candidate in second.candidates}, {"anno1602"})
                self.assertEqual(search_candidates.call_count, 1)
                self.assertEqual(metadata_json.call_count, 1)
            finally:
                conn.close()

    def test_strategy_cache_reuses_vollversion_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = connect_database(Path(temp_dir) / "cache.sqlite")
            record = ArchiveRecord(
                archive_item="cbs-2000-09",
                archive_name="2000/CBS042000.7z",
                archive_url="https://example.invalid/CBS042000.7z",
                size_bytes=1,
                year=2000,
                issue_code="CBS042000",
                variant="CD",
            )
            html = """
            <p>Enthaltene Vollversionen:</p>
            <table><tr><td><a href="/programm/mystery-island.html">Mystery Island</a></td></tr></table>
            """
            try:
                with mock.patch("scripts.index_cbs_exes.fetch_cached_text", return_value=html) as fetch_text:
                    first = run_vollversion_strategy(conn, record)
                    second = run_vollversion_strategy(conn, record)
                self.assertEqual({candidate.normalized_title for candidate in first.candidates}, {"mystery island"})
                self.assertEqual({candidate.normalized_title for candidate in second.candidates}, {"mystery island"})
                self.assertEqual(fetch_text.call_count, 1)
            finally:
                conn.close()


class PublishableRepairTests(unittest.TestCase):
    def test_repairs_baldurs_gate_mojibake(self) -> None:
        row = {
            "archive_item": "cbs-2000-09",
            "archive_name": "2008/CBS122008DVDGold.7z",
            "issue_code": "CBS122008DVDGold",
            "year": "2008",
            "variant": "DVDGold",
            "normalized_title": "baldur s gate compilation",
            "representative_title": "Baldur�s Gate � Compilation",
            "source_kinds": "disc-metadata-value",
            "confidence": "high",
            "content_kind": "unknown",
        }
        repaired = repair_issue_row(row)
        self.assertEqual(repaired["representative_title"], "Baldur's Gate - Compilation")
        self.assertEqual(repaired["normalized_title"], "baldur s gate compilation")

    def test_repairs_umlaut_mojibake(self) -> None:
        row = {
            "archive_item": "cbs-2000-09",
            "archive_name": "2005/CBS022005DVD.7z",
            "issue_code": "CBS022005DVD",
            "year": "2005",
            "variant": "DVD",
            "normalized_title": "r ckkehr zur insel",
            "representative_title": "R�ckkehr zur Insel",
            "source_kinds": "disc-metadata-value",
            "confidence": "high",
            "content_kind": "unknown",
        }
        repaired = repair_issue_row(row)
        self.assertEqual(repaired["representative_title"], "Rückkehr zur Insel")
        self.assertEqual(repaired["normalized_title"], "r ckkehr zur insel")

    def test_strips_trailing_version_metadata_from_title(self) -> None:
        row = {
            "archive_item": "cbs-2000-09",
            "archive_name": "2008/CBS032008DVD.7z",
            "issue_code": "CBS032008DVD",
            "year": "2008",
            "variant": "DVD",
            "normalized_title": "codename panzers phase 2 v 1",
            "representative_title": "Codename Panzers Phase 2 v 1",
            "source_kinds": "disc-metadata-value",
            "confidence": "high",
            "content_kind": "unknown",
        }
        repaired = repair_issue_row(row)
        self.assertEqual(repaired["representative_title"], "Codename Panzers Phase 2")
        self.assertEqual(repaired["normalized_title"], "codename panzers phase 2")

    def test_publishable_filter_drops_ui_noise(self) -> None:
        rows = [
            {
                "archive_item": "cbs-2000-09",
                "archive_name": "2005/CBS012005DVD.7z",
                "issue_code": "CBS012005DVD",
                "year": "2005",
                "variant": "DVD",
                "normalized_title": "zurueck",
                "representative_title": "Zurueck",
                "source_kinds": "disc-metadata-value",
                "confidence": "high",
                "content_kind": "unknown",
                "clean_reason": "singleword-titlecase",
            },
            {
                "archive_item": "cbs-2000-09",
                "archive_name": "2009/CBS062009DVD.7z",
                "issue_code": "CBS062009DVD",
                "year": "2009",
                "variant": "DVD",
                "normalized_title": "ati pr fsoftware",
                "representative_title": "ATI Prüfsoftware",
                "source_kinds": "disc-metadata-value",
                "confidence": "high",
                "content_kind": "unknown",
                "clean_reason": "multiword",
            },
            {
                "archive_item": "cbs-2000-09",
                "archive_name": "2008/CBS122008DVDGold.7z",
                "issue_code": "CBS122008DVDGold",
                "year": "2008",
                "variant": "DVDGold",
                "normalized_title": "baldur s gate compilation",
                "representative_title": "Baldur's Gate - Compilation",
                "source_kinds": "disc-metadata-value",
                "confidence": "high",
                "content_kind": "unknown",
                "clean_reason": "multiword",
            },
            {
                "archive_item": "cbs-2000-09",
                "archive_name": "2007/CBS112007DVD.7z",
                "issue_code": "CBS112007DVD",
                "year": "2007",
                "variant": "DVD",
                "normalized_title": "acronis true image10 home",
                "representative_title": "Acronis True Image10 Home",
                "source_kinds": "disc-metadata-value",
                "confidence": "high",
                "content_kind": "unknown",
                "clean_reason": "multiword",
            },
            {
                "archive_item": "cbs-2000-09",
                "archive_name": "2008/CBS032008DVD.7z",
                "issue_code": "CBS032008DVD",
                "year": "2008",
                "variant": "DVD",
                "normalized_title": "codename panzers phase 2 v 1",
                "representative_title": "Codename Panzers Phase 2",
                "source_kinds": "disc-metadata-value",
                "confidence": "high",
                "content_kind": "unknown",
                "clean_reason": "multiword",
            },
        ]
        publishable = publishable_issue_rows(rows)
        self.assertEqual(
            [row["representative_title"] for row in publishable],
            ["Baldur's Gate - Compilation", "Codename Panzers Phase 2"],
        )


class DownloadTests(unittest.TestCase):
    def test_download_record_archive_uses_archiveorg_url(self) -> None:
        record = ArchiveRecord(
            archive_item="cbs-2000-09",
            archive_name="2007/CBS022007DVD.7z",
            archive_url="https://archive.org/download/cbs-2000-09/2007/CBS022007DVD.7z",
            size_bytes=1,
            year=2007,
            issue_code="CBS022007DVD",
            variant="DVD",
        )
        calls: list[tuple[str, str]] = []

        def fake_download(url: str, destination: Path) -> None:
            calls.append((url, destination.name))
            destination.write_bytes(b"ok")

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch("scripts.index_cbs_exes.download_archive", side_effect=fake_download):
                archive_path, downloaded_url = download_record_archive(record, Path(temp_dir))
        self.assertEqual(downloaded_url, record.archive_url)
        self.assertEqual(archive_path.name, "CBS022007DVD.7z")
        self.assertEqual(calls, [(record.archive_url, "CBS022007DVD.7z")])


class ExecutableDiscoveryTests(unittest.TestCase):
    def test_detects_case_insensitive_executables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nested").mkdir()
            (root / "SETUP.EXE").write_bytes(b"setup")
            (root / "nested" / "game.ExE").write_bytes(b"game")
            (root / "readme.txt").write_text("ignore", encoding="utf-8")

            found = [path.relative_to(root).as_posix() for path in iter_executable_paths(root)]
            self.assertEqual(found, ["SETUP.EXE", "nested/game.ExE"])

    def test_prefers_descriptor_files_as_mount_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "disc.cue").write_text(
                'FILE "disc.bin" BINARY\n'
                'FILE "disc (Track 02).bin" BINARY\n',
                encoding="utf-8",
            )
            (root / "disc.bin").write_bytes(b"bin")
            (root / "disc (Track 02).bin").write_bytes(b"bin")
            (root / "bonus.iso").write_bytes(b"iso")

            candidates = sorted(candidate.inner_container for candidate in find_mount_candidates(root))
            self.assertEqual(candidates, ["bonus.iso", "disc.cue"])

    def test_converts_mode1_2352_data_track_to_iso(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cue_path = root / "disc.cue"
            bin_path = root / "disc.bin"
            cue_path.write_text(
                'FILE "disc.bin" BINARY\n'
                "  TRACK 01 MODE1/2352\n"
                "    INDEX 01 00:00:00\n",
                encoding="utf-8",
            )
            sector_a = b"\x00" * 16 + b"A" * 2048 + b"\x00" * (2352 - 16 - 2048)
            sector_b = b"\x00" * 16 + b"B" * 2048 + b"\x00" * (2352 - 16 - 2048)
            bin_path.write_bytes(sector_a + sector_b)

            iso_path = convert_cue_to_iso(cue_path, root / "disc.iso")
            self.assertEqual(iso_path.read_bytes(), b"A" * 2048 + b"B" * 2048)

    def test_extracts_title_candidates_from_exe_path(self) -> None:
        candidates = title_candidates_from_exe_path(Path("CBS/Demo/progs/Anno1602/DEMO/ANNO1602DEMO.exe"))
        self.assertEqual(candidates[0].candidate_title, "Anno1602")
        self.assertEqual(candidates[0].normalized_title, "anno1602")

    def test_extracts_title_candidates_from_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata = root / "autorun.inf"
            metadata.write_text(
                "[autorun]\n"
                "label=Prince of Persia 3D Demo\n"
                "open=CBS/Demo/progs/PrinceoP/PRINCEOFPERSIA3DDEMO.EXE\n",
                encoding="utf-8",
            )
            candidates = title_candidates_from_metadata_file(metadata, root)
            normalized = sorted(candidate.normalized_title for candidate in candidates)
            self.assertIn("prince of persia 3d", normalized)


class BenchmarkAndAutoModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.out_dir = self.root / "out"
        self.tmp_dir = self.root / "tmp"
        self.conn = connect_database(self.out_dir / "cbs_titles.sqlite")
        self.record = ArchiveRecord(
            archive_item="cbs-2000-09",
            archive_name="2000/CBS092000.7z",
            archive_url="https://example.invalid/CBS092000.7z",
            size_bytes=123,
            year=2000,
            issue_code="CBS092000",
            variant="CD",
        )

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _args(self, **overrides: object) -> SimpleNamespace:
        values = {
            "title_strategy": "auto",
            "force_disc": False,
            "validate_disc": False,
            "use_redump": False,
            "use_archive_ocr": False,
            "issue_search_limit": 5,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _insert_disc_title(self, title: str, source_kind: str, source_path: str, confidence: str = "high") -> None:
        normalized = normalize_title(title)
        self.assertIsNotNone(normalized)
        insert_title_row(
            self.conn,
            self.record,
            inner_container="disc.iso",
            mount_method="hdiutil",
            source_kind=source_kind,
            source_path=source_path,
            candidate_title=title,
            normalized_title=str(normalized),
            confidence=confidence,
            status="ok",
            error=None,
        )

    def test_benchmark_rows_compute_recall_against_union(self) -> None:
        rows = build_benchmark_rows(
            self.record,
            [
                StrategyRunResult(
                    strategy="archive-metadata",
                    candidates=(candidate("archiveorg-subject", "item:subject", "Anno 1602", "anno1602"),),
                    structured=True,
                    elapsed_ms=10,
                ),
                StrategyRunResult(
                    strategy="disc-full",
                    candidates=(
                        candidate("disc-exe-parent", "Anno1602/SETUP.EXE", "Anno 1602", "anno1602"),
                        candidate("disc-exe-parent", "PoP3D/SETUP.EXE", "Prince of Persia 3D", "prince of persia 3d"),
                    ),
                    structured=False,
                    elapsed_ms=20,
                ),
            ],
        )
        metadata_row = next(row for row in rows if row["strategy"] == "archive-metadata")
        self.assertEqual(metadata_row["union_title_count"], 2)
        self.assertEqual(metadata_row["recall_vs_union"], 0.5)

    def test_auto_mode_skips_disc_when_cheap_sources_are_sufficient(self) -> None:
        vollversion = StrategyRunResult(
            strategy="vollversion",
            candidates=(
                candidate("vollversion-fullversion", "https://www.vollversion.de/ausgabe/computer-bild-spiele-04-2000.html", "Mystery Island", "mystery island"),
            ),
            structured=True,
            elapsed_ms=5,
        )
        metadata = StrategyRunResult(strategy="archive-metadata", candidates=tuple(), structured=False, elapsed_ms=3)
        with mock.patch("scripts.index_cbs_exes.run_vollversion_strategy", return_value=vollversion), mock.patch(
            "scripts.index_cbs_exes.run_archive_metadata_strategy",
            return_value=metadata,
        ), mock.patch(
            "scripts.index_cbs_exes.run_disc_title_strategy"
        ) as run_disc:
            process_title_issue(self.conn, self.record, self.tmp_dir, self._args())
        run_disc.assert_not_called()
        resolution = self.conn.execute(
            "SELECT unresolved, resolution_path FROM issue_resolution WHERE archive_name = ?",
            (self.record.archive_name,),
        ).fetchone()
        self.assertEqual(int(resolution["unresolved"]), 0)
        self.assertEqual(str(resolution["resolution_path"]), "vollversion")

    def test_auto_mode_falls_back_to_disc_when_cheap_sources_are_insufficient(self) -> None:
        vollversion = StrategyRunResult(
            strategy="vollversion",
            candidates=tuple(),
            structured=False,
            elapsed_ms=1,
        )
        result = StrategyRunResult(
            strategy="archive-metadata",
            candidates=(candidate("archiveorg-title", "issue:title", "Anno 1602", "anno1602", "low"),),
            structured=False,
            elapsed_ms=5,
        )

        def disc_side_effect(conn, record, tmp_root, *, title_scan_mode: str, archive_path: Path | None = None) -> tuple[str, str | None]:
            self._insert_disc_title("Prince of Persia 3D", "disc-metadata-value", "autorun.inf")
            self._insert_disc_title("RollerCoaster Tycoon", "disc-manifest-path", "Demos/RollerCoasterTycoon")
            return ("ok", None)

        with mock.patch("scripts.index_cbs_exes.run_vollversion_strategy", return_value=vollversion), mock.patch(
            "scripts.index_cbs_exes.run_archive_metadata_strategy",
            return_value=result,
        ), mock.patch(
            "scripts.index_cbs_exes.download_record_archive",
            return_value=(self.tmp_dir / "disc-download.zip", "https://example.invalid/disc-download.zip"),
        ), mock.patch(
            "scripts.index_cbs_exes.run_disc_title_strategy",
            side_effect=disc_side_effect,
        ) as run_disc:
            process_title_issue(self.conn, self.record, self.tmp_dir, self._args())
        self.assertGreaterEqual(run_disc.call_count, 1)
        archived = self.conn.execute(
            "SELECT status FROM archives WHERE archive_name = ?",
            (self.record.archive_name,),
        ).fetchone()
        self.assertEqual(str(archived["status"]), "ok")

    def test_disc_quick_manifest_runs_before_full_fallback(self) -> None:
        vollversion = StrategyRunResult(
            strategy="vollversion",
            candidates=tuple(),
            structured=False,
            elapsed_ms=1,
        )
        result = StrategyRunResult(
            strategy="archive-metadata",
            candidates=(candidate("archiveorg-title", "issue:title", "Anno 1602", "anno1602", "low"),),
            structured=False,
            elapsed_ms=5,
        )
        seen_modes: list[str] = []

        def disc_side_effect(conn, record, tmp_root, *, title_scan_mode: str, archive_path: Path | None = None) -> tuple[str, str | None]:
            seen_modes.append(title_scan_mode)
            if title_scan_mode == "quick":
                self._insert_disc_title("Anno 1602", "disc-manifest-path", "Games/Anno1602")
            else:
                self._insert_disc_title("Prince of Persia 3D", "disc-exe-parent", "PoP3D/SETUP.EXE")
                self._insert_disc_title("RollerCoaster Tycoon", "disc-exe-parent", "RCT/SETUP.EXE")
            return ("ok", None)

        with mock.patch("scripts.index_cbs_exes.run_vollversion_strategy", return_value=vollversion), mock.patch(
            "scripts.index_cbs_exes.run_archive_metadata_strategy",
            return_value=result,
        ), mock.patch(
            "scripts.index_cbs_exes.download_record_archive",
            return_value=(self.tmp_dir / "disc-download.zip", "https://example.invalid/disc-download.zip"),
        ), mock.patch(
            "scripts.index_cbs_exes.run_disc_title_strategy",
            side_effect=disc_side_effect,
        ):
            process_title_issue(self.conn, self.record, self.tmp_dir, self._args())
        self.assertEqual(seen_modes, ["quick", "full"])


class ProcessingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.out_dir = self.root / "out"
        self.tmp_dir = self.root / "tmp"
        self.conn = connect_database(self.out_dir / "cbs_exes.sqlite")

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _make_outer_archive(self, name: str) -> Path:
        outer_path = self.root / f"{name}.zip"
        with zipfile.ZipFile(outer_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("disc.iso", b"placeholder image bytes")
        return outer_path

    @contextmanager
    def _fake_mounted_image(self, _image_path: Path, _mount_root: Path):
        mount_point = self.root / "fake-mounts" / uuid.uuid4().hex
        (mount_point / "GAMES").mkdir(parents=True, exist_ok=True)
        (mount_point / "GAMES" / "SETUP.EXE").write_bytes(b"setup payload")
        (mount_point / "GAMES" / "Bonus.ExE").write_bytes(b"bonus payload")
        try:
            yield AttachedImage(devices=("/dev/disk99",), mount_points=(mount_point,))
        finally:
            shutil.rmtree(mount_point, ignore_errors=True)

    @contextmanager
    def _fake_mounted_title_image(self, _image_path: Path, _mount_root: Path):
        mount_point = self.root / "fake-title-mounts" / uuid.uuid4().hex
        (mount_point / "Anno1602").mkdir(parents=True, exist_ok=True)
        (mount_point / "Anno1602" / "SETUP.EXE").write_bytes(b"setup payload")
        (mount_point / "autorun.inf").write_text(
            "[autorun]\nlabel=Anno 1602 Demo\nopen=Anno1602/SETUP.EXE\n",
            encoding="utf-8",
        )
        try:
            yield AttachedImage(devices=("/dev/disk98",), mount_points=(mount_point,))
        finally:
            shutil.rmtree(mount_point, ignore_errors=True)

    def _process_exe_record(self, archive_name: str) -> None:
        outer_path = self._make_outer_archive(archive_name.replace("/", "_"))
        year, issue_code, variant = parse_archive_name(archive_name)
        record = ArchiveRecord(
            archive_item="cbs-2000-09",
            archive_name=archive_name,
            archive_url=f"https://example.invalid/{Path(archive_name).name}",
            size_bytes=outer_path.stat().st_size,
            year=year,
            issue_code=issue_code,
            variant=variant,
        )

        with mock.patch("scripts.index_cbs_exes.mounted_image", side_effect=self._fake_mounted_image):
            status, error = process_downloaded_archive(record, outer_path, self.conn, self.tmp_dir, "exes")
        self.assertEqual(status, "ok")
        self.assertIsNone(error)

    def test_processes_cd_style_archive(self) -> None:
        self._process_exe_record("2000/CBS092000.7z")
        rows = self.conn.execute(
            """
            SELECT inner_container, mount_method, exe_path, status
            FROM inventory
            ORDER BY exe_path
            """
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [(row["inner_container"], row["mount_method"], row["exe_path"], row["status"]) for row in rows],
            [
                ("disc.iso", "hdiutil", "GAMES/Bonus.ExE", "ok"),
                ("disc.iso", "hdiutil", "GAMES/SETUP.EXE", "ok"),
            ],
        )
        self.assertFalse(any(self.tmp_dir.iterdir()))

    def test_processes_dvd_gold_style_archive_and_exports_dedup(self) -> None:
        self._process_exe_record("2010/CBS062010DVDGold.7z")
        export_csvs(self.conn, self.out_dir, "exes")
        raw_csv = (self.out_dir / "all_executables.csv").read_text(encoding="utf-8")
        dedup_csv = (self.out_dir / "executables_dedup.csv").read_text(encoding="utf-8")
        self.assertIn("CBS062010DVDGold", raw_csv)
        self.assertIn("occurrence_count", dedup_csv)

    def test_processes_title_mode_and_exports_issue_and_master_lists(self) -> None:
        outer_path = self._make_outer_archive("2000_CBS092000_titles")
        year, issue_code, variant = parse_archive_name("2000/CBS092000.7z")
        record = ArchiveRecord(
            archive_item="cbs-2000-09",
            archive_name="2000/CBS092000.7z",
            archive_url="https://example.invalid/CBS092000.7z",
            size_bytes=outer_path.stat().st_size,
            year=year,
            issue_code=issue_code,
            variant=variant,
        )
        with mock.patch("scripts.index_cbs_exes.mounted_image", side_effect=self._fake_mounted_title_image):
            status, error = process_downloaded_archive(record, outer_path, self.conn, self.tmp_dir, "titles")
        self.assertEqual(status, "ok")
        self.assertIsNone(error)
        self.conn.execute(
            """
            INSERT INTO issue_resolution (
                archive_name, archive_item, issue_code, year, variant, title_strategy,
                resolution_path, reason, unresolved, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2000/CBS092000.7z",
                "cbs-2000-09",
                "CBS092000",
                2000,
                "CD",
                "auto",
                "archive-metadata",
                "verified",
                0,
                "ok",
                "2026-03-12T00:00:00+00:00",
            ),
        )
        self.conn.commit()
        export_csvs(self.conn, self.out_dir, "titles")
        raw_csv = (self.out_dir / "all_title_candidates.csv").read_text(encoding="utf-8")
        dedup_csv = (self.out_dir / "titles_dedup.csv").read_text(encoding="utf-8")
        issue_titles_csv = (self.out_dir / "issue_titles.csv").read_text(encoding="utf-8")
        master_csv = (self.out_dir / "master_games.csv").read_text(encoding="utf-8")
        unresolved_csv = (self.out_dir / "unresolved_issues.csv").read_text(encoding="utf-8")
        self.assertIn("Anno1602", raw_csv)
        self.assertIn("representative_title", dedup_csv)
        self.assertIn("normalized_title", issue_titles_csv)
        self.assertIn("normalized_title", master_csv)
        self.assertIn("archive_name", unresolved_csv)


if __name__ == "__main__":
    unittest.main()
