from __future__ import annotations

import json
import shutil
import struct
import tempfile
import unittest
from hashlib import sha1
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from scripts.build_media_release import build_release
from scripts.fetch_media_evidence import discover_commons_candidates, download_file
from scripts.media_common import (
    ASSET_EVIDENCE_FIELDS,
    COMMONS_EVIDENCE_FIELDS,
    IA_FILE_EVIDENCE_FIELDS,
    normalize_scan_key,
    read_csv,
    safe_archive_member,
    select_issue_sources,
    tiff_dimensions,
    write_csv,
)
from scripts.media_release_contract import ROOT as REPO_ROOT
from scripts.media_release_contract import sha256 as file_sha256
from scripts.media_release_contract import validate_release


class MediaCommonTests(unittest.TestCase):
    def test_download_verifies_and_reuses_cached_file(self) -> None:
        payload = b"verified media payload"
        expected_sha1 = sha1(payload, usedforsecurity=False).hexdigest()

        class FakeResponse(BytesIO):
            status = 200

            def __init__(self, body: bytes) -> None:
                super().__init__(body)
                self.headers = {"Content-Length": str(len(body))}

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            destination = root / "cache" / "asset.bin"

            with patch(
                "scripts.fetch_media_evidence.open_https",
                return_value=FakeResponse(payload),
            ) as open_https:
                download_file(
                    "https://upload.wikimedia.org/test.bin",
                    destination,
                    expected_size=len(payload),
                    expected_sha1=expected_sha1,
                )
                download_file(
                    "https://upload.wikimedia.org/test.bin",
                    destination,
                    expected_size=len(payload),
                    expected_sha1=expected_sha1,
                )

            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(open_https.call_count, 1)

    def test_download_rejects_non_https_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "asset.bin"
            with self.assertRaises(ValueError):
                download_file(
                    "file:///tmp/source.bin",
                    destination,
                    expected_size=1,
                    expected_sha1="0" * 40,
                )

    def test_download_rejects_oversized_response_and_removes_partial(self) -> None:
        class FakeResponse(BytesIO):
            status = 200

            def __init__(self) -> None:
                super().__init__(b"too large")
                self.headers = {"Content-Length": "9"}

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "asset.bin"
            with (
                patch("scripts.fetch_media_evidence.open_https", return_value=FakeResponse()),
                self.assertRaisesRegex(ValueError, "exceeds"),
            ):
                download_file(
                    "https://upload.wikimedia.org/test.bin",
                    destination,
                    expected_size=2,
                    expected_sha1="0" * 40,
                    attempts=1,
                )
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix(".bin.part").exists())

    @patch("scripts.fetch_media_evidence.request_json")
    def test_candidate_discovery_can_skip_depicts_queries(self, request_json) -> None:
        request_json.return_value = {
            "entities": {
                "Q1": {
                    "claims": {
                        "P18": [
                            {
                                "rank": "normal",
                                "mainsnak": {
                                    "snaktype": "value",
                                    "datavalue": {"value": "Exact cover.png"},
                                },
                            }
                        ]
                    }
                }
            }
        }

        candidates = discover_commons_candidates({"Q1": {"game_id": "example"}}, include_depicts=False)

        self.assertEqual(
            candidates,
            [
                {
                    "subject_id": "example",
                    "source_file": "Exact cover.png",
                    "match_basis": "wikidata_p18",
                }
            ],
        )
        self.assertEqual(request_json.call_count, 1)

    def test_scan_keys_normalize_historical_filename_variants(self) -> None:
        cases = {
            "CBS012006DVD": "0106",
            "2007/Scans/CBS01_07Gold_Scans.7z": "0107gold",
            "2009/Scans/CBS0109SH_Scans.7z": "0109sh",
            "CBS032004 (CD1)": "03041",
            "2004/Scans/CBS092004DVD Scans.7z": "0904",
            "2010/Scans/CBS0810Gold_Scnas.7z": "0810gold",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_scan_key(value), expected)

    def test_archive_member_validation_rejects_paths(self) -> None:
        self.assertTrue(safe_archive_member("disc.tif"))
        self.assertFalse(safe_archive_member("../disc.tif"))
        self.assertFalse(safe_archive_member("folder/disc.tif"))
        self.assertFalse(safe_archive_member("/tmp/disc.tif"))

    def test_reads_classic_tiff_dimensions(self) -> None:
        header = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
        entries = struct.pack("<H", 2)
        entries += struct.pack("<HHI", 256, 4, 1) + struct.pack("<I", 2894)
        entries += struct.pack("<HHI", 257, 4, 1) + struct.pack("<I", 2907)
        entries += struct.pack("<I", 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "disc.tif"
            path.write_bytes(header + entries)
            self.assertEqual(tiff_dimensions(path), (2894, 2907))

    def test_issue_source_selection_uses_exact_override_and_rejection(self) -> None:
        files = [
            {"name": "2007/Scans/CBS07_2007_2_Scans.7z"},
            {"name": "2008/Scans/CBS01_08_Scans.7z"},
        ]
        overrides = {
            ("issue", "CBS072007DVD"): {
                "action": "approve",
                "source_file": "2007/Scans/CBS07_2007_2_Scans.7z",
            },
            ("issue", "CBS012008DVDSonder"): {
                "action": "reject",
                "reason": "no_corresponding_scan",
            },
        }
        selected, rejected = select_issue_sources(
            ["CBS072007DVD", "CBS012008DVD", "CBS012008DVDSonder"], files, overrides
        )
        self.assertEqual(selected["CBS072007DVD"]["name"], files[0]["name"])
        self.assertEqual(selected["CBS012008DVD"]["name"], files[1]["name"])
        self.assertEqual(rejected["CBS012008DVDSonder"], "no_corresponding_scan")

    def test_media_build_requires_evidence_from_the_selected_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            published = root / "published"
            enriched = root / "enriched"
            evidence_dir = root / "evidence"
            overrides = root / "overrides.csv"

            write_csv(
                published / "publishable_issue_titles.csv",
                ("issue_code",),
                [{"issue_code": "CBS012003"}],
            )
            write_csv(
                enriched / "enriched_master_games.csv",
                ("game_id", "match_status", "wikidata_id"),
                [],
            )
            write_csv(
                evidence_dir / "ia_files.csv",
                IA_FILE_EVIDENCE_FIELDS,
                [
                    {
                        "source_record_id": "record-b",
                        "source_file": "Scans/selected-B.7z",
                        "source_download_url": "https://example.invalid/selected-B.7z",
                        "source_sha1": "b" * 40,
                        "source_revision": "revision-b",
                    }
                ],
            )
            write_csv(evidence_dir / "commons_candidates.csv", COMMONS_EVIDENCE_FIELDS, [])
            asset = {
                "subject_type": "issue",
                "subject_id": "CBS012003",
                "source_record_id": "record-a",
                "source_file": "Scans/source-A.7z",
                "source_sha1": "a" * 40,
                "source_revision": "revision-a",
                "source_archive_member": "member-from-A.tif",
                "source_member_sha256": "a" * 64,
                "source_mime": "image/tiff",
                "source_width": "100",
                "source_height": "100",
                "export_relpath": "originals/from-A.tif",
            }
            write_csv(evidence_dir / "asset_evidence.csv", ASSET_EVIDENCE_FIELDS, [asset])
            write_csv(
                overrides,
                ("subject_type", "subject_id", "action", "source_file", "media_role", "featured_rank", "reason"),
                [
                    {
                        "subject_type": "issue",
                        "subject_id": "CBS012003",
                        "action": "approve",
                        "source_file": "Scans/selected-B.7z",
                        "media_role": "disc_face",
                        "reason": "fixture",
                    }
                ],
            )

            with self.assertRaisesRegex(ValueError, "asset evidence source mismatch"):
                build_release(published, enriched, overrides, evidence_dir)

            asset.update(
                {
                    "source_record_id": "record-b",
                    "source_file": "Scans/selected-B.7z",
                    "source_sha1": "b" * 40,
                    "source_revision": "revision-b",
                    "source_archive_member": "member-from-B.tif",
                    "source_member_sha256": "b" * 64,
                    "export_relpath": "originals/from-B.tif",
                }
            )
            write_csv(evidence_dir / "asset_evidence.csv", ASSET_EVIDENCE_FIELDS, [asset])
            manifest, _ = build_release(published, enriched, overrides, evidence_dir)
            self.assertEqual(manifest[0]["source_file"], "Scans/selected-B.7z")
            self.assertEqual(manifest[0]["source_archive_member"], "member-from-B.tif")

    def test_media_contract_rejects_rebound_asset_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir) / "media-20260809"
            shutil.copytree(REPO_ROOT / "results" / "media-20260809", release_dir)

            evidence_path = release_dir / "asset_evidence.csv"
            evidence = read_csv(evidence_path)
            evidence[0]["source_file"] = "forged-source.png"
            write_csv(evidence_path, ASSET_EVIDENCE_FIELDS, evidence)

            frozen_path = release_dir / "release-manifest.json"
            frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
            evidence_record = next(row for row in frozen["artifacts"] if row["path"] == "asset_evidence.csv")
            evidence_record["bytes"] = evidence_path.stat().st_size
            evidence_record["sha256"] = file_sha256(evidence_path)
            frozen_path.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "asset evidence source mismatch"):
                validate_release(
                    release_dir,
                    REPO_ROOT / "results" / "published-20260808",
                    REPO_ROOT / "results" / "enriched-20260808",
                    REPO_ROOT / "data" / "manual_media_overrides.csv",
                )


if __name__ == "__main__":
    unittest.main()
