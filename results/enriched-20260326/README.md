# Enriched Results

This directory contains the cluster-aware enriched CBS release built on top of the canonical `results/published-20260326` outputs.

Current enriched snapshot:

- canonical master rows: `1642`
- enriched issue/title rows: `2125`
- ambiguous titles: `141`
- unmatched titles: `1360`
- match demotions: `13`

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
