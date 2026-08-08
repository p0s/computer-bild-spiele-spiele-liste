# Raw Candidate Snapshot (20260325)

This directory is the compact, immutable publication input for the `20260326` public release. It allows the cleaned and clustered CSVs to be regenerated without re-downloading and scanning the roughly 949 GB Internet Archive source collection.

The candidate files are content-preserving copies of the completed VPS extraction snapshot, normalized from CRLF to LF for portable Git storage. The local worker status recorded digest `816a6b6fe1d63a25e46d0b1d4552dfa48e904817`.

- `issue_titles.csv`: observed issue-level title candidates
- `master_games.csv`: raw normalized-title aggregation
- `unresolved_issues.csv`: extraction failures reported by the worker
- `source_archives.csv`: immutable source archive inventory and checksums
- `manifest.json`: artifact provenance and SHA-256 digests

This is raw candidate evidence, not the recommended end-user game list. Use the corresponding `results/published-*` directory for public consumption.
