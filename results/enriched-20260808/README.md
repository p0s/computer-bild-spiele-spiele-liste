# Enriched Results

This directory contains the cluster-aware enriched CBS release built on top of the canonical `results/published-20260808` outputs.

Current enriched snapshot:

- canonical master rows: `1601`
- enriched issue/title rows: `2100`
- ambiguous titles: `27`
- unmatched titles: `1363`
- pending lookups: `90`
- match demotions: `0`

Files:

- `enriched_master_games.csv`
- `enriched_issue_titles.csv`
- `title_aliases.csv`
- `ambiguous_matches.csv`
- `unmatched_titles.csv`
- `pending_lookups.csv`
- `match_demotions.csv`
- `source_attribution.csv`
- `enrichment_audit.md`

Notes:

- Enrichment is cluster-aware and conservative.
- Raw-QID canonical labels and release-year conflicts are demoted instead of published as confident facts.
- Sparse future-proof metadata columns remain blank unless safely verified.
- Operational lookup failures are reported as pending, never as semantic no-match results.
