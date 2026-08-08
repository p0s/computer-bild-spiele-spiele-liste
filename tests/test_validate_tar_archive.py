from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.validate_tar_archive import UnsafeArchiveError, validate_tar_archive


def write_tar(path: Path, members: list[tuple[tarfile.TarInfo, bytes]]) -> None:
    with tarfile.open(path, mode="w:gz") as handle:
        for info, payload in members:
            info.size = len(payload)
            handle.addfile(info, io.BytesIO(payload))


class TarArchiveValidationTests(unittest.TestCase):
    def test_accepts_regular_files_under_one_expected_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "snapshot.tar.gz"
            write_tar(
                archive,
                [
                    (tarfile.TarInfo("snapshot/issue_titles.csv"), b"header\n"),
                    (tarfile.TarInfo("snapshot/master_games.csv"), b"header\n"),
                ],
            )
            validate_tar_archive(archive, expected_root="snapshot")

    def test_rejects_traversal_links_and_declared_size_bombs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            traversal = root / "traversal.tar.gz"
            write_tar(traversal, [(tarfile.TarInfo("snapshot/../escape"), b"bad")])
            with self.assertRaises(UnsafeArchiveError):
                validate_tar_archive(traversal, expected_root="snapshot")

            link = root / "link.tar.gz"
            info = tarfile.TarInfo("snapshot/link")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../escape"
            write_tar(link, [(info, b"")])
            with self.assertRaises(UnsafeArchiveError):
                validate_tar_archive(link, expected_root="snapshot")

            oversized = root / "oversized.tar.gz"
            write_tar(oversized, [(tarfile.TarInfo("snapshot/data"), b"12345")])
            with self.assertRaises(UnsafeArchiveError):
                validate_tar_archive(oversized, expected_root="snapshot", maximum_uncompressed_bytes=4)


if __name__ == "__main__":
    unittest.main()
