#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "1.0.0"
DEFAULT_REFERENCE_RESULTS = ROOT / "results" / "reference_results-20260325.csv"
INTEGER_FIELDS = {
    "year",
    "release_year",
    "first_seen_year",
    "last_seen_year",
    "issue_count",
    "occurrence_count",
    "alias_count",
    "occurrence_count_in_issue",
    "data_quality_score",
    "observation_confidence_score",
    "cluster_confidence_score",
    "entity_match_score",
    "metadata_completeness_score",
    "source_size_bytes",
    "raw_candidate_rows",
    "cleaned_candidate_rows",
    "dropped_candidate_rows",
    "publishable_game_rows",
    "rating_count",
}
NUMBER_FIELDS = {"rating_value", "rating_scale"}
SCORE_FIELDS = {
    "data_quality_score",
    "observation_confidence_score",
    "cluster_confidence_score",
    "entity_match_score",
    "metadata_completeness_score",
}


@dataclass(frozen=True)
class ResourceSpec:
    name: str
    location: str
    filename: str
    primary_key: tuple[str, ...]
    foreign_resource: str = ""
    foreign_fields: tuple[str, ...] = ()


RESOURCE_SPECS = (
    ResourceSpec("publishable-master-games", "published", "publishable_master_games.csv", ("game_id",)),
    ResourceSpec(
        "publishable-issue-titles",
        "published",
        "publishable_issue_titles.csv",
        ("issue_code", "game_id"),
        "publishable-master-games",
        ("game_id",),
    ),
    ResourceSpec("source-issue-inventory", "published", "source_issue_inventory.csv", ("archive_name",)),
    ResourceSpec("unresolved-issues", "published", "final_unresolved_issues.csv", ("archive_name",)),
    ResourceSpec("enriched-master-games", "enriched", "enriched_master_games.csv", ("game_id",)),
    ResourceSpec(
        "enriched-issue-titles",
        "enriched",
        "enriched_issue_titles.csv",
        ("issue_code", "game_id"),
        "enriched-master-games",
        ("game_id",),
    ),
    ResourceSpec("ambiguous-matches", "enriched", "ambiguous_matches.csv", ("game_id",)),
    ResourceSpec("unmatched-titles", "enriched", "unmatched_titles.csv", ("game_id",)),
    ResourceSpec("pending-lookups", "enriched", "pending_lookups.csv", ("game_id",)),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_if_changed(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != payload:
        path.write_bytes(payload)


def field_descriptor(name: str, *, required: bool) -> dict[str, object]:
    descriptor: dict[str, object] = {"name": name, "type": "string"}
    if name in INTEGER_FIELDS:
        descriptor["type"] = "integer"
    elif name in NUMBER_FIELDS:
        descriptor["type"] = "number"

    constraints: dict[str, object] = {}
    if required:
        constraints["required"] = True
    if name in SCORE_FIELDS:
        constraints.update({"minimum": 0, "maximum": 100})
    if name == "game_id":
        constraints["pattern"] = "^[a-z0-9]+$"
    if name == "source_sha1":
        constraints["pattern"] = "^[0-9a-f]{40}$"
    if name == "wikidata_id":
        constraints["pattern"] = "^Q[1-9][0-9]*$"
    if constraints:
        descriptor["constraints"] = constraints
    return descriptor


def resource_path(spec: ResourceSpec, *, published_dir: Path, enriched_dir: Path) -> Path:
    return (published_dir if spec.location == "published" else enriched_dir) / spec.filename


def schema_document(spec: ResourceSpec, path: Path) -> dict[str, object]:
    header = csv_header(path)
    document: dict[str, object] = {
        "$schema": "https://specs.frictionlessdata.io/schemas/table-schema.json",
        "fields": [field_descriptor(name, required=name in spec.primary_key) for name in header],
        "missingValues": [""],
        "primaryKey": list(spec.primary_key) if len(spec.primary_key) > 1 else spec.primary_key[0],
    }
    if spec.foreign_resource:
        document["foreignKeys"] = [
            {
                "fields": list(spec.foreign_fields) if len(spec.foreign_fields) > 1 else spec.foreign_fields[0],
                "reference": {
                    "resource": spec.foreign_resource,
                    "fields": list(spec.foreign_fields) if len(spec.foreign_fields) > 1 else spec.foreign_fields[0],
                },
            }
        ]
    return document


def release_metadata(published_dir: Path) -> tuple[str, str, str]:
    match = re.fullmatch(r"published-(\d{4})(\d{2})(\d{2})", published_dir.name)
    if not match:
        raise ValueError(f"published directory must end in YYYYMMDD: {published_dir}")
    year, month, day = match.groups()
    return f"{year}{month}{day}", f"{year}-{month}-{day}", f"{year}.{int(month)}.{int(day)}"


def data_package(*, published_dir: Path, enriched_dir: Path) -> dict[str, object]:
    resources: list[dict[str, object]] = []
    for spec in RESOURCE_SPECS:
        path = resource_path(spec, published_dir=published_dir, enriched_dir=enriched_dir)
        resources.append(
            {
                "name": spec.name,
                "path": path.relative_to(ROOT).as_posix(),
                "profile": "tabular-data-resource",
                "format": "csv",
                "mediatype": "text/csv",
                "encoding": "utf-8",
                "schema": f"schemas/{spec.name}.schema.json",
            }
        )
    return {
        "$schema": "https://specs.frictionlessdata.io/schemas/data-package.json",
        "profile": "tabular-data-package",
        "name": "computer-bild-spiele-game-list",
        "title": "Computer Bild Spiele Cover-disc Game List",
        "version": release_metadata(published_dir)[2],
        "licenses": [{"name": "CC-BY-4.0", "path": "LICENSE-DATA.md", "title": "Creative Commons Attribution 4.0"}],
        "resources": resources,
    }


def artifact_paths(
    *,
    raw_dir: Path,
    published_dir: Path,
    enriched_dir: Path,
    reference_results: Path = DEFAULT_REFERENCE_RESULTS,
) -> list[Path]:
    paths = [
        *raw_dir.glob("*"),
        *published_dir.glob("*"),
        *enriched_dir.glob("*"),
        *(path for path in (ROOT / "data").glob("*.csv") if path.name != "manual_media_overrides.csv"),
        *(ROOT / "schemas").glob("*.json"),
        ROOT / "datapackage.json",
        reference_results,
    ]
    manifest_name = "release-manifest.json"
    return sorted(
        {path.resolve() for path in paths if path.is_file() and path.name != manifest_name},
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def file_record(path: Path) -> dict[str, object]:
    record: dict[str, object] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if path.suffix == ".csv":
        record["rows"] = len(read_csv(path))
    return record


def release_manifest(
    *,
    raw_dir: Path,
    published_dir: Path,
    enriched_dir: Path,
    reference_results: Path = DEFAULT_REFERENCE_RESULTS,
) -> dict[str, object]:
    inventory = read_csv(published_dir / "source_issue_inventory.csv")
    enriched = read_csv(enriched_dir / "enriched_master_games.csv")
    release_id, release_date, _ = release_metadata(published_dir)
    status_counts = {status: 0 for status in ("matched", "ambiguous", "unmatched", "pending")}
    for row in enriched:
        status = row.get("match_status", "")
        if status in status_counts:
            status_counts[status] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "release_date": release_date,
        "dataset_license": "CC-BY-4.0",
        "code_license": "MIT",
        "provenance": {
            "raw_snapshot": raw_dir.relative_to(ROOT).as_posix(),
            "reference_results": reference_results.relative_to(ROOT).as_posix(),
            "source_archives": len(inventory),
            "source_archives_with_public_rows": sum(
                int(row.get("publishable_game_rows", "0") or 0) > 0 for row in inventory
            ),
            "source_archives_unresolved": sum(
                int(row.get("publishable_game_rows", "0") or 0) == 0 for row in inventory
            ),
        },
        "identity": {
            "primary_key": "game_id",
            "policy": "stable from release 20260326; retired IDs remain resolvable through the redirect registry",
            "redirect_registry": "data/manual_cluster_overrides.csv",
        },
        "enrichment": status_counts,
        "files": [
            file_record(path)
            for path in artifact_paths(
                raw_dir=raw_dir,
                published_dir=published_dir,
                enriched_dir=enriched_dir,
                reference_results=reference_results,
            )
        ],
    }


def validate_table(path: Path, schema: dict[str, object]) -> tuple[list[dict[str, str]], list[str]]:
    problems: list[str] = []
    expected_header = [field["name"] for field in schema.get("fields", [])]
    actual_header = csv_header(path)
    if actual_header != expected_header:
        return [], [f"{path}: header differs from its checked-in schema"]
    rows = read_csv(path)
    primary = schema.get("primaryKey", [])
    key_fields = [primary] if isinstance(primary, str) else list(primary)
    seen: set[tuple[str, ...]] = set()
    for number, row in enumerate(rows, 2):
        key = tuple(row.get(field, "") for field in key_fields)
        if any(not value for value in key):
            problems.append(f"{path}:{number}: blank primary-key value")
        elif key in seen:
            problems.append(f"{path}:{number}: duplicate primary key {key}")
        seen.add(key)
        for field in schema.get("fields", []):
            name = str(field["name"])
            value = row.get(name, "")
            if value == "":
                continue
            kind = field.get("type")
            try:
                parsed: int | float | str = (
                    int(value) if kind == "integer" else float(value) if kind == "number" else value
                )
            except ValueError:
                problems.append(f"{path}:{number}: {name} is not {kind}: {value!r}")
                continue
            constraints = field.get("constraints", {})
            pattern = constraints.get("pattern")
            if pattern and not re.fullmatch(str(pattern), str(value)):
                problems.append(f"{path}:{number}: {name} violates its pattern constraint")
            if isinstance(parsed, (int, float)):
                if "minimum" in constraints and parsed < constraints["minimum"]:
                    problems.append(f"{path}:{number}: {name} is below its minimum")
                if "maximum" in constraints and parsed > constraints["maximum"]:
                    problems.append(f"{path}:{number}: {name} exceeds its maximum")
    return rows, problems


def validate_redirects(master_ids: set[str], redirects: Iterable[dict[str, str]]) -> list[str]:
    problems: list[str] = []
    mapping: dict[str, str] = {}
    for row in redirects:
        source = row.get("source_game_id", "")
        target = row.get("target_game_id", "")
        if not source or not target or source == target:
            problems.append("game ID redirect contains a blank or self-referential mapping")
            continue
        if source in mapping:
            problems.append(f"game ID redirect source is duplicated: {source}")
        mapping[source] = target
        if source in master_ids:
            problems.append(f"retired game ID remains active: {source}")
        if target not in master_ids:
            problems.append(f"game ID redirect target is not active: {target}")
    for source in mapping:
        visited: set[str] = set()
        cursor = source
        while cursor in mapping:
            if cursor in visited:
                problems.append(f"game ID redirect cycle includes: {source}")
                break
            visited.add(cursor)
            cursor = mapping[cursor]
    return problems


def validate_relationships(tables: dict[str, list[dict[str, str]]]) -> list[str]:
    problems: list[str] = []
    published_ids = {row["game_id"] for row in tables["publishable-master-games"]}
    enriched_ids = {row["game_id"] for row in tables["enriched-master-games"]}
    if enriched_ids != published_ids:
        problems.append("enriched master game IDs do not exactly match the published master")
    for resource in ("publishable-issue-titles", "enriched-issue-titles"):
        missing = {row["game_id"] for row in tables[resource]} - published_ids
        if missing:
            problems.append(f"{resource} contains {len(missing)} unknown game IDs")

    allowed_statuses = {
        ("matched", "matched", "complete"),
        ("ambiguous", "ambiguous", "complete"),
        ("unmatched", "no_match", "complete"),
        ("pending", "unknown", "rate_limited"),
        ("pending", "unknown", "deferred"),
        ("pending", "unknown", "failed"),
        ("pending", "unknown", "not_attempted"),
        ("pending", "unknown", "needs_candidate_refresh"),
    }
    invalid_statuses = {
        (row.get("match_status", ""), row.get("semantic_match_status", ""), row.get("lookup_status", ""))
        for row in tables["enriched-master-games"]
    } - allowed_statuses
    if invalid_statuses:
        problems.append(f"enriched status tuples violate the semantic/operational contract: {sorted(invalid_statuses)}")

    ambiguous_ids = {row["game_id"] for row in tables["ambiguous-matches"]}
    unmatched_ids = {row["game_id"] for row in tables["unmatched-titles"]}
    pending_ids = {row["game_id"] for row in tables["pending-lookups"]}
    expected = {
        "ambiguous": {row["game_id"] for row in tables["enriched-master-games"] if row["match_status"] == "ambiguous"},
        "unmatched": {row["game_id"] for row in tables["enriched-master-games"] if row["match_status"] == "unmatched"},
        "pending": {row["game_id"] for row in tables["enriched-master-games"] if row["match_status"] == "pending"},
    }
    for name, actual in (("ambiguous", ambiguous_ids), ("unmatched", unmatched_ids), ("pending", pending_ids)):
        if actual != expected[name]:
            problems.append(f"{name} queue does not exactly match enriched master statuses")
    if any(not row.get("candidate_1_title") and not row.get("candidate_1_url") for row in tables["ambiguous-matches"]):
        problems.append("ambiguous queue contains a row without candidate evidence")
    return problems


def validate_manifest(
    path: Path,
    *,
    raw_dir: Path,
    published_dir: Path,
    enriched_dir: Path,
    reference_results: Path = DEFAULT_REFERENCE_RESULTS,
) -> list[str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append("release manifest schema version is unsupported")
    records = manifest.get("files", [])
    recorded_paths = [record.get("path", "") for record in records]
    expected_paths = [
        artifact.relative_to(ROOT).as_posix()
        for artifact in artifact_paths(
            raw_dir=raw_dir,
            published_dir=published_dir,
            enriched_dir=enriched_dir,
            reference_results=reference_results,
        )
    ]
    if len(recorded_paths) != len(set(recorded_paths)):
        problems.append("release manifest contains duplicate artifact records")
    if set(recorded_paths) != set(expected_paths):
        problems.append("release manifest artifact inventory is incomplete or contains unexpected paths")
    for record in records:
        artifact = ROOT / record["path"]
        if not artifact.exists():
            problems.append(f"manifest artifact is missing: {record['path']}")
            continue
        if artifact.stat().st_size != record["bytes"] or sha256_file(artifact) != record["sha256"]:
            problems.append(f"manifest artifact digest differs: {record['path']}")
        if artifact.suffix == ".csv" and len(read_csv(artifact)) != record.get("rows"):
            problems.append(f"manifest artifact row count differs: {record['path']}")
    return problems


def write_contract(
    *,
    raw_dir: Path,
    published_dir: Path,
    enriched_dir: Path,
    reference_results: Path = DEFAULT_REFERENCE_RESULTS,
) -> None:
    schema_dir = ROOT / "schemas"
    for spec in RESOURCE_SPECS:
        path = resource_path(spec, published_dir=published_dir, enriched_dir=enriched_dir)
        write_if_changed(schema_dir / f"{spec.name}.schema.json", json_bytes(schema_document(spec, path)))
    write_if_changed(
        ROOT / "datapackage.json", json_bytes(data_package(published_dir=published_dir, enriched_dir=enriched_dir))
    )
    manifest_path = published_dir / "release-manifest.json"
    write_if_changed(
        manifest_path,
        json_bytes(
            release_manifest(
                raw_dir=raw_dir,
                published_dir=published_dir,
                enriched_dir=enriched_dir,
                reference_results=reference_results,
            )
        ),
    )


def check_contract(
    *,
    raw_dir: Path,
    published_dir: Path,
    enriched_dir: Path,
    reference_results: Path = DEFAULT_REFERENCE_RESULTS,
) -> list[str]:
    tables: dict[str, list[dict[str, str]]] = {}
    problems: list[str] = []
    for spec in RESOURCE_SPECS:
        path = resource_path(spec, published_dir=published_dir, enriched_dir=enriched_dir)
        schema_path = ROOT / "schemas" / f"{spec.name}.schema.json"
        if not path.exists() or not schema_path.exists():
            problems.append(f"missing contract input: {path if not path.exists() else schema_path}")
            continue
        rows, table_problems = validate_table(path, json.loads(schema_path.read_text(encoding="utf-8")))
        tables[spec.name] = rows
        problems.extend(table_problems)
    if len(tables) == len(RESOURCE_SPECS):
        problems.extend(validate_relationships(tables))
        master_ids = {row["game_id"] for row in tables["publishable-master-games"]}
        problems.extend(validate_redirects(master_ids, read_csv(ROOT / "data" / "manual_cluster_overrides.csv")))
    manifest_path = published_dir / "release-manifest.json"
    if manifest_path.exists():
        problems.extend(
            validate_manifest(
                manifest_path,
                raw_dir=raw_dir,
                published_dir=published_dir,
                enriched_dir=enriched_dir,
                reference_results=reference_results,
            )
        )
    else:
        problems.append(f"release manifest is missing: {manifest_path}")
    return problems


def latest_dir(prefix: str) -> Path:
    candidates = sorted((ROOT / "results").glob(f"{prefix}-*"))
    if not candidates:
        raise SystemExit(f"no results/{prefix}-* directory exists")
    return candidates[-1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write or verify the machine-readable CBS release contract.")
    parser.add_argument("command", choices=("write", "check"))
    parser.add_argument("--raw-dir", type=Path, default=latest_dir("raw-candidates"))
    parser.add_argument("--published-dir", type=Path, default=latest_dir("published"))
    parser.add_argument("--enriched-dir", type=Path, default=latest_dir("enriched"))
    parser.add_argument("--reference-results", type=Path, default=DEFAULT_REFERENCE_RESULTS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_dir = args.raw_dir.resolve()
    published_dir = args.published_dir.resolve()
    enriched_dir = args.enriched_dir.resolve()
    reference_results = args.reference_results.resolve()
    if args.command == "write":
        write_contract(
            raw_dir=raw_dir,
            published_dir=published_dir,
            enriched_dir=enriched_dir,
            reference_results=reference_results,
        )
    problems = check_contract(
        raw_dir=raw_dir,
        published_dir=published_dir,
        enriched_dir=enriched_dir,
        reference_results=reference_results,
    )
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    print(f"release contract valid: {published_dir.name} + {enriched_dir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
