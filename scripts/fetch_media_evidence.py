#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import html
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from scripts.media_common import (
    ASSET_EVIDENCE_FIELDS,
    COMMONS_EVIDENCE_FIELDS,
    IA_FILE_EVIDENCE_FIELDS,
    archive_download_url,
    asset_id,
    load_media_overrides,
    matches_mediawiki_sha1,
    read_csv,
    safe_archive_member,
    select_issue_sources,
    sha1_digest,
    sha256_digest,
    tiff_dimensions,
    write_csv,
)

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "cbsdisks-media-bot/1.0 (https://computerbildspiele.p0s.eu/)"
IA_RECORD_ID = "cbs-2000-09"
IA_METADATA_URL = f"https://archive.org/metadata/{IA_RECORD_ID}"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_ARCHIVE_MEMBERS = 20
MAX_MEMBER_BYTES = 128 * 1024 * 1024


class HtmlMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.first_href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or self.first_href:
            return
        for name, value in attrs:
            if name == "href" and value:
                self.first_href = urllib.parse.urljoin("https://commons.wikimedia.org/", value)
                return

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def parse_html_metadata(value: str) -> tuple[str, str]:
    parser = HtmlMetadataParser()
    parser.feed(value or "")
    return " ".join(html.unescape("".join(parser.text)).split()), parser.first_href


def request_json(url: str, params: dict[str, str], attempts: int = 4) -> dict[str, Any]:
    query_url = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(attempts):
        request = urllib.request.Request(query_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise
            retry_after = int(error.headers.get("Retry-After", "0") or "0")
            time.sleep(max(retry_after, 2**attempt))
        except (TimeoutError, urllib.error.URLError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"request failed: {query_url}")


def download_file(
    url: str,
    destination: Path,
    *,
    expected_size: int | None = None,
    expected_sha1: str = "",
    mediawiki_sha1: bool = False,
    attempts: int = 4,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_suffix(destination.suffix + ".lock")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        def is_valid(path: Path) -> bool:
            size_ok = expected_size is None or path.stat().st_size == expected_size
            hash_ok = not expected_sha1 or (
                matches_mediawiki_sha1(path, expected_sha1)
                if mediawiki_sha1
                else sha1_digest(path) == expected_sha1.casefold()
            )
            return size_ok and hash_ok

        if destination.exists():
            if is_valid(destination):
                return
            destination.unlink()

        partial = destination.with_suffix(destination.suffix + ".part")
        for attempt in range(attempts):
            offset = partial.stat().st_size if partial.exists() else 0
            headers = {"User-Agent": USER_AGENT}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    append = offset > 0 and getattr(response, "status", 200) == 206
                    mode = "ab" if append else "wb"
                    with partial.open(mode) as handle:
                        shutil.copyfileobj(response, handle, length=1024 * 1024)
                if not is_valid(partial):
                    raise ValueError(f"download verification failed for {url}")
                partial.replace(destination)
                return
            except (TimeoutError, urllib.error.URLError, ValueError):
                if attempt + 1 == attempts:
                    raise
                time.sleep(2**attempt)


def load_or_fetch_ia_metadata(cache_dir: Path) -> dict[str, Any]:
    path = cache_dir / f"{IA_RECORD_ID}.metadata.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = request_json(IA_METADATA_URL, {})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def selected_ia_file_rows(metadata: dict[str, Any], selected_names: set[str]) -> list[dict[str, Any]]:
    item_metadata = metadata.get("metadata", {})
    rows = []
    for source in metadata.get("files", []):
        if source.get("name") not in selected_names:
            continue
        rows.append(
            {
                "source_record_id": IA_RECORD_ID,
                "source_file": source["name"],
                "source_download_url": archive_download_url(IA_RECORD_ID, source["name"]),
                "source_size_bytes": source.get("size", ""),
                "source_sha1": source.get("sha1", ""),
                "source_mtime": source.get("mtime", ""),
                "source_creator": item_metadata.get("creator", ""),
                "source_license_url": item_metadata.get("licenseurl", ""),
                "source_rights": item_metadata.get("rights", ""),
                "source_revision": metadata.get("item_last_updated", ""),
            }
        )
    return sorted(rows, key=lambda row: row["source_file"])


def archive_members(archive_path: Path) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["lsar", "-j", str(archive_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    listing = json.loads(result.stdout)
    members = listing.get("lsarContents", [])
    if not 1 <= len(members) <= MAX_ARCHIVE_MEMBERS:
        raise ValueError(f"unexpected member count in {archive_path}: {len(members)}")
    for member in members:
        name = str(member.get("XADFileName", ""))
        size = int(member.get("XADFileSize", 0) or 0)
        if not safe_archive_member(name):
            raise ValueError(f"unsafe archive member in {archive_path}: {name}")
        if size <= 0 or size > MAX_MEMBER_BYTES:
            raise ValueError(f"unsafe archive member size in {archive_path}: {name}: {size}")
    return members


def extract_disc_face(archive_path: Path, extract_dir: Path) -> tuple[Path, str]:
    members = archive_members(archive_path)
    candidates = [
        member for member in members if str(member.get("XADFileName", "")).casefold().endswith((".tif", ".tiff"))
    ]
    if not candidates:
        raise ValueError(f"no TIFF scan in {archive_path}")
    candidate = max(candidates, key=lambda member: int(member.get("XADFileSize", 0) or 0))
    member_name = str(candidate["XADFileName"])
    extract_dir.mkdir(parents=True, exist_ok=True)
    target = extract_dir / member_name
    if not target.exists() or target.stat().st_size != int(candidate["XADFileSize"]):
        subprocess.run(
            ["unar", "-q", "-f", "-D", "-o", str(extract_dir), str(archive_path), member_name],
            check=True,
        )
    width, height = tiff_dimensions(target)
    aspect = width / height
    if min(width, height) < 1000 or not 0.8 <= aspect <= 1.25:
        raise ValueError(f"selected scan is not a disc face: {archive_path}: {member_name}: {width}x{height}")
    return target, member_name


def matched_games(enriched_path: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_qid: dict[str, dict[str, str]] = {}
    by_id: dict[str, dict[str, str]] = {}
    for row in read_csv(enriched_path):
        if row.get("match_status") != "matched" or not row.get("wikidata_id"):
            continue
        by_qid[row["wikidata_id"]] = row
        by_id[row["game_id"]] = row
    return by_qid, by_id


def discover_commons_candidates(
    by_qid: dict[str, dict[str, str]], *, include_depicts: bool = True
) -> list[dict[str, str]]:
    candidates: dict[tuple[str, str], set[str]] = defaultdict(set)
    qids = sorted(by_qid)
    for start in range(0, len(qids), 50):
        batch = qids[start : start + 50]
        payload = request_json(
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "format": "json",
                "props": "claims",
                "ids": "|".join(batch),
                "maxlag": "5",
            },
        )
        for qid in batch:
            claims = payload.get("entities", {}).get(qid, {}).get("claims", {}).get("P18", [])
            for claim in claims:
                mainsnak = claim.get("mainsnak", {})
                if claim.get("rank") == "deprecated" or mainsnak.get("snaktype") != "value":
                    continue
                filename = mainsnak.get("datavalue", {}).get("value", "")
                if filename:
                    candidates[(by_qid[qid]["game_id"], filename)].add("wikidata_p18")

    if include_depicts:
        for qid in qids:
            payload = request_json(
                COMMONS_API,
                {
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "generator": "search",
                    "gsrsearch": f"haswbstatement:P180={qid}",
                    "gsrnamespace": "6",
                    "gsrlimit": "20",
                    "prop": "info",
                    "maxlag": "5",
                },
            )
            for page in payload.get("query", {}).get("pages", []):
                title = page.get("title", "")
                if title.startswith("File:"):
                    candidates[(by_qid[qid]["game_id"], title.removeprefix("File:"))].add("commons_depicts")

    return [
        {
            "subject_id": subject_id,
            "source_file": source_file,
            "match_basis": ";".join(sorted(bases)),
        }
        for (subject_id, source_file), bases in sorted(candidates.items())
    ]


def file_key(value: str) -> str:
    return value.replace("_", " ").casefold()


def commons_metadata(candidates: list[dict[str, str]], by_id: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        by_file[file_key(candidate["source_file"])].append(candidate)
    filenames = sorted({candidate["source_file"] for candidate in candidates}, key=str.casefold)
    rows: list[dict[str, Any]] = []
    for start in range(0, len(filenames), 10):
        batch = filenames[start : start + 10]
        payload = request_json(
            COMMONS_API,
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "info|imageinfo",
                "iiprop": "url|size|mime|sha1|timestamp|user|extmetadata",
                "iiextmetadatafilter": (
                    "Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms|AttributionRequired|"
                    "Restrictions|ImageDescription|ObjectName"
                ),
                "titles": "|".join(f"File:{filename}" for filename in batch),
                "maxlag": "5",
            },
        )
        aliases: dict[str, str] = {}
        for group in ("normalized", "redirects"):
            for mapping in payload.get("query", {}).get(group, []):
                aliases[file_key(mapping.get("to", "").removeprefix("File:"))] = file_key(
                    mapping.get("from", "").removeprefix("File:")
                )
        for page in payload.get("query", {}).get("pages", []):
            if page.get("missing"):
                continue
            filename = page.get("title", "").removeprefix("File:")
            key = file_key(filename)
            candidate_rows = by_file.get(key) or by_file.get(aliases.get(key, ""), [])
            imageinfo = (page.get("imageinfo") or [{}])[0]
            metadata = imageinfo.get("extmetadata", {})

            def value(name: str) -> str:
                return str(metadata.get(name, {}).get("value", "")).strip()

            creator_name, creator_url = parse_html_metadata(value("Artist"))
            credit_line, _ = parse_html_metadata(value("Credit"))
            description, _ = parse_html_metadata(value("ImageDescription"))
            for candidate in candidate_rows:
                game = by_id[candidate["subject_id"]]
                rows.append(
                    {
                        "subject_id": candidate["subject_id"],
                        "wikidata_id": game["wikidata_id"],
                        "match_basis": candidate["match_basis"],
                        "source_file": filename,
                        "source_page_url": imageinfo.get("descriptionurl", ""),
                        "source_download_url": urllib.parse.urlunsplit(
                            urllib.parse.urlsplit(imageinfo.get("url", ""))._replace(query="", fragment="")
                        ),
                        "source_sha1": imageinfo.get("sha1", ""),
                        "source_revision": page.get("lastrevid", ""),
                        "source_mime": imageinfo.get("mime", ""),
                        "source_width": imageinfo.get("width", ""),
                        "source_height": imageinfo.get("height", ""),
                        "creator_name": creator_name,
                        "creator_url": creator_url,
                        "license_id": value("LicenseShortName"),
                        "license_name": value("LicenseShortName"),
                        "license_url": value("LicenseUrl"),
                        "credit_line": credit_line or creator_name,
                        "attribution_required": value("AttributionRequired"),
                        "usage_terms": value("UsageTerms"),
                        "restrictions": value("Restrictions"),
                        "description": description,
                    }
                )
    return sorted(rows, key=lambda row: (row["subject_id"], row["source_file"].casefold()))


def acquire_issue_assets(
    selected: dict[str, dict[str, Any]],
    cache_dir: Path,
    export_dir: Path,
    *,
    source_revision: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for number, (issue_code, source) in enumerate(sorted(selected.items()), start=1):
        source_file = source.get("name") or source.get("source_file", "")
        expected_sha1 = source.get("sha1") or source.get("source_sha1", "")
        expected_size = int(source.get("size") or source.get("source_size_bytes") or 0)
        archive_path = cache_dir / "ia" / f"{expected_sha1}.7z"
        download_file(
            archive_download_url(IA_RECORD_ID, source_file),
            archive_path,
            expected_size=expected_size,
            expected_sha1=expected_sha1,
        )
        extracted, member_name = extract_disc_face(archive_path, cache_dir / "extracted" / expected_sha1)
        width, height = tiff_dimensions(extracted)
        export_relpath = f"originals/{asset_id('issue', issue_code)}.tif"
        export_path = export_dir / export_relpath
        export_path.parent.mkdir(parents=True, exist_ok=True)
        if not export_path.exists() or sha256_digest(export_path) != sha256_digest(extracted):
            shutil.copyfile(extracted, export_path)
        evidence.append(
            {
                "subject_type": "issue",
                "subject_id": issue_code,
                "source_record_id": IA_RECORD_ID,
                "source_file": source_file,
                "source_sha1": expected_sha1,
                "source_revision": source_revision,
                "source_archive_member": member_name,
                "source_member_sha256": sha256_digest(extracted),
                "source_mime": "image/tiff",
                "source_width": width,
                "source_height": height,
                "export_relpath": export_relpath,
            }
        )
        print(f"issue media {number}/{len(selected)}: {issue_code}", flush=True)
    return evidence


def acquire_game_assets(
    commons_rows: list[dict[str, Any]],
    overrides: dict[tuple[str, str], dict[str, str]],
    cache_dir: Path,
    export_dir: Path,
) -> list[dict[str, Any]]:
    by_key = {(row["subject_id"], file_key(row["source_file"])): row for row in commons_rows}
    evidence: list[dict[str, Any]] = []
    for (subject_type, subject_id), override in sorted(overrides.items()):
        if subject_type != "game" or override.get("action") != "approve":
            continue
        row = by_key.get((subject_id, file_key(override.get("source_file", ""))))
        if not row:
            raise ValueError(f"approved Commons asset is missing from evidence: {subject_id}")
        extension = Path(urllib.parse.urlparse(row["source_download_url"]).path).suffix.casefold() or ".img"
        source_path = cache_dir / "commons" / f"{row['source_sha1']}{extension}"
        download_file(
            row["source_download_url"],
            source_path,
            expected_sha1=row["source_sha1"],
            mediawiki_sha1=True,
        )
        export_relpath = f"originals/{asset_id('game', subject_id)}{extension}"
        export_path = export_dir / export_relpath
        export_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, export_path)
        evidence.append(
            {
                "subject_type": "game",
                "subject_id": subject_id,
                "source_record_id": row["wikidata_id"],
                "source_file": row["source_file"],
                "source_sha1": row["source_sha1"],
                "source_revision": row["source_revision"],
                "source_archive_member": "",
                "source_member_sha256": sha256_digest(source_path),
                "source_mime": row["source_mime"],
                "source_width": row["source_width"],
                "source_height": row["source_height"],
                "export_relpath": export_relpath,
            }
        )
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned image evidence and reviewed source assets.")
    parser.add_argument("--published-dir", type=Path, default=ROOT / "results" / "published-20260808")
    parser.add_argument("--enriched-dir", type=Path, default=ROOT / "results" / "enriched-20260808")
    parser.add_argument("--overrides", type=Path, default=ROOT / "data" / "manual_media_overrides.csv")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--skip-depicts", action="store_true")
    args = parser.parse_args()

    overrides = load_media_overrides(args.overrides)
    metadata = load_or_fetch_ia_metadata(args.cache_dir)
    issue_codes = {row["issue_code"] for row in read_csv(args.published_dir / "publishable_issue_titles.csv")}
    selected, rejected = select_issue_sources(issue_codes, metadata.get("files", []), overrides)
    unexpected = {code: reason for code, reason in rejected.items() if code != "CBS012008DVDSonder"}
    if unexpected:
        raise ValueError(f"unresolved issue scan mappings: {unexpected}")

    selected_names = {str(row["name"]) for row in selected.values()}
    ia_rows = selected_ia_file_rows(metadata, selected_names)
    write_csv(args.evidence_dir / "ia_files.csv", IA_FILE_EVIDENCE_FIELDS, ia_rows)

    by_qid, by_id = matched_games(args.enriched_dir / "enriched_master_games.csv")
    candidates = discover_commons_candidates(by_qid, include_depicts=not args.skip_depicts)
    commons_rows = commons_metadata(candidates, by_id)
    write_csv(args.evidence_dir / "commons_candidates.csv", COMMONS_EVIDENCE_FIELDS, commons_rows)

    issue_evidence = acquire_issue_assets(
        selected,
        args.cache_dir,
        args.export_dir,
        source_revision=str(metadata.get("item_last_updated", "")),
    )
    game_evidence = acquire_game_assets(commons_rows, overrides, args.cache_dir, args.export_dir)
    write_csv(
        args.evidence_dir / "asset_evidence.csv",
        ASSET_EVIDENCE_FIELDS,
        sorted(issue_evidence + game_evidence, key=lambda row: (row["subject_type"], row["subject_id"])),
    )
    print(
        f"media evidence ready: {len(issue_evidence)} issue image(s), "
        f"{len(game_evidence)} game cover(s), {len(commons_rows)} Commons candidate(s)"
    )


if __name__ == "__main__":
    main()
