# Computer Bild Spiele Game List

This repo contains the extraction pipeline and the current best public CSV reconstruction of game titles found on `Computer Bild Spiele` cover discs from the `cbs-2000-09` Internet Archive set.

This is an unofficial research dataset. `Computer Bild Spiele`, game titles, and other product names mentioned here may be trademarks of their respective owners. No affiliation with, endorsement by, or sponsorship from any publisher, rights holder, or archive source is implied.

## What Is In The Repo

- `scripts/index_cbs_exes.py`: raw extraction and title-candidate collection
- `scripts/prepare_publishable_results.py`: publishable cleanup, clustering, and exclusion audit
- `scripts/improved_release_common.py`: shared clustering, normalization, and match-audit helpers
- `scripts/build_enriched_release.py`: cluster-aware enrichment rebuild from the published release plus the March 25 enriched baseline
- `scripts/merge_retry_snapshot.py`: overlay a retry snapshot onto the preserved raw base snapshot
- `scripts/release_audit.py`: audit a raw/published/enriched release trio
- `data/manual_content_overrides.csv`: durable non-game/manual content overrides
- `data/manual_rejections.csv`: explicit bad canonical matches that must be rejected

## Current Canonical Release

- published snapshot: `results/published-20260326/`
- enriched snapshot: `results/enriched-20260326/`
- previous preserved release: `results/published-20260325/` and `results/enriched-20260325/`

Current `20260326` counts:

- publishable master rows: `1642`
- publishable issue/title rows: `2125`
- excluded non-game/media clusters: `114`
- unresolved issues: `0`
- enriched matched rows: `141`
- enriched ambiguous rows: `141`
- enriched unmatched rows: `1360`
- explicit match demotions: `13`

The tracked CSVs are a best-effort public dataset, not a claim of perfect completeness.

## Data Contract

The canonical public release is now cluster-based.

- `publishable_master_games.csv` is one row per clustered game keyed by `game_id`
- `publishable_issue_titles.csv` is one row per `issue_code + game_id`
- observed CBS title fields stay separate from external canonical entity fields
- utilities, editors/SDKs, guide media, and disc-noise rows are excluded from the canonical public game outputs and listed in `excluded_non_game_titles.csv`

Important public fields:

- `game_id`: stable join key across published and enriched outputs
- `representative_title`: best observed CBS-facing display title for the cluster
- `canonical_title`, `wikidata_id`, `wikipedia_url`: external entity fields, carried conservatively
- `content_class`: `game`, `expansion_or_addon`, `mod_or_conversion`, `utility`, `editor_sdk`, `guide_media`, or `disc_noise`
- `cleanup_flags`: normalization operations applied during clustering
- `merge_confidence`: confidence in the automatic alias merge
- `match_action`, `match_notes`: what the match audit did to the inherited canonical match
- `data_quality_score`: 0-100 heuristic summary of structural and metadata quality

The key design rule is still that enrichment is separate from extraction. Blanks are preferred over weak guesses.

## Pipeline

The pipeline is intentionally layered:

1. raw extraction from cover-disc archives
2. cleaned issue-level publishable candidates
3. clustered public release outputs
4. cluster-aware enrichment rebuild
5. release audit

The `20260326` publishable step is deterministic from the preserved March 25 rerun raw snapshot plus the tracked manual policy files and March 25 enriched baseline.

## Commands

Generate the canonical published release:

```bash
python3 scripts/prepare_publishable_results.py \
  --input-dir results/vps-linux-full-rerun-20260325 \
  --output-dir results/published-20260326 \
  --baseline-enriched-master results/enriched-20260325/enriched_master_games.csv \
  --manual-content-overrides data/manual_content_overrides.csv \
  --manual-rejections data/manual_rejections.csv
```

Build the cluster-aware enriched release:

```bash
python3 scripts/build_enriched_release.py \
  --input-master results/published-20260326/publishable_master_games.csv \
  --input-issues results/published-20260326/publishable_issue_titles.csv \
  --baseline-enriched-master results/enriched-20260325/enriched_master_games.csv \
  --output-dir results/enriched-20260326 \
  --manual-rejections data/manual_rejections.csv \
  --review-csv results/reference_review-20260326.csv
```

Audit the release trio:

```bash
python3 scripts/release_audit.py \
  --raw-dir results/vps-linux-full-rerun-20260325 \
  --published-dir results/published-20260326 \
  --enriched-dir results/enriched-20260326
```

For unresolved-only overlays against the March 24 raw snapshot, use `scripts/merge_retry_snapshot.py`.

## Outputs

Published release:

- `publishable_master_games.csv`
- `publishable_issue_titles.csv`
- `excluded_non_game_titles.csv`
- `final_unresolved_issues.csv`
- `audit_summary.md`
- `unresolved_summary.md`

Enriched release:

- `enriched_master_games.csv`
- `enriched_issue_titles.csv`
- `title_aliases.csv`
- `ambiguous_matches.csv`
- `unmatched_titles.csv`
- `match_demotions.csv`
- `source_attribution.csv`
- `enrichment_audit.md`

Local-only artifacts:

- `results/enrichment.sqlite`
- `results/reference_review*.csv`

## Licensing

- code in this repo is licensed under the MIT License: `LICENSE`
- dataset and documentation files are licensed under CC BY 4.0: `LICENSE-DATA.md`
