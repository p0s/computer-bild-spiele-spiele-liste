from __future__ import annotations

import struct
import tempfile
import unittest
from hashlib import sha1
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_media_evidence import discover_commons_candidates, download_file
from scripts.media_common import (
    normalize_scan_key,
    safe_archive_member,
    select_issue_sources,
    tiff_dimensions,
)


class MediaCommonTests(unittest.TestCase):
    def test_download_verifies_and_reuses_cached_file(self) -> None:
        payload = b"verified media payload"
        expected_sha1 = sha1(payload, usedforsecurity=False).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.bin"
            destination = root / "cache" / "asset.bin"
            source.write_bytes(payload)

            download_file(
                source.as_uri(),
                destination,
                expected_size=len(payload),
                expected_sha1=expected_sha1,
            )
            source.write_bytes(b"different upstream bytes")
            download_file(
                source.as_uri(),
                destination,
                expected_size=len(payload),
                expected_sha1=expected_sha1,
            )

            self.assertEqual(destination.read_bytes(), payload)

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


if __name__ == "__main__":
    unittest.main()
