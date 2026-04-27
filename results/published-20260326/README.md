# Published Results (20260326)

This directory is the public-facing clustered result set for the Computer Bild Spiele title reconstruction project.

It is derived from the preserved raw snapshot in:
- `results/vps-linux-full-rerun-20260325`

## Which file should be used publicly?

Use:
- `publishable_master_games.csv`

That is the best current public game list.

For issue-level detail, use:
- `publishable_issue_titles.csv`

## Files

- `publishable_master_games.csv`
  - one row per clustered game keyed by `game_id`
  - includes audit columns and conservative carried match status

- `publishable_issue_titles.csv`
  - one row per `issue_code + game_id`
  - preserves observed-title provenance and carried cluster match fields

- `excluded_non_game_titles.csv`
  - auditable list of utilities, editors, guide media, and disc-noise clusters removed from the canonical public game tables

- `final_unresolved_issues.csv`
  - unresolved tail from the raw extraction run

- `audit_summary.md`
  - summary of the publishable cleanup and clustering pass

- `unresolved_summary.md`
  - short summary of the unresolved tail

## Current counts

- `publishable_master_games.csv`: 1642 rows
- `publishable_issue_titles.csv`: 2125 rows
- `excluded_non_game_titles.csv`: 114 rows
- `final_unresolved_issues.csv`: 0 rows

## Important caveat

This is a best-effort public game catalog. Observed CBS titles remain distinct from external canonical entity fields, and blank metadata is preferred over weak guesses.
