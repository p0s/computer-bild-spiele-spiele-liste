#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.improved_release_common import (
    MATCH_FIELDS,
    choose_best_match,
    compute_data_quality_score,
    normalize_public_title,
    safe_text,
    semicolon_join,
    slugify,
    to_int,
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
    "developer",
    "publisher",
    "franchise",
    "series",
    "original_language",
    "engine",
    "wikipedia_url",
    "wikidata_id",
    "wikidata_url",
    "official_website",
    "steam_app_id",
    "steam_url",
    "mobygames_url",
    "igdb_id",
    "igdb_url",
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
    "usk_rating",
    "pegi_rating",
    "metadata_sources",
    "match_notes",
    "game_id",
    "first_seen_year",
    "last_seen_issue",
    "last_seen_year",
    "alias_count",
    "alias_titles",
    "legacy_normalized_titles",
    "observed_content_kinds",
    "observed_content_forms",
    "content_class",
    "cleanup_flags",
    "merge_confidence",
    "match_action",
    "data_quality_score",
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
    "game_id",
    "source_title",
    "source_normalized_title",
    "observed_title_variants",
    "source_normalized_variants",
    "occurrence_count_in_issue",
    "content_class",
    "content_form",
    "content_kinds_merged",
    "content_forms_merged",
    "cleanup_flags",
    "merge_confidence",
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
    "match_action",
    "match_notes",
    "data_quality_score",
]

TITLE_ALIAS_FIELDS = [
    "game_id",
    "normalized_title",
    "representative_title",
    "cluster_title",
    "match_status",
    "match_confidence",
    "canonical_title",
    "canonical_slug",
    "alias_match_status",
    "alias_match_confidence",
    "alias_canonical_title",
    "alias_canonical_slug",
    "alias_rejection_notes",
]

AMBIGUOUS_FIELDS = [
    "game_id",
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
    "game_id",
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

MATCH_DEMOTIONS_FIELDS = [
    "game_id",
    "representative_title",
    "demotion_reason",
    "source_alias_titles",
    "candidate_match_statuses",
]


def parse_args() -> argparse.Namespace:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    parser = argparse.ArgumentParser(description="Build the clustered enriched CBS release outputs.")
    parser.add_argument("--input-master", default="results/published-20260326/publishable_master_games.csv")
    parser.add_argument("--input-issues", default="results/published-20260326/publishable_issue_titles.csv")
    parser.add_argument("--baseline-enriched-master", default="results/enriched-20260325/enriched_master_games.csv")
    parser.add_argument("--output-dir", default=f"results/enriched-{today}")
    parser.add_argument("--manual-rejections", default="data/manual_rejections.csv")
    parser.add_argument("--cache-db", default="results/enrichment.sqlite")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only-unmatched", action="store_true")
    parser.add_argument("--only-ambiguous", action="store_true")
    parser.add_argument("--manual-alias-overrides", default="data/manual_alias_overrides.csv")
    parser.add_argument("--manual-entity-overrides", default="data/manual_entity_overrides.csv")
    parser.add_argument("--manual-url-overrides", default="data/manual_url_overrides.csv")
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


def read_baseline_match_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["normalized_title"]: row for row in read_csv(path) if row.get("normalized_title")}


def read_rejections(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        if row.get("normalized_title"):
            grouped[row["normalized_title"]].append(row)
    return grouped


def rejection_reason_for_match(match_row: dict[str, str], rejections: list[dict[str, str]]) -> str:
    if not match_row or not rejections:
        return ""
    canonical_title = safe_text(match_row.get("canonical_title")).casefold()
    canonical_slug = safe_text(match_row.get("canonical_slug")).casefold()
    source = safe_text(match_row.get("match_source")).casefold()
    reasons: list[str] = []
    for rejection in rejections:
        rejected = safe_text(rejection.get("rejected_candidate")).casefold()
        rejected_source = safe_text(rejection.get("source")).casefold()
        if rejected_source and source and rejected_source not in source:
            continue
        if rejected and (rejected == canonical_title or rejected == canonical_slug):
            reasons.append(safe_text(rejection.get("reason")) or "manual rejection")
    return semicolon_join(reasons)


def build_source_attribution_rows() -> list[dict[str, str]]:
    return [
        {
            "source_name": "Clustered Published Release",
            "source_type": "derived-csv",
            "homepage": "",
            "fields_used": "observed titles, clustering, content-class audit columns",
            "attribution_note": "Cluster-level public title reconstruction",
            "terms_note": "Derived from tracked CBS release artifacts",
        },
        {
            "source_name": "Wikimedia Baseline Release",
            "source_type": "derived-csv",
            "homepage": "https://www.wikidata.org/",
            "fields_used": "canonical entity, release year, categories, genres, ratings when present",
            "attribution_note": "Carried forward from the 20260325 alias-level enriched release",
            "terms_note": "Use minimal factual metadata with source attribution",
        },
    ]


def flatten_alias_pairs(issue_rows: list[dict[str, str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for row in issue_rows:
        source_title = safe_text(row.get("source_title"))
        source_normalized_title = safe_text(row.get("source_normalized_title"))
        if source_title or source_normalized_title:
            pairs.append((source_normalized_title, source_title))
        variants = [part.strip() for part in safe_text(row.get("observed_title_variants")).split(";") if part.strip()]
        normalized_variants = [part.strip() for part in safe_text(row.get("source_normalized_variants")).split(";") if part.strip()]
        if len(variants) == len(normalized_variants):
            pairs.extend(zip(normalized_variants, variants))
    return list(dict.fromkeys((pair for pair in pairs if pair[0] or pair[1])))


def build_enrichment_audit(
    *,
    master_rows: list[dict[str, object]],
    issue_rows: list[dict[str, object]],
    demotions: list[dict[str, object]],
) -> str:
    statuses = Counter(safe_text(row.get("match_status")) for row in master_rows)
    quality_80 = sum(1 for row in master_rows if to_int(row.get("data_quality_score")) and to_int(row.get("data_quality_score")) >= 80)
    quality_60 = sum(1 for row in master_rows if to_int(row.get("data_quality_score")) and to_int(row.get("data_quality_score")) >= 60)
    return (
        "# Enrichment Audit\n\n"
        f"- enriched master rows: {len(master_rows)}\n"
        f"- enriched issue rows: {len(issue_rows)}\n"
        f"- matched: {statuses.get('matched', 0)}\n"
        f"- ambiguous: {statuses.get('ambiguous', 0)}\n"
        f"- unmatched: {statuses.get('unmatched', 0)}\n"
        f"- match demotions: {len(demotions)}\n"
        f"- data quality >= 80: {quality_80}\n"
        f"- data quality >= 60: {quality_60}\n"
    )


def write_enriched_readme(path: Path, master_count: int, issue_count: int, ambiguous_count: int, unmatched_count: int, demotions_count: int) -> None:
    text = f"""# Enriched Results

This directory contains the cluster-aware enriched CBS release built on top of the canonical `20260326` published outputs.

Current enriched snapshot:

- canonical master rows: `{master_count}`
- enriched issue/title rows: `{issue_count}`
- ambiguous titles: `{ambiguous_count}`
- unmatched titles: `{unmatched_count}`
- match demotions: `{demotions_count}`

Files:

- `enriched_master_games.csv`
- `enriched_issue_titles.csv`
- `title_aliases.csv`
- `ambiguous_matches.csv`
- `unmatched_titles.csv`
- `match_demotions.csv`
- `source_attribution.csv`
- `enrichment_audit.md`

Notes:

- Enrichment is cluster-aware and conservative.
- Raw-QID canonical labels and release-year conflicts are demoted instead of published as confident facts.
- Sparse future-proof metadata columns remain blank unless safely verified.
"""
    path.write_text(text, encoding="utf-8")


def run_build(args: argparse.Namespace) -> int:
    master_rows = read_csv(Path(args.input_master))
    issue_rows = read_csv(Path(args.input_issues))
    baseline_match_map = read_baseline_match_map(Path(args.baseline_enriched_master))
    rejection_map = read_rejections(Path(args.manual_rejections))
    output_dir = Path(args.output_dir)
    review_csv = Path(args.review_csv)

    master_by_game = {row["game_id"]: dict(row) for row in master_rows if row.get("game_id")}
    issue_rows_by_game: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in issue_rows:
        issue_rows_by_game[safe_text(row.get("game_id"))].append(dict(row))

    enriched_master_rows: list[dict[str, object]] = []
    enriched_issue_rows: list[dict[str, object]] = []
    title_alias_rows: list[dict[str, object]] = []
    ambiguous_rows: list[dict[str, object]] = []
    unmatched_rows: list[dict[str, object]] = []
    match_demotions: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []

    selected_games = sorted(issue_rows_by_game)
    if args.only_unmatched:
        selected_games = [game_id for game_id in selected_games if safe_text(master_by_game.get(game_id, {}).get("match_status")) == "unmatched"]
    elif args.only_ambiguous:
        selected_games = [game_id for game_id in selected_games if safe_text(master_by_game.get(game_id, {}).get("match_status")) == "ambiguous"]
    if args.limit is not None:
        selected_games = selected_games[: args.limit]

    for game_id in selected_games:
        cluster_issue_rows = issue_rows_by_game[game_id]
        published_master = dict(master_by_game.get(game_id, {}))
        first_year = to_int(published_master.get("first_seen_year"))

        alias_pairs = flatten_alias_pairs(cluster_issue_rows)
        alias_match_rows: list[dict[str, object]] = []
        for normalized_title, representative_title in alias_pairs:
            baseline = baseline_match_map.get(normalized_title, {})
            alias = {field: safe_text(baseline.get(field, "")) for field in MATCH_FIELDS}
            alias["normalized_title"] = normalized_title
            alias["source_title"] = representative_title
            alias["alias_rejection_notes"] = rejection_reason_for_match(baseline, rejection_map.get(normalized_title, []))
            alias_match_rows.append(alias)

        best_match, match_action, ranked_candidates = choose_best_match(alias_match_rows, first_year)
        if match_action == "demoted_weak_alias_match" and any(safe_text(row.get("match_status")) == "matched" for row in ranked_candidates):
            match_demotions.append(
                {
                    "game_id": game_id,
                    "representative_title": safe_text(published_master.get("representative_title")),
                    "demotion_reason": safe_text(best_match.get("_match_notes") or best_match.get("notes")),
                    "source_alias_titles": semicolon_join(row.get("source_title", "") for row in ranked_candidates),
                    "candidate_match_statuses": semicolon_join(
                        f"{safe_text(row.get('source_title'))}:{safe_text(row.get('match_status'))}:{safe_text(row.get('canonical_title'))}"
                        for row in ranked_candidates[:5]
                    ),
                }
            )

        notes_parts = [best_match.get("notes"), best_match.get("_match_notes")]
        if match_action != "retained_best_alias_match":
            notes_parts.append(match_action)

        enriched_master = dict(published_master)
        enriched_master.update(
            {
                "canonical_title": safe_text(best_match.get("canonical_title")),
                "canonical_slug": safe_text(best_match.get("canonical_slug"))
                or (slugify(safe_text(best_match.get("canonical_title"))) if safe_text(best_match.get("canonical_title")) else ""),
                "match_status": safe_text(best_match.get("match_status")),
                "match_confidence": safe_text(best_match.get("match_confidence")),
                "match_method": safe_text(best_match.get("match_method")),
                "match_source": safe_text(best_match.get("match_source")),
                "match_source_url": safe_text(best_match.get("match_source_url")),
                "match_fetched_at": safe_text(best_match.get("match_fetched_at")),
                "entity_type": safe_text(best_match.get("entity_type")),
                "release_year": safe_text(best_match.get("release_year")),
                "developer": "",
                "publisher": "",
                "franchise": "",
                "series": "",
                "original_language": "",
                "engine": "",
                "wikipedia_url": safe_text(best_match.get("wikipedia_url")),
                "wikidata_id": safe_text(best_match.get("wikidata_id")),
                "wikidata_url": safe_text(best_match.get("wikidata_url")),
                "official_website": "",
                "steam_app_id": "",
                "steam_url": "",
                "mobygames_url": "",
                "igdb_id": "",
                "igdb_url": "",
                "categories": safe_text(best_match.get("categories")),
                "genres": safe_text(best_match.get("genres")),
                "themes": safe_text(best_match.get("themes")),
                "category_source": safe_text(best_match.get("category_source")),
                "category_source_url": safe_text(best_match.get("category_source_url")),
                "category_fetched_at": safe_text(best_match.get("category_fetched_at")),
                "category_confidence": safe_text(best_match.get("category_confidence")),
                "rating_value": safe_text(best_match.get("rating_value")),
                "rating_scale": safe_text(best_match.get("rating_scale")),
                "rating_count": safe_text(best_match.get("rating_count")),
                "rating_source": safe_text(best_match.get("rating_source")),
                "rating_url": safe_text(best_match.get("rating_url")),
                "rating_fetched_at": safe_text(best_match.get("rating_fetched_at")),
                "rating_confidence": safe_text(best_match.get("rating_confidence")),
                "usk_rating": "",
                "pegi_rating": "",
                "metadata_sources": safe_text(best_match.get("metadata_sources")),
                "match_notes": semicolon_join(notes_parts),
                "match_action": match_action,
            }
        )
        enriched_master["data_quality_score"] = compute_data_quality_score(enriched_master)
        enriched_master_rows.append(enriched_master)

        for cluster_issue_row in cluster_issue_rows:
            enriched_issue = dict(cluster_issue_row)
            enriched_issue.update(
                {
                    "canonical_title": enriched_master.get("canonical_title", ""),
                    "canonical_slug": enriched_master.get("canonical_slug", ""),
                    "match_status": enriched_master.get("match_status", ""),
                    "match_confidence": enriched_master.get("match_confidence", ""),
                    "match_method": enriched_master.get("match_method", ""),
                    "match_source": enriched_master.get("match_source", ""),
                    "match_source_url": enriched_master.get("match_source_url", ""),
                    "match_fetched_at": enriched_master.get("match_fetched_at", ""),
                    "entity_type": enriched_master.get("entity_type", ""),
                    "release_year": enriched_master.get("release_year", ""),
                    "wikipedia_url": enriched_master.get("wikipedia_url", ""),
                    "wikidata_id": enriched_master.get("wikidata_id", ""),
                    "wikidata_url": enriched_master.get("wikidata_url", ""),
                    "categories": enriched_master.get("categories", ""),
                    "genres": enriched_master.get("genres", ""),
                    "themes": enriched_master.get("themes", ""),
                    "category_source": enriched_master.get("category_source", ""),
                    "category_source_url": enriched_master.get("category_source_url", ""),
                    "category_fetched_at": enriched_master.get("category_fetched_at", ""),
                    "category_confidence": enriched_master.get("category_confidence", ""),
                    "rating_value": enriched_master.get("rating_value", ""),
                    "rating_scale": enriched_master.get("rating_scale", ""),
                    "rating_count": enriched_master.get("rating_count", ""),
                    "rating_source": enriched_master.get("rating_source", ""),
                    "rating_url": enriched_master.get("rating_url", ""),
                    "rating_fetched_at": enriched_master.get("rating_fetched_at", ""),
                    "rating_confidence": enriched_master.get("rating_confidence", ""),
                    "metadata_sources": enriched_master.get("metadata_sources", ""),
                    "match_action": enriched_master.get("match_action", ""),
                    "match_notes": enriched_master.get("match_notes", ""),
                    "data_quality_score": enriched_master.get("data_quality_score", ""),
                }
            )
            enriched_issue_rows.append(enriched_issue)

        for normalized_title, representative_title in alias_pairs:
            baseline = baseline_match_map.get(normalized_title, {})
            title_alias_rows.append(
                {
                    "game_id": game_id,
                    "normalized_title": normalized_title,
                    "representative_title": representative_title,
                    "cluster_title": safe_text(enriched_master.get("representative_title")),
                    "match_status": safe_text(enriched_master.get("match_status")),
                    "match_confidence": safe_text(enriched_master.get("match_confidence")),
                    "canonical_title": safe_text(enriched_master.get("canonical_title")),
                    "canonical_slug": safe_text(enriched_master.get("canonical_slug")),
                    "alias_match_status": safe_text(baseline.get("match_status")),
                    "alias_match_confidence": safe_text(baseline.get("match_confidence")),
                    "alias_canonical_title": safe_text(baseline.get("canonical_title")),
                    "alias_canonical_slug": safe_text(baseline.get("canonical_slug")),
                    "alias_rejection_notes": rejection_reason_for_match(baseline, rejection_map.get(normalized_title, [])),
                }
            )

        if safe_text(enriched_master.get("match_status")) == "ambiguous":
            ambiguous_rows.append(
                {
                    "game_id": game_id,
                    "normalized_title": safe_text(enriched_master.get("normalized_title")),
                    "representative_title": safe_text(enriched_master.get("representative_title")),
                    "match_status": "ambiguous",
                    "match_confidence": safe_text(enriched_master.get("match_confidence")),
                    "failure_reason": safe_text(enriched_master.get("match_notes")),
                    "candidate_1_title": safe_text(ranked_candidates[0].get("canonical_title")) if ranked_candidates else "",
                    "candidate_1_url": safe_text(ranked_candidates[0].get("match_source_url")) if ranked_candidates else "",
                    "candidate_2_title": safe_text(ranked_candidates[1].get("canonical_title")) if len(ranked_candidates) > 1 else "",
                    "candidate_2_url": safe_text(ranked_candidates[1].get("match_source_url")) if len(ranked_candidates) > 1 else "",
                    "candidate_3_title": safe_text(ranked_candidates[2].get("canonical_title")) if len(ranked_candidates) > 2 else "",
                    "candidate_3_url": safe_text(ranked_candidates[2].get("match_source_url")) if len(ranked_candidates) > 2 else "",
                }
            )
        elif safe_text(enriched_master.get("match_status")) == "unmatched":
            unmatched_rows.append(
                {
                    "game_id": game_id,
                    "normalized_title": safe_text(enriched_master.get("normalized_title")),
                    "representative_title": safe_text(enriched_master.get("representative_title")),
                    "match_status": "unmatched",
                    "match_confidence": safe_text(enriched_master.get("match_confidence")),
                    "failure_reason": safe_text(enriched_master.get("match_notes")),
                    "search_variants": semicolon_join(part[1] for part in alias_pairs),
                }
            )

        review_rows.extend(ambiguous_rows[-1:] if ambiguous_rows and ambiguous_rows[-1]["game_id"] == game_id else [])

    enriched_master_rows.sort(key=lambda row: safe_text(row.get("normalized_title")))
    enriched_issue_rows.sort(key=lambda row: (safe_text(row.get("archive_name")), safe_text(row.get("game_id"))))
    title_alias_rows = list(
        {
            (row["game_id"], row["normalized_title"], row["representative_title"]): row
            for row in title_alias_rows
        }.values()
    )
    title_alias_rows.sort(key=lambda row: (row["game_id"], row["normalized_title"], row["representative_title"]))
    ambiguous_rows.sort(key=lambda row: (row["representative_title"], row["game_id"]))
    unmatched_rows.sort(key=lambda row: (row["representative_title"], row["game_id"]))
    match_demotions.sort(key=lambda row: (row["representative_title"], row["game_id"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "enriched_master_games.csv", enriched_master_rows, ENRICHED_MASTER_FIELDS)
    write_csv(output_dir / "enriched_issue_titles.csv", enriched_issue_rows, ENRICHED_ISSUE_FIELDS)
    write_csv(output_dir / "title_aliases.csv", title_alias_rows, TITLE_ALIAS_FIELDS)
    write_csv(output_dir / "ambiguous_matches.csv", ambiguous_rows, AMBIGUOUS_FIELDS)
    write_csv(output_dir / "unmatched_titles.csv", unmatched_rows, UNMATCHED_FIELDS)
    write_csv(output_dir / "match_demotions.csv", match_demotions, MATCH_DEMOTIONS_FIELDS)
    write_csv(output_dir / "source_attribution.csv", build_source_attribution_rows(), SOURCE_ATTRIBUTION_FIELDS)
    write_csv(review_csv, review_rows, AMBIGUOUS_FIELDS)
    (output_dir / "enrichment_audit.md").write_text(
        build_enrichment_audit(master_rows=enriched_master_rows, issue_rows=enriched_issue_rows, demotions=match_demotions),
        encoding="utf-8",
    )
    write_enriched_readme(
        output_dir / "README.md",
        master_count=len(enriched_master_rows),
        issue_count=len(enriched_issue_rows),
        ambiguous_count=len(ambiguous_rows),
        unmatched_count=len(unmatched_rows),
        demotions_count=len(match_demotions),
    )
    return 0


def main() -> int:
    return run_build(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
