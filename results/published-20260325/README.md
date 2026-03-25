# Published Results (2026-03-25)

This directory is the public-facing derived result set for the Computer Bild Spiele title reconstruction project.

It is derived from the preserved raw rerun snapshot in:
- `results/vps-linux-full-rerun-20260325/`

The March 24, 2026 release remains preserved at:
- `results/published-20260324/`

## Which file should be used publicly?

Use:
- `publishable_master_games.csv`

That is the best current public title list from the full rerun.

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
  - unresolved issues after the rerun
  - this snapshot currently has no unresolved rows

- `audit_summary.md`
  - explains how the cleaned and publishable sets were derived

- `unresolved_summary.md`
  - short summary of the unresolved tail

## Current counts

- `publishable_master_games.csv`: 1917 rows
- `publishable_issue_titles.csv`: 2645 rows
- `final_unresolved_issues.csv`: 0 rows

## Important caveat

This is still a best-effort cleaned list, not a guaranteed perfect canonical archive.

Compared with the March 24, 2026 release, this rerun mainly changes coverage:
- it includes many more late-year archives
- it removes the previously unresolved retry queue
- it may still contain borderline extracted titles that need later cleanup review

## Recommended interpretation

- treat `publishable_master_games.csv` as the current best public list
- treat `publishable_issue_titles.csv` as the backing issue table
- treat `final_unresolved_issues.csv` as an empty transparency file for this rerun snapshot
