# Unresolved Issue Analysis

These unresolved rows come from the preserved VPS snapshot in:
- `results/vps-linux-full-20260324/unresolved_issues.csv`

Summary:
- unresolved issues: `35`
- dominant root cause: `network/download`
- dominant years:
  - `2007`: 22
  - `2008`: 7
  - `2009`: 6
- dominant variants:
  - `DVD`: 17
  - `DVDGold` / `DVDGOLD`: 16
  - `DVDBonus`: 1
  - `DVDSonder`: 1

Interpretation:
- these are mostly not semantic parse failures
- they are mostly late-year Archive.org fetch failures from the VPS run
- that means the current published result set is bounded mainly by transport reliability on those 35 issues, not by the title-cleaning pass

Recommended next step for the unresolved set:
1. rerun only the unresolved archive names
2. keep the same VPS Linux `7z` fallback path
3. add a slightly more patient downloader/backoff for Archive.org on the late DVD/Gold years

Practical implication:
- the current publishable CSVs are good enough to review and publish as a provisional list
- the unresolved 35 are a retry queue, not a full pipeline redesign
