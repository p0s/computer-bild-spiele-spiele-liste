# Contributing

This repository publishes both extraction code and an immutable, attributed dataset snapshot. Keep changes reviewable and preserve that distinction.

## Local verification

Python 3.10 or newer and `uv` are required for the complete gate. Python 3.10 installs the small `tomli` compatibility dependency; newer Python versions use the standard library. Run:

```bash
uv run --group dev ./scripts/check_repo.sh
```

The gate compiles the Python sources, runs every unit test, checks worker-script syntax, validates the relational data contract and frozen hashes, regenerates the publishable layer in a temporary directory, and compares it byte-for-byte with the checked-in snapshot.

## Changing code

- Add a focused unit test for behavior changes.
- Keep network access outside deterministic release builds. Export network lookup evidence to a pinned CSV before building an enriched release.
- Never weaken archive path, source-integrity, or VPS exact-target checks to make an input pass.
- Do not commit local databases, caches, worker logs, review scratch files, or credentials.

## Changing data

- Do not edit generated canonical CSV rows by hand.
- Put durable decisions in the appropriate `data/manual_*.csv` policy file, then regenerate the published and enriched snapshots.
- Preserve `game_id`. If two IDs merge, add a redirect in `data/manual_cluster_overrides.csv`; never silently recycle an ID.
- Re-run `uv run python scripts/release_contract.py write` only after every intended generated file is final. Review the manifest diff and run the full gate afterward.
- Keep unresolved sources and pending lookups explicit. Missing evidence is not evidence of no match.

Code is MIT-licensed. Dataset and documentation contributions are accepted under CC BY 4.0 as described in `LICENSE-DATA.md`.
