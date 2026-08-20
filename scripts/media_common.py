#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import re
import struct
import urllib.parse
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

MEDIA_MANIFEST_FIELDS = (
    "asset_id",
    "subject_type",
    "subject_id",
    "media_role",
    "featured_rank",
    "source_provider",
    "source_record_id",
    "source_file",
    "source_archive_member",
    "source_page_url",
    "source_download_url",
    "source_sha1",
    "source_member_sha256",
    "source_revision",
    "source_mime",
    "source_width",
    "source_height",
    "creator_name",
    "creator_url",
    "license_id",
    "license_name",
    "license_url",
    "credit_line",
    "attribution_required",
    "rights_status",
    "review_status",
    "alt_en",
    "alt_de",
    "caption_en",
    "caption_de",
    "export_relpath",
)

ASSET_SOURCE_IDENTITY_FIELDS = (
    "source_record_id",
    "source_file",
    "source_sha1",
    "source_revision",
)

ASSET_EVIDENCE_FIELDS = (
    "subject_type",
    "subject_id",
    *ASSET_SOURCE_IDENTITY_FIELDS,
    "source_archive_member",
    "source_member_sha256",
    "source_mime",
    "source_width",
    "source_height",
    "export_relpath",
)


def asset_source_identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")).strip() for field in ASSET_SOURCE_IDENTITY_FIELDS)


COMMONS_EVIDENCE_FIELDS = (
    "subject_id",
    "wikidata_id",
    "match_basis",
    "source_file",
    "source_page_url",
    "source_download_url",
    "source_sha1",
    "source_revision",
    "source_mime",
    "source_width",
    "source_height",
    "creator_name",
    "creator_url",
    "license_id",
    "license_name",
    "license_url",
    "credit_line",
    "attribution_required",
    "usage_terms",
    "restrictions",
    "description",
)

IA_FILE_EVIDENCE_FIELDS = (
    "source_record_id",
    "source_file",
    "source_download_url",
    "source_size_bytes",
    "source_sha1",
    "source_mtime",
    "source_creator",
    "source_license_url",
    "source_rights",
    "source_revision",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in writer.fieldnames})


def normalize_scan_key(value: str) -> str:
    stem = PurePosixPath(value).stem
    stem = re.sub(r"(?:[_ ]scans?|[_ ]scnas)$", "", stem, flags=re.IGNORECASE)
    normalized = re.sub(r"[^a-z0-9]+", "", stem.casefold())
    normalized = normalized.removeprefix("cbs")
    normalized = normalized.replace("sonder", "sh")
    normalized = normalized.replace("dvd", "").replace("cd", "")
    match = re.fullmatch(r"(\d{2})(?:20)?(\d{2})(.*)", normalized)
    if not match:
        return normalized
    return "".join(match.groups())


def scan_file_index(files: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in files:
        name = str(entry.get("name", ""))
        if "/Scans/" not in name or not name.casefold().endswith(".7z"):
            continue
        index[normalize_scan_key(name)].append(entry)
    return dict(index)


def safe_archive_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and len(path.parts) == 1


def sha1_digest(path: Path) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def base36(number: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"
    encoded = ""
    while number:
        number, remainder = divmod(number, 36)
        encoded = alphabet[remainder] + encoded
    return encoded


def matches_mediawiki_sha1(path: Path, expected: str) -> bool:
    actual_hex = sha1_digest(path)
    normalized = expected.casefold().strip()
    return normalized in {actual_hex, base36(int(actual_hex, 16))}


def tiff_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        byte_order = handle.read(2)
        endian = {b"II": "<", b"MM": ">"}.get(byte_order)
        if not endian:
            raise ValueError(f"unsupported TIFF byte order: {path}")
        magic = struct.unpack(f"{endian}H", handle.read(2))[0]
        if magic != 42:
            raise ValueError(f"unsupported TIFF format: {path}")
        ifd_offset = struct.unpack(f"{endian}I", handle.read(4))[0]
        handle.seek(ifd_offset)
        entry_count = struct.unpack(f"{endian}H", handle.read(2))[0]
        dimensions: dict[int, int] = {}
        for _ in range(entry_count):
            raw = handle.read(12)
            if len(raw) != 12:
                raise ValueError(f"truncated TIFF directory: {path}")
            tag, value_type, count = struct.unpack(f"{endian}HHI", raw[:8])
            if tag not in {256, 257} or count != 1:
                continue
            if value_type == 3:
                value = struct.unpack(f"{endian}H", raw[8:10])[0]
            elif value_type == 4:
                value = struct.unpack(f"{endian}I", raw[8:12])[0]
            else:
                continue
            dimensions[tag] = value
    if 256 not in dimensions or 257 not in dimensions:
        raise ValueError(f"TIFF dimensions are missing: {path}")
    return dimensions[256], dimensions[257]


def asset_id(subject_type: str, subject_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", subject_id.casefold()).strip("-")
    return f"{subject_type}-{normalized}"


def archive_download_url(record_id: str, source_file: str) -> str:
    encoded = urllib.parse.quote(source_file, safe="/")
    return f"https://archive.org/download/{record_id}/{encoded}"


def load_media_overrides(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    overrides: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv(path):
        key = (row["subject_type"], row["subject_id"])
        if key in overrides:
            raise ValueError(f"duplicate media override: {key}")
        if row["action"] not in {"approve", "reject"}:
            raise ValueError(f"unsupported media action for {key}: {row['action']}")
        overrides[key] = row
    return overrides


def select_issue_sources(
    issue_codes: Iterable[str],
    files: Iterable[dict[str, Any]],
    overrides: dict[tuple[str, str], dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    file_rows = list(files)
    by_name = {str(row.get("name") or row.get("source_file") or ""): row for row in file_rows}
    index = scan_file_index({"name": row.get("name") or row.get("source_file", "")} for row in file_rows)
    selected: dict[str, dict[str, Any]] = {}
    rejected: dict[str, str] = {}
    for issue_code in sorted(set(issue_codes)):
        override = overrides.get(("issue", issue_code), {})
        if override.get("action") == "reject":
            rejected[issue_code] = override.get("reason", "rejected")
            continue
        source_file = override.get("source_file", "")
        if source_file:
            if source_file not in by_name:
                raise ValueError(f"media override references a missing source file: {issue_code}: {source_file}")
            selected[issue_code] = by_name[source_file]
            continue
        candidates = index.get(normalize_scan_key(issue_code), [])
        if len(candidates) != 1:
            reason = "no_corresponding_scan" if not candidates else "ambiguous_scan_mapping"
            rejected[issue_code] = reason
            continue
        candidate_name = str(candidates[0]["name"])
        selected[issue_code] = by_name[candidate_name]
    return selected, rejected
