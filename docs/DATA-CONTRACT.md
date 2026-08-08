# Dataset contract

The canonical public dataset is a versioned, relational CSV release. Its machine-readable contract is `datapackage.json`; per-table schemas live in `schemas/`, and `results/published-20260808/release-manifest.json` freezes hashes, byte sizes, and row counts for every release input and output.

## Identity

`game_id` is the durable primary key from release `20260326` onward. Display-title, spelling, punctuation, and external-entity corrections must not silently change it. When two IDs are merged, the retired ID is kept in `data/manual_cluster_overrides.csv` as a redirect to one active ID. Redirect sources may not remain active, redirect targets must exist, and redirect cycles are invalid.

The issue-level tables reference `game_id`; enriched and published master tables contain exactly the same active IDs. Consumers should join on `game_id`, never on a title or a third-party entity ID.

## Enrichment state

Entity meaning and network execution are separate:

- `matched / matched / complete`: a supported entity match
- `ambiguous / ambiguous / complete`: reviewable candidates exist, but no entity was selected
- `unmatched / no_match / complete`: a completed search found no supportable match
- `pending / unknown / *`: the lookup was incomplete, deferred, rate-limited, failed, or needs candidate refresh

An operational failure may never be published as a semantic no-match. Ambiguous rows must contain candidate evidence. One Wikidata entity may not be silently assigned to multiple active game IDs.

## Validation and evolution

Run `python3 scripts/release_contract.py check`. It validates table headers and types, primary and foreign keys, score ranges, redirects, status/queue consistency, and every manifest digest. Release identifiers and data-package versions are derived from the `published-YYYYMMDD` directory instead of being hard-coded. Run the `write` command only when intentionally cutting a coherent replacement snapshot, then review and commit the resulting schemas and manifest together.

Breaking field or meaning changes require a major `schema_version`; additive nullable fields require a minor version; documentation-only clarifications require a patch version. A historical release is immutable after publication.
