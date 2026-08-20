# Computer Bild Spiele Game List

[![CI](https://github.com/p0s/computer-bild-spiele-spiele-liste/actions/workflows/ci.yml/badge.svg)](https://github.com/p0s/computer-bild-spiele-spiele-liste/actions/workflows/ci.yml)

This repo contains the extraction pipeline and the current best public CSV reconstruction of game titles found on `Computer Bild Spiele` cover discs from the `cbs-2000-09` Internet Archive set.

This is an unofficial research dataset. `Computer Bild Spiele`, game titles, and other product names mentioned here may be trademarks of their respective owners. No affiliation with, endorsement by, or sponsorship from any publisher, rights holder, or archive source is implied.

## What Is In The Repo

- `scripts/index_cbs_exes.py`: raw extraction and title-candidate collection
- `scripts/prepare_publishable_results.py`: publishable cleanup, clustering, and exclusion audit
- `scripts/improved_release_common.py`: shared clustering, normalization, and match-audit helpers
- `scripts/build_enriched_release.py`: cluster-aware enrichment rebuild from a published release plus a pinned baseline
- `scripts/merge_retry_snapshot.py`: overlay a retry snapshot onto the preserved raw base snapshot
- `scripts/release_audit.py`: audit a raw/published/enriched release trio
- `scripts/release_contract.py`: validate schemas, keys, redirects, state semantics, and frozen artifact hashes
- `scripts/fetch_media_evidence.py`: discover, verify, and extract reviewed issue and game imagery
- `scripts/build_media_release.py`: build the deterministic public media manifest and audit
- `data/manual_content_overrides.csv`: durable non-game/manual content overrides
- `data/manual_candidate_overrides.csv`: reviewed source-disc candidates that automated extraction missed
- `data/manual_cluster_overrides.csv`: reviewed alias redirects for stable game clusters
- `data/manual_rejections.csv`: explicit bad canonical matches that must be rejected

## Current Canonical Release

- published snapshot: `results/published-20260808/`
- enriched snapshot: `results/enriched-20260808/`
- media snapshot: `results/media-20260809/`
- preserved historical release: `results/published-20260326/` and `results/enriched-20260326/`

Current `20260808` counts:

- publishable master rows: `1601`
- publishable issue/title rows: `2100`
- excluded non-game/media clusters: `148`
- unresolved source archives: `25`
- source archives inventoried: `193`
- source archives with public game rows: `168`
- enriched matched rows: `121`
- enriched ambiguous rows: `27`
- enriched unmatched rows: `1104`
- enriched pending lookups: `349`
- explicit match demotions: `0`
- approved issue disc images: `167`
- approved game cover images: `1`

The tracked CSVs are a best-effort public dataset, not a claim of perfect completeness.

## Data Contract

The canonical public release is now cluster-based.

The versioned contract is documented in `docs/DATA-CONTRACT.md`, described for tools by `datapackage.json` and `schemas/`, and frozen by the release manifest in the published snapshot.

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

## Operational Integrity

- downloaded source archives are accepted only when byte size and SHA-1 match the HTTPS metadata record
- archive member paths are validated before extraction, and extracted symbolic links are rejected
- VPS result bundles are checksum-verified and structurally inspected before extraction; their individual files are verified before an atomic move into `results/`
- VPS sync is restricted to the exact configured repository path and either one unambiguous running worker container or an explicitly named container

These checks establish integrity against transfer corruption, path traversal, and accidental target selection. The upstream archive metadata remains a trusted input; the tracked raw manifest and release manifest freeze the exact values used for this published snapshot.

## Pipeline

The pipeline is intentionally layered:

1. raw extraction from cover-disc archives
2. cleaned issue-level publishable candidates
3. clustered public release outputs
4. cluster-aware enrichment rebuild
5. media evidence and reviewed image manifest
6. release audit

The worker exports `source_archives.csv` directly from its database, including source size and SHA-1, so future raw snapshots carry their own provenance. Retry overlays merge that inventory together with issue and unresolved rows. Strategy and HTTP caches are versioned, failed requests do not poison persistent caches, and SQLite writes use WAL plus batched candidate transactions.

The `20260808` publishable step is reproducible from the tracked March 25 raw-candidate snapshot, the immutable March 26 enriched baseline, the pinned reference-result export, and the tracked manual policy files. Extraction completion and public game coverage are measured separately; a source archive with no public game rows remains explicitly unresolved.

## Commands

Run the complete local gate with Python 3.10+ and `uv`:

```bash
uv run --group dev ./scripts/check_repo.sh
```

Generate the canonical published release:

```bash
python3 scripts/prepare_publishable_results.py \
  --input-dir results/raw-candidates-20260325 \
  --output-dir results/published-20260808 \
  --baseline-enriched-master results/enriched-20260326/enriched_master_games.csv \
  --manual-content-overrides data/manual_content_overrides.csv \
  --manual-candidate-overrides data/manual_candidate_overrides.csv \
  --manual-cluster-overrides data/manual_cluster_overrides.csv \
  --manual-rejections data/manual_rejections.csv
```

Build the cluster-aware enriched release:

```bash
python3 scripts/build_enriched_release.py \
  --input-master results/published-20260808/publishable_master_games.csv \
  --input-issues results/published-20260808/publishable_issue_titles.csv \
  --baseline-enriched-master results/enriched-20260326/enriched_master_games.csv \
  --output-dir results/enriched-20260808 \
  --manual-rejections data/manual_rejections.csv \
  --reference-results-input results/reference_results-20260325.csv \
  --review-csv results/reference_review-20260808.csv
```

Audit the release trio:

```bash
python3 scripts/release_audit.py \
  --raw-dir results/raw-candidates-20260325 \
  --published-dir results/published-20260808 \
  --enriched-dir results/enriched-20260808
```

Validate the machine-readable data contract and frozen artifact manifest:

```bash
python3 scripts/release_contract.py check
```

Build the media evidence and release using a cache and source-export directory outside the repository. The acquisition step requires `lsar` and `unar`; source images remain in the export directory and are not tracked here.

```bash
python3 scripts/fetch_media_evidence.py \
  --cache-dir /tmp/cbs-media-cache \
  --export-dir /tmp/cbs-media-export \
  --evidence-dir results/media-20260809

python3 scripts/build_media_release.py \
  --evidence-dir results/media-20260809 \
  --output-dir results/media-20260809
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
- `release-manifest.json`

Enriched release:

- `enriched_master_games.csv`
- `enriched_issue_titles.csv`
- `title_aliases.csv`
- `ambiguous_matches.csv`
- `unmatched_titles.csv`
- `pending_lookups.csv`
- `match_demotions.csv`
- `source_attribution.csv`
- `enrichment_audit.md`

Media release:

- `media_manifest.csv`
- `media_audit.csv`
- `ia_files.csv`
- `commons_candidates.csv`
- `asset_evidence.csv`
- `audit_summary.md`
- `release-manifest.json`

Local-only artifacts:

- `results/enrichment.sqlite`
- newly generated `results/reference_review*.csv` working queues; the March 25 review and lookup-result exports are pinned tracked inputs

## Licensing

- code in this repo is licensed under the MIT License: `LICENSE`
- dataset and documentation files are licensed under CC BY 4.0: `LICENSE-DATA.md`
