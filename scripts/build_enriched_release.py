#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.enrich_reference_links import (
    build_search_variants,
    connect_cache,
    load_metadata_cache,
    resolve_title_reference,
    slugify_title,
    store_metadata_cache,
    wikidata_entities,
)


ENRICHED_MASTER_FIELDS = [
    "normalized_title",
    "representative_title",
    "first_seen_issue",
    "issue_count",
    "occurrence_count",
    "best_confidence",
    "source_kinds",
    "canonical_title",
    "canonical_slug",
    "match_status",
    "match_confidence",
    "match_method",
    "match_source",
    "match_source_url",
    "match_fetched_at",
    "entity_type",
    "release_year",
    "wikipedia_url",
    "wikidata_id",
    "wikidata_url",
    "categories",
    "genres",
    "themes",
    "category_source",
    "category_source_url",
    "category_fetched_at",
    "category_confidence",
    "rating_value",
    "rating_scale",
    "rating_count",
    "rating_source",
    "rating_url",
    "rating_fetched_at",
    "rating_confidence",
    "metadata_sources",
    "notes",
]

ENRICHED_ISSUE_FIELDS = [
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
    "clean_reason",
    "canonical_title",
    "canonical_slug",
    "match_status",
    "match_confidence",
    "entity_type",
    "categories",
    "genres",
    "themes",
    "wikipedia_url",
    "wikidata_id",
    "wikidata_url",
    "rating_value",
    "rating_scale",
    "rating_count",
    "rating_source",
    "rating_url",
]

TITLE_ALIAS_FIELDS = [
    "normalized_title",
    "representative_title",
    "canonical_title",
    "canonical_slug",
    "match_status",
    "match_confidence",
    "match_method",
    "override_applied",
    "match_source",
    "match_source_url",
]

AMBIGUOUS_FIELDS = [
    "normalized_title",
    "representative_title",
    "match_status",
    "match_confidence",
    "failure_reason",
    "candidate_1_title",
    "candidate_1_url",
    "candidate_2_title",
    "candidate_2_url",
    "candidate_3_title",
    "candidate_3_url",
]

UNMATCHED_FIELDS = [
    "normalized_title",
    "representative_title",
    "match_status",
    "match_confidence",
    "failure_reason",
    "search_variants",
]

SOURCE_ATTRIBUTION_FIELDS = [
    "source_name",
    "source_type",
    "homepage",
    "fields_used",
    "attribution_note",
    "terms_note",
]

MOBYGAMES_USER_AGENT = "Mozilla/5.0 (compatible; cbs-metadata-enricher/1.0)"
LEGACY_REFERENCE_CACHE = Path("results/reference_enrichment.sqlite")


@dataclass(frozen=True)
class OverrideAlias:
    canonical_slug: str
    canonical_title: str
    reason: str


@dataclass(frozen=True)
class OverrideEntity:
    wikidata_id: str
    wikipedia_url: str
    canonical_title: str
    entity_type: str
    reason: str


@dataclass(frozen=True)
class OverrideUrl:
    wikipedia_url: str
    wikidata_id: str
    source_url: str
    reason: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    parser = argparse.ArgumentParser(description="Build enriched public release outputs for CBS game titles.")
    parser.add_argument("--input-master", default="results/published-20260324/publishable_master_games.csv")
    parser.add_argument("--input-issues", default="results/published-20260324/publishable_issue_titles.csv")
    parser.add_argument("--output-dir", default=f"results/enriched-{today}")
    parser.add_argument("--cache-db", default="results/enrichment.sqlite")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only-unmatched", action="store_true")
    parser.add_argument("--only-ambiguous", action="store_true")
    parser.add_argument("--manual-alias-overrides", default="data/manual_alias_overrides.csv")
    parser.add_argument("--manual-entity-overrides", default="data/manual_entity_overrides.csv")
    parser.add_argument("--manual-url-overrides", default="data/manual_url_overrides.csv")
    parser.add_argument("--manual-rejections", default="data/manual_rejections.csv")
    parser.add_argument("--review-csv", default="results/reference_review.csv")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_override_map(path: Path, key_field: str, factory):
    if not path.exists():
        return {}
    rows = read_csv(path)
    return {
        row[key_field]: factory(row)
        for row in rows
        if row.get(key_field)
    }


def read_rejections(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        if row.get("normalized_title"):
            grouped[row["normalized_title"]].append(row)
    return grouped


def choose_label(entity: dict[str, object]) -> str:
    labels = dict(entity.get("labels", {}))
    for language in ("en", "de"):
        if language in labels:
            return str(labels[language]["value"])
    if labels:
        return str(next(iter(labels.values()))["value"])
    return ""


def claim_values(entity: dict[str, object], prop: str) -> list[object]:
    values: list[object] = []
    for claim in entity.get("claims", {}).get(prop, []):
        datavalue = claim.get("mainsnak", {}).get("datavalue")
        if datavalue is not None:
            values.append(datavalue.get("value"))
    return values


def claim_entity_ids(entity: dict[str, object], prop: str) -> list[str]:
    ids: list[str] = []
    for value in claim_values(entity, prop):
        if isinstance(value, dict):
            entity_id = value.get("id")
            if entity_id:
                ids.append(str(entity_id))
    return ids


def claim_first_year(entity: dict[str, object], prop: str) -> str:
    for value in claim_values(entity, prop):
        if isinstance(value, dict) and isinstance(value.get("time"), str):
            match = re.search(r"([+-]?\d{4})-", str(value["time"]))
            if match:
                return match.group(1).lstrip("+")
    return ""


def fetch_entity_with_claims(conn: sqlite3.Connection, qid: str) -> dict[str, object]:
    cache_key = f"entity-claims:{qid}"
    cached = load_metadata_cache(conn, cache_key)
    if cached is not None:
        return cached
    try:
        entities = wikidata_entities(conn, [qid], props="labels|aliases|sitelinks|claims")
    except RuntimeError:
        return {}
    payload = dict(entities.get(qid, {}))
    store_metadata_cache(conn, cache_key, payload)
    return payload


def fetch_labels(conn: sqlite3.Connection, entity_ids: list[str]) -> dict[str, str]:
    unique_ids = sorted(set(entity_ids))
    if not unique_ids:
        return {}
    cache_key = f"entity-labels:{'|'.join(unique_ids)}"
    cached = load_metadata_cache(conn, cache_key)
    if cached is not None:
        return {key: str(value) for key, value in cached.items()}
    try:
        entities = wikidata_entities(conn, unique_ids, props="labels")
    except RuntimeError:
        return {}
    labels = {entity_id: choose_label(entity) for entity_id, entity in entities.items()}
    store_metadata_cache(conn, cache_key, labels)
    return labels


def derive_entity_type(instance_labels: list[str]) -> str:
    lowered = [label.casefold() for label in instance_labels]
    if any("expansion" in label or "downloadable content" in label for label in lowered):
        return "expansion"
    if any("compilation" in label for label in lowered):
        return "compilation"
    if any("software" in label or "application" in label or "utility" in label for label in lowered):
        return "tool"
    if any("video game" in label or "computer game" in label or "videospiel" in label for label in lowered):
        return "game"
    return "unknown"


def map_categories(entity_type: str, genres: list[str]) -> list[str]:
    if entity_type == "tool":
        return ["utility"]
    categories: set[str] = set()
    for genre in genres:
        lower = genre.casefold()
        if "action" in lower or "hack and slash" in lower or "beat 'em up" in lower or "fighting" in lower:
            categories.add("action")
        if "adventure" in lower or "point and click" in lower or "visual novel" in lower:
            categories.add("adventure")
        if "strategy" in lower or "tactic" in lower or "wargame" in lower:
            categories.add("strategy")
        if "role-playing" in lower or "rpg" in lower:
            categories.add("rpg")
        if "simulation" in lower or "management" in lower or "city-building" in lower:
            categories.add("simulation")
        if "sport" in lower or "soccer" in lower or "football" in lower or "golf" in lower:
            categories.add("sports")
        if "racing" in lower or "driving" in lower:
            categories.add("racing")
        if "puzzle" in lower:
            categories.add("puzzle")
        if "shooter" in lower or "first-person" in lower or "third-person" in lower:
            categories.add("shooter")
        if "arcade" in lower:
            categories.add("arcade")
        if "platform" in lower:
            categories.add("platformer")
        if "party" in lower:
            categories.add("party")
    if entity_type == "game" and not categories:
        categories.add("other")
    return sorted(categories)


def extract_wikidata_rating(entity: dict[str, object], label_lookup: dict[str, str], game_qid: str) -> dict[str, str]:
    claims = entity.get("claims", {}).get("P444", [])
    if not claims:
        return {
            "rating_value": "",
            "rating_scale": "",
            "rating_count": "",
            "rating_source": "",
            "rating_url": "",
            "rating_fetched_at": "",
            "rating_confidence": "",
        }
    if len(claims) > 1:
        return {
            "rating_value": "",
            "rating_scale": "",
            "rating_count": "",
            "rating_source": "",
            "rating_url": "",
            "rating_fetched_at": "",
            "rating_confidence": "",
        }
    claim = claims[0]
    mainsnak = claim.get("mainsnak", {})
    datavalue = mainsnak.get("datavalue", {})
    value = datavalue.get("value")
    rating_value = ""
    if isinstance(value, dict) and "amount" in value:
        rating_value = str(value["amount"]).lstrip("+")
    elif value is not None:
        rating_value = str(value)
    reviewer_ids = []
    for qualifier in claim.get("qualifiers", {}).get("P447", []):
        qvalue = qualifier.get("datavalue", {}).get("value", {})
        if isinstance(qvalue, dict) and qvalue.get("id"):
            reviewer_ids.append(str(qvalue["id"]))
    reviewer_label = label_lookup.get(reviewer_ids[0], "wikidata") if reviewer_ids else "wikidata"
    reviewer_url = f"https://www.wikidata.org/wiki/{reviewer_ids[0]}" if reviewer_ids else f"https://www.wikidata.org/wiki/{game_qid}"
    return {
        "rating_value": rating_value,
        "rating_scale": "",
        "rating_count": "",
        "rating_source": reviewer_label,
        "rating_url": reviewer_url,
        "rating_fetched_at": utc_now(),
        "rating_confidence": "medium" if rating_value else "",
    }


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": MOBYGAMES_USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def fetch_mobygames_metadata(conn: sqlite3.Connection, url: str) -> dict[str, str]:
    cache_key = f"mobygames:{url}"
    cached = load_metadata_cache(conn, cache_key)
    if cached is not None:
        return {key: str(value) for key, value in cached.items()}
    try:
        text = fetch_text(url)
    except (urllib.error.URLError, TimeoutError, OSError):
        payload = {
            "genres": "",
            "categories": "",
            "themes": "",
            "rating_value": "",
            "rating_scale": "",
            "rating_count": "",
            "rating_source": "",
            "rating_url": "",
            "rating_fetched_at": "",
            "rating_confidence": "",
            "notes": "mobygames unavailable",
        }
        store_metadata_cache(conn, cache_key, payload)
        return payload

    genres = sorted(set(re.findall(r'"genre":"([^"]+)"', text, flags=re.IGNORECASE)))
    rating_value_match = re.search(r'"ratingValue":"([^"]+)"', text)
    rating_count_match = re.search(r'"ratingCount":"([^"]+)"', text)
    payload = {
        "genres": "; ".join(genres),
        "categories": "",
        "themes": "",
        "rating_value": rating_value_match.group(1) if rating_value_match else "",
        "rating_scale": "5" if rating_value_match else "",
        "rating_count": rating_count_match.group(1) if rating_count_match else "",
        "rating_source": "MobyGames" if rating_value_match else "",
        "rating_url": url if rating_value_match else "",
        "rating_fetched_at": utc_now() if rating_value_match else "",
        "rating_confidence": "medium" if rating_value_match else "",
        "notes": "",
    }
    store_metadata_cache(conn, cache_key, payload)
    return payload


def reference_to_wikipedia_url(reference_source: str, reference_url: str, manual_url: str) -> str:
    if manual_url:
        return manual_url
    if reference_source.startswith("wikipedia"):
        return reference_url
    return ""


def build_source_attribution_rows() -> list[dict[str, str]]:
    return [
        {
            "source_name": "Wikidata",
            "source_type": "api",
            "homepage": "https://www.wikidata.org/",
            "fields_used": "canonical entity, release year, entity type, genres, ratings when present, MobyGames id when present",
            "attribution_note": "Structured Wikimedia entity data",
            "terms_note": "Use minimal factual metadata with source attribution",
        },
        {
            "source_name": "Wikipedia",
            "source_type": "api",
            "homepage": "https://www.wikipedia.org/",
            "fields_used": "canonical page URL and fallback page discovery",
            "attribution_note": "Used only for page URLs and entity confirmation",
            "terms_note": "Use minimal factual metadata with source attribution",
        },
        {
            "source_name": "MobyGames",
            "source_type": "public-page",
            "homepage": "https://www.mobygames.com/",
            "fields_used": "best-effort genre/rating confirmation when page access is possible",
            "attribution_note": "Optional secondary source only after strong canonical match",
            "terms_note": "Do not copy large page content; use minimal factual metadata only",
        },
    ]


def write_enriched_readme(path: Path, master_count: int, issue_count: int, ambiguous_count: int, unmatched_count: int) -> None:
    text = f"""# Enriched Results

This directory contains the enriched game-entity layer built on top of the current publishable CBS title list.

Current enriched snapshot:

- canonical master rows: `{master_count}`
- enriched issue/title rows: `{issue_count}`
- ambiguous titles: `{ambiguous_count}`
- unmatched titles: `{unmatched_count}`

Files:

- `enriched_master_games.csv`
- `enriched_issue_titles.csv`
- `title_aliases.csv`
- `ambiguous_matches.csv`
- `unmatched_titles.csv`
- `source_attribution.csv`

Notes:

- URLs are Wikimedia-first.
- Categories and genres come primarily from Wikidata.
- Ratings are source-labeled and intentionally sparse.
- `ambiguous` and `unmatched` are explicit by design.
"""
    path.write_text(text, encoding="utf-8")


def derive_review_outputs_from_master(master_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    aliases: list[dict[str, str]] = []
    ambiguous_rows: list[dict[str, str]] = []
    unmatched_rows: list[dict[str, str]] = []
    for row in master_rows:
        aliases.append(
            {
                "normalized_title": row["normalized_title"],
                "representative_title": row["representative_title"],
                "canonical_title": row["canonical_title"],
                "canonical_slug": row["canonical_slug"],
                "match_status": row["match_status"],
                "match_confidence": row["match_confidence"],
                "match_method": row["match_method"],
                "override_applied": row.get("override_applied", "false"),
                "match_source": row["match_source"],
                "match_source_url": row["match_source_url"],
            }
        )
        if row["match_status"] == "ambiguous":
            ambiguous_rows.append(
                {
                    "normalized_title": row["normalized_title"],
                    "representative_title": row["representative_title"],
                    "match_status": row["match_status"],
                    "match_confidence": row["match_confidence"],
                    "failure_reason": row["notes"],
                    "candidate_1_title": "",
                    "candidate_1_url": "",
                    "candidate_2_title": "",
                    "candidate_2_url": "",
                    "candidate_3_title": "",
                    "candidate_3_url": "",
                }
            )
        elif row["match_status"] == "unmatched":
            unmatched_rows.append(
                {
                    "normalized_title": row["normalized_title"],
                    "representative_title": row["representative_title"],
                    "match_status": row["match_status"],
                    "match_confidence": row["match_confidence"],
                    "failure_reason": row["notes"],
                    "search_variants": "",
                }
            )
    return aliases, ambiguous_rows, unmatched_rows


def write_current_outputs(
    output_dir: Path,
    enriched_master: list[dict[str, str]],
    issue_rows: list[dict[str, str]],
    review_csv: Path,
    review_rows: list[dict[str, str]],
) -> None:
    master_by_title = {row["normalized_title"]: row for row in enriched_master}
    enriched_issue_rows: list[dict[str, str]] = []
    for row in issue_rows:
        master_row = master_by_title.get(row["normalized_title"])
        if master_row is None:
            continue
        enriched_issue_rows.append(
            {
                **row,
                "canonical_title": master_row["canonical_title"],
                "canonical_slug": master_row["canonical_slug"],
                "match_status": master_row["match_status"],
                "match_confidence": master_row["match_confidence"],
                "entity_type": master_row["entity_type"],
                "categories": master_row["categories"],
                "genres": master_row["genres"],
                "themes": master_row["themes"],
                "wikipedia_url": master_row["wikipedia_url"],
                "wikidata_id": master_row["wikidata_id"],
                "wikidata_url": master_row["wikidata_url"],
                "rating_value": master_row["rating_value"],
                "rating_scale": master_row["rating_scale"],
                "rating_count": master_row["rating_count"],
                "rating_source": master_row["rating_source"],
                "rating_url": master_row["rating_url"],
            }
        )

    aliases, ambiguous_rows, unmatched_rows = derive_review_outputs_from_master(enriched_master)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "enriched_master_games.csv", enriched_master, ENRICHED_MASTER_FIELDS)
    write_csv(output_dir / "enriched_issue_titles.csv", enriched_issue_rows, ENRICHED_ISSUE_FIELDS)
    write_csv(output_dir / "title_aliases.csv", aliases, TITLE_ALIAS_FIELDS)
    write_csv(output_dir / "ambiguous_matches.csv", ambiguous_rows, AMBIGUOUS_FIELDS)
    write_csv(output_dir / "unmatched_titles.csv", unmatched_rows, UNMATCHED_FIELDS)
    write_csv(output_dir / "source_attribution.csv", build_source_attribution_rows(), SOURCE_ATTRIBUTION_FIELDS)
    write_enriched_readme(
        output_dir / "README.md",
        master_count=len(enriched_master),
        issue_count=len(enriched_issue_rows),
        ambiguous_count=len(ambiguous_rows),
        unmatched_count=len(unmatched_rows),
    )
    write_csv(review_csv, review_rows, AMBIGUOUS_FIELDS)


def default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path(f"results/enriched-{stamp}")


def reset_enrichment_cache(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM request_cache")
    conn.execute("DELETE FROM resolved_titles")
    conn.execute("DELETE FROM metadata_cache")
    conn.commit()


def output_master_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows = read_csv(path)
    return {row["normalized_title"]: row for row in rows}


def load_overrides(args: argparse.Namespace):
    alias_overrides = read_override_map(
        Path(args.manual_alias_overrides),
        "normalized_title",
        lambda row: OverrideAlias(
            canonical_slug=row["canonical_slug"],
            canonical_title=row["canonical_title"],
            reason=row["reason"],
        ),
    )
    entity_overrides = read_override_map(
        Path(args.manual_entity_overrides),
        "normalized_title",
        lambda row: OverrideEntity(
            wikidata_id=row["wikidata_id"],
            wikipedia_url=row["wikipedia_url"],
            canonical_title=row["canonical_title"],
            entity_type=row["entity_type"],
            reason=row["reason"],
        ),
    )
    url_overrides = read_override_map(
        Path(args.manual_url_overrides),
        "canonical_slug",
        lambda row: OverrideUrl(
            wikipedia_url=row["wikipedia_url"],
            wikidata_id=row["wikidata_id"],
            source_url=row["source_url"],
            reason=row["reason"],
        ),
    )
    rejections = read_rejections(Path(args.manual_rejections))
    return alias_overrides, entity_overrides, url_overrides, rejections


def source_kind_list(value: str) -> list[str]:
    return [part for part in value.split(",") if part]


def apply_rejections(resolution, rejections: list[dict[str, str]]):
    if not rejections:
        return resolution
    for rejection in rejections:
        rejected = rejection.get("rejected_candidate", "").casefold()
        if any(candidate.label.casefold() == rejected for candidate in resolution.top_candidates):
            from scripts.enrich_reference_links import Resolution

            return Resolution(
                normalized_title=resolution.normalized_title,
                representative_title=resolution.representative_title,
                canonical_title="",
                canonical_slug="",
                reference_url="",
                reference_source="",
                reference_lang="",
                reference_title="",
                reference_confidence="",
                reference_status="unmatched",
                match_method="manual-rejection",
                match_source="",
                match_source_url="",
                wikidata_id="",
                wikidata_url="",
                match_fetched_at=utc_now(),
                failure_reason=rejection.get("reason", "manually rejected candidate"),
                top_candidates=resolution.top_candidates,
            )
    return resolution


def qid_from_url(url: str) -> str:
    match = re.search(r"/wiki/(Q\d+)$", url)
    return match.group(1) if match else ""


def normalize_semicolon(values: list[str]) -> str:
    cleaned = sorted({value.strip() for value in values if value and value.strip()})
    return "; ".join(cleaned)


def enrich_row(
    conn: sqlite3.Connection,
    row: dict[str, str],
    alias_overrides: dict[str, OverrideAlias],
    entity_overrides: dict[str, OverrideEntity],
    url_overrides: dict[str, OverrideUrl],
    rejections: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, str], dict[str, str] | None, dict[str, str] | None]:
    normalized = row["normalized_title"]
    representative = row["representative_title"]
    override_applied = "false"
    notes: list[str] = []
    review_candidates = []
    search_variants = build_search_variants(representative)

    if normalized in entity_overrides:
        override = entity_overrides[normalized]
        override_applied = "true"
        canonical_title = override.canonical_title or representative
        canonical_slug = slugify_title(canonical_title)
        wikidata_id = override.wikidata_id
        wikipedia_url = override.wikipedia_url
        resolution = {
            "canonical_title": canonical_title,
            "canonical_slug": canonical_slug,
            "match_status": "matched",
            "match_confidence": "high",
            "match_method": "manual-entity-override",
            "match_source": "manual",
            "match_source_url": wikipedia_url or (f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else ""),
            "match_fetched_at": utc_now(),
            "reference_url": wikipedia_url or (f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else ""),
            "reference_source": "wikipedia-manual" if wikipedia_url else "wikidata-manual",
            "reference_lang": "en" if "en.wikipedia.org" in wikipedia_url else ("de" if "de.wikipedia.org" in wikipedia_url else ""),
            "reference_title": canonical_title,
            "reference_confidence": "high",
            "reference_status": "matched",
            "wikidata_id": wikidata_id,
            "wikidata_url": f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else "",
            "entity_type_override": override.entity_type,
        }
        if override.reason:
            notes.append(override.reason)
    else:
        search_title = representative
        match_method_prefix = ""
        if normalized in alias_overrides:
            alias = alias_overrides[normalized]
            search_title = alias.canonical_title or representative
            override_applied = "true"
            match_method_prefix = "manual-alias-override+"
            if alias.reason:
                notes.append(alias.reason)
            search_variants = build_search_variants(search_title)
        ref = resolve_title_reference(conn, normalized, search_title)
        ref = apply_rejections(ref, rejections.get(normalized, []))
        review_candidates = list(ref.top_candidates)
        resolution = {
            "canonical_title": ref.canonical_title,
            "canonical_slug": ref.canonical_slug,
            "match_status": ref.reference_status,
            "match_confidence": ref.reference_confidence or ("low" if ref.reference_status != "matched" else ""),
            "match_method": f"{match_method_prefix}{ref.match_method}" if ref.match_method else match_method_prefix.rstrip("+"),
            "match_source": ref.match_source,
            "match_source_url": ref.match_source_url,
            "match_fetched_at": ref.match_fetched_at,
            "reference_url": ref.reference_url,
            "reference_source": ref.reference_source,
            "reference_lang": ref.reference_lang,
            "reference_title": ref.reference_title,
            "reference_confidence": ref.reference_confidence,
            "reference_status": ref.reference_status,
            "wikidata_id": ref.wikidata_id or qid_from_url(ref.wikidata_url),
            "wikidata_url": ref.wikidata_url,
            "entity_type_override": "",
        }
        if ref.failure_reason:
            notes.append(ref.failure_reason)

    canonical_title = resolution["canonical_title"]
    canonical_slug = resolution["canonical_slug"]
    wikidata_id = resolution["wikidata_id"]
    wikipedia_url = resolution["reference_url"] if resolution["reference_source"].startswith("wikipedia") else ""

    entity_type = resolution.get("entity_type_override", "") or "unknown"
    release_year = ""
    genres: list[str] = []
    categories: list[str] = []
    themes: list[str] = []
    category_source = ""
    category_source_url = ""
    category_fetched_at = ""
    category_confidence = ""
    rating = {
        "rating_value": "",
        "rating_scale": "",
        "rating_count": "",
        "rating_source": "",
        "rating_url": "",
        "rating_fetched_at": "",
        "rating_confidence": "",
    }
    metadata_sources: list[str] = []

    if resolution["match_status"] == "matched" and wikidata_id:
        entity = fetch_entity_with_claims(conn, wikidata_id)
        instance_ids = claim_entity_ids(entity, "P31")
        genre_ids = claim_entity_ids(entity, "P136")
        reviewer_ids = []
        for claim in entity.get("claims", {}).get("P444", []):
            for qualifier in claim.get("qualifiers", {}).get("P447", []):
                value = qualifier.get("datavalue", {}).get("value", {})
                if isinstance(value, dict) and value.get("id"):
                    reviewer_ids.append(str(value["id"]))
        label_lookup = fetch_labels(conn, instance_ids + genre_ids + reviewer_ids)
        instance_labels = [label_lookup[item_id] for item_id in instance_ids if item_id in label_lookup]
        genre_labels = [label_lookup[item_id] for item_id in genre_ids if item_id in label_lookup]
        entity_type = resolution.get("entity_type_override", "") or derive_entity_type(instance_labels)
        release_year = claim_first_year(entity, "P577")
        genres = sorted({label for label in genre_labels if label})
        categories = map_categories(entity_type, genres)
        category_source = "wikidata"
        category_source_url = f"https://www.wikidata.org/wiki/{wikidata_id}"
        category_fetched_at = utc_now()
        category_confidence = "high" if genres or entity_type != "unknown" else ""
        rating = extract_wikidata_rating(entity, label_lookup, wikidata_id)
        metadata_sources.append("wikidata")

        mobygames_values = claim_values(entity, "P11688")
        mobygames_id = ""
        if mobygames_values:
            first_value = mobygames_values[0]
            mobygames_id = str(first_value if not isinstance(first_value, dict) else first_value.get("id", ""))
        moby_url_override = url_overrides.get(canonical_slug)
        moby_url = ""
        if moby_url_override and moby_url_override.source_url:
            moby_url = moby_url_override.source_url
        elif mobygames_id:
            moby_url = f"https://www.mobygames.com/game/{mobygames_id}/"
        if moby_url:
            moby = fetch_mobygames_metadata(conn, moby_url)
            if moby.get("genres"):
                moby_genres = [part.strip() for part in moby["genres"].split(";") if part.strip()]
                genres = sorted(set(genres) | set(moby_genres))
                categories = map_categories(entity_type, genres)
                category_source = "wikidata;mobygames" if category_source else "mobygames"
                category_source_url = moby_url
                category_fetched_at = moby.get("rating_fetched_at") or utc_now()
                category_confidence = "medium"
                metadata_sources.append("mobygames")
            if moby.get("rating_value") and not rating["rating_value"]:
                rating = {
                    "rating_value": moby.get("rating_value", ""),
                    "rating_scale": moby.get("rating_scale", ""),
                    "rating_count": moby.get("rating_count", ""),
                    "rating_source": moby.get("rating_source", ""),
                    "rating_url": moby.get("rating_url", ""),
                    "rating_fetched_at": moby.get("rating_fetched_at", ""),
                    "rating_confidence": moby.get("rating_confidence", ""),
                }
                metadata_sources.append("mobygames")
            if moby.get("notes"):
                notes.append(moby["notes"])

    canonical_title = canonical_title or representative
    canonical_slug = canonical_slug or slugify_title(canonical_title) if resolution["match_status"] == "matched" else ""

    wikipedia_url = url_overrides.get(canonical_slug).wikipedia_url if canonical_slug in url_overrides and url_overrides[canonical_slug].wikipedia_url else wikipedia_url
    if canonical_slug in url_overrides and url_overrides[canonical_slug].wikidata_id and not wikidata_id:
        wikidata_id = url_overrides[canonical_slug].wikidata_id
    wikidata_url = f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else ""

    master_row = {
        **row,
        "override_applied": override_applied,
        "canonical_title": canonical_title if resolution["match_status"] == "matched" else "",
        "canonical_slug": canonical_slug if resolution["match_status"] == "matched" else "",
        "match_status": resolution["match_status"],
        "match_confidence": resolution["match_confidence"],
        "match_method": resolution["match_method"],
        "match_source": resolution["match_source"],
        "match_source_url": resolution["match_source_url"],
        "match_fetched_at": resolution["match_fetched_at"],
        "entity_type": entity_type,
        "release_year": release_year,
        "wikipedia_url": wikipedia_url,
        "wikidata_id": wikidata_id,
        "wikidata_url": wikidata_url,
        "categories": normalize_semicolon(categories),
        "genres": normalize_semicolon(genres),
        "themes": normalize_semicolon(themes),
        "category_source": category_source,
        "category_source_url": category_source_url,
        "category_fetched_at": category_fetched_at,
        "category_confidence": category_confidence,
        "rating_value": rating["rating_value"],
        "rating_scale": rating["rating_scale"],
        "rating_count": rating["rating_count"],
        "rating_source": rating["rating_source"],
        "rating_url": rating["rating_url"],
        "rating_fetched_at": rating["rating_fetched_at"],
        "rating_confidence": rating["rating_confidence"],
        "metadata_sources": normalize_semicolon(metadata_sources),
        "notes": normalize_semicolon(notes),
    }

    alias_row = {
        "normalized_title": row["normalized_title"],
        "representative_title": row["representative_title"],
        "canonical_title": master_row["canonical_title"],
        "canonical_slug": master_row["canonical_slug"],
        "match_status": master_row["match_status"],
        "match_confidence": master_row["match_confidence"],
        "match_method": master_row["match_method"],
        "override_applied": override_applied,
        "match_source": master_row["match_source"],
        "match_source_url": master_row["match_source_url"],
    }

    review_row = None
    if resolution["match_status"] == "ambiguous":
        candidate_cols = {}
        for idx, candidate in enumerate(review_candidates[:3], start=1):
            candidate_cols[f"candidate_{idx}_title"] = candidate.label
            candidate_cols[f"candidate_{idx}_url"] = candidate.url
        review_row = {
            "normalized_title": row["normalized_title"],
            "representative_title": row["representative_title"],
            "match_status": "ambiguous",
            "match_confidence": master_row["match_confidence"],
            "failure_reason": master_row["notes"],
            **candidate_cols,
        }
    elif resolution["match_status"] == "unmatched":
        review_row = {
            "normalized_title": row["normalized_title"],
            "representative_title": row["representative_title"],
            "match_status": "unmatched",
            "match_confidence": master_row["match_confidence"],
            "failure_reason": master_row["notes"],
            "candidate_1_title": "",
            "candidate_1_url": "",
            "candidate_2_title": "",
            "candidate_2_url": "",
            "candidate_3_title": "",
            "candidate_3_url": "",
        }
    if review_row is not None and resolution["match_status"] == "unmatched":
        review_row["failure_reason"] = f"{master_row['notes']} | search_variants={'; '.join(search_variants)}".strip(" |")
    return master_row, alias_row, review_row


def run_build(args: argparse.Namespace) -> int:
    master_input = Path(args.input_master)
    issue_input = Path(args.input_issues)
    output_dir = Path(args.output_dir)
    cache_db = Path(args.cache_db)
    review_csv = Path(args.review_csv)

    if args.refresh_cache and cache_db.exists():
        conn = connect_cache(cache_db)
        try:
            reset_enrichment_cache(conn)
        finally:
            conn.close()

    alias_overrides, entity_overrides, url_overrides, rejections = load_overrides(args)
    conn = connect_cache(cache_db)

    master_rows = sorted(read_csv(master_input), key=lambda row: row["normalized_title"])
    issue_rows = sorted(read_csv(issue_input), key=lambda row: (row["archive_name"], row["normalized_title"]))
    existing_master = output_master_index(output_dir / "enriched_master_games.csv") if args.resume else {}

    if args.only_unmatched or args.only_ambiguous:
        existing_path = output_dir / "enriched_master_games.csv"
        existing = output_master_index(existing_path)
        if args.only_unmatched:
            master_rows = [row for row in master_rows if existing.get(row["normalized_title"], {}).get("match_status") == "unmatched"]
        else:
            master_rows = [row for row in master_rows if existing.get(row["normalized_title"], {}).get("match_status") == "ambiguous"]
    elif args.resume and existing_master:
        master_rows = [row for row in master_rows if row["normalized_title"] not in existing_master]

    if args.limit is not None:
        master_rows = master_rows[: args.limit]

    enriched_master: list[dict[str, str]] = list(existing_master.values()) if args.resume else []
    aliases: list[dict[str, str]] = []
    ambiguous_rows: list[dict[str, str]] = []
    unmatched_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, str]] = []
    master_by_title: dict[str, dict[str, str]] = dict(existing_master)

    try:
        for index, row in enumerate(master_rows, start=1):
            master_row, alias_row, review_row = enrich_row(
                conn,
                row,
                alias_overrides,
                entity_overrides,
                url_overrides,
                rejections,
            )
            enriched_master.append(master_row)
            aliases.append(alias_row)
            master_by_title[row["normalized_title"]] = master_row
            if master_row["match_status"] == "ambiguous":
                ambiguous_rows.append(
                    {
                        "normalized_title": row["normalized_title"],
                        "representative_title": row["representative_title"],
                        "match_status": "ambiguous",
                        "match_confidence": master_row["match_confidence"],
                        "failure_reason": master_row["notes"],
                        "candidate_1_title": review_row.get("candidate_1_title", "") if review_row else "",
                        "candidate_1_url": review_row.get("candidate_1_url", "") if review_row else "",
                        "candidate_2_title": review_row.get("candidate_2_title", "") if review_row else "",
                        "candidate_2_url": review_row.get("candidate_2_url", "") if review_row else "",
                        "candidate_3_title": review_row.get("candidate_3_title", "") if review_row else "",
                        "candidate_3_url": review_row.get("candidate_3_url", "") if review_row else "",
                    }
                )
            elif master_row["match_status"] == "unmatched":
                unmatched_rows.append(
                    {
                        "normalized_title": row["normalized_title"],
                        "representative_title": row["representative_title"],
                        "match_status": "unmatched",
                        "match_confidence": master_row["match_confidence"],
                        "failure_reason": master_row["notes"],
                        "search_variants": "; ".join([]),
                    }
                )
            if review_row is not None:
                review_rows.append(review_row)
            if index % 50 == 0:
                write_current_outputs(output_dir, enriched_master, issue_rows, review_csv, review_rows)

        write_current_outputs(output_dir, enriched_master, issue_rows, review_csv, review_rows)
    finally:
        conn.close()
    return 0


def main() -> int:
    return run_build(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
