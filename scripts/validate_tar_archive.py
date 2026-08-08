#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tarfile
from pathlib import Path, PurePosixPath


class UnsafeArchiveError(ValueError):
    pass


def validate_tar_archive(
    archive: Path,
    *,
    expected_root: str,
    maximum_members: int = 100_000,
    maximum_uncompressed_bytes: int = 20 * 1024 * 1024 * 1024,
) -> None:
    if not expected_root or "/" in expected_root or "\\" in expected_root or expected_root in {".", ".."}:
        raise UnsafeArchiveError("expected root must be one safe path component")

    seen: set[str] = set()
    total_size = 0
    with tarfile.open(archive, mode="r:gz") as handle:
        members = handle.getmembers()
        if len(members) > maximum_members:
            raise UnsafeArchiveError(f"archive has {len(members)} members; limit is {maximum_members}")
        for member in members:
            name = member.name
            if not name or "\x00" in name or "\\" in name or len(name) > 4096:
                raise UnsafeArchiveError(f"unsafe archive member path: {name!r}")
            path = PurePosixPath(name)
            if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
                raise UnsafeArchiveError(f"unsafe archive member path: {name!r}")
            if not path.parts or path.parts[0] != expected_root:
                raise UnsafeArchiveError(f"archive member is outside expected root {expected_root!r}: {name!r}")
            if name in seen:
                raise UnsafeArchiveError(f"duplicate archive member: {name!r}")
            seen.add(name)
            if not (member.isfile() or member.isdir()):
                raise UnsafeArchiveError(f"links and special files are forbidden: {name!r}")
            if member.size < 0:
                raise UnsafeArchiveError(f"negative archive member size: {name!r}")
            total_size += member.size
            if total_size > maximum_uncompressed_bytes:
                raise UnsafeArchiveError(
                    f"archive declares {total_size} uncompressed bytes; limit is {maximum_uncompressed_bytes}"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reject unsafe tar members before extracting a VPS result bundle.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-root", required=True)
    parser.add_argument("--maximum-members", type=int, default=100_000)
    parser.add_argument("--maximum-uncompressed-bytes", type=int, default=20 * 1024 * 1024 * 1024)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_tar_archive(
            args.archive,
            expected_root=args.expected_root,
            maximum_members=args.maximum_members,
            maximum_uncompressed_bytes=args.maximum_uncompressed_bytes,
        )
    except (UnsafeArchiveError, tarfile.TarError, OSError) as exc:
        print(f"unsafe tar archive: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
