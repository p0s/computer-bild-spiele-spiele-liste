# Changelog

## 2026.8.8

- Preserved the published March 26 artifacts unchanged and cut a new immutable release instead of rewriting history.
- Removed 20 reviewed utilities, videos, patches, and disc-interface false positives from the public game tables.
- Merged versioned Frontlines: Fuel of War rows, the X³: Reunion rolling demo, and the Zoo Empire CBS edition into their durable game identities.
- Derived release metadata from dated snapshot directories and recorded the pinned reference-result input in the manifest.
- Corrected transient enrichment failures so they remain pending rather than becoming semantic no-match results.
- Fixed worker failure notifications and failed-transfer cleanup, restored Python 3.10 compatibility, and made packaging buildable.
- Added enforced Ruff formatting/linting and source/wheel builds to local and CI quality gates.

## 2026.3.26

- Published a reproducible raw-candidate snapshot with source archive sizes and SHA-1 provenance.
- Added source-level coverage accounting and an explicit unresolved queue for every zero-output archive.
- Added reviewed content, candidate, and cluster policies; recovered strong missed candidates while removing UI, guide, utility, and editor noise.
- Separated semantic entity state from operational lookup state and added reviewable ambiguous and pending queues.
- Added component quality scores, stable ID redirects, Frictionless schemas, a data package, citation metadata, and a frozen release manifest.
- Hardened source downloads, archive extraction, VPS bundle transfer, container selection, and destructive remote target validation.
- Made source provenance a first-class worker export, preserved it through retry overlays, versioned caches by source identity, and batched SQLite writes.
- Added deterministic repository checks and a Python 3.10/3.14 CI matrix.
