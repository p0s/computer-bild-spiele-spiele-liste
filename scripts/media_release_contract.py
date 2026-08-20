#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from scripts.media_common import (
    ASSET_EVIDENCE_FIELDS,
    MEDIA_MANIFEST_FIELDS,
    asset_source_identity,
    load_media_overrides,
    read_csv,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIT_FIELDS = (
    "subject_type",
    "subject_id",
    "candidate_count",
    "selected_source_file",
    "review_status",
    "review_reason",
)


def csv_columns(path: Path) -> tuple[str, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        return tuple(csv.reader(handle).__next__())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_release(
    release_dir: Path,
    published_dir: Path,
    enriched_dir: Path,
    overrides_path: Path,
) -> None:
    release_dir = release_dir.resolve()
    published_dir = published_dir.resolve()
    enriched_dir = enriched_dir.resolve()
    overrides_path = overrides_path.resolve()
    required_files = {
        "README.md",
        "asset_evidence.csv",
        "audit_summary.md",
        "commons_candidates.csv",
        "ia_files.csv",
        "media_audit.csv",
        "media_manifest.csv",
        "release-manifest.json",
    }
    actual_files = {path.name for path in release_dir.iterdir() if path.is_file()}
    if actual_files != required_files:
        raise ValueError(f"media release file set mismatch: {sorted(actual_files ^ required_files)}")

    if csv_columns(release_dir / "media_manifest.csv") != MEDIA_MANIFEST_FIELDS:
        raise ValueError("media manifest columns do not match the versioned contract")
    if csv_columns(release_dir / "asset_evidence.csv") != ASSET_EVIDENCE_FIELDS:
        raise ValueError("asset evidence columns do not match the versioned contract")
    if csv_columns(release_dir / "media_audit.csv") != AUDIT_FIELDS:
        raise ValueError("media audit columns do not match the versioned contract")

    frozen = json.loads((release_dir / "release-manifest.json").read_text(encoding="utf-8"))
    expected_release_id = release_dir.name.removeprefix("media-")
    if frozen.get("release_id") != expected_release_id or frozen.get("schema_version") != "1.0.0":
        raise ValueError("invalid media release identity")
    frozen_artifacts = {row["path"]: row for row in frozen.get("artifacts", [])}
    expected_frozen = {
        "README.md",
        "asset_evidence.csv",
        "audit_summary.md",
        "commons_candidates.csv",
        overrides_path.relative_to(ROOT).as_posix(),
        f"{enriched_dir.relative_to(ROOT).as_posix()}/enriched_master_games.csv",
        "ia_files.csv",
        "media_audit.csv",
        "media_manifest.csv",
        f"{published_dir.relative_to(ROOT).as_posix()}/publishable_issue_titles.csv",
    }
    if set(frozen_artifacts) != expected_frozen:
        raise ValueError("invalid frozen media artifact set")
    for filename, record in frozen_artifacts.items():
        artifact = ROOT / filename if "/" in filename else release_dir / filename
        if record["bytes"] != artifact.stat().st_size or record["sha256"] != sha256(artifact):
            raise ValueError(f"frozen media artifact mismatch: {filename}")
        expected_rows = len(read_csv(artifact)) if artifact.suffix == ".csv" else 0
        if record["rows"] != expected_rows:
            raise ValueError(f"frozen media row count mismatch: {filename}")

    manifest = read_csv(release_dir / "media_manifest.csv")
    audit = read_csv(release_dir / "media_audit.csv")
    assets = read_csv(release_dir / "asset_evidence.csv")
    ia_files = read_csv(release_dir / "ia_files.csv")
    commons = read_csv(release_dir / "commons_candidates.csv")
    overrides = load_media_overrides(overrides_path)

    manifest_keys = {(row["subject_type"], row["subject_id"]) for row in manifest}
    if len(manifest_keys) != len(manifest) or len({row["asset_id"] for row in manifest}) != len(manifest):
        raise ValueError("duplicate media manifest subject or asset id")
    asset_keys = [(row["subject_type"], row["subject_id"]) for row in assets]
    if len(asset_keys) != len(set(asset_keys)):
        raise ValueError("duplicate asset evidence subject")
    if set(asset_keys) != manifest_keys:
        raise ValueError("asset evidence does not exactly cover the media manifest")
    assets_by_key = dict(zip(asset_keys, assets, strict=True))

    featured_ranks = [row["featured_rank"] for row in manifest if row["featured_rank"]]
    if sorted(featured_ranks, key=int) != ["1", "2", "3", "4"]:
        raise ValueError("homepage media ranks must be exactly 1 through 4")

    ia_sources = {row["source_file"] for row in ia_files}
    commons_sources = {(row["subject_id"], row["source_file"]): row for row in commons}
    for row in manifest:
        evidence = assets_by_key[(row["subject_type"], row["subject_id"])]
        if asset_source_identity(evidence) != asset_source_identity(row):
            raise ValueError(f"asset evidence source mismatch: {row['asset_id']}")
        if row["review_status"] != "approved" or not row["credit_line"]:
            raise ValueError(f"unapproved or unattributed media: {row['asset_id']}")
        if not re.fullmatch(r"[a-f0-9]{40}", row["source_sha1"]):
            raise ValueError(f"invalid source SHA-1: {row['asset_id']}")
        if not re.fullmatch(r"[a-f0-9]{64}", row["source_member_sha256"]):
            raise ValueError(f"invalid source SHA-256: {row['asset_id']}")
        if not row["source_page_url"].startswith("https://") or not row["source_download_url"].startswith("https://"):
            raise ValueError(f"non-HTTPS media source: {row['asset_id']}")
        if "utm_" in row["source_download_url"]:
            raise ValueError(f"tracking query in media source: {row['asset_id']}")
        if int(row["source_width"]) <= 0 or int(row["source_height"]) <= 0:
            raise ValueError(f"invalid source dimensions: {row['asset_id']}")
        if not row["alt_en"] or not row["alt_de"] or not row["caption_en"] or not row["caption_de"]:
            raise ValueError(f"missing localized media text: {row['asset_id']}")
        if row["subject_type"] == "issue":
            if row["source_provider"] != "Internet Archive" or row["source_file"] not in ia_sources:
                raise ValueError(f"invalid issue media provenance: {row['asset_id']}")
        else:
            source = commons_sources.get((row["subject_id"], row["source_file"]))
            if (
                row["source_provider"] != "Wikimedia Commons"
                or not source
                or not row["creator_name"]
                or not row["license_name"]
                or not row["license_url"].startswith("https://")
                or overrides.get(("game", row["subject_id"]), {}).get("action") != "approve"
            ):
                raise ValueError(f"invalid game media provenance: {row['asset_id']}")

    issue_keys = {("issue", row["issue_code"]) for row in read_csv(published_dir / "publishable_issue_titles.csv")}
    game_keys = {
        ("game", row["game_id"])
        for row in read_csv(enriched_dir / "enriched_master_games.csv")
        if row["match_status"] == "matched" and row["wikidata_id"]
    }
    expected_audit_keys = issue_keys | game_keys
    audit_keys = {(row["subject_type"], row["subject_id"]) for row in audit}
    if len(audit_keys) != len(audit) or audit_keys != expected_audit_keys:
        raise ValueError("media audit does not exactly cover eligible subjects")
    approved_audit = {(row["subject_type"], row["subject_id"]) for row in audit if row["review_status"] == "approved"}
    if approved_audit != manifest_keys:
        raise ValueError("approved media audit rows do not match the manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a frozen CBS media release.")
    parser.add_argument("--release-dir", type=Path, default=ROOT / "results" / "media-20260809")
    parser.add_argument("--published-dir", type=Path, default=ROOT / "results" / "published-20260808")
    parser.add_argument("--enriched-dir", type=Path, default=ROOT / "results" / "enriched-20260808")
    parser.add_argument("--overrides", type=Path, default=ROOT / "data" / "manual_media_overrides.csv")
    args = parser.parse_args()
    validate_release(args.release_dir, args.published_dir, args.enriched_dir, args.overrides)
    print(f"media release contract valid: {args.release_dir}")


if __name__ == "__main__":
    main()
