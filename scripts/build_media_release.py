#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.media_common import (
    MEDIA_MANIFEST_FIELDS,
    archive_download_url,
    asset_id,
    load_media_overrides,
    read_csv,
    select_issue_sources,
    write_csv,
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


def truthy(value: str) -> str:
    return "true" if value.casefold() in {"1", "true", "yes"} else "false"


def build_release(
    published_dir: Path,
    enriched_dir: Path,
    overrides_path: Path,
    evidence_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overrides = load_media_overrides(overrides_path)
    issue_codes = {row["issue_code"] for row in read_csv(published_dir / "publishable_issue_titles.csv")}
    ia_rows = read_csv(evidence_dir / "ia_files.csv")
    selected_issues, rejected_issues = select_issue_sources(issue_codes, ia_rows, overrides)
    asset_evidence = {
        (row["subject_type"], row["subject_id"]): row for row in read_csv(evidence_dir / "asset_evidence.csv")
    }
    commons_rows = read_csv(evidence_dir / "commons_candidates.csv")
    commons_by_game: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in commons_rows:
        commons_by_game[row["subject_id"]].append(row)

    manifest: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for issue_code in sorted(issue_codes):
        override = overrides.get(("issue", issue_code), {})
        if issue_code in rejected_issues:
            audit.append(
                {
                    "subject_type": "issue",
                    "subject_id": issue_code,
                    "candidate_count": 0,
                    "selected_source_file": "",
                    "review_status": "unavailable",
                    "review_reason": rejected_issues[issue_code],
                }
            )
            continue
        source = selected_issues[issue_code]
        evidence = asset_evidence.get(("issue", issue_code))
        if not evidence:
            raise ValueError(f"asset evidence missing for issue: {issue_code}")
        source_file = source["source_file"]
        manifest.append(
            {
                "asset_id": asset_id("issue", issue_code),
                "subject_type": "issue",
                "subject_id": issue_code,
                "media_role": "disc_face",
                "featured_rank": override.get("featured_rank", ""),
                "source_provider": "Internet Archive",
                "source_record_id": source["source_record_id"],
                "source_file": source_file,
                "source_archive_member": evidence["source_archive_member"],
                "source_page_url": "https://archive.org/details/cbs-2000-09",
                "source_download_url": source.get("source_download_url")
                or archive_download_url(source["source_record_id"], source_file),
                "source_sha1": source["source_sha1"],
                "source_member_sha256": evidence["source_member_sha256"],
                "source_revision": source["source_revision"],
                "source_mime": evidence["source_mime"],
                "source_width": evidence["source_width"],
                "source_height": evidence["source_height"],
                "creator_name": source.get("source_creator", ""),
                "creator_url": "",
                "license_id": "",
                "license_name": "",
                "license_url": source.get("source_license_url", ""),
                "credit_line": "Disc scan from Internet Archive item cbs-2000-09.",
                "attribution_required": "true",
                "rights_status": "not_specified",
                "review_status": "approved",
                "alt_en": f"Disc face for Computer Bild Spiele issue {issue_code}.",
                "alt_de": f"Datenträger von Computer Bild Spiele, Ausgabe {issue_code}.",
                "caption_en": f"Original cover-disc scan for issue {issue_code}.",
                "caption_de": f"Originalscan des Heft-Datenträgers für Ausgabe {issue_code}.",
                "export_relpath": evidence["export_relpath"],
            }
        )
        audit.append(
            {
                "subject_type": "issue",
                "subject_id": issue_code,
                "candidate_count": 1,
                "selected_source_file": source_file,
                "review_status": "approved",
                "review_reason": "disc_face_scan",
            }
        )

    matched_games = [
        row
        for row in read_csv(enriched_dir / "enriched_master_games.csv")
        if row.get("match_status") == "matched" and row.get("wikidata_id")
    ]
    for game in sorted(matched_games, key=lambda row: row["game_id"]):
        game_id = game["game_id"]
        candidates = commons_by_game.get(game_id, [])
        override = overrides.get(("game", game_id), {})
        if override.get("action") != "approve":
            status = "rejected" if override.get("action") == "reject" else "unavailable"
            audit.append(
                {
                    "subject_type": "game",
                    "subject_id": game_id,
                    "candidate_count": len(candidates),
                    "selected_source_file": override.get("source_file", ""),
                    "review_status": status,
                    "review_reason": override.get("reason", "no_cover_candidate"),
                }
            )
            continue
        source_name = override.get("source_file", "")
        selected = [row for row in candidates if row["source_file"].casefold() == source_name.casefold()]
        if len(selected) != 1:
            raise ValueError(f"approved Commons source is missing or ambiguous: {game_id}: {source_name}")
        source = selected[0]
        evidence = asset_evidence.get(("game", game_id))
        if not evidence:
            raise ValueError(f"asset evidence missing for game: {game_id}")
        title = game.get("canonical_title") or game["representative_title"]
        manifest.append(
            {
                "asset_id": asset_id("game", game_id),
                "subject_type": "game",
                "subject_id": game_id,
                "media_role": "cover_art",
                "featured_rank": override.get("featured_rank", ""),
                "source_provider": "Wikimedia Commons",
                "source_record_id": game["wikidata_id"],
                "source_file": source["source_file"],
                "source_archive_member": "",
                "source_page_url": source["source_page_url"],
                "source_download_url": source["source_download_url"],
                "source_sha1": source["source_sha1"],
                "source_member_sha256": evidence["source_member_sha256"],
                "source_revision": source["source_revision"],
                "source_mime": evidence["source_mime"],
                "source_width": evidence["source_width"],
                "source_height": evidence["source_height"],
                "creator_name": source["creator_name"],
                "creator_url": source["creator_url"],
                "license_id": source["license_id"],
                "license_name": source["license_name"],
                "license_url": source["license_url"],
                "credit_line": source["credit_line"] or source["creator_name"],
                "attribution_required": truthy(source["attribution_required"]),
                "rights_status": "licensed",
                "review_status": "approved",
                "alt_en": f"Cover art for {title}.",
                "alt_de": f"Covermotiv von {title}.",
                "caption_en": f"Cover art for {title}.",
                "caption_de": f"Covermotiv von {title}.",
                "export_relpath": evidence["export_relpath"],
            }
        )
        audit.append(
            {
                "subject_type": "game",
                "subject_id": game_id,
                "candidate_count": len(candidates),
                "selected_source_file": source["source_file"],
                "review_status": "approved",
                "review_reason": "exact_cover_art",
            }
        )

    return sorted(manifest, key=lambda row: row["asset_id"]), sorted(
        audit, key=lambda row: (row["subject_type"], row["subject_id"])
    )


def artifact_record(path: Path, record_path: str) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": record_path,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "rows": len(read_csv(path)) if path.suffix == ".csv" else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the deterministic CBS media release.")
    parser.add_argument("--published-dir", type=Path, default=ROOT / "results" / "published-20260808")
    parser.add_argument("--enriched-dir", type=Path, default=ROOT / "results" / "enriched-20260808")
    parser.add_argument("--overrides", type=Path, default=ROOT / "data" / "manual_media_overrides.csv")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest, audit = build_release(
        args.published_dir,
        args.enriched_dir,
        args.overrides,
        args.evidence_dir,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "media_manifest.csv"
    audit_path = args.output_dir / "media_audit.csv"
    write_csv(manifest_path, MEDIA_MANIFEST_FIELDS, manifest)
    write_csv(audit_path, AUDIT_FIELDS, audit)

    counts = Counter(row["subject_type"] for row in manifest)
    summary_path = args.output_dir / "audit_summary.md"
    summary_path.write_text(
        "# Media release audit\n\n"
        f"- Approved issue disc images: {counts['issue']}\n"
        f"- Approved game cover images: {counts['game']}\n"
        f"- Audited subjects: {len(audit)}\n"
        f"- Unavailable or rejected subjects: {sum(row['review_status'] != 'approved' for row in audit)}\n",
        encoding="utf-8",
    )
    readme_path = args.output_dir / "README.md"
    readme_path.write_text(
        f"# Media snapshot {args.output_dir.name.removeprefix('media-')}\n\n"
        "This directory contains the reviewed image manifest and its source evidence. "
        "Each approved row records source identity, immutable hashes, dimensions, rights metadata, "
        "localized alt text, and the relative source-export path used for derivative generation.\n\n"
        "Source image bytes are intentionally kept outside this dataset repository.\n",
        encoding="utf-8",
    )
    published_record_path = args.published_dir.resolve().relative_to(ROOT).as_posix()
    enriched_record_path = args.enriched_dir.resolve().relative_to(ROOT).as_posix()
    overrides_record_path = args.overrides.resolve().relative_to(ROOT).as_posix()
    artifact_paths = {
        "README.md": readme_path,
        "asset_evidence.csv": args.evidence_dir / "asset_evidence.csv",
        "audit_summary.md": summary_path,
        "commons_candidates.csv": args.evidence_dir / "commons_candidates.csv",
        overrides_record_path: args.overrides,
        f"{enriched_record_path}/enriched_master_games.csv": args.enriched_dir / "enriched_master_games.csv",
        "ia_files.csv": args.evidence_dir / "ia_files.csv",
        "media_audit.csv": audit_path,
        "media_manifest.csv": manifest_path,
        f"{published_record_path}/publishable_issue_titles.csv": (args.published_dir / "publishable_issue_titles.csv"),
    }
    release_manifest = {
        "release_id": args.output_dir.name.removeprefix("media-"),
        "schema_version": "1.0.0",
        "artifacts": [artifact_record(path, record_path) for record_path, path in sorted(artifact_paths.items())],
    }
    (args.output_dir / "release-manifest.json").write_text(
        json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"media release built: {len(manifest)} approved asset(s), {len(audit)} audited subject(s)")


if __name__ == "__main__":
    main()
