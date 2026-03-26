# Published Result Set Audit

- raw master rows: 3856
- cleaned master rows: 2602
- raw issue/title rows: 7407
- cleaned issue/title rows: 3965
- publishable clustered master rows: 1711
- publishable clustered issue/title rows: 2183
- excluded non-game/media clusters: 83
- dropped noisy rows: 3442
- unresolved issues: 0

Cleaning rules used:
- drop obvious issue-code/track rows like `CBS0100 (Track 01)`
- drop obvious UI/settings/manual/software noise
- keep multi-word titles that survive the blacklist
- keep title-cased single-word titles only when they are not obvious noise

Publishable tier:
- clusters aliases under a stable `game_id`
- normalizes disc-only version/demo suffixes for clustering
- excludes utilities, editors/SDKs, guide media, and disc-noise rows
- carries conservative cluster-level match/audit columns from the prior enriched release

Original raw data remains untouched in the source snapshot.
