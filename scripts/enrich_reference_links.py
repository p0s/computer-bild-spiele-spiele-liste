#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

HTTP_USER_AGENT = (
    "cbs-reference-enricher/2.0 (https://github.com/p0s/computer-bild-spiele-spiele-liste; public research dataset)"
)
HTTP_TIMEOUT_SECONDS = 15
HTTP_RETRY_ATTEMPTS = 4
HTTP_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
HTTP_MIN_INTERVAL_SECONDS = 0.1
CACHE_KEY_VERSION = "v2"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://{lang}.wikipedia.org/w/api.php"
REFERENCE_COLUMNS = [
    "reference_url",
    "reference_source",
    "reference_lang",
    "reference_title",
    "reference_confidence",
    "reference_status",
]
REFERENCE_RESULT_FIELDS = [
    "normalized_title",
    "representative_title",
    "canonical_title",
    "canonical_slug",
    "match_status",
    "match_confidence",
    "match_method",
    "match_source",
    "match_source_url",
    "match_fetched_at",
    "wikipedia_url",
    "wikidata_id",
    "wikidata_url",
    "failure_reason",
    "candidate_1_title",
    "candidate_1_url",
    "candidate_2_title",
    "candidate_2_url",
    "candidate_3_title",
    "candidate_3_url",
]
LEGACY_CACHE_PATH = Path("results/reference_enrichment.sqlite")
DEFAULT_CACHE_PATH = Path("results/enrichment.sqlite")
_LAST_REQUEST_AT = 0.0


@dataclass(frozen=True)
class CandidateLink:
    label: str
    url: str
    source: str
    lang: str
    score: int


@dataclass(frozen=True)
class Resolution:
    normalized_title: str
    representative_title: str
    canonical_title: str
    canonical_slug: str
    reference_url: str
    reference_source: str
    reference_lang: str
    reference_title: str
    reference_confidence: str
    reference_status: str
    match_method: str
    match_source: str
    match_source_url: str
    wikidata_id: str
    wikidata_url: str
    match_fetched_at: str
    failure_reason: str
    top_candidates: tuple[CandidateLink, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def snapshot_date(path: Path | None) -> str | None:
    if path is None:
        return None
    token = path.name.rsplit("-", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return token
    return None


def latest_snapshot_dir(kind: str) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in Path("results").glob(f"{kind}-*"):
        date = snapshot_date(path)
        if path.is_dir() and date:
            candidates.append((date, path))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def parse_args() -> argparse.Namespace:
    published_dir = latest_snapshot_dir("published") or Path("results/published-latest")
    parser = argparse.ArgumentParser(description="Enrich published CBS game titles with one reference URL each.")
    parser.add_argument("--master-csv", default=str(published_dir / "publishable_master_games.csv"))
    parser.add_argument("--cache-db", default="results/enrichment.sqlite")
    parser.add_argument("--results-csv", default="results/reference_results.csv")
    parser.add_argument("--review-csv", default="results/reference_review.csv")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument(
        "--cache-only", action="store_true", help="Export preserved resolutions without making network requests."
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def normalize_reference_title(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'").replace("`", "'").replace("–", "-").replace("—", "-")
    text = text.replace("&", " and ")
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def strip_version_suffix(value: str) -> str:
    text = value.strip()
    patterns = [
        r"\s+v(?:ersion)?\s*\d+(?:[\s._-]*\d+)*(?:[a-z])?$",
        r"\s+v\d+(?:[\s._-]*\d+)*(?:[a-z])?$",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
        if updated != text:
            text = updated
    return text


def build_search_variants(title: str) -> list[str]:
    variants = [title.strip()]
    ascii_punct = title.replace("’", "'").replace("`", "'").replace("–", "-").replace("—", "-").strip()
    variants.append(ascii_punct)
    stripped = strip_version_suffix(ascii_punct)
    variants.append(stripped)
    variants.append(re.sub(r"\s+", " ", stripped.replace("-", " ")).strip())

    ordered: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        if not variant:
            continue
        if variant in seen:
            continue
        seen.add(variant)
        ordered.append(variant)
    return ordered


def slugify_title(value: str) -> str:
    text = normalize_reference_title(value)
    return text.replace(" ", "-")


def ensure_cache_seed(path: Path) -> None:
    if path.exists():
        return
    if path != DEFAULT_CACHE_PATH:
        return
    if LEGACY_CACHE_PATH.exists() and path != LEGACY_CACHE_PATH:
        path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(LEGACY_CACHE_PATH)
        try:
            target = sqlite3.connect(path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()


def connect_cache(path: Path) -> sqlite3.Connection:
    ensure_cache_seed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;

        CREATE TABLE IF NOT EXISTS request_cache (
            cache_key TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resolved_titles (
            normalized_title TEXT PRIMARY KEY,
            representative_title TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            resolved_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metadata_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        """
    )
    return conn


def http_get_json(url: str) -> dict[str, object]:
    global _LAST_REQUEST_AT
    last_error: Exception | None = None
    for attempt in range(HTTP_RETRY_ATTEMPTS):
        elapsed = time.monotonic() - _LAST_REQUEST_AT
        if elapsed < HTTP_MIN_INTERVAL_SECONDS:
            time.sleep(HTTP_MIN_INTERVAL_SECONDS - elapsed)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": HTTP_USER_AGENT,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                _LAST_REQUEST_AT = time.monotonic()
                payload = response.read(HTTP_MAX_RESPONSE_BYTES + 1)
                if len(payload) > HTTP_MAX_RESPONSE_BYTES:
                    raise RuntimeError("Wikimedia response exceeded the 5 MiB safety limit")
                if response.headers.get("Content-Encoding", "").casefold() == "gzip":
                    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    payload = decompressor.decompress(payload, HTTP_MAX_RESPONSE_BYTES + 1)
                    if len(payload) > HTTP_MAX_RESPONSE_BYTES or decompressor.unconsumed_tail:
                        raise RuntimeError("Wikimedia decompressed response exceeded the 5 MiB safety limit")
                    payload += decompressor.flush(HTTP_MAX_RESPONSE_BYTES + 1 - len(payload))
                    if len(payload) > HTTP_MAX_RESPONSE_BYTES:
                        raise RuntimeError("Wikimedia decompressed response exceeded the 5 MiB safety limit")
                return json.loads(payload.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == HTTP_RETRY_ATTEMPTS - 1:
                break
            retry_after = 0.0
            if isinstance(exc, urllib.error.HTTPError) and exc.headers:
                try:
                    retry_after = float(exc.headers.get("Retry-After", "0") or 0)
                except ValueError:
                    retry_after = 0.0
            time.sleep(max(retry_after, 2.0**attempt))
    raise RuntimeError(f"request failed for {url}: {last_error}")


def public_failure_reason(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.casefold()
    if "http error 429" in lowered or "too many requests" in lowered:
        return "reference_lookup_rate_limited"
    if "maxlag" in lowered or "http error 503" in lowered:
        return "reference_lookup_deferred"
    if lowered.startswith("request failed for http") or "urlopen error" in lowered or "timed out" in lowered:
        return "reference_lookup_failed"
    return text


def is_transient_failure(value: object) -> bool:
    return public_failure_reason(value) in {
        "reference_lookup_rate_limited",
        "reference_lookup_deferred",
        "reference_lookup_failed",
    }


def fetch_json_cached(
    conn: sqlite3.Connection,
    cache_key: str,
    url: str,
    *,
    refresh: bool = False,
) -> dict[str, object]:
    cache_key = f"{CACHE_KEY_VERSION}:{cache_key}"
    row = conn.execute(
        "SELECT payload_json FROM request_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is not None and not refresh:
        return json.loads(str(row["payload_json"]))
    payload = http_get_json(url)
    conn.execute(
        "INSERT OR REPLACE INTO request_cache (cache_key, url, payload_json, fetched_at) VALUES (?, ?, ?, ?)",
        (cache_key, url, json.dumps(payload, sort_keys=True), utc_now()),
    )
    conn.commit()
    return payload


def load_metadata_cache(conn: sqlite3.Connection, cache_key: str) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT payload_json FROM metadata_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return None
    return json.loads(str(row["payload_json"]))


def store_metadata_cache(conn: sqlite3.Connection, cache_key: str, payload: dict[str, object]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO metadata_cache (cache_key, payload_json, fetched_at) VALUES (?, ?, ?)",
        (cache_key, json.dumps(payload, sort_keys=True), utc_now()),
    )
    conn.commit()


def score_candidate(variants: list[str], label: str, aliases: list[str]) -> int:
    candidate_texts = [label, *aliases]
    best = 0
    for variant in variants:
        variant_norm = normalize_reference_title(variant)
        variant_trim = normalize_reference_title(strip_version_suffix(variant))
        for candidate in candidate_texts:
            candidate_norm = normalize_reference_title(candidate)
            if not candidate_norm:
                continue
            if variant_norm == candidate_norm:
                best = max(best, 100)
                continue
            if variant_trim and variant_trim == candidate_norm:
                best = max(best, 96)
                continue
            if variant_norm in candidate_norm or candidate_norm in variant_norm:
                best = max(best, 82)
            ratio = SequenceMatcher(None, variant_norm, candidate_norm).ratio()
            if ratio >= 0.97:
                best = max(best, 90)
            elif ratio >= 0.93:
                best = max(best, 80)
            elif ratio >= 0.89:
                best = max(best, 68)
    return best


def description_adjustment(description: str) -> int:
    lower = description.casefold()
    game_markers = (
        "video game",
        "computer game",
        "videogame",
        "videospiel",
        "computerspiel",
    )
    non_game_markers = (
        "film",
        "movie",
        "album",
        "song",
        "single",
        "novel",
        "book",
        "tv series",
        "television",
        "character",
        "magazine",
    )
    score = 0
    if any(marker in lower for marker in game_markers):
        score += 18
    if any(marker in lower for marker in non_game_markers):
        score -= 18
    return score


def wikidata_search(conn: sqlite3.Connection, query: str, language: str) -> list[dict[str, object]]:
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": language,
        "type": "item",
        "limit": "7",
        "format": "json",
        "maxlag": "5",
    }
    url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
    payload = fetch_json_cached(conn, f"wikidata-search:{language}:{query}", url)
    return list(payload.get("search", []))


def wikidata_entities(
    conn: sqlite3.Connection,
    ids: list[str],
    *,
    props: str = "labels|aliases|sitelinks",
) -> dict[str, object]:
    if not ids:
        return {}
    params = {
        "action": "wbgetentities",
        "ids": "|".join(ids),
        "props": props,
        "format": "json",
        "maxlag": "5",
    }
    url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
    payload = fetch_json_cached(conn, f"wikidata-entities:{props}:{'|'.join(ids)}", url)
    return dict(payload.get("entities", {}))


def wikipedia_search(conn: sqlite3.Connection, query: str, language: str) -> list[dict[str, object]]:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": "5",
        "format": "json",
        "maxlag": "5",
    }
    url = WIKIPEDIA_API.format(lang=language) + "?" + urllib.parse.urlencode(params)
    payload = fetch_json_cached(conn, f"wikipedia-search:{language}:{query}", url)
    return list(payload.get("query", {}).get("search", []))


def wikipedia_url(language: str, title: str) -> str:
    return f"https://{language}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"


def wikipedia_pageprops(conn: sqlite3.Connection, title: str, language: str) -> dict[str, object]:
    params = {
        "action": "query",
        "prop": "pageprops",
        "titles": title,
        "format": "json",
        "maxlag": "5",
    }
    url = WIKIPEDIA_API.format(lang=language) + "?" + urllib.parse.urlencode(params)
    payload = fetch_json_cached(conn, f"wikipedia-pageprops:{language}:{title}", url)
    return dict(payload.get("query", {}).get("pages", {}))


def pick_wikimedia_link(entity: dict[str, object]) -> tuple[str, str, str, str]:
    sitelinks = dict(entity.get("sitelinks", {}))
    for site, source in (("enwiki", "wikipedia-en"), ("dewiki", "wikipedia-de")):
        if site in sitelinks:
            title = str(sitelinks[site]["title"])
            lang = site[:-4]
            return wikipedia_url(lang, title), source, lang, title

    other_sites = sorted(
        site
        for site in sitelinks
        if site.endswith("wiki") and site not in {"commonswiki", "specieswiki", "wikidatawiki"}
    )
    if other_sites:
        site = other_sites[0]
        title = str(sitelinks[site]["title"])
        lang = site[:-4]
        return wikipedia_url(lang, title), "wikipedia-other", lang, title

    qid = str(entity.get("id", ""))
    return f"https://www.wikidata.org/wiki/{qid}", "wikidata", "", qid


def confidence_from_score(score: int) -> str:
    if score >= 95:
        return "high"
    if score >= 80:
        return "medium"
    return "low"


def resolution_from_payload(
    normalized_title: str,
    representative_title: str,
    data: dict[str, object],
) -> Resolution:
    return Resolution(
        normalized_title=normalized_title,
        representative_title=representative_title,
        canonical_title=str(data.get("canonical_title", data.get("reference_title", representative_title))),
        canonical_slug=str(
            data.get(
                "canonical_slug",
                slugify_title(str(data.get("reference_title", representative_title)))
                if data.get("reference_status") == "matched"
                else "",
            )
        ),
        reference_url=str(data.get("reference_url", "")),
        reference_source=str(data.get("reference_source", "")),
        reference_lang=str(data.get("reference_lang", "")),
        reference_title=str(data.get("reference_title", "")),
        reference_confidence=str(data.get("reference_confidence", "")),
        reference_status=str(data.get("reference_status", "unmatched")),
        match_method=str(data.get("match_method", "wikimedia")),
        match_source=str(data.get("match_source", str(data.get("reference_source", "")))),
        match_source_url=str(data.get("match_source_url", str(data.get("reference_url", "")))),
        wikidata_id=str(data.get("wikidata_id", "")),
        wikidata_url=str(data.get("wikidata_url", "")),
        match_fetched_at=str(data.get("match_fetched_at", utc_now())),
        failure_reason=public_failure_reason(data.get("failure_reason", "")),
        top_candidates=tuple(CandidateLink(**item) for item in data.get("top_candidates", [])),
    )


def load_cached_resolution(
    conn: sqlite3.Connection,
    normalized_title: str,
    representative_title: str,
) -> Resolution | None:
    cached = conn.execute(
        "SELECT payload_json FROM resolved_titles WHERE normalized_title = ?",
        (normalized_title,),
    ).fetchone()
    if cached is None:
        return None
    return resolution_from_payload(
        normalized_title,
        representative_title,
        json.loads(str(cached["payload_json"])),
    )


def resolve_title_reference(
    conn: sqlite3.Connection,
    normalized_title: str,
    representative_title: str,
    *,
    refresh: bool = False,
) -> Resolution:
    cached = load_cached_resolution(conn, normalized_title, representative_title)
    if cached is not None and not refresh and not is_transient_failure(cached.failure_reason):
        return cached
    variants = build_search_variants(representative_title)
    wikidata_candidates: dict[str, CandidateLink] = {}

    try:
        for language in ("en", "de"):
            for query in variants:
                search_results = wikidata_search(conn, query, language)
                descriptions = {
                    str(item["id"]): str(item.get("description", "")) for item in search_results if "id" in item
                }
                ids = [str(item["id"]) for item in search_results if "id" in item][:7]
                entities = wikidata_entities(conn, ids)
                for qid in ids:
                    entity = entities.get(qid)
                    if not entity:
                        continue
                    labels = dict(entity.get("labels", {}))
                    aliases = dict(entity.get("aliases", {}))
                    label_values = [str(labels[key]["value"]) for key in labels if key in {"en", "de"}]
                    if not label_values and labels:
                        label_values = [str(next(iter(labels.values()))["value"])]
                    label = label_values[0] if label_values else qid
                    alias_values = [
                        str(alias["value"]) for key in aliases if key in {"en", "de"} for alias in aliases[key]
                    ]
                    score = score_candidate(variants, label, alias_values) + description_adjustment(
                        descriptions.get(qid, "")
                    )
                    if score < 68:
                        continue
                    url, source, lang, title = pick_wikimedia_link(entity)
                    current = wikidata_candidates.get(qid)
                    candidate = CandidateLink(label=title or label, url=url, source=source, lang=lang, score=score)
                    if current is None or score > current.score:
                        wikidata_candidates[qid] = candidate
                if wikidata_candidates:
                    break
            if wikidata_candidates:
                break

        ranked = sorted(
            wikidata_candidates.values(), key=lambda item: (-item.score, item.source, item.label.casefold())
        )
        if ranked:
            top = ranked[0]
            second = ranked[1] if len(ranked) > 1 else None
            top_qid = next((key for key, value in wikidata_candidates.items() if value == top), "")
            if top.score >= 95 and (second is None or second.score <= top.score - 8):
                resolution = Resolution(
                    normalized_title=normalized_title,
                    representative_title=representative_title,
                    canonical_title=top.label,
                    canonical_slug=slugify_title(top.label),
                    reference_url=top.url,
                    reference_source=top.source,
                    reference_lang=top.lang,
                    reference_title=top.label,
                    reference_confidence=confidence_from_score(top.score),
                    reference_status="matched",
                    match_method="wikidata-search",
                    match_source=top.source,
                    match_source_url=top.url,
                    wikidata_id=top_qid,
                    wikidata_url=f"https://www.wikidata.org/wiki/{top_qid}" if top_qid else "",
                    match_fetched_at=utc_now(),
                    failure_reason="",
                    top_candidates=tuple(ranked[:3]),
                )
                store_resolution(conn, resolution)
                return resolution
            if second is not None and second.score >= top.score - 5:
                resolution = Resolution(
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
                    match_method="wikidata-search",
                    match_source="",
                    match_source_url="",
                    wikidata_id="",
                    wikidata_url="",
                    match_fetched_at=utc_now(),
                    failure_reason="multiple plausible Wikimedia entities",
                    top_candidates=tuple(ranked[:3]),
                )
                store_resolution(conn, resolution)
                return resolution

        wikipedia_candidates: list[CandidateLink] = []
        for language in ("en", "de"):
            for query in variants:
                for result in wikipedia_search(conn, query, language):
                    title = str(result.get("title", ""))
                    score = score_candidate(variants, title, []) + description_adjustment(
                        str(result.get("snippet", ""))
                    )
                    if score < 80:
                        continue
                    wikipedia_candidates.append(
                        CandidateLink(
                            label=title,
                            url=wikipedia_url(language, title),
                            source=f"wikipedia-{language}",
                            lang=language,
                            score=score,
                        )
                    )
                if wikipedia_candidates:
                    break
            if wikipedia_candidates:
                break

        wikipedia_candidates.sort(key=lambda item: (-item.score, item.source, item.label.casefold()))
        if wikipedia_candidates:
            top = wikipedia_candidates[0]
            second = wikipedia_candidates[1] if len(wikipedia_candidates) > 1 else None
            if top.score >= 95 and (second is None or second.score <= top.score - 8):
                wikipedia_qid = next(
                    (
                        str(page.get("pageprops", {}).get("wikibase_item", ""))
                        for page in wikipedia_pageprops(conn, top.label, top.lang).values()
                        if page.get("pageprops", {}).get("wikibase_item")
                    ),
                    "",
                )
                resolution = Resolution(
                    normalized_title=normalized_title,
                    representative_title=representative_title,
                    canonical_title=top.label,
                    canonical_slug=slugify_title(top.label),
                    reference_url=top.url,
                    reference_source=top.source,
                    reference_lang=top.lang,
                    reference_title=top.label,
                    reference_confidence=confidence_from_score(top.score),
                    reference_status="matched",
                    match_method="wikipedia-search",
                    match_source=top.source,
                    match_source_url=top.url,
                    wikidata_id=wikipedia_qid,
                    wikidata_url=f"https://www.wikidata.org/wiki/{wikipedia_qid}" if wikipedia_qid else "",
                    match_fetched_at=utc_now(),
                    failure_reason="",
                    top_candidates=tuple(wikipedia_candidates[:3]),
                )
                store_resolution(conn, resolution)
                return resolution
            resolution = Resolution(
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
                match_method="wikipedia-search",
                match_source="",
                match_source_url="",
                wikidata_id="",
                wikidata_url="",
                match_fetched_at=utc_now(),
                failure_reason="multiple plausible Wikipedia search results",
                top_candidates=tuple(wikipedia_candidates[:3]),
            )
            store_resolution(conn, resolution)
            return resolution

        resolution = Resolution(
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
            match_method="wikimedia",
            match_source="",
            match_source_url="",
            wikidata_id="",
            wikidata_url="",
            match_fetched_at=utc_now(),
            failure_reason="no confident Wikimedia match",
            top_candidates=tuple(ranked[:3]),
        )
    except RuntimeError as exc:
        resolution = Resolution(
            normalized_title=normalized_title,
            representative_title=representative_title,
            canonical_title="",
            canonical_slug="",
            reference_url="",
            reference_source="",
            reference_lang="",
            reference_title="",
            reference_confidence="",
            reference_status="pending",
            match_method="wikimedia",
            match_source="",
            match_source_url="",
            wikidata_id="",
            wikidata_url="",
            match_fetched_at=utc_now(),
            failure_reason=public_failure_reason(exc),
            top_candidates=tuple(
                sorted(
                    wikidata_candidates.values(), key=lambda item: (-item.score, item.source, item.label.casefold())
                )[:3]
            ),
        )
    store_resolution(conn, resolution)
    return resolution


def store_resolution(conn: sqlite3.Connection, resolution: Resolution) -> None:
    if is_transient_failure(resolution.failure_reason):
        return
    payload = {
        "canonical_title": resolution.canonical_title,
        "canonical_slug": resolution.canonical_slug,
        "reference_url": resolution.reference_url,
        "reference_source": resolution.reference_source,
        "reference_lang": resolution.reference_lang,
        "reference_title": resolution.reference_title,
        "reference_confidence": resolution.reference_confidence,
        "reference_status": resolution.reference_status,
        "match_method": resolution.match_method,
        "match_source": resolution.match_source,
        "match_source_url": resolution.match_source_url,
        "wikidata_id": resolution.wikidata_id,
        "wikidata_url": resolution.wikidata_url,
        "match_fetched_at": resolution.match_fetched_at,
        "failure_reason": resolution.failure_reason,
        "top_candidates": [
            {
                "label": candidate.label,
                "url": candidate.url,
                "source": candidate.source,
                "lang": candidate.lang,
                "score": candidate.score,
            }
            for candidate in resolution.top_candidates
        ],
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO resolved_titles (normalized_title, representative_title, payload_json, resolved_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            resolution.normalized_title,
            resolution.representative_title,
            json.dumps(payload, sort_keys=True),
            utc_now(),
        ),
    )
    conn.commit()


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    args = parse_args()
    master_csv = Path(args.master_csv)
    cache_db = Path(args.cache_db)
    results_csv = Path(args.results_csv)
    review_csv = Path(args.review_csv)

    master_rows = read_csv(master_csv)
    if args.limit is not None:
        master_rows = master_rows[: args.limit]
    conn = connect_cache(cache_db)

    try:
        result_rows: list[dict[str, str]] = []
        review_rows: list[dict[str, str]] = []

        for row in master_rows:
            if args.cache_only:
                resolution = load_cached_resolution(conn, row["normalized_title"], row["representative_title"])
                if resolution is None:
                    resolution = Resolution(
                        normalized_title=row["normalized_title"],
                        representative_title=row["representative_title"],
                        canonical_title="",
                        canonical_slug="",
                        reference_url="",
                        reference_source="",
                        reference_lang="",
                        reference_title="",
                        reference_confidence="",
                        reference_status="pending",
                        match_method="wikimedia-cache",
                        match_source="",
                        match_source_url="",
                        wikidata_id="",
                        wikidata_url="",
                        match_fetched_at="",
                        failure_reason="reference_lookup_not_cached",
                        top_candidates=(),
                    )
            else:
                resolution = resolve_title_reference(
                    conn,
                    row["normalized_title"],
                    row["representative_title"],
                    refresh=args.refresh_cache,
                )
            result_row = {
                "normalized_title": resolution.normalized_title,
                "representative_title": resolution.representative_title,
                "canonical_title": resolution.canonical_title,
                "canonical_slug": resolution.canonical_slug,
                "match_status": resolution.reference_status,
                "match_confidence": resolution.reference_confidence,
                "match_method": resolution.match_method,
                "match_source": resolution.match_source,
                "match_source_url": resolution.match_source_url,
                "match_fetched_at": resolution.match_fetched_at,
                "wikipedia_url": resolution.reference_url
                if resolution.reference_source.startswith("wikipedia-")
                else "",
                "wikidata_id": resolution.wikidata_id,
                "wikidata_url": resolution.wikidata_url,
                "failure_reason": resolution.failure_reason,
            }
            for idx, candidate in enumerate(resolution.top_candidates[:3], start=1):
                result_row[f"candidate_{idx}_title"] = candidate.label
                result_row[f"candidate_{idx}_url"] = candidate.url
            result_rows.append(result_row)
            if resolution.reference_status != "matched":
                review_rows.append(result_row)

        results_csv.parent.mkdir(parents=True, exist_ok=True)
        write_csv(results_csv, result_rows, REFERENCE_RESULT_FIELDS)
        review_csv.parent.mkdir(parents=True, exist_ok=True)
        write_csv(review_csv, review_rows, REFERENCE_RESULT_FIELDS)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
