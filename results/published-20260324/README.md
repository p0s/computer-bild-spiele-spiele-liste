# Published Results (2026-03-24)

This directory is the **public-facing derived result set** for the Computer Bild Spiele title reconstruction project.

It is derived from the preserved raw VPS snapshot in:
- `results/vps-linux-full-20260324/`

The raw snapshot remains untouched.

## Which file should be used publicly?

Use:
- `publishable_master_games.csv`

That is the best current public title list.

For issue-level detail, use:
- `publishable_issue_titles.csv`

## Files

### Public-facing

- `publishable_master_games.csv`
  - one row per cleaned normalized title
  - best current list for website/repo publication

- `publishable_issue_titles.csv`
  - one row per issue/title pair
  - use when you want to show which issue contained which title

- `final_unresolved_issues.csv`
  - issues still unresolved after the VPS run
  - these are mostly retry/network cases

- `audit_summary.md`
  - explains how the cleaned and publishable sets were derived

- `unresolved_summary.md`
  - short summary of the unresolved tail

Additional broader local audit artifacts may exist outside the tracked public repo,
but they are intentionally not published here.

## Current counts

- `publishable_master_games.csv`: 1407 rows
- `publishable_issue_titles.csv`: 1718 rows
- `final_unresolved_issues.csv`: 35 rows

## Important caveat

This is a **best-effort cleaned list**, not a guaranteed perfect canonical archive.

Known limitations:
- some true titles may still be missing
- some remaining rows may still be borderline or noisy
- unresolved late-year DVD/Gold issues still exist

## Recommended interpretation

- treat `publishable_master_games.csv` as the current best public list
- treat `publishable_issue_titles.csv` as the backing issue table
- treat `final_unresolved_issues.csv` as the transparent follow-up queue
