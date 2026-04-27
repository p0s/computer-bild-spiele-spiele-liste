#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import plistlib
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

HTTP_USER_AGENT = "cbs-title-collector/1.0"


RAW_COLUMNS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "archive_url",
    "inner_container",
    "mount_method",
    "exe_path",
    "exe_name",
    "size_bytes",
    "sha1",
    "status",
    "error",
]

DEDUP_COLUMNS = [
    "sha1",
    "exe_name",
    "size_bytes",
    "first_seen_issue",
    "occurrence_count",
]

TITLE_COLUMNS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "archive_url",
    "inner_container",
    "mount_method",
    "source_kind",
    "source_path",
    "candidate_title",
    "normalized_title",
    "confidence",
    "status",
    "error",
]

TITLE_DEDUP_COLUMNS = [
    "normalized_title",
    "representative_title",
    "first_seen_issue",
    "occurrence_count",
    "issue_count",
]

MASTER_GAME_COLUMNS = [
    "normalized_title",
    "representative_title",
    "first_seen_issue",
    "issue_count",
    "occurrence_count",
    "best_confidence",
    "source_kinds",
]

ISSUE_TITLE_COLUMNS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "normalized_title",
    "representative_title",
    "source_kinds",
    "confidence",
    "content_kind",
]

UNRESOLVED_COLUMNS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "title_strategy",
    "resolution_path",
    "reason",
    "status",
]

BENCHMARK_COLUMNS = [
    "archive_name",
    "issue_code",
    "strategy",
    "elapsed_ms",
    "candidate_count",
    "unique_title_count",
    "structured",
    "unresolved",
    "union_title_count",
    "recall_vs_union",
    "notes",
]

TERMINAL_STATUSES = {
    "ok",
    "download_failed",
    "extract_failed",
    "mount_failed",
    "hash_failed",
}

CONTAINER_EXTENSIONS = {
    ".bin",
    ".ccd",
    ".cdr",
    ".cue",
    ".dmg",
    ".img",
    ".iso",
    ".mdf",
    ".mds",
    ".nrg",
    ".toast",
}

SINGLE_FILE_CONTAINER_EXTENSIONS = {
    ".bin",
    ".cdr",
    ".dmg",
    ".img",
    ".iso",
    ".mdf",
    ".nrg",
    ".toast",
}

TITLE_METADATA_SUFFIXES = {
    ".inf",
    ".ini",
    ".html",
    ".htm",
    ".txt",
    ".nfo",
}

GENERIC_TITLE_SEGMENTS = {
    "autorun",
    "bonus",
    "cd",
    "cd1",
    "cd2",
    "data",
    "demo",
    "demos",
    "disk",
    "disk1",
    "disk2",
    "driver",
    "drivers",
    "extras",
    "game",
    "games",
    "install",
    "launcher",
    "menu",
    "patch",
    "patches",
    "play",
    "progs",
    "program",
    "programme",
    "programs",
    "setup",
    "software",
    "start",
    "starter",
    "support",
    "tools",
    "treiber",
    "uninstall",
    "update",
    "utils",
    "vollv",
}

GENERIC_TITLE_WORDS = GENERIC_TITLE_SEGMENTS | {
    "bild",
    "cbs",
    "cd",
    "computer",
    "coverdisc",
    "covermount",
    "demo",
    "dvd",
    "edition",
    "gold",
    "inhalt",
    "issue",
    "launcher",
    "magazine",
    "setup",
    "silber",
    "spiele",
    "platin",
    "shareware",
    "trial",
}

GENERIC_NORMALIZED_TITLES = {
    "computer bild",
    "computer bild spiele",
    "computer bild spiele cd",
    "computer bild spiele dvd",
    "coverdisc",
    "covermount",
    "issue",
    "magazine",
}

TITLE_SECTION_PATTERNS = {
    "full_version": re.compile(r"\b(vollversion(?:en)?|full\s*version(?:s)?)\b", re.IGNORECASE),
    "demo": re.compile(r"\b(demo|demos)\b", re.IGNORECASE),
    "bonus": re.compile(r"\b(bonus|extras?)\b", re.IGNORECASE),
    "unknown": re.compile(
        r"\b(beinhaltet|inhalt|contents|spiele|cd-?inhalt|dvd-?inhalt)\b",
        re.IGNORECASE,
    ),
}

SOURCE_KIND_RANKS = {
    "vollversion-fullversion": 8,
    "vollversion-description": 7,
    "vollversion-title": 6,
    "archiveorg-ocr": 6,
    "archiveorg-description": 5,
    "archiveorg-subject": 4,
    "archiveorg-note": 4,
    "archiveorg-title": 3,
    "redump-title": 2,
    "redump-snippet": 1,
    "disc-metadata-value": 2,
    "disc-metadata-command": 2,
    "disc-manifest-path": 1,
    "disc-exe-parent": 1,
    "disc-exe-name": 0,
}

CONFIDENCE_RANKS = {"high": 3, "medium": 2, "low": 1}


class CommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArchiveRecord:
    archive_item: str
    archive_name: str
    archive_url: str
    size_bytes: int
    year: int
    issue_code: str
    variant: str


@dataclass(frozen=True)
class MountCandidate:
    path: Path
    inner_container: str


@dataclass(frozen=True)
class AttachedImage:
    devices: tuple[str, ...]
    mount_points: tuple[Path, ...]


@dataclass(frozen=True)
class CueDataTrack:
    bin_path: Path
    mode: str
    start_sector: int
    end_sector: int | None


@dataclass(frozen=True)
class TitleCandidate:
    source_kind: str
    source_path: str
    candidate_title: str
    normalized_title: str
    confidence: str
    content_kind: str = "unknown"


@dataclass(frozen=True)
class StrategyRunResult:
    strategy: str
    candidates: tuple[TitleCandidate, ...]
    structured: bool
    elapsed_ms: int
    error: str | None = None
    notes: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_name(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("._") or "archive"


def parse_archive_name(name: str) -> tuple[int, str, str]:
    basename = Path(name).name
    if not basename.lower().endswith(".7z"):
        raise ValueError(f"Unsupported archive name: {name}")

    stem = basename[:-3]
    if not stem.startswith("CBS") or len(stem) < 7:
        raise ValueError(f"Unsupported archive name: {name}")

    month = stem[3:5]
    if not month.isdigit():
        raise ValueError(f"Unsupported archive name: {name}")

    month_value = int(month)
    if month_value < 1 or month_value > 12:
        raise ValueError(f"Unsupported archive name: {name}")

    if len(stem) >= 9 and stem[5:9].isdigit():
        year = int(stem[5:9])
        suffix = stem[9:]
        variant = suffix or "CD"
        return year, stem, variant

    short_year = stem[5:7]
    suffix = stem[7:]
    if not short_year.isdigit():
        raise ValueError(f"Unsupported archive name: {name}")

    short_year_value = int(short_year)
    year = 2000 + short_year_value if short_year_value <= 69 else 1900 + short_year_value
    variant = suffix or "Standard"
    return year, stem, variant


def ensure_required_tools(
    *,
    mode: str,
    title_strategy: str,
) -> None:
    missing = []
    required = {"curl"}
    if mode == "exes":
        required.update({"lsar", "unar", "hdiutil"})
    elif mode == "titles" and title_strategy == "disc-only":
        required.update({"lsar", "unar", "hdiutil"})

    for tool in sorted(required):
        if shutil.which(tool) is None:
            missing.append(tool)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise SystemExit(f"Missing required tools: {missing_text}")


def ensure_disc_tools() -> None:
    if shutil.which("lsar") and shutil.which("unar") and shutil.which("hdiutil"):
        return
    if seven_zip_binary() is not None:
        return
    raise CommandError("Missing required disc tools: need either lsar+unar+hdiutil or 7z/7zz")


def fetch_archive_records(item: str) -> list[ArchiveRecord]:
    url = f"https://archive.org/metadata/{item}"
    payload = json.loads(http_get_text(url))

    records: list[ArchiveRecord] = []
    for file_info in payload.get("files", []):
        name = file_info.get("name", "")
        if "/Scans/" in name:
            continue
        parts = name.split("/")
        if len(parts) != 2:
            continue
        if not name.lower().endswith(".7z"):
            continue
        try:
            year, issue_code, variant = parse_archive_name(name)
        except ValueError:
            continue
        records.append(
            ArchiveRecord(
                archive_item=item,
                archive_name=name,
                archive_url=f"https://archive.org/download/{item}/{name}",
                size_bytes=int(file_info.get("size", "0") or 0),
                year=year,
                issue_code=issue_code,
                variant=variant,
            )
        )
    records.sort(key=lambda record: record.archive_name)
    return records


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS archives (
            archive_name TEXT PRIMARY KEY,
            archive_item TEXT NOT NULL,
            archive_url TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            year INTEGER NOT NULL,
            issue_code TEXT NOT NULL,
            variant TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_item TEXT NOT NULL,
            archive_name TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            variant TEXT NOT NULL,
            archive_url TEXT NOT NULL,
            inner_container TEXT,
            mount_method TEXT,
            exe_path TEXT,
            exe_name TEXT,
            size_bytes INTEGER,
            sha1 TEXT,
            status TEXT NOT NULL,
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_inventory_archive_name
        ON inventory (archive_name);

        CREATE INDEX IF NOT EXISTS idx_inventory_sha1
        ON inventory (sha1);

        CREATE TABLE IF NOT EXISTS titles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_item TEXT NOT NULL,
            archive_name TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            variant TEXT NOT NULL,
            archive_url TEXT NOT NULL,
            inner_container TEXT,
            mount_method TEXT,
            source_kind TEXT,
            source_path TEXT,
            candidate_title TEXT,
            normalized_title TEXT,
            confidence TEXT,
            status TEXT NOT NULL,
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_titles_archive_name
        ON titles (archive_name);

        CREATE INDEX IF NOT EXISTS idx_titles_normalized_title
        ON titles (normalized_title);

        CREATE TABLE IF NOT EXISTS external_cache (
            cache_key TEXT PRIMARY KEY,
            cache_kind TEXT NOT NULL,
            source_url TEXT NOT NULL,
            payload TEXT,
            error TEXT,
            fetched_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS strategy_cache (
            cache_key TEXT PRIMARY KEY,
            strategy TEXT NOT NULL,
            archive_name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            structured INTEGER NOT NULL,
            elapsed_ms INTEGER NOT NULL,
            error TEXT,
            notes TEXT,
            fetched_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS strategy_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_name TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            strategy TEXT NOT NULL,
            elapsed_ms INTEGER NOT NULL,
            candidate_count INTEGER NOT NULL,
            unique_title_count INTEGER NOT NULL,
            structured INTEGER NOT NULL,
            unresolved INTEGER NOT NULL,
            union_title_count INTEGER,
            recall_vs_union REAL,
            notes TEXT,
            benchmark_run_id TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_strategy_runs_archive
        ON strategy_runs (archive_name, strategy);

        CREATE INDEX IF NOT EXISTS idx_strategy_runs_benchmark
        ON strategy_runs (benchmark_run_id);

        CREATE TABLE IF NOT EXISTS issue_resolution (
            archive_name TEXT PRIMARY KEY,
            archive_item TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            variant TEXT NOT NULL,
            title_strategy TEXT NOT NULL,
            resolution_path TEXT,
            reason TEXT,
            unresolved INTEGER NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    return conn


def archive_status(conn: sqlite3.Connection, archive_name: str) -> str | None:
    row = conn.execute(
        "SELECT status FROM archives WHERE archive_name = ?",
        (archive_name,),
    ).fetchone()
    if row is None:
        return None
    return str(row["status"])


def mark_archive_started(conn: sqlite3.Connection, record: ArchiveRecord, mode: str) -> None:
    result_table = "titles" if mode == "titles" else "inventory"
    conn.execute(f"DELETE FROM {result_table} WHERE archive_name = ?", (record.archive_name,))
    conn.execute(
        """
        INSERT INTO archives (
            archive_name,
            archive_item,
            archive_url,
            size_bytes,
            year,
            issue_code,
            variant,
            status,
            error,
            started_at,
            finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL)
        ON CONFLICT(archive_name) DO UPDATE SET
            archive_item = excluded.archive_item,
            archive_url = excluded.archive_url,
            size_bytes = excluded.size_bytes,
            year = excluded.year,
            issue_code = excluded.issue_code,
            variant = excluded.variant,
            status = excluded.status,
            error = NULL,
            started_at = excluded.started_at,
            finished_at = NULL
        """,
        (
            record.archive_name,
            record.archive_item,
            record.archive_url,
            record.size_bytes,
            record.year,
            record.issue_code,
            record.variant,
            "in_progress",
            utc_now(),
        ),
    )
    conn.commit()


def mark_archive_finished(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    status: str,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE archives
        SET status = ?, error = ?, finished_at = ?
        WHERE archive_name = ?
        """,
        (status, error, utc_now(), record.archive_name),
    )
    conn.commit()


def insert_inventory_row(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    inner_container: str | None,
    mount_method: str | None,
    exe_path: str | None,
    exe_name: str | None,
    size_bytes: int | None,
    sha1: str | None,
    status: str,
    error: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO inventory (
            archive_item,
            archive_name,
            issue_code,
            year,
            variant,
            archive_url,
            inner_container,
            mount_method,
            exe_path,
            exe_name,
            size_bytes,
            sha1,
            status,
            error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.archive_item,
            record.archive_name,
            record.issue_code,
            record.year,
            record.variant,
            record.archive_url,
            inner_container,
            mount_method,
            exe_path,
            exe_name,
            size_bytes,
            sha1,
            status,
            error,
        ),
    )
    conn.commit()


def insert_title_row(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    inner_container: str | None,
    mount_method: str | None,
    source_kind: str | None,
    source_path: str | None,
    candidate_title: str | None,
    normalized_title: str | None,
    confidence: str | None,
    status: str,
    error: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO titles (
            archive_item,
            archive_name,
            issue_code,
            year,
            variant,
            archive_url,
            inner_container,
            mount_method,
            source_kind,
            source_path,
            candidate_title,
            normalized_title,
            confidence,
            status,
            error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.archive_item,
            record.archive_name,
            record.issue_code,
            record.year,
            record.variant,
            record.archive_url,
            inner_container,
            mount_method,
            source_kind,
            source_path,
            candidate_title,
            normalized_title,
            confidence,
            status,
            error,
        ),
    )
    conn.commit()


def strategy_cache_key(record: ArchiveRecord, strategy: str, *, issue_search_limit: int = 0) -> str:
    suffix = f":rows={issue_search_limit}" if issue_search_limit else ""
    return f"{strategy}:{record.archive_name}{suffix}"


def serialize_strategy_result(result: StrategyRunResult) -> str:
    return json.dumps(
        {
            "strategy": result.strategy,
            "structured": result.structured,
            "elapsed_ms": result.elapsed_ms,
            "error": result.error,
            "notes": result.notes,
            "candidates": [asdict(candidate) for candidate in result.candidates],
        },
        ensure_ascii=True,
        sort_keys=True,
    )


def deserialize_strategy_result(payload: str) -> StrategyRunResult:
    data = json.loads(payload)
    return StrategyRunResult(
        strategy=str(data["strategy"]),
        candidates=tuple(TitleCandidate(**candidate) for candidate in data.get("candidates", [])),
        structured=bool(data.get("structured", False)),
        elapsed_ms=int(data.get("elapsed_ms", 0)),
        error=data.get("error"),
        notes=str(data.get("notes", "")),
    )


def load_strategy_cache(conn: sqlite3.Connection, cache_key: str) -> StrategyRunResult | None:
    row = conn.execute(
        "SELECT payload_json FROM strategy_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return None
    return deserialize_strategy_result(str(row["payload_json"]))


def store_strategy_cache(conn: sqlite3.Connection, cache_key: str, archive_name: str, result: StrategyRunResult) -> None:
    conn.execute(
        """
        INSERT INTO strategy_cache (
            cache_key, strategy, archive_name, payload_json, structured, elapsed_ms, error, notes, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            strategy = excluded.strategy,
            archive_name = excluded.archive_name,
            payload_json = excluded.payload_json,
            structured = excluded.structured,
            elapsed_ms = excluded.elapsed_ms,
            error = excluded.error,
            notes = excluded.notes,
            fetched_at = excluded.fetched_at
        """,
        (
            cache_key,
            result.strategy,
            archive_name,
            serialize_strategy_result(result),
            1 if result.structured else 0,
            result.elapsed_ms,
            result.error,
            result.notes,
            utc_now(),
        ),
    )
    conn.commit()


def cached_strategy_result(
    conn: sqlite3.Connection,
    cache_key: str,
    archive_name: str,
    compute: Callable[[], StrategyRunResult],
) -> StrategyRunResult:
    cached = load_strategy_cache(conn, cache_key)
    if cached is not None:
        return cached
    result = compute()
    store_strategy_cache(conn, cache_key, archive_name, result)
    return result


def load_external_cache(conn: sqlite3.Connection, cache_key: str) -> tuple[str | None, str | None] | None:
    row = conn.execute(
        "SELECT payload, error FROM external_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return None
    return (row["payload"], row["error"])


def store_external_cache(
    conn: sqlite3.Connection,
    cache_key: str,
    cache_kind: str,
    source_url: str,
    payload: str | None,
    error: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO external_cache (cache_key, cache_kind, source_url, payload, error, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            cache_kind = excluded.cache_kind,
            source_url = excluded.source_url,
            payload = excluded.payload,
            error = excluded.error,
            fetched_at = excluded.fetched_at
        """,
        (cache_key, cache_kind, source_url, payload, error, utc_now()),
    )
    conn.commit()


def record_strategy_run(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    result: StrategyRunResult,
    *,
    union_title_count: int | None = None,
    recall_vs_union: float | None = None,
    unresolved: bool = False,
    benchmark_run_id: str | None = None,
    notes: str | None = None,
    candidate_count_override: int | None = None,
    unique_title_count_override: int | None = None,
) -> None:
    unique_titles = (
        unique_title_count_override
        if unique_title_count_override is not None
        else len({candidate.normalized_title for candidate in result.candidates})
    )
    candidate_count = candidate_count_override if candidate_count_override is not None else len(result.candidates)
    conn.execute(
        """
        INSERT INTO strategy_runs (
            archive_name, issue_code, strategy, elapsed_ms, candidate_count, unique_title_count,
            structured, unresolved, union_title_count, recall_vs_union, notes, benchmark_run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.archive_name,
            record.issue_code,
            result.strategy,
            result.elapsed_ms,
            candidate_count,
            unique_titles,
            1 if result.structured else 0,
            1 if unresolved else 0,
            union_title_count,
            recall_vs_union,
            notes if notes is not None else result.notes,
            benchmark_run_id,
            utc_now(),
        ),
    )
    conn.commit()


def record_issue_resolution(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    title_strategy: str,
    resolution_path: str,
    reason: str,
    unresolved: bool,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO issue_resolution (
            archive_name, archive_item, issue_code, year, variant, title_strategy,
            resolution_path, reason, unresolved, status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(archive_name) DO UPDATE SET
            archive_item = excluded.archive_item,
            issue_code = excluded.issue_code,
            year = excluded.year,
            variant = excluded.variant,
            title_strategy = excluded.title_strategy,
            resolution_path = excluded.resolution_path,
            reason = excluded.reason,
            unresolved = excluded.unresolved,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (
            record.archive_name,
            record.archive_item,
            record.issue_code,
            record.year,
            record.variant,
            title_strategy,
            resolution_path,
            reason,
            1 if unresolved else 0,
            status,
            utc_now(),
        ),
    )
    conn.commit()


def run_command(args: list[str], *, capture_output: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        args,
        check=False,
        capture_output=capture_output,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        stdout = result.stdout.decode("utf-8", "replace").strip()
        details = stderr or stdout or f"exit code {result.returncode}"
        raise CommandError(f"{' '.join(args)} failed: {details}")
    return result


def seven_zip_binary() -> str | None:
    for candidate in ("7zz", "7z"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def http_get_text(url: str) -> str:
    result = run_command(
        [
            "curl",
            "--http1.1",
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "5",
            "--retry-all-errors",
            "--retry-delay",
            "5",
            "-A",
            HTTP_USER_AGENT,
            url,
        ]
    )
    return result.stdout.decode("utf-8", "replace")


def fetch_cached_text(
    conn: sqlite3.Connection,
    *,
    cache_kind: str,
    cache_key: str,
    url: str,
) -> str:
    cached = load_external_cache(conn, cache_key)
    if cached is not None:
        payload, error = cached
        if error:
            raise CommandError(str(error))
        return str(payload or "")

    try:
        payload = http_get_text(url)
    except CommandError as exc:
        store_external_cache(conn, cache_key, cache_kind, url, None, str(exc))
        raise

    store_external_cache(conn, cache_key, cache_kind, url, payload, None)
    return payload


def download_archive(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    run_command(
        [
            "curl",
            "--http1.1",
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "5",
            "--retry-all-errors",
            "--retry-delay",
            "5",
            "-A",
            HTTP_USER_AGENT,
            "-C",
            "-",
            "--output",
            str(temp_path),
            url,
        ]
    )
    temp_path.replace(destination)


def archive_download_candidates(record: ArchiveRecord) -> list[tuple[str, str]]:
    parsed = urllib.parse.urlparse(record.archive_url)
    filename = urllib.parse.unquote(Path(parsed.path).name) or Path(record.archive_name).name
    return [(record.archive_url, filename)]


def download_record_archive(record: ArchiveRecord, download_dir: Path) -> tuple[Path, str]:
    download_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for url, filename in archive_download_candidates(record):
        archive_path = download_dir / filename
        try:
            download_archive(url, archive_path)
            return archive_path, url
        except CommandError as exc:
            errors.append(f"{url}: {exc}")
            archive_path.unlink(missing_ok=True)
            archive_path.with_suffix(archive_path.suffix + ".part").unlink(missing_ok=True)
    joined = " | ".join(errors) if errors else "no candidate URLs"
    raise CommandError(f"all archive downloads failed for {record.archive_name}: {joined}")


def list_archive_contents(archive_path: Path) -> list[str]:
    if shutil.which("lsar"):
        result = run_command(["lsar", "-jss", "-j", str(archive_path)])
        payload = json.loads(result.stdout.decode("utf-8", "replace"))
        entries: list[str] = []
        for item in payload.get("lsarContents", []):
            path = item.get("XADFileName")
            if path:
                entries.append(str(path))
        return entries
    return [entry["Path"] for entry in list_7z_entries(archive_path)]


def extract_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if shutil.which("unar"):
        run_command(
            [
                "unar",
                "-quiet",
                "-no-directory",
                "-no-recursion",
                "-no-quarantine",
                "-forks",
                "skip",
                "-output-directory",
                str(destination),
                str(archive_path),
            ]
        )
        return
    seven = seven_zip_binary()
    if seven is None:
        raise CommandError("No archive extractor available")
    run_command([seven, "x", "-y", f"-o{destination}", str(archive_path)])


def find_mount_candidates(root: Path) -> list[MountCandidate]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    selected: list[MountCandidate] = []
    consumed: set[Path] = set()

    def add_candidate(path: Path, extra_suffixes: tuple[str, ...] = ()) -> None:
        relative = path.relative_to(root).as_posix()
        selected.append(MountCandidate(path=path, inner_container=relative))
        consumed.add(path)
        for suffix in extra_suffixes:
            sibling = path.with_suffix(suffix)
            if sibling.exists():
                consumed.add(sibling)

    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".cue" and path not in consumed:
            add_candidate(path)
            for referenced_path in cue_referenced_files(path):
                if referenced_path.exists():
                    consumed.add(referenced_path)
        elif suffix == ".mds" and path not in consumed:
            add_candidate(path, extra_suffixes=(".mdf",))
        elif suffix == ".ccd" and path not in consumed:
            add_candidate(path, extra_suffixes=(".img", ".sub"))

    for path in files:
        suffix = path.suffix.lower()
        if path in consumed:
            continue
        if suffix in SINGLE_FILE_CONTAINER_EXTENSIONS:
            add_candidate(path)

    return selected


def parse_cue_data_track(cue_path: Path) -> CueDataTrack:
    current_file: str | None = None
    tracks: list[dict[str, object]] = []
    cue_text = cue_path.read_text(encoding="utf-8", errors="replace")

    for raw_line in cue_text.splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("REM"):
            continue

        file_match = re.match(r'^FILE\s+"(.+)"\s+(\S+)$', line, flags=re.IGNORECASE)
        if file_match:
            file_type = file_match.group(2).upper()
            if file_type != "BINARY":
                raise ValueError(f"Unsupported CUE file type: {file_type}")
            current_file = file_match.group(1)
            continue

        track_match = re.match(r"^TRACK\s+(\d+)\s+(\S+)$", line, flags=re.IGNORECASE)
        if track_match:
            if current_file is None:
                raise ValueError(f"TRACK before FILE in {cue_path}")
            tracks.append(
                {
                    "mode": track_match.group(2).upper(),
                    "file_name": current_file,
                    "index1": None,
                }
            )
            continue

        index_match = re.match(
            r"^INDEX\s+01\s+(\d{2}):(\d{2}):(\d{2})$",
            line,
            flags=re.IGNORECASE,
        )
        if index_match and tracks:
            minutes = int(index_match.group(1))
            seconds = int(index_match.group(2))
            frames = int(index_match.group(3))
            tracks[-1]["index1"] = minutes * 60 * 75 + seconds * 75 + frames

    data_track_index = None
    for index, track in enumerate(tracks):
        mode = str(track["mode"])
        if mode != "AUDIO" and track["index1"] is not None:
            data_track_index = index
            break

    if data_track_index is None:
        raise ValueError(f"No data track found in {cue_path}")

    track = tracks[data_track_index]
    end_sector = None
    if data_track_index + 1 < len(tracks):
        next_track = tracks[data_track_index + 1]
        if next_track["file_name"] == track["file_name"] and next_track["index1"] is not None:
            end_sector = int(next_track["index1"])

    return CueDataTrack(
        bin_path=cue_path.parent / str(track["file_name"]),
        mode=str(track["mode"]),
        start_sector=int(track["index1"]),
        end_sector=end_sector,
    )


def cue_referenced_files(cue_path: Path) -> set[Path]:
    referenced: set[Path] = set()
    cue_text = cue_path.read_text(encoding="utf-8", errors="replace")
    for raw_line in cue_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        file_match = re.match(r'^FILE\s+"(.+)"\s+(\S+)$', line, flags=re.IGNORECASE)
        if file_match:
            referenced.add(cue_path.parent / file_match.group(1))
    return referenced


def convert_cue_to_iso(cue_path: Path, destination: Path) -> Path:
    track = parse_cue_data_track(cue_path)
    mode = track.mode.upper()
    if mode == "MODE1/2352":
        sector_size = 2352
        data_offset = 16
        data_size = 2048
    elif mode == "MODE2/2352":
        sector_size = 2352
        data_offset = 24
        data_size = 2048
    elif mode in {"MODE1/2048", "MODE2/2048"}:
        sector_size = 2048
        data_offset = 0
        data_size = 2048
    else:
        raise ValueError(f"Unsupported CUE track mode: {track.mode}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_size = track.bin_path.stat().st_size
    start_offset = track.start_sector * sector_size
    if start_offset >= source_size:
        raise ValueError(f"CUE start sector is beyond end of BIN file: {cue_path}")

    if track.end_sector is not None and track.end_sector > track.start_sector:
        sectors_to_copy = track.end_sector - track.start_sector
    else:
        sectors_to_copy = (source_size - start_offset) // sector_size
    if sectors_to_copy <= 0:
        raise ValueError(f"No sectors available for data track in {cue_path}")

    with track.bin_path.open("rb") as source, destination.open("wb") as output:
        source.seek(start_offset)
        remaining = sectors_to_copy
        sectors_per_chunk = 256
        while remaining > 0:
            current = min(remaining, sectors_per_chunk)
            chunk = source.read(current * sector_size)
            if not chunk:
                break
            full_sectors = len(chunk) // sector_size
            if full_sectors == 0:
                break
            for sector_index in range(full_sectors):
                offset = sector_index * sector_size + data_offset
                output.write(chunk[offset : offset + data_size])
            remaining -= full_sectors

    return destination


def clean_title_fragment(value: str) -> str:
    text = Path(value).stem
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?i)(demo|setup|install|launcher|autorun|uninstall|patch)$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" '\"-_.,:/\\")
    return text


def normalize_title(value: str) -> str | None:
    text = clean_title_fragment(value)
    if not text:
        return None
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower().strip()
    text = re.sub(r"(?<=[a-z])\s+(?=\d{2,4}\b)", "", text)
    text = re.sub(r"(?<=\d)\s+(?=[a-z]\b)", "", text)
    if not text:
        return None
    words = [word for word in text.split() if word not in GENERIC_TITLE_WORDS]
    if not words:
        return None
    if len("".join(words)) < 3:
        return None
    return " ".join(words)


def is_noise_title(candidate_title: str, normalized_title: str | None) -> bool:
    if normalized_title is None:
        return True
    compact = normalized_title.replace(" ", "")
    if normalized_title in GENERIC_NORMALIZED_TITLES:
        return True
    if normalized_title.startswith("computer bild"):
        return True
    if compact in GENERIC_TITLE_SEGMENTS:
        return True
    if re.fullmatch(r"(cb|cbs)\d{3,4}[a-z]*", compact):
        return True
    return False


def infer_content_kind(text: str) -> str:
    for content_kind, pattern in TITLE_SECTION_PATTERNS.items():
        if pattern.search(text):
            return content_kind
    return "unknown"


def has_section_marker(text: str) -> bool:
    return any(pattern.search(text) for pattern in TITLE_SECTION_PATTERNS.values())


def make_title_candidate(
    *,
    source_kind: str,
    source_path: str,
    candidate_title: str,
    confidence: str,
    content_kind: str = "unknown",
) -> TitleCandidate | None:
    cleaned = clean_title_fragment(candidate_title)
    normalized = normalize_title(cleaned)
    if is_noise_title(cleaned, normalized):
        return None
    return TitleCandidate(
        source_kind=source_kind,
        source_path=source_path,
        candidate_title=cleaned,
        normalized_title=str(normalized),
        confidence=confidence,
        content_kind=content_kind,
    )


def choose_title_from_parts(parts: tuple[str, ...]) -> str | None:
    for part in reversed(parts):
        cleaned = clean_title_fragment(part)
        if not cleaned:
            continue
        normalized = normalize_title(cleaned)
        if is_noise_title(cleaned, normalized):
            continue
        return cleaned
    return None


def iter_metadata_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if len(relative_parts) > 3:
            continue
        if path.suffix.lower() not in TITLE_METADATA_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 128 * 1024:
                continue
        except OSError:
            continue
        yield path


def title_from_command_value(value: str) -> str | None:
    raw = value.strip().strip('"').split(",", 1)[0].strip()
    if not raw:
        return None
    if " " in raw and not raw.lower().endswith(".exe"):
        raw = raw.split()[0]
    cleaned = clean_title_fragment(raw)
    if normalize_title(cleaned) is None:
        return choose_title_from_parts(tuple(Path(raw).parts[:-1]))
    return cleaned


def html_to_text(text: str) -> str:
    cooked = re.sub(r"(?i)<br\s*/?>", "\n", text)
    cooked = re.sub(r"(?i)</?(div|p|li|ul|ol|h[1-6])[^>]*>", "\n", cooked)
    cooked = re.sub(r"<[^>]+>", " ", cooked)
    cooked = html.unescape(cooked)
    cooked = cooked.replace("\r", "\n")
    cooked = re.sub(r"\n{3,}", "\n\n", cooked)
    return cooked


def split_list_items(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    stripped = re.sub(r"^[\s*•\-]+", "", stripped)
    parts = re.split(r"\s*[•;]\s*|\s+\|\s+|\s+/\s+|\s+\*\s+|\s+-\s+", stripped)
    if len(parts) == 1 and stripped.count(",") >= 2:
        parts = [piece.strip() for piece in stripped.split(",")]
    return [piece.strip(" -*•\t") for piece in parts if piece.strip(" -*•\t")]


def dedupe_candidates(candidates: list[TitleCandidate]) -> list[TitleCandidate]:
    seen: set[tuple[str, str, str]] = set()
    ordered: list[TitleCandidate] = []
    for candidate in candidates:
        key = (candidate.source_kind, candidate.source_path, candidate.normalized_title)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def parse_text_candidates(
    text: str,
    *,
    source_kind: str,
    source_path: str,
    confidence: str,
) -> tuple[list[TitleCandidate], bool]:
    candidates: list[TitleCandidate] = []
    structured = False
    current_section = "unknown"
    in_section = False
    cooked = html_to_text(text)

    for raw_line in cooked.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            in_section = False
            current_section = "unknown"
            continue

        section_kind = infer_content_kind(stripped)
        if ":" in stripped and has_section_marker(stripped):
            header, tail = stripped.split(":", 1)
            current_section = infer_content_kind(header)
            in_section = True
            items = split_list_items(tail)
            if items:
                structured = True
            for item in items:
                candidate = make_title_candidate(
                    source_kind=source_kind,
                    source_path=source_path,
                    candidate_title=item,
                    confidence=confidence,
                    content_kind=current_section,
                )
                if candidate is not None:
                    candidates.append(candidate)
            continue

        if has_section_marker(stripped):
            current_section = section_kind
            in_section = True
            structured = True
            continue

        if in_section and (raw_line.lstrip().startswith(("-", "*", "•")) or len(stripped.split()) <= 8):
            structured = True
            for item in split_list_items(stripped):
                candidate = make_title_candidate(
                    source_kind=source_kind,
                    source_path=source_path,
                    candidate_title=item,
                    confidence=confidence,
                    content_kind=current_section,
                )
                if candidate is not None:
                    candidates.append(candidate)
            continue

        if not candidates and source_kind in {"archiveorg-title", "archiveorg-note", "redump-snippet", "redump-title"}:
            candidate = make_title_candidate(
                source_kind=source_kind,
                source_path=source_path,
                candidate_title=stripped,
                confidence=confidence,
                content_kind=current_section,
            )
            if candidate is not None:
                candidates.append(candidate)

    return dedupe_candidates(candidates), structured


def title_candidates_from_metadata_file(
    path: Path,
    root: Path,
    *,
    source_prefix: str = "disc",
) -> list[TitleCandidate]:
    candidates: list[TitleCandidate] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return candidates

    relative = path.relative_to(root).as_posix()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not value:
            continue
        if key in {"label", "title", "caption", "name"}:
            candidate = make_title_candidate(
                source_kind=f"{source_prefix}-metadata-value",
                source_path=relative,
                candidate_title=value,
                confidence="high",
                content_kind=infer_content_kind(value),
            )
            if candidate is not None:
                candidates.append(candidate)
        elif key in {"open", "icon", "exe", "run", "shell\\open\\command"}:
            title = title_from_command_value(value)
            if title is None:
                continue
            candidate = make_title_candidate(
                source_kind=f"{source_prefix}-metadata-command",
                source_path=relative,
                candidate_title=title,
                confidence="medium",
                content_kind=infer_content_kind(value),
            )
            if candidate is not None:
                candidates.append(candidate)
    return dedupe_candidates(candidates)


def title_candidates_from_exe_path(
    relative_path: Path,
    *,
    source_prefix: str = "disc",
) -> list[TitleCandidate]:
    candidates: list[TitleCandidate] = []
    source_path = relative_path.as_posix()
    seen: set[str] = set()

    parent_title = choose_title_from_parts(relative_path.parts[:-1])
    if parent_title is not None:
        candidate = make_title_candidate(
            source_kind=f"{source_prefix}-exe-parent",
            source_path=source_path,
            candidate_title=parent_title,
            confidence="high",
            content_kind=infer_content_kind(source_path),
        )
        if candidate is not None and candidate.normalized_title not in seen:
            candidates.append(candidate)
            seen.add(candidate.normalized_title)

    stem_title = clean_title_fragment(relative_path.stem)
    candidate = make_title_candidate(
        source_kind=f"{source_prefix}-exe-name",
        source_path=source_path,
        candidate_title=stem_title,
        confidence="medium",
        content_kind=infer_content_kind(source_path),
    )
    if candidate is not None and candidate.normalized_title not in seen:
        candidates.append(candidate)

    return dedupe_candidates(candidates)


def title_candidates_from_path_parts(
    relative_path: str,
    *,
    source_prefix: str,
    confidence: str,
) -> list[TitleCandidate]:
    path = Path(relative_path)
    title = choose_title_from_parts(path.parts)
    if title is None:
        return []
    candidate = make_title_candidate(
        source_kind=f"{source_prefix}-manifest-path",
        source_path=path.as_posix(),
        candidate_title=title,
        confidence=confidence,
        content_kind=infer_content_kind(relative_path),
    )
    return [] if candidate is None else [candidate]


def iter_executable_paths(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            continue
        if path.is_file() and path.suffix.lower() == ".exe":
            yield path


def list_7z_entries(archive_path: Path) -> list[dict[str, str]]:
    seven = seven_zip_binary()
    if seven is None:
        raise CommandError("7z is not available")
    result = run_command([seven, "l", "-slt", str(archive_path)])
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    archive_path_text = str(archive_path)
    for raw_line in result.stdout.decode("utf-8", "replace").splitlines():
        line = raw_line.strip()
        if not line:
            if current.get("Path") and current.get("Path") != archive_path_text and current.get("Folder") != "+":
                entries.append(current)
            current = {}
            continue
        if " = " in line:
            key, value = line.split(" = ", 1)
            current[key] = value
    if current.get("Path") and current.get("Path") != archive_path_text and current.get("Folder") != "+":
        entries.append(current)
    return entries


def extract_7z_members(archive_path: Path, destination: Path, members: list[str]) -> None:
    if not members:
        return
    seven = seven_zip_binary()
    if seven is None:
        raise CommandError("7z is not available")
    destination.mkdir(parents=True, exist_ok=True)
    run_command([seven, "x", "-y", f"-o{destination}", str(archive_path), *members])


def issue_month(record: ArchiveRecord) -> int:
    return int(record.issue_code[3:5])


def archiveorg_issue_queries(record: ArchiveRecord) -> list[str]:
    month = issue_month(record)
    short_year = record.year % 100
    queries = [
        f'"Computer Bild Spiele" "{record.issue_code}"',
        f'"Computer Bild Spiele" "{month:02d}/{record.year}"',
        f'"Computer Bild Spiele" "{month:02d}/{short_year:02d}"',
    ]
    if record.variant not in {"CD", "Standard"}:
        queries.append(f'"Computer Bild Spiele" "{month:02d}/{short_year:02d}" "{record.variant}"')
    ordered: list[str] = []
    seen: set[str] = set()
    for query in queries:
        if query not in seen:
            seen.add(query)
            ordered.append(query)
    return ordered


def archiveorg_search(
    conn: sqlite3.Connection,
    *,
    query: str,
    rows: int,
) -> list[dict[str, object]]:
    params = [
        ("q", query),
        ("rows", str(rows)),
        ("page", "1"),
        ("output", "json"),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "description"),
        ("fl[]", "subject"),
    ]
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params, doseq=True)
    cache_key = f"archiveorg-search:{query}:rows={rows}"
    payload = json.loads(
        fetch_cached_text(
            conn,
            cache_kind="archiveorg-search",
            cache_key=cache_key,
            url=url,
        )
    )
    return list(payload.get("response", {}).get("docs", []))


def archiveorg_metadata_json(conn: sqlite3.Connection, identifier: str) -> dict[str, object]:
    url = f"https://archive.org/metadata/{identifier}"
    cache_key = f"archiveorg-metadata:{identifier}"
    return json.loads(
        fetch_cached_text(
            conn,
            cache_kind="archiveorg-metadata",
            cache_key=cache_key,
            url=url,
        )
    )


def archiveorg_search_candidates(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    issue_search_limit: int,
) -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for query in archiveorg_issue_queries(record):
        for doc in archiveorg_search(conn, query=query, rows=issue_search_limit):
            identifier = str(doc.get("identifier", "")).strip()
            if not identifier or identifier in seen_ids:
                continue
            seen_ids.add(identifier)
            docs.append(doc)
            if len(docs) >= issue_search_limit:
                return docs
    return docs


def archiveorg_text_sidecars(metadata: dict[str, object]) -> list[str]:
    files = metadata.get("files", [])
    candidates: list[tuple[int, str]] = []
    for file_info in files if isinstance(files, list) else []:
        name = str(file_info.get("name", ""))
        if not name.lower().endswith(".txt"):
            continue
        size = int(file_info.get("size", "0") or 0)
        if size <= 0 or size > 5 * 1024 * 1024:
            continue
        if re.search(r"(?i)(djvu|ocr|text)\.txt$", name) or size < 512 * 1024:
            candidates.append((size, name))
    candidates.sort(key=lambda item: (item[0], item[1].lower()))
    return [name for _, name in candidates]


def list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def parse_archiveorg_subject_titles(
    values: list[str],
    *,
    source_path: str,
) -> StrategyRunResult:
    started = time.monotonic()
    candidates: list[TitleCandidate] = []
    for value in values:
        candidate = make_title_candidate(
            source_kind="archiveorg-subject",
            source_path=source_path,
            candidate_title=value,
            confidence="high",
            content_kind=infer_content_kind(value),
        )
        if candidate is not None:
            candidates.append(candidate)
    return StrategyRunResult(
        strategy="archive-metadata",
        candidates=tuple(dedupe_candidates(candidates)),
        structured=len(candidates) >= 2,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


def parse_archiveorg_text_field(
    text: str,
    *,
    source_kind: str,
    source_path: str,
    confidence: str,
) -> tuple[list[TitleCandidate], bool]:
    candidates, structured = parse_text_candidates(
        text,
        source_kind=source_kind,
        source_path=source_path,
        confidence=confidence,
    )
    return candidates, structured


def parse_archiveorg_metadata_payload(
    identifier: str,
    payload: dict[str, object],
) -> tuple[list[TitleCandidate], bool]:
    metadata = payload.get("metadata", payload)
    candidates: list[TitleCandidate] = []
    structured = False

    subjects = list_value(metadata.get("subject")) + list_value(metadata.get("topics"))
    subject_result = parse_archiveorg_subject_titles(subjects, source_path=f"{identifier}:subject")
    candidates.extend(subject_result.candidates)
    structured = structured or subject_result.structured

    for field_name, source_kind, confidence in (
        ("description", "archiveorg-description", "high"),
        ("notes", "archiveorg-note", "medium"),
        ("note", "archiveorg-note", "medium"),
        ("title", "archiveorg-title", "low"),
    ):
        for value in list_value(metadata.get(field_name)):
            field_candidates, field_structured = parse_archiveorg_text_field(
                value,
                source_kind=source_kind,
                source_path=f"{identifier}:{field_name}",
                confidence=confidence,
            )
            candidates.extend(field_candidates)
            structured = structured or field_structured

    return dedupe_candidates(candidates), structured


def fetch_archiveorg_ocr_text(
    conn: sqlite3.Connection,
    identifier: str,
    file_name: str,
) -> str:
    quoted_file = urllib.parse.quote(file_name)
    url = f"https://archive.org/download/{identifier}/{quoted_file}"
    cache_key = f"archiveorg-ocr:{identifier}:{file_name}"
    return fetch_cached_text(
        conn,
        cache_kind="archiveorg-ocr",
        cache_key=cache_key,
        url=url,
    )


def parse_redump_search_html(text: str) -> list[TitleCandidate]:
    cooked = html_to_text(text)
    candidates: list[TitleCandidate] = []
    for line in cooked.splitlines():
        stripped = line.strip()
        if "Computer Bild Spiele" not in stripped:
            continue
        piece = stripped.split("Computer Bild Spiele", 1)[-1].strip(" :-")
        if not piece:
            continue
        candidate = make_title_candidate(
            source_kind="redump-title",
            source_path="redump-search",
            candidate_title=piece,
            confidence="low",
            content_kind=infer_content_kind(piece),
        )
        if candidate is not None:
            candidates.append(candidate)
    return dedupe_candidates(candidates)


def vollversion_issue_url(record: ArchiveRecord) -> str | None:
    if record.year < 1999 or record.year > 2004:
        return None
    month = issue_month(record)
    return f"https://www.vollversion.de/ausgabe/computer-bild-spiele-{month:02d}-{record.year}.html"


def parse_vollversion_issue_html(text: str, *, source_path: str) -> tuple[list[TitleCandidate], bool]:
    candidates: list[TitleCandidate] = []
    structured = False

    table_match = re.search(
        r"Enthaltene Vollversionen:</p>\s*<table[^>]*>(.*?)</table>",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if table_match:
        structured = True
        for title in re.findall(r'<td>\s*<a[^>]+/programm/[^"]+"[^>]*>([^<]+)</a>', table_match.group(1), re.IGNORECASE):
            candidate = make_title_candidate(
                source_kind="vollversion-fullversion",
                source_path=source_path,
                candidate_title=html.unescape(title),
                confidence="high",
                content_kind="full_version",
            )
            if candidate is not None:
                candidates.append(candidate)

    return dedupe_candidates(candidates), structured


def run_vollversion_strategy(conn: sqlite3.Connection, record: ArchiveRecord) -> StrategyRunResult:
    cache_key = strategy_cache_key(record, "vollversion")

    def compute() -> StrategyRunResult:
        started = time.monotonic()
        url = vollversion_issue_url(record)
        if url is None:
            return StrategyRunResult(
                strategy="vollversion",
                candidates=tuple(),
                structured=False,
                elapsed_ms=0,
                notes="unsupported year",
            )
        try:
            text = fetch_cached_text(
                conn,
                cache_kind="vollversion-issue",
                cache_key=f"vollversion:{record.issue_code}",
                url=url,
            )
            candidates, structured = parse_vollversion_issue_html(text, source_path=url)
            return StrategyRunResult(
                strategy="vollversion",
                candidates=tuple(candidates),
                structured=structured,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:
            return StrategyRunResult(
                strategy="vollversion",
                candidates=tuple(),
                structured=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
            )

    return cached_strategy_result(conn, cache_key, record.archive_name, compute)


def run_archive_metadata_strategy(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    issue_search_limit: int,
) -> StrategyRunResult:
    cache_key = strategy_cache_key(record, "archive-metadata", issue_search_limit=issue_search_limit)

    def compute() -> StrategyRunResult:
        started = time.monotonic()
        try:
            docs = archiveorg_search_candidates(conn, record, issue_search_limit=issue_search_limit)
            candidates: list[TitleCandidate] = []
            structured = False
            for doc in docs:
                identifier = str(doc.get("identifier", "")).strip()
                if not identifier:
                    continue
                payload = archiveorg_metadata_json(conn, identifier)
                field_candidates, field_structured = parse_archiveorg_metadata_payload(identifier, payload)
                candidates.extend(field_candidates)
                structured = structured or field_structured
            return StrategyRunResult(
                strategy="archive-metadata",
                candidates=tuple(dedupe_candidates(candidates)),
                structured=structured,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                notes=f"docs={len(docs)}",
            )
        except Exception as exc:
            return StrategyRunResult(
                strategy="archive-metadata",
                candidates=tuple(),
                structured=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
            )

    return cached_strategy_result(conn, cache_key, record.archive_name, compute)


def run_archive_ocr_strategy(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    issue_search_limit: int,
) -> StrategyRunResult:
    cache_key = strategy_cache_key(record, "archive-ocr", issue_search_limit=issue_search_limit)

    def compute() -> StrategyRunResult:
        started = time.monotonic()
        try:
            docs = archiveorg_search_candidates(conn, record, issue_search_limit=issue_search_limit)
            candidates: list[TitleCandidate] = []
            structured = False
            file_count = 0
            for doc in docs:
                identifier = str(doc.get("identifier", "")).strip()
                if not identifier:
                    continue
                payload = archiveorg_metadata_json(conn, identifier)
                for file_name in archiveorg_text_sidecars(payload)[:2]:
                    file_count += 1
                    text = fetch_archiveorg_ocr_text(conn, identifier, file_name)
                    parsed, parsed_structured = parse_text_candidates(
                        text,
                        source_kind="archiveorg-ocr",
                        source_path=f"{identifier}:{file_name}",
                        confidence="high",
                    )
                    candidates.extend(parsed)
                    structured = structured or parsed_structured
            return StrategyRunResult(
                strategy="archive-ocr",
                candidates=tuple(dedupe_candidates(candidates)),
                structured=structured,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                notes=f"files={file_count}",
            )
        except Exception as exc:
            return StrategyRunResult(
                strategy="archive-ocr",
                candidates=tuple(),
                structured=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
            )

    return cached_strategy_result(conn, cache_key, record.archive_name, compute)


def run_redump_strategy(conn: sqlite3.Connection, record: ArchiveRecord) -> StrategyRunResult:
    cache_key = strategy_cache_key(record, "redump")

    def compute() -> StrategyRunResult:
        started = time.monotonic()
        query = urllib.parse.quote(f"Computer Bild Spiele {record.issue_code}")
        url = f"https://redump.org/discs/quicksearch/{query}"
        try:
            text = fetch_cached_text(
                conn,
                cache_kind="redump-search",
                cache_key=f"redump:{record.issue_code}",
                url=url,
            )
            candidates = parse_redump_search_html(text)
            return StrategyRunResult(
                strategy="redump",
                candidates=tuple(candidates),
                structured=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:
            return StrategyRunResult(
                strategy="redump",
                candidates=tuple(),
                structured=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
            )

    return cached_strategy_result(conn, cache_key, record.archive_name, compute)


def merge_strategy_candidates(results: list[StrategyRunResult]) -> list[TitleCandidate]:
    merged: list[TitleCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        for candidate in result.candidates:
            key = (candidate.normalized_title, candidate.source_kind, candidate.source_path)
            if key in seen:
                continue
            seen.add(key)
            merged.append(candidate)
    merged.sort(
        key=lambda candidate: (
            candidate.normalized_title,
            -SOURCE_KIND_RANKS.get(candidate.source_kind, 0),
            -CONFIDENCE_RANKS.get(candidate.confidence, 0),
            candidate.source_path,
        )
    )
    return merged


def cheap_results_sufficient(results: list[StrategyRunResult]) -> tuple[bool, str]:
    cheap_candidates = merge_strategy_candidates(results)
    unique_titles = {candidate.normalized_title for candidate in cheap_candidates}
    structured_sources = {
        result.strategy
        for result in results
        if result.structured and result.candidates
    }
    title_to_strategies: dict[str, set[str]] = {}
    for result in results:
        for candidate in result.candidates:
            title_to_strategies.setdefault(candidate.normalized_title, set()).add(result.strategy)
    agreed_titles = sum(1 for strategies in title_to_strategies.values() if len(strategies) >= 2)
    vollversion_result = next((result for result in results if result.strategy == "vollversion"), None)

    if vollversion_result is not None and vollversion_result.structured and vollversion_result.candidates:
        return True, "vollversion structured issue page"
    if len(unique_titles) >= 3 and structured_sources:
        return True, "structured external list"
    if len(unique_titles) >= 3 and agreed_titles >= 2:
        return True, "multiple cheap strategies agree"
    return False, "cheap sources incomplete"


def sha1_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha1()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def iter_quick_metadata_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if len(relative_parts) > 2:
            continue
        if path.suffix.lower() not in TITLE_METADATA_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 128 * 1024:
                continue
        except OSError:
            continue
        yield path


def persist_title_candidates(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    inner_container: str | None,
    mount_method: str | None,
    candidates: list[TitleCandidate],
) -> None:
    existing = {
        (
            str(row["source_kind"] or ""),
            str(row["source_path"] or ""),
            str(row["normalized_title"] or ""),
        )
        for row in conn.execute(
            """
            SELECT source_kind, source_path, normalized_title
            FROM titles
            WHERE archive_name = ?
            """,
            (record.archive_name,),
        )
    }
    for candidate in candidates:
        key = (candidate.source_kind, candidate.source_path, candidate.normalized_title)
        if key in existing:
            continue
        existing.add(key)
        insert_title_row(
            conn,
            record,
            inner_container=inner_container,
            mount_method=mount_method,
            source_kind=candidate.source_kind,
            source_path=candidate.source_path,
            candidate_title=candidate.candidate_title,
            normalized_title=candidate.normalized_title,
            confidence=candidate.confidence,
            status="ok",
            error=None,
        )


def collect_quick_title_candidates(
    root: Path,
    *,
    source_prefix: str = "disc",
) -> list[TitleCandidate]:
    candidates: list[TitleCandidate] = []
    for path in sorted(root.iterdir()):
        if path.name.startswith("."):
            continue
        relative = path.relative_to(root).as_posix()
        candidates.extend(
            title_candidates_from_path_parts(
                relative,
                source_prefix=source_prefix,
                confidence="medium",
            )
        )
        if path.is_dir() and path.name.lower() in {"demo", "demos", "vollv", "bonus", "extras", "games", "spiele"}:
            for child in sorted(path.iterdir()):
                if child.name.startswith("."):
                    continue
                candidates.extend(
                    title_candidates_from_path_parts(
                        child.relative_to(root).as_posix(),
                        source_prefix=source_prefix,
                        confidence="high",
                    )
                )

    for metadata_path in iter_quick_metadata_files(root):
        candidates.extend(title_candidates_from_metadata_file(metadata_path, root, source_prefix=source_prefix))

    return dedupe_candidates(candidates)


def collect_full_title_candidates(
    root: Path,
    *,
    source_prefix: str = "disc",
) -> list[TitleCandidate]:
    candidates = collect_quick_title_candidates(root, source_prefix=source_prefix)
    for exe_path in iter_executable_paths(root):
        relative = exe_path.relative_to(root)
        candidates.extend(title_candidates_from_exe_path(relative, source_prefix=source_prefix))
    return dedupe_candidates(candidates)


def scan_title_tree(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    root: Path,
    inner_container: str,
    mount_method: str,
) -> int:
    candidates = collect_full_title_candidates(root)
    persist_title_candidates(
        conn,
        record,
        inner_container=inner_container,
        mount_method=mount_method,
        candidates=candidates,
    )
    return len(candidates)


def scan_quick_title_tree(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    root: Path,
    inner_container: str,
    mount_method: str,
) -> int:
    candidates = collect_quick_title_candidates(root)
    persist_title_candidates(
        conn,
        record,
        inner_container=inner_container,
        mount_method=mount_method,
        candidates=candidates,
    )
    return len(candidates)


def image_path_for_7z(candidate: MountCandidate, generated_root: Path) -> tuple[Path, str]:
    suffix = candidate.path.suffix.lower()
    if suffix == ".cue":
        generated_iso = generated_root / f"{candidate.path.stem}.iso"
        return convert_cue_to_iso(candidate.path, generated_iso), "7z+cue2iso"
    if suffix == ".mds":
        sibling = candidate.path.with_suffix(".mdf")
        if sibling.exists():
            return sibling, "7z+mdf"
    if suffix == ".ccd":
        sibling = candidate.path.with_suffix(".img")
        if sibling.exists():
            return sibling, "7z+img"
    return candidate.path, "7z"


def collect_image_title_candidates_7z(
    candidate: MountCandidate,
    generated_root: Path,
    *,
    quick_only: bool,
) -> tuple[list[TitleCandidate], str]:
    image_path, method = image_path_for_7z(candidate, generated_root)
    entries = list_7z_entries(image_path)
    candidates: list[TitleCandidate] = []

    top_levels: set[str] = set()
    second_levels: set[str] = set()
    metadata_members: list[str] = []
    exe_paths: list[Path] = []
    for entry in entries:
        path_text = entry["Path"]
        path = Path(path_text)
        if not path.parts:
            continue
        top_levels.add(path.parts[0])
        if len(path.parts) >= 2 and path.parts[0].lower() in {"demo", "demos", "vollv", "bonus", "extras", "games", "spiele"}:
            second_levels.add("/".join(path.parts[:2]))
        if path.suffix.lower() in TITLE_METADATA_SUFFIXES:
            if quick_only and len(path.parts) <= 2:
                metadata_members.append(path_text)
            elif not quick_only and len(path.parts) <= 3:
                metadata_members.append(path_text)
        if not quick_only and path.suffix.lower() == ".exe":
            exe_paths.append(path)

    for relative in sorted(top_levels):
        candidates.extend(title_candidates_from_path_parts(relative, source_prefix="disc", confidence="medium"))
    for relative in sorted(second_levels):
        candidates.extend(title_candidates_from_path_parts(relative, source_prefix="disc", confidence="high"))
    for relative in [candidate.inner_container]:
        candidates.extend(title_candidates_from_path_parts(relative, source_prefix="disc", confidence="low"))

    extract_root = generated_root / f"{candidate.path.stem}-7z-listing"
    extract_7z_members(image_path, extract_root, metadata_members)
    for metadata_path in iter_metadata_files(extract_root if not quick_only else extract_root):
        candidates.extend(title_candidates_from_metadata_file(metadata_path, extract_root, source_prefix="disc"))
    for exe_path in exe_paths:
        candidates.extend(title_candidates_from_exe_path(exe_path, source_prefix="disc"))

    return dedupe_candidates(candidates), method


def attach_image(image_path: Path, mount_root: Path) -> AttachedImage:
    mount_root.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            "hdiutil",
            "attach",
            "-readonly",
            "-noautoopen",
            "-noautofsck",
            "-mountroot",
            str(mount_root),
            "-plist",
            str(image_path),
        ]
    )
    payload = plistlib.loads(result.stdout)
    devices: list[str] = []
    mount_points: list[Path] = []
    for entity in payload.get("system-entities", []):
        dev_entry = entity.get("dev-entry")
        if dev_entry:
            devices.append(str(dev_entry))
        mount_point = entity.get("mount-point")
        if mount_point:
            mount_points.append(Path(str(mount_point)))
    if not mount_points:
        if devices:
            detach_image(AttachedImage(tuple(devices), tuple()))
        raise CommandError(f"No mount points exposed by {image_path}")
    return AttachedImage(tuple(devices), tuple(mount_points))


def detach_image(attachment: AttachedImage) -> None:
    targets = sorted(set(attachment.devices), key=len)
    targets.extend(str(path) for path in attachment.mount_points if str(path) not in targets)
    last_error: Exception | None = None
    for target in targets:
        try:
            run_command(["hdiutil", "detach", target])
            return
        except Exception as exc:  # pragma: no cover - only hit on system failure
            last_error = exc
    if last_error is not None:
        raise last_error


@contextmanager
def mounted_image(image_path: Path, mount_root: Path) -> Iterator[AttachedImage]:
    attachment = attach_image(image_path, mount_root)
    try:
        yield attachment
    finally:
        detach_image(attachment)


@contextmanager
def mounted_candidate(
    candidate: MountCandidate,
    mount_root: Path,
    generated_root: Path,
) -> Iterator[tuple[AttachedImage, str]]:
    try:
        with mounted_image(candidate.path, mount_root) as attachment:
            yield attachment, "hdiutil"
        return
    except CommandError as direct_error:
        if candidate.path.suffix.lower() != ".cue":
            raise
        generated_iso = generated_root / f"{candidate.path.stem}.iso"
        try:
            convert_cue_to_iso(candidate.path, generated_iso)
        except Exception as conversion_error:
            raise CommandError(
                f"{direct_error}; CUE conversion failed: {conversion_error}"
            ) from conversion_error
        with mounted_image(generated_iso, mount_root) as attachment:
            yield attachment, "hdiutil+cue2iso"


def record_failure(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    mode: str,
    inner_container: str | None,
    mount_method: str | None,
    status: str,
    error: str,
) -> None:
    if mode == "titles":
        insert_title_row(
            conn,
            record,
            inner_container=inner_container,
            mount_method=mount_method,
            source_kind=None,
            source_path=None,
            candidate_title=None,
            normalized_title=None,
            confidence=None,
            status=status,
            error=error,
        )
        return

    insert_inventory_row(
        conn,
        record,
        inner_container=inner_container,
        mount_method=mount_method,
        exe_path=None,
        exe_name=None,
        size_bytes=None,
        sha1=None,
        status=status,
        error=error,
    )


def scan_executable_tree(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    *,
    root: Path,
    inner_container: str,
    mount_method: str,
) -> tuple[int, bool]:
    found = 0
    hash_failed = False
    for exe_path in iter_executable_paths(root):
        relative = exe_path.relative_to(root).as_posix()
        try:
            size_bytes, sha1_value = sha1_file(exe_path)
            insert_inventory_row(
                conn,
                record,
                inner_container=inner_container,
                mount_method=mount_method,
                exe_path=relative,
                exe_name=exe_path.name,
                size_bytes=size_bytes,
                sha1=sha1_value,
                status="ok",
                error=None,
            )
        except OSError as exc:
            hash_failed = True
            insert_inventory_row(
                conn,
                record,
                inner_container=inner_container,
                mount_method=mount_method,
                exe_path=relative,
                exe_name=exe_path.name,
                size_bytes=None,
                sha1=None,
                status="hash_failed",
                error=str(exc),
            )
        found += 1
    return found, hash_failed


def process_downloaded_archive(
    record: ArchiveRecord,
    archive_path: Path,
    conn: sqlite3.Connection,
    tmp_root: Path,
    mode: str,
    title_scan_mode: str = "full",
) -> tuple[str, str | None]:
    status = "ok"
    errors: list[str] = []
    cleanup_error: str | None = None
    workspace = tmp_root / f"{sanitize_name(record.issue_code)}-{uuid.uuid4().hex[:8]}"
    extracted_root = workspace / "extracted"
    generated_root = workspace / "generated"
    mount_root = workspace / "mounts"
    workspace.mkdir(parents=True, exist_ok=True)

    try:
        list_archive_contents(archive_path)
        extract_archive(archive_path, extracted_root)

        if mode == "titles":
            title_scanner = scan_quick_title_tree if title_scan_mode == "quick" else scan_title_tree
            direct_found = title_scanner(
                conn,
                record,
                root=extracted_root,
                inner_container="archive-root",
                mount_method="direct",
            )
            direct_hash_failed = False
        else:
            direct_found, direct_hash_failed = scan_executable_tree(
                conn,
                record,
                root=extracted_root,
                inner_container="archive-root",
                mount_method="direct",
            )
            if direct_hash_failed:
                status = "hash_failed"
                errors.append("Failed to hash one or more executables in archive-root")

        candidates = find_mount_candidates(extracted_root)
        if not candidates and direct_found == 0:
            status = "mount_failed"
            errors.append("No mountable inner container found")

        for candidate in candidates:
            try:
                if mode == "titles" and seven_zip_binary() and not shutil.which("hdiutil"):
                    title_candidates, mount_method = collect_image_title_candidates_7z(
                        candidate,
                        generated_root,
                        quick_only=(title_scan_mode == "quick"),
                    )
                    persist_title_candidates(
                        conn,
                        record,
                        inner_container=candidate.inner_container,
                        mount_method=mount_method,
                        candidates=title_candidates,
                    )
                    mounted_found = len(title_candidates)
                    mounted_hash_failed = False
                else:
                    with mounted_candidate(candidate, mount_root, generated_root) as (attachment, mount_method):
                        mounted_found = 0
                        mounted_hash_failed = False
                        for mount_point in attachment.mount_points:
                            if mode == "titles":
                                title_scanner = scan_quick_title_tree if title_scan_mode == "quick" else scan_title_tree
                                count = title_scanner(
                                    conn,
                                    record,
                                    root=mount_point,
                                    inner_container=candidate.inner_container,
                                    mount_method=mount_method,
                                )
                                failed = False
                            else:
                                count, failed = scan_executable_tree(
                                    conn,
                                    record,
                                    root=mount_point,
                                    inner_container=candidate.inner_container,
                                    mount_method=mount_method,
                                )
                            mounted_found += count
                            mounted_hash_failed = mounted_hash_failed or failed
                        if mode != "titles" and mounted_hash_failed and status == "ok":
                            status = "hash_failed"
                        if mode != "titles" and mounted_hash_failed:
                            errors.append(
                                f"Failed to hash one or more executables in {candidate.inner_container}"
                            )
            except Exception as exc:
                if status == "ok":
                    status = "mount_failed"
                errors.append(f"{candidate.inner_container}: {exc}")
                record_failure(
                    conn,
                    record,
                    mode=mode,
                    inner_container=candidate.inner_container,
                    mount_method="hdiutil",
                    status="mount_failed",
                    error=str(exc),
                )
    finally:
        try:
            shutil.rmtree(workspace)
        except OSError as exc:
            cleanup_error = str(exc)

    if cleanup_error is not None:
        if status == "ok":
            status = "mount_failed"
        errors.append(f"cleanup failed: {cleanup_error}")

    error_text = "; ".join(dict.fromkeys(errors)) or None
    return status, error_text


def process_archive(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    tmp_root: Path,
    mode: str,
) -> None:
    mark_archive_started(conn, record, mode)
    download_dir = tmp_root / "downloads"
    try:
        archive_path, _downloaded_url = download_record_archive(record, download_dir)
    except (OSError, urllib.error.URLError) as exc:
        record_failure(
            conn,
            record,
            mode=mode,
            inner_container=None,
            mount_method=None,
            status="download_failed",
            error=str(exc),
        )
        mark_archive_finished(conn, record, "download_failed", str(exc))
        return
    except CommandError as exc:
        record_failure(
            conn,
            record,
            mode=mode,
            inner_container=None,
            mount_method=None,
            status="download_failed",
            error=str(exc),
        )
        mark_archive_finished(conn, record, "download_failed", str(exc))
        return

    try:
        status, error = process_downloaded_archive(record, archive_path, conn, tmp_root, mode)
        mark_archive_finished(conn, record, status, error)
    except CommandError as exc:
        record_failure(
            conn,
            record,
            mode=mode,
            inner_container=None,
            mount_method=None,
            status="extract_failed",
            error=str(exc),
        )
        mark_archive_finished(conn, record, "extract_failed", str(exc))
    except Exception as exc:
        record_failure(
            conn,
            record,
            mode=mode,
            inner_container=None,
            mount_method=None,
            status="extract_failed",
            error=str(exc),
        )
        mark_archive_finished(conn, record, "extract_failed", str(exc))
    finally:
        archive_path.unlink(missing_ok=True)


def persist_strategy_result_titles(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    result: StrategyRunResult,
) -> None:
    persist_title_candidates(
        conn,
        record,
        inner_container=None,
        mount_method=None,
        candidates=list(result.candidates),
    )


def issue_title_rows(conn: sqlite3.Connection, archive_name: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT candidate_title, normalized_title, source_kind, source_path, confidence
            FROM titles
            WHERE archive_name = ? AND status = 'ok' AND normalized_title IS NOT NULL
            ORDER BY normalized_title, source_kind, source_path
            """,
            (archive_name,),
        )
    )


def issue_title_candidates(conn: sqlite3.Connection, archive_name: str) -> list[TitleCandidate]:
    rows = issue_title_rows(conn, archive_name)
    return [
        TitleCandidate(
            source_kind=str(row["source_kind"]),
            source_path=str(row["source_path"]),
            candidate_title=str(row["candidate_title"]),
            normalized_title=str(row["normalized_title"]),
            confidence=str(row["confidence"]),
        )
        for row in rows
    ]


def candidates_look_sufficient(candidates: list[TitleCandidate]) -> bool:
    unique_titles = {candidate.normalized_title for candidate in candidates}
    structured = any(
        candidate.source_kind in {
            "vollversion-fullversion",
            "vollversion-description",
            "archiveorg-ocr",
            "archiveorg-description",
            "archiveorg-subject",
            "disc-metadata-value",
            "disc-metadata-command",
        }
        for candidate in candidates
    )
    if any(candidate.source_kind == "vollversion-fullversion" for candidate in candidates):
        return True
    if len(unique_titles) >= 3 and structured:
        return True
    if len(unique_titles) >= 4:
        return True
    if len(unique_titles) >= 2 and structured:
        return True
    return False


def run_external_title_strategies(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    args: argparse.Namespace,
) -> list[StrategyRunResult]:
    results = [run_vollversion_strategy(conn, record), run_archive_metadata_strategy(conn, record, issue_search_limit=args.issue_search_limit)]
    if args.use_archive_ocr:
        results.append(run_archive_ocr_strategy(conn, record, issue_search_limit=args.issue_search_limit))
    if args.use_redump:
        results.append(run_redump_strategy(conn, record))

    for result in results:
        persist_strategy_result_titles(conn, record, result)
        record_strategy_run(
            conn,
            record,
            result,
            unresolved=len({candidate.normalized_title for candidate in result.candidates}) == 0,
        )
    return results


def run_disc_title_strategy(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    tmp_root: Path,
    *,
    title_scan_mode: str,
    archive_path: Path | None = None,
) -> tuple[str, str | None]:
    ensure_disc_tools()
    owned_archive = archive_path is None
    if archive_path is None:
        download_dir = tmp_root / "downloads"
        archive_path, _downloaded_url = download_record_archive(record, download_dir)
    try:
        return process_downloaded_archive(
            record,
            archive_path,
            conn,
            tmp_root,
            "titles",
            title_scan_mode=title_scan_mode,
        )
    finally:
        if owned_archive:
            archive_path.unlink(missing_ok=True)


def process_title_issue(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    tmp_root: Path,
    args: argparse.Namespace,
) -> None:
    mark_archive_started(conn, record, "titles")
    resolution_steps: list[str] = []
    reason = ""
    unresolved = False
    status = "ok"

    try:
        cheap_results: list[StrategyRunResult] = []
        cheap_sufficient = False
        if args.title_strategy != "disc-only":
            cheap_results = run_external_title_strategies(conn, record, args)
            cheap_sufficient, reason = cheap_results_sufficient(cheap_results)
            resolution_steps.extend(result.strategy for result in cheap_results if result.candidates)

            if args.title_strategy == "external-only":
                unresolved = not cheap_sufficient
                if unresolved and not reason:
                    reason = "external sources insufficient"
                record_issue_resolution(
                    conn,
                    record,
                    title_strategy=args.title_strategy,
                    resolution_path=">".join(resolution_steps) or "external",
                    reason=reason or "external-only",
                    unresolved=unresolved,
                    status="ok",
                )
                mark_archive_finished(conn, record, "ok", None)
                return

            if cheap_sufficient and not args.force_disc and not args.validate_disc:
                record_issue_resolution(
                    conn,
                    record,
                    title_strategy=args.title_strategy,
                    resolution_path=">".join(resolution_steps) or "external",
                    reason=reason or "cheap sources sufficient",
                    unresolved=False,
                    status="ok",
                )
                mark_archive_finished(conn, record, "ok", None)
                return

        disc_used = False
        disc_quick_status = "ok"
        disc_quick_error: str | None = None
        if args.title_strategy in {"disc-only", "auto"} or args.force_disc or args.validate_disc:
            disc_used = True
            download_dir = tmp_root / "downloads"
            archive_path, _downloaded_url = download_record_archive(record, download_dir)
            try:
                disc_quick_status, disc_quick_error = run_disc_title_strategy(
                    conn,
                    record,
                    tmp_root,
                    title_scan_mode="quick",
                    archive_path=archive_path,
                )
                resolution_steps.append("disc-quick")
                if disc_quick_status != "ok":
                    status = disc_quick_status
                quick_candidates = issue_title_candidates(conn, record.archive_name)
                needs_full = (
                    args.title_strategy == "disc-only"
                    or args.validate_disc
                    or not candidates_look_sufficient(quick_candidates)
                )
                if needs_full:
                    full_status, full_error = run_disc_title_strategy(
                        conn,
                        record,
                        tmp_root,
                        title_scan_mode="full",
                        archive_path=archive_path,
                    )
                    resolution_steps.append("disc-full")
                    if full_status != "ok":
                        status = full_status
                    if full_error:
                        reason = full_error
                elif disc_quick_error and not reason:
                    reason = disc_quick_error
            finally:
                archive_path.unlink(missing_ok=True)

        final_candidates = issue_title_candidates(conn, record.archive_name)
        unresolved = not candidates_look_sufficient(final_candidates)
        if unresolved and not reason:
            reason = "insufficient titles after resolution path"
        record_issue_resolution(
            conn,
            record,
            title_strategy=args.title_strategy,
            resolution_path=">".join(resolution_steps) or "none",
            reason=reason or ("disc used" if disc_used else "cheap sources sufficient"),
            unresolved=unresolved,
            status=status,
        )
        mark_archive_finished(conn, record, status, None if status == "ok" else reason)
    except CommandError as exc:
        record_failure(
            conn,
            record,
            mode="titles",
            inner_container=None,
            mount_method=None,
            status="extract_failed",
            error=str(exc),
        )
        record_issue_resolution(
            conn,
            record,
            title_strategy=args.title_strategy,
            resolution_path=">".join(resolution_steps) or "none",
            reason=str(exc),
            unresolved=True,
            status="extract_failed",
        )
        mark_archive_finished(conn, record, "extract_failed", str(exc))
    except Exception as exc:
        record_failure(
            conn,
            record,
            mode="titles",
            inner_container=None,
            mount_method=None,
            status="extract_failed",
            error=str(exc),
        )
        record_issue_resolution(
            conn,
            record,
            title_strategy=args.title_strategy,
            resolution_path=">".join(resolution_steps) or "none",
            reason=str(exc),
            unresolved=True,
            status="extract_failed",
        )
        mark_archive_finished(conn, record, "extract_failed", str(exc))


def export_exe_csvs(conn: sqlite3.Connection, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "all_executables.csv"
    dedup_path = out_dir / "executables_dedup.csv"

    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS, lineterminator="\n")
        writer.writeheader()
        rows = conn.execute(
            """
            SELECT archive_item, archive_name, issue_code, year, variant, archive_url,
                   inner_container, mount_method, exe_path, exe_name, size_bytes,
                   sha1, status, error
            FROM inventory
            ORDER BY archive_name, COALESCE(inner_container, ''), COALESCE(exe_path, '')
            """
        )
        for row in rows:
            writer.writerow({column: row[column] if row[column] is not None else "" for column in RAW_COLUMNS})

    grouped: dict[str, dict[str, object]] = {}
    rows = conn.execute(
        """
        SELECT sha1, exe_name, size_bytes, issue_code, year, archive_name
        FROM inventory
        WHERE status = 'ok' AND sha1 IS NOT NULL
        ORDER BY year, archive_name, COALESCE(inner_container, ''), COALESCE(exe_path, '')
        """
    )
    for row in rows:
        sha1_value = str(row["sha1"])
        current = grouped.get(sha1_value)
        if current is None:
            grouped[sha1_value] = {
                "sha1": sha1_value,
                "exe_name": row["exe_name"],
                "size_bytes": row["size_bytes"],
                "first_seen_issue": row["issue_code"],
                "occurrence_count": 1,
            }
            continue
        current["occurrence_count"] = int(current["occurrence_count"]) + 1

    ordered_rows = sorted(
        grouped.values(),
        key=lambda row: (
            str(row["first_seen_issue"]),
            str(row["exe_name"]).lower(),
            str(row["sha1"]),
        ),
    )
    with dedup_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEDUP_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in ordered_rows:
            writer.writerow(row)


def export_title_csvs(conn: sqlite3.Connection, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "all_title_candidates.csv"
    dedup_path = out_dir / "titles_dedup.csv"
    master_path = out_dir / "master_games.csv"
    issue_titles_path = out_dir / "issue_titles.csv"
    unresolved_path = out_dir / "unresolved_issues.csv"
    benchmark_path = out_dir / "strategy_benchmark.csv"

    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TITLE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        rows = conn.execute(
            """
            SELECT archive_item, archive_name, issue_code, year, variant, archive_url,
                   inner_container, mount_method, source_kind, source_path, candidate_title,
                   normalized_title, confidence, status, error
            FROM titles
            ORDER BY archive_name, COALESCE(inner_container, ''), COALESCE(source_path, ''), COALESCE(normalized_title, '')
            """
        )
        for row in rows:
            writer.writerow({column: row[column] if row[column] is not None else "" for column in TITLE_COLUMNS})

    grouped: dict[str, dict[str, object]] = {}
    issue_sets: dict[str, set[str]] = {}
    source_kind_sets: dict[str, set[str]] = {}
    best_confidence: dict[str, str] = {}
    rows = conn.execute(
        """
        SELECT normalized_title, candidate_title, issue_code, archive_name, source_kind, confidence
        FROM titles
        WHERE status = 'ok' AND normalized_title IS NOT NULL
        ORDER BY archive_name, COALESCE(source_path, ''), COALESCE(candidate_title, '')
        """
    )
    for row in rows:
        normalized = str(row["normalized_title"])
        issue_sets.setdefault(normalized, set()).add(str(row["archive_name"]))
        source_kind_sets.setdefault(normalized, set()).add(str(row["source_kind"]))
        current_confidence = best_confidence.get(normalized)
        if current_confidence is None or CONFIDENCE_RANKS.get(str(row["confidence"]), 0) > CONFIDENCE_RANKS.get(current_confidence, 0):
            best_confidence[normalized] = str(row["confidence"])
        current = grouped.get(normalized)
        if current is None:
            grouped[normalized] = {
                "normalized_title": normalized,
                "representative_title": row["candidate_title"],
                "first_seen_issue": row["issue_code"],
                "occurrence_count": 1,
                "issue_count": 1,
                "best_confidence": row["confidence"],
                "source_kinds": "",
            }
            continue
        current["occurrence_count"] = int(current["occurrence_count"]) + 1
        current["issue_count"] = len(issue_sets[normalized])

    ordered_rows = sorted(
        grouped.values(),
        key=lambda row: (
            str(row["first_seen_issue"]),
            str(row["representative_title"]).lower(),
            str(row["normalized_title"]),
        ),
    )
    with dedup_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TITLE_DEDUP_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in ordered_rows:
            normalized = str(row["normalized_title"])
            writer.writerow(
                {
                    "normalized_title": normalized,
                    "representative_title": row["representative_title"],
                    "first_seen_issue": row["first_seen_issue"],
                    "occurrence_count": row["occurrence_count"],
                    "issue_count": len(issue_sets[normalized]),
                }
            )

    with master_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MASTER_GAME_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in ordered_rows:
            normalized = str(row["normalized_title"])
            writer.writerow(
                {
                    "normalized_title": normalized,
                    "representative_title": row["representative_title"],
                    "first_seen_issue": row["first_seen_issue"],
                    "issue_count": len(issue_sets[normalized]),
                    "occurrence_count": row["occurrence_count"],
                    "best_confidence": best_confidence.get(normalized, ""),
                    "source_kinds": ",".join(sorted(source_kind_sets.get(normalized, set()))),
                }
            )

    issue_grouped: dict[tuple[str, str], dict[str, object]] = {}
    rows = conn.execute(
        """
        SELECT archive_item, archive_name, issue_code, year, variant, normalized_title, candidate_title, source_kind, confidence, source_path
        FROM titles
        WHERE status = 'ok' AND normalized_title IS NOT NULL
        ORDER BY archive_name, normalized_title, source_kind, source_path
        """
    )
    for row in rows:
        key = (str(row["archive_name"]), str(row["normalized_title"]))
        current = issue_grouped.get(key)
        current_rank = CONFIDENCE_RANKS.get(str(row["confidence"]), 0)
        source_kind = str(row["source_kind"])
        content_kind = infer_content_kind(f"{row['source_path']} {row['candidate_title']} {source_kind}")
        if current is None:
            issue_grouped[key] = {
                "archive_item": row["archive_item"],
                "archive_name": row["archive_name"],
                "issue_code": row["issue_code"],
                "year": row["year"],
                "variant": row["variant"],
                "normalized_title": row["normalized_title"],
                "representative_title": row["candidate_title"],
                "source_kinds": {source_kind},
                "confidence": row["confidence"],
                "content_kind": content_kind,
                "_rank": current_rank,
            }
            continue
        current["source_kinds"].add(source_kind)
        if current_rank > int(current["_rank"]):
            current["representative_title"] = row["candidate_title"]
            current["confidence"] = row["confidence"]
            current["content_kind"] = content_kind
            current["_rank"] = current_rank

    with issue_titles_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_TITLE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for key in sorted(issue_grouped):
            row = issue_grouped[key]
            writer.writerow(
                {
                    "archive_item": row["archive_item"],
                    "archive_name": row["archive_name"],
                    "issue_code": row["issue_code"],
                    "year": row["year"],
                    "variant": row["variant"],
                    "normalized_title": row["normalized_title"],
                    "representative_title": row["representative_title"],
                    "source_kinds": ",".join(sorted(row["source_kinds"])),
                    "confidence": row["confidence"],
                    "content_kind": row["content_kind"],
                }
            )

    with unresolved_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNRESOLVED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        rows = conn.execute(
            """
            SELECT archive_item, archive_name, issue_code, year, variant, title_strategy, resolution_path, reason, status
            FROM issue_resolution
            WHERE unresolved = 1 OR status != 'ok'
            ORDER BY archive_name
            """
        )
        for row in rows:
            writer.writerow({column: row[column] if row[column] is not None else "" for column in UNRESOLVED_COLUMNS})

    with benchmark_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BENCHMARK_COLUMNS, lineterminator="\n")
        writer.writeheader()
        rows = conn.execute(
            """
            SELECT archive_name, issue_code, strategy, elapsed_ms, candidate_count, unique_title_count,
                   structured, unresolved, union_title_count, recall_vs_union, notes
            FROM strategy_runs
            WHERE benchmark_run_id IS NOT NULL
            ORDER BY benchmark_run_id, archive_name, strategy
            """
        )
        for row in rows:
            writer.writerow({column: row[column] if row[column] is not None else "" for column in BENCHMARK_COLUMNS})


def variant_bucket(record: ArchiveRecord) -> str:
    variant = record.variant.lower()
    if "platin" in variant:
        return "platin"
    if "gold" in variant:
        return "gold"
    if "silber" in variant:
        return "silber"
    if "dvd" in variant:
        return "dvd"
    return "standard"


def naming_bucket(record: ArchiveRecord) -> str:
    return "new" if len(record.issue_code) <= 7 else "old"


def year_bucket(record: ArchiveRecord) -> str:
    if record.year <= 2004:
        return "early"
    if record.year <= 2010:
        return "late"
    return "modern"


def benchmark_sample_records(records: list[ArchiveRecord], sample_size: int, seed: int) -> list[ArchiveRecord]:
    if sample_size >= len(records):
        return list(records)
    rng = random.Random(seed)
    pools: dict[tuple[str, str, str], list[ArchiveRecord]] = {}
    for record in records:
        pools.setdefault((year_bucket(record), variant_bucket(record), naming_bucket(record)), []).append(record)
    chosen: list[ArchiveRecord] = []
    seen: set[str] = set()
    for key in sorted(pools):
        pool = pools[key][:]
        rng.shuffle(pool)
        for record in pool:
            if record.archive_name in seen:
                continue
            chosen.append(record)
            seen.add(record.archive_name)
            break
        if len(chosen) >= sample_size:
            return chosen[:sample_size]

    remaining = [record for record in records if record.archive_name not in seen]
    rng.shuffle(remaining)
    chosen.extend(remaining[: max(0, sample_size - len(chosen))])
    chosen.sort(key=lambda record: record.archive_name)
    return chosen[:sample_size]


def run_benchmark_disc_strategy(
    conn: sqlite3.Connection,
    record: ArchiveRecord,
    tmp_root: Path,
    *,
    strategy_name: str,
    title_scan_mode: str,
) -> StrategyRunResult:
    cache_key = strategy_cache_key(record, strategy_name)

    def compute() -> StrategyRunResult:
        started = time.monotonic()
        try:
            conn.execute("DELETE FROM titles WHERE archive_name = ?", (record.archive_name,))
            conn.execute("DELETE FROM archives WHERE archive_name = ?", (record.archive_name,))
            conn.commit()
            status, error = run_disc_title_strategy(conn, record, tmp_root, title_scan_mode=title_scan_mode)
            candidates = issue_title_candidates(conn, record.archive_name)
            structured = any(
                candidate.source_kind in {"disc-metadata-value", "disc-metadata-command", "disc-manifest-path"}
                for candidate in candidates
            )
            return StrategyRunResult(
                strategy=strategy_name,
                candidates=tuple(candidates),
                structured=structured,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=error if status != "ok" else None,
                notes=status,
            )
        except Exception as exc:
            return StrategyRunResult(
                strategy=strategy_name,
                candidates=tuple(),
                structured=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                error=str(exc),
            )
        finally:
            conn.execute("DELETE FROM titles WHERE archive_name = ?", (record.archive_name,))
            conn.execute("DELETE FROM archives WHERE archive_name = ?", (record.archive_name,))
            conn.execute("DELETE FROM issue_resolution WHERE archive_name = ?", (record.archive_name,))
            conn.commit()

    return cached_strategy_result(conn, cache_key, record.archive_name, compute)


def build_benchmark_rows(
    record: ArchiveRecord,
    strategy_results: list[StrategyRunResult],
) -> list[dict[str, object]]:
    union_titles = {candidate.normalized_title for result in strategy_results for candidate in result.candidates}
    union_count = len(union_titles)
    rows: list[dict[str, object]] = []
    for result in strategy_results:
        unique_titles = {candidate.normalized_title for candidate in result.candidates}
        unresolved = not candidates_look_sufficient(list(result.candidates))
        recall = 1.0 if union_count == 0 else len(unique_titles) / union_count
        rows.append(
            {
                "archive_name": record.archive_name,
                "issue_code": record.issue_code,
                "strategy": result.strategy,
                "elapsed_ms": result.elapsed_ms,
                "candidate_count": len(result.candidates),
                "unique_title_count": len(unique_titles),
                "structured": 1 if result.structured else 0,
                "unresolved": 1 if unresolved else 0,
                "union_title_count": union_count,
                "recall_vs_union": round(recall, 6),
                "notes": result.notes if not result.error else f"{result.notes}; {result.error}".strip("; "),
            }
        )
    return rows


def run_title_benchmark(
    conn: sqlite3.Connection,
    records: list[ArchiveRecord],
    args: argparse.Namespace,
    tmp_root: Path,
) -> None:
    conn.execute("DELETE FROM strategy_runs WHERE benchmark_run_id IS NOT NULL")
    conn.commit()
    benchmark_run_id = utc_now()
    sample = benchmark_sample_records(records, args.benchmark_sample, args.benchmark_seed)

    for record in sample:
        results: list[StrategyRunResult] = [
            run_vollversion_strategy(conn, record),
            run_archive_metadata_strategy(conn, record, issue_search_limit=args.issue_search_limit)
        ]
        if args.use_archive_ocr:
            results.append(run_archive_ocr_strategy(conn, record, issue_search_limit=args.issue_search_limit))
        if args.use_redump:
            results.append(run_redump_strategy(conn, record))

        cheap_merged = StrategyRunResult(
            strategy="cheap-merged",
            candidates=tuple(merge_strategy_candidates(results)),
            structured=any(result.structured for result in results),
            elapsed_ms=sum(result.elapsed_ms for result in results),
            notes="merged cheap strategies",
        )
        results.append(cheap_merged)

        try:
            ensure_disc_tools()
            results.append(
                run_benchmark_disc_strategy(
                    conn,
                    record,
                    tmp_root,
                    strategy_name="disc-quick-manifest",
                    title_scan_mode="quick",
                )
            )
            results.append(
                run_benchmark_disc_strategy(
                    conn,
                    record,
                    tmp_root,
                    strategy_name="disc-full",
                    title_scan_mode="full",
                )
            )
        except CommandError as exc:
            results.append(
                StrategyRunResult(
                    strategy="disc-quick-manifest",
                    candidates=tuple(),
                    structured=False,
                    elapsed_ms=0,
                    error=str(exc),
                )
            )
            results.append(
                StrategyRunResult(
                    strategy="disc-full",
                    candidates=tuple(),
                    structured=False,
                    elapsed_ms=0,
                    error=str(exc),
                )
            )

        for row in build_benchmark_rows(record, results):
            record_strategy_run(
                conn,
                record,
                StrategyRunResult(
                    strategy=str(row["strategy"]),
                    candidates=tuple(),
                    structured=bool(row["structured"]),
                    elapsed_ms=int(row["elapsed_ms"]),
                    notes=str(row["notes"]),
                ),
                union_title_count=int(row["union_title_count"]),
                recall_vs_union=float(row["recall_vs_union"]),
                unresolved=bool(row["unresolved"]),
                benchmark_run_id=benchmark_run_id,
                notes=str(row["notes"]),
                candidate_count_override=int(row["candidate_count"]),
                unique_title_count_override=int(row["unique_title_count"]),
            )


def export_csvs(conn: sqlite3.Connection, out_dir: Path, mode: str) -> None:
    if mode == "titles":
        export_title_csvs(conn, out_dir)
        return
    export_exe_csvs(conn, out_dir)


def database_filename(mode: str) -> str:
    return "cbs_titles.sqlite" if mode == "titles" else "cbs_exes.sqlite"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index CBS coverdisc contents without executing them.")
    parser.add_argument("--item", required=True, help="Internet Archive item identifier, for example cbs-2000-09")
    parser.add_argument("--out-dir", default="results", help="Directory for the SQLite database and CSV exports")
    parser.add_argument("--tmp-dir", default="/tmp/cbs-index", help="Scratch directory for downloads, extraction, and mounts")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N archives after sorting")
    parser.add_argument("--resume", action="store_true", help="Skip archives that already reached a terminal status in the SQLite database")
    parser.add_argument(
        "--mode",
        choices=("titles", "exes"),
        default="titles",
        help="titles: infer probable game titles from paths and metadata; exes: exhaustive executable inventory",
    )
    parser.add_argument(
        "--title-strategy",
        choices=("auto", "disc-only", "external-only", "benchmark"),
        default="auto",
        help="Title collection strategy. In titles mode, auto prefers cheap external sources before disc fallback.",
    )
    parser.add_argument("--force-disc", action="store_true", help="Run disc inspection even if cheap title sources look sufficient")
    parser.add_argument("--validate-disc", action="store_true", help="Run cheap title sources first, then compare against disc fallback")
    parser.add_argument("--use-redump", action="store_true", help="Enable Redump lookup as a secondary title source")
    parser.add_argument("--use-archive-ocr", action="store_true", help="Enable Archive.org OCR/text sidecar lookup")
    parser.add_argument("--issue-search-limit", type=int, default=5, help="Maximum Archive.org search candidates per issue")
    parser.add_argument("--benchmark-sample", type=int, default=6, help="Number of issues to sample in benchmark mode")
    parser.add_argument("--benchmark-seed", type=int, default=1, help="Deterministic RNG seed for benchmark sampling")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.umask(0o077)
    ensure_required_tools(mode=args.mode, title_strategy=args.title_strategy)

    out_dir = Path(args.out_dir).expanduser().resolve()
    tmp_root = Path(args.tmp_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_root.mkdir(parents=True, exist_ok=True)

    db_path = out_dir / database_filename(args.mode)
    conn = connect_database(db_path)
    exit_code = 0

    try:
        records = fetch_archive_records(args.item)
        if args.limit is not None:
            records = records[: args.limit]

        if args.mode == "titles" and args.title_strategy == "benchmark":
            run_title_benchmark(conn, records, args, tmp_root)
            export_csvs(conn, out_dir, args.mode)
            return 0

        total = len(records)
        for index, record in enumerate(records, start=1):
            current_status = archive_status(conn, record.archive_name)
            if args.resume and current_status in TERMINAL_STATUSES:
                if args.mode == "titles":
                    resolution = conn.execute(
                        "SELECT unresolved, title_strategy FROM issue_resolution WHERE archive_name = ?",
                        (record.archive_name,),
                    ).fetchone()
                    if resolution is not None and int(resolution["unresolved"]) == 1 and args.title_strategy != "external-only":
                        pass
                    else:
                        print(f"[{index}/{total}] skip {record.archive_name} ({current_status})", file=sys.stderr)
                        continue
                else:
                    print(f"[{index}/{total}] skip {record.archive_name} ({current_status})", file=sys.stderr)
                    continue
            print(f"[{index}/{total}] processing {record.archive_name}", file=sys.stderr)
            if args.mode == "titles":
                process_title_issue(conn, record, tmp_root, args)
            else:
                process_archive(conn, record, tmp_root, args.mode)
            final_status = archive_status(conn, record.archive_name)
            print(f"[{index}/{total}] done {record.archive_name} -> {final_status}", file=sys.stderr)
        export_csvs(conn, out_dir, args.mode)
    except KeyboardInterrupt:
        export_csvs(conn, out_dir, args.mode)
        exit_code = 130
    finally:
        conn.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
