# Enriched Results

This directory contains the enriched game-entity layer built on top of the current publishable CBS title list.

Current enriched snapshot:

- canonical master rows: `2018`
- enriched issue/title rows: `2631`
- ambiguous titles: `165`
- unmatched titles: `1672`

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
