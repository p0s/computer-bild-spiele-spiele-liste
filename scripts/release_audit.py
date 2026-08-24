#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import stat
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.release_contract import check_contract

ROOT = Path(__file__).resolve().parent.parent

BASE_EXPECTED_TRACKED = {
    ".gitignore",
    "LICENSE",
    "LICENSE-DATA.md",
    "README.md",
    "data/manual_alias_overrides.csv",
    "data/manual_content_overrides.csv",
    "data/manual_entity_overrides.csv",
    "data/manual_rejections.csv",
    "data/manual_url_overrides.csv",
    "scripts/__init__.py",
    "scripts/build_enriched_release.py",
    "scripts/csv_safety.py",
    "scripts/enrich_reference_links.py",
    "scripts/improved_release_common.py",
    "scripts/index_cbs_exes.py",
    "scripts/http_safety.py",
    "scripts/merge_retry_snapshot.py",
    "scripts/prepare_publishable_results.py",
    "scripts/release_audit.py",
    "scripts/vps_worker_common.sh",
    "scripts/vps_worker_fetch_results.sh",
    "scripts/vps_worker_matrix_notify.py",
    "scripts/vps_worker_run.sh",
    "scripts/vps_worker_start.sh",
    "scripts/vps_worker_status.sh",
    "scripts/vps_worker_stop.sh",
    "scripts/vps_worker_sync.sh",
    "scripts/vps_worker_tail.sh",
    "tests/fixtures/enrichment/publishable_issue_titles.csv",
    "tests/fixtures/enrichment/publishable_master_games.csv",
    "tests/test_enrich_master_games.py",
    "tests/test_enrich_reference_links.py",
    "tests/test_index_cbs_exes.py",
    "tests/test_merge_retry_snapshot.py",
    "tests/test_release_audit.py",
}

OPTIONAL_TRACKED = {
    "FINAL-RELEASE-AUDIT.md",
    "FINAL-RELEASE-SAMPLE.csv",
}

ALLOWED_PUBLISHED_FILES = {
    "README.md",
    "audit_summary.md",
    "dropped_candidates.csv",
    "excluded_non_game_titles.csv",
    "final_issue_titles.csv",
    "final_master_games.csv",
    "final_unresolved_issues.csv",
    "publishable_issue_titles.csv",
    "publishable_master_games.csv",
    "release-manifest.json",
    "source_issue_inventory.csv",
    "unresolved_summary.md",
}

ALLOWED_RAW_FILES = {
    "README.md",
    "issue_titles.csv",
    "manifest.json",
    "master_games.csv",
    "source_archives.csv",
    "unresolved_issues.csv",
}

GENERATED_PUBLISHED_FILES = (
    "audit_summary.md",
    "dropped_candidates.csv",
    "excluded_non_game_titles.csv",
    "final_issue_titles.csv",
    "final_master_games.csv",
    "final_unresolved_issues.csv",
    "publishable_issue_titles.csv",
    "publishable_master_games.csv",
    "source_issue_inventory.csv",
    "unresolved_summary.md",
)

ALLOWED_ENRICHED_FILES = {
    "README.md",
    "ambiguous_matches.csv",
    "enriched_issue_titles.csv",
    "enrichment_audit.md",
    "enriched_master_games.csv",
    "match_demotions.csv",
    "pending_lookups.csv",
    "source_attribution.csv",
    "title_aliases.csv",
    "unmatched_titles.csv",
}

ALLOWED_MEDIA_FILES = {
    "README.md",
    "asset_evidence.csv",
    "audit_summary.md",
    "commons_candidates.csv",
    "ia_files.csv",
    "media_audit.csv",
    "media_manifest.csv",
    "release-manifest.json",
}

PERSONAL_LITERAL_PATTERNS = (
    "/Users/",
    "/home/",
    ".takopi/",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "ssh-ed25519 AAAA",
)
MAX_TRACKED_TEXT_BYTES = 16 * 1024 * 1024

KNOWN_PUBLIC_NOISE_PATTERNS = (
    "zurueck",
    "zur ck ",
    "bildschirmhintergr",
    "bildschirmschoner",
    "lautst rke",
    "aufl sung",
    "pr fsoftware",
    "l sungsb",
    "l sungb",
    "loesungsbuch",
    "lsungsbuch",
    "m chten sie das spiel verlassen",
    "ip hinzuf gen",
    "browsergames",
    "passworte",
    "physx",
    "phys x",
    "radeon",
    "sandra",
    "tutorial",
    "window title",
    "adventure editor",
    "burn in test xp vista version",
    "eragonfilm",
    "free commander",
    "indeo 5",
    "paraworldfilm",
    "shop client",
    "technik video ruby whiteout",
    "two worlds service release",
    "videotippszu anno",
    "yahoo messenger",
)

SAMPLE_SUSPICIOUS_SUBSTRINGS = (
    "ageof ",
    " fuelof ",
    "bseunterder",
    "unddanngabskeinesmehr",
    "legendender",
    "emmoandthe",
    "komplettlsung",
    "stundeder",
    "herzdes",
    "kampfder",
    "dieheiligen",
    "knig",
    "spinnfischenin",
    "dutchmans",
)

SAMPLE_SUSPICIOUS_EXCEPTIONS = {
    "knights of honor",
    "knights of the old republic 2",
}

SAMPLE_DROP_SUBSTRINGS = (
    "bildschirmhintergr",
    "bildschirmschoner",
    "passworte",
    "physx",
    "phys x",
    "radeon",
    "software",
    "tutorial",
    "instal",
)


@dataclass(frozen=True)
class AuditPaths:
    root: Path
    raw_dir: Path
    published_dir: Path
    enriched_dir: Path | None
    report_path: Path
    sample_path: Path
    audit_date: str


def snapshot_date(path: Path | None) -> str | None:
    if path is None:
        return None
    for token in reversed(path.name.split("-")):
        if len(token) == 8 and token.isdigit():
            return token
    return None


def latest_dated_dir(pattern: str, *, required_files: tuple[str, ...] = ()) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in Path("results").glob(pattern):
        date = snapshot_date(path)
        if path.is_dir() and date and all((path / name).exists() for name in required_files):
            candidates.append((date, path))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_default = latest_dated_dir(
        "raw-candidates-*",
        required_files=("issue_titles.csv", "master_games.csv", "unresolved_issues.csv", "source_archives.csv"),
    ) or latest_dated_dir("vps-*", required_files=("issue_titles.csv", "master_games.csv", "unresolved_issues.csv"))
    published_default = latest_dated_dir("published-*")
    enriched_default = latest_dated_dir("enriched-*")
    parser = argparse.ArgumentParser(description="Audit a dated CBS published snapshot and its raw inputs.")
    parser.add_argument("--raw-dir", default=str(raw_default or Path("results/raw-latest")))
    parser.add_argument("--published-dir", default=str(published_default or Path("results/published-latest")))
    parser.add_argument("--enriched-dir", default=str(enriched_default or Path("results/enriched-latest")))
    parser.add_argument("--report-path", default="FINAL-RELEASE-AUDIT.md")
    parser.add_argument("--sample-path", default="FINAL-RELEASE-SAMPLE.csv")
    parser.add_argument("--skip-git-fetch", action="store_true")
    parser.add_argument(
        "--require-remote-sync",
        action="store_true",
        help=(
            "Fail unless local HEAD equals origin/master; normally remote state is reported but is not a dataset gate."
        ),
    )
    return parser.parse_args(argv)


def build_paths(args: argparse.Namespace, root: Path = ROOT) -> AuditPaths:
    published_dir = (
        (root / args.published_dir).resolve()
        if not Path(args.published_dir).is_absolute()
        else Path(args.published_dir)
    )
    raw_dir = (root / args.raw_dir).resolve() if not Path(args.raw_dir).is_absolute() else Path(args.raw_dir)
    enriched_dir = None
    if args.enriched_dir:
        enriched_dir = (
            (root / args.enriched_dir).resolve()
            if not Path(args.enriched_dir).is_absolute()
            else Path(args.enriched_dir)
        )
    report_path = (
        (root / args.report_path).resolve() if not Path(args.report_path).is_absolute() else Path(args.report_path)
    )
    sample_path = (
        (root / args.sample_path).resolve() if not Path(args.sample_path).is_absolute() else Path(args.sample_path)
    )
    audit_date = published_dir.name.rsplit("-", 1)[-1] if "-" in published_dir.name else published_dir.name
    return AuditPaths(
        root=root.resolve(),
        raw_dir=raw_dir.resolve(),
        published_dir=published_dir.resolve(),
        enriched_dir=enriched_dir.resolve() if enriched_dir is not None else None,
        report_path=report_path.resolve(),
        sample_path=sample_path.resolve(),
        audit_date=audit_date,
    )


def run(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def git_tracked_files(root: Path) -> list[str]:
    return sorted(path for path in run(["git", "ls-files"], cwd=root).splitlines() if path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def tracked_text_findings(root: Path, paths: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    resolved_root = root.resolve()
    for rel in paths:
        if rel == "scripts/release_audit.py":
            continue
        path = root / rel
        try:
            path_info = path.lstat()
            resolved = path.resolve(strict=True)
            resolved.relative_to(resolved_root)
            if stat.S_ISLNK(path_info.st_mode) or not stat.S_ISREG(path_info.st_mode):
                findings.append((rel, "unsafe tracked file type"))
                continue
            if path_info.st_size > MAX_TRACKED_TEXT_BYTES:
                findings.append((rel, "tracked text exceeds safety limit"))
                continue
            text = path.read_text(encoding="utf-8")
        except ValueError:
            findings.append((rel, "tracked path escapes repository"))
            continue
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in PERSONAL_LITERAL_PATTERNS:
            if pattern in text:
                findings.append((rel, pattern))
    return findings


def current_counts(published_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, path in {
        "master_titles": published_dir / "publishable_master_games.csv",
        "issue_rows": published_dir / "publishable_issue_titles.csv",
        "unresolved": published_dir / "final_unresolved_issues.csv",
    }.items():
        with path.open(encoding="utf-8", newline="") as handle:
            counts[key] = len(list(csv.DictReader(handle)))
    inventory_path = published_dir / "source_issue_inventory.csv"
    if inventory_path.exists():
        inventory = read_csv(inventory_path)
        counts["source_archives"] = len(inventory)
        counts["published_archives"] = sum(int(row.get("publishable_game_rows", "0") or 0) > 0 for row in inventory)
    else:
        counts["source_archives"] = 0
        counts["published_archives"] = 0
    return counts


def count_mojibake(root: Path, paths: list[Path]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        counts[relpath(path, root)] = text.count("�") + text.count("Ã") + text.count("Â")
    return counts


def keyword_noise_hits(root: Path, published_dir: Path) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    for path in [
        published_dir / "publishable_master_games.csv",
        published_dir / "publishable_issue_titles.csv",
        root / "README.md",
    ]:
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for pattern in KNOWN_PUBLIC_NOISE_PATTERNS:
            if pattern in lower:
                hits.append((relpath(path, root), pattern, "matched"))
    return hits


def near_variant_groups(master_rows: list[dict[str, str]]) -> list[list[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for row in master_rows:
        title = row["representative_title"]
        canonical = title.casefold()
        canonical = canonical.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        canonical = re.sub(r"[^a-z0-9]+", "", canonical)
        groups[canonical].add(title)
    collisions = [sorted(values) for values in groups.values() if len(values) > 1]
    collisions.sort(key=lambda group: (len(group), group))
    return collisions


def classify_sample(title: str) -> tuple[str, str]:
    lower = title.casefold()
    if lower in SAMPLE_SUSPICIOUS_EXCEPTIONS:
        return "keep", "known valid game title"
    if any(fragment in lower for fragment in SAMPLE_DROP_SUBSTRINGS):
        return "drop", "obvious non-game or resource/tool string"
    if re.search(r"\bv\s*\d", lower) or re.search(r"v\d{2,}", lower):
        return "uncertain", "looks like version/build metadata"
    if any(fragment in lower for fragment in SAMPLE_SUSPICIOUS_SUBSTRINGS):
        return "uncertain", "looks like concatenated or malformed extracted metadata"
    if re.search(r"[A-Za-z]{18,}", title):
        return "uncertain", "contains very long unbroken token"
    return "keep", "looks like a plausible game title"


def build_sample(
    master_rows: list[dict[str, str]], issue_rows: list[dict[str, str]]
) -> tuple[list[dict[str, object]], str]:
    sorted_master = sorted(
        master_rows,
        key=lambda row: (
            -int(row["issue_count"]),
            -int(row["occurrence_count"]),
            row["representative_title"].casefold(),
        ),
    )
    top_master = sorted_master[:100]
    remainder = sorted_master[100:]
    rng = random.Random(1)
    random_master = rng.sample(remainder, min(100, len(remainder))) if remainder else []

    noisy_issue_codes = {"CBS122004DVD", "CBS012005DVD", "CBS122008DVD", "CBS122008DVDGold"}
    late_issue_codes = sorted({row["issue_code"] for row in issue_rows if row["year"] >= "2007"})
    late_issue_pick = random.Random(1).choice(late_issue_codes) if late_issue_codes else ""
    if late_issue_pick:
        noisy_issue_codes.add(late_issue_pick)
    noisy_issue_rows = [row for row in issue_rows if row["issue_code"] in noisy_issue_codes]

    sample_rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_master(bucket: str, row: dict[str, str]) -> None:
        key = ("master", row["normalized_title"], bucket)
        if key in seen:
            return
        seen.add(key)
        classification, reason = classify_sample(row["representative_title"])
        sample_rows.append(
            {
                "sample_bucket": bucket,
                "row_kind": "master",
                "issue_code": row["first_seen_issue"],
                "archive_name": "",
                "normalized_title": row["normalized_title"],
                "representative_title": row["representative_title"],
                "issue_count": row["issue_count"],
                "source_kinds": row["source_kinds"],
                "classification": classification,
                "reason": reason,
            }
        )

    def add_issue(bucket: str, row: dict[str, str]) -> None:
        key = ("issue", row["archive_name"], row["normalized_title"])
        if key in seen:
            return
        seen.add(key)
        classification, reason = classify_sample(row["representative_title"])
        sample_rows.append(
            {
                "sample_bucket": bucket,
                "row_kind": "issue",
                "issue_code": row["issue_code"],
                "archive_name": row["archive_name"],
                "normalized_title": row["normalized_title"],
                "representative_title": row["representative_title"],
                "issue_count": "",
                "source_kinds": row["source_kinds"],
                "classification": classification,
                "reason": reason,
            }
        )

    for row in top_master:
        add_master("top-100-by-issue-count", row)
    for row in random_master:
        add_master("random-100-seed-1", row)
    for row in sorted(noisy_issue_rows, key=lambda item: (item["issue_code"], item["representative_title"].casefold())):
        bucket = f"noisy-issue:{row['issue_code']}"
        if row["issue_code"] == late_issue_pick:
            bucket = f"late-year-seed-1:{row['issue_code']}"
        add_issue(bucket, row)

    sample_rows.sort(
        key=lambda row: (
            row["sample_bucket"],
            row["row_kind"],
            row["issue_code"],
            row["representative_title"].casefold(),
        )
    )
    return sample_rows, late_issue_pick


def parse_readme_table(root: Path) -> list[tuple[str, str, str]]:
    text = (root / "README.md").read_text(encoding="utf-8")
    _, _, tail = text.partition("## Full Table")
    rows: list[tuple[str, str, str]] = []
    for line in tail.splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("| Title |") or line.startswith("| --- |"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def readme_snapshot_counts(root: Path) -> dict[str, int] | None:
    text = (root / "README.md").read_text(encoding="utf-8")
    match_master = re.search(r"(?:publishable master rows|master titles): `(\d+)`", text)
    match_issue = re.search(r"(?:publishable issue/title rows|issue/title rows): `(\d+)`", text)
    match_unresolved = re.search(r"unresolved (?:issues|source archives): `(\d+)`", text)
    if not (match_master and match_issue and match_unresolved):
        return None
    return {
        "master_titles": int(match_master.group(1)),
        "issue_rows": int(match_issue.group(1)),
        "unresolved": int(match_unresolved.group(1)),
    }


def published_readme_snapshot_counts(published_dir: Path) -> dict[str, int] | None:
    text = (published_dir / "README.md").read_text(encoding="utf-8")
    match_master = re.search(r"publishable_master_games\.csv`: (\d+) rows", text)
    match_issue = re.search(r"publishable_issue_titles\.csv`: (\d+) rows", text)
    match_unresolved = re.search(r"final_unresolved_issues\.csv`: (\d+) rows", text)
    if not (match_master and match_issue and match_unresolved):
        return None
    return {
        "master_titles": int(match_master.group(1)),
        "issue_rows": int(match_issue.group(1)),
        "unresolved": int(match_unresolved.group(1)),
    }


def compare_output_files(
    generated_dir: Path,
    published_dir: Path,
    names: tuple[str, ...] = GENERATED_PUBLISHED_FILES,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        generated = generated_dir / name
        canonical = published_dir / name
        if not generated.exists():
            result[name] = "missing_generated"
        elif not canonical.exists():
            result[name] = "missing_canonical"
        else:
            result[name] = "match" if sha256_file(generated) == sha256_file(canonical) else "mismatch"
    return result


def prior_enriched_master(root: Path, published_dir: Path) -> Path | None:
    published_date = snapshot_date(published_dir)
    candidates: list[tuple[str, Path]] = []
    for directory in (root / "results").glob("enriched-*"):
        date = snapshot_date(directory)
        master = directory / "enriched_master_games.csv"
        if date and master.exists() and (published_date is None or date < published_date):
            candidates.append((date, master))
    return sorted(candidates)[-1][1] if candidates else None


def compare_generator_outputs(root: Path, raw_snapshot_dir: Path, published_dir: Path) -> dict[str, str]:
    script = root / "scripts" / "prepare_publishable_results.py"
    with tempfile.TemporaryDirectory(prefix="cbs-audit-generated-") as generated_dir:
        command = [
            sys.executable,
            str(script),
            "--input-dir",
            str(raw_snapshot_dir),
            "--output-dir",
            generated_dir,
        ]
        baseline = prior_enriched_master(root, published_dir)
        if baseline is not None:
            command.extend(["--baseline-enriched-master", str(baseline)])
        run(command, cwd=root)
        return compare_output_files(Path(generated_dir), published_dir)


def expected_tracked(paths: AuditPaths) -> set[str]:
    expected = set(BASE_EXPECTED_TRACKED)
    for dir_path, names in (
        (
            paths.published_dir,
            ALLOWED_PUBLISHED_FILES,
        ),
        (
            paths.enriched_dir,
            ALLOWED_ENRICHED_FILES,
        ),
    ):
        if dir_path is None:
            continue
        try:
            rel_dir = dir_path.relative_to(paths.root)
        except ValueError:
            continue
        for name in names:
            expected.add(str(rel_dir / name))
    return expected


def is_allowed_preserved_release_file(path: str) -> bool:
    parts = Path(path).parts
    if len(parts) == 2 and parts[0] == "results" and parts[1].startswith(("reference_review", "reference_results")):
        return True
    if len(parts) != 3 or parts[0] != "results":
        return False
    directory = parts[1]
    filename = parts[2]
    if directory.startswith("raw-candidates-"):
        return filename in ALLOWED_RAW_FILES
    if directory.startswith("published-"):
        return filename in ALLOWED_PUBLISHED_FILES
    if directory.startswith("enriched-"):
        return filename in ALLOWED_ENRICHED_FILES
    if directory.startswith("media-"):
        return filename in ALLOWED_MEDIA_FILES
    return False


def is_allowed_project_file(path: str) -> bool:
    project_prefixes = ("scripts/", "tests/", "data/", "docs/", "schemas/", "src/", ".github/")
    project_root_files = {
        ".editorconfig",
        ".gitignore",
        "CITATION.cff",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "LICENSE-DATA.md",
        "README.md",
        "datapackage.json",
        "pyproject.toml",
        "uv.lock",
    }
    return path in project_root_files or path.startswith(project_prefixes)


def readme_table_consistent(readme_table_rows: list[tuple[str, str, str]], master_rows: list[dict[str, str]]) -> bool:
    if not readme_table_rows:
        return True
    expected_rows = [
        (
            row["representative_title"],
            row["first_seen_issue"],
            row["issue_count"],
        )
        for row in master_rows
    ]
    return readme_table_rows == expected_rows


def source_coverage_problems(published_dir: Path) -> list[str]:
    inventory_path = published_dir / "source_issue_inventory.csv"
    if not inventory_path.exists():
        return ["source_issue_inventory.csv is missing"]

    inventory_rows = read_csv(inventory_path)
    issue_rows = read_csv(published_dir / "publishable_issue_titles.csv")
    unresolved_rows = read_csv(published_dir / "final_unresolved_issues.csv")
    names = [row.get("archive_name", "") for row in inventory_rows]
    inventory_names = {name for name in names if name}
    public_names = {row.get("archive_name", "") for row in issue_rows if row.get("archive_name")}
    unresolved_names = {row.get("archive_name", "") for row in unresolved_rows if row.get("archive_name")}
    zero_output_names = {
        row.get("archive_name", "") for row in inventory_rows if int(row.get("publishable_game_rows", "0") or 0) == 0
    }

    problems: list[str] = []
    if len(names) != len(inventory_names):
        problems.append("source archive inventory contains blank or duplicate archive names")
    missing_inventory = sorted(public_names - inventory_names)
    if missing_inventory:
        problems.append(f"{len(missing_inventory)} public archives are absent from the source inventory")
    missing_unresolved = sorted(zero_output_names - unresolved_names)
    if missing_unresolved:
        problems.append(
            f"{len(missing_unresolved)} zero-output source archives are not represented in the unresolved queue"
        )
    false_unresolved = sorted(
        name
        for name in unresolved_names & inventory_names
        if name not in zero_output_names
        and not any(
            row.get("archive_name") == name and row.get("publication_status") == "published_with_extraction_warning"
            for row in inventory_rows
        )
    )
    if false_unresolved:
        problems.append(f"{len(false_unresolved)} unresolved archive rows conflict with published coverage state")
    missing_source_hashes = [
        row.get("archive_name", "")
        for row in inventory_rows
        if not row.get("source_sha1") or not row.get("source_size_bytes")
    ]
    if missing_source_hashes:
        problems.append(f"{len(missing_source_hashes)} source archives lack size or SHA-1 provenance")
    return problems


def enrichment_quality(enriched_dir: Path | None) -> tuple[list[str], dict[str, int]]:
    counts = {"matched": 0, "ambiguous": 0, "unmatched": 0, "pending": 0}
    if enriched_dir is None:
        return [], counts

    master_path = enriched_dir / "enriched_master_games.csv"
    ambiguous_path = enriched_dir / "ambiguous_matches.csv"
    unmatched_path = enriched_dir / "unmatched_titles.csv"
    pending_path = enriched_dir / "pending_lookups.csv"
    missing = [path.name for path in (master_path, ambiguous_path, unmatched_path, pending_path) if not path.exists()]
    if missing:
        return [f"enrichment outputs are missing: {', '.join(missing)}"], counts

    master_rows = read_csv(master_path)
    ambiguous_rows = read_csv(ambiguous_path)
    unmatched_rows = read_csv(unmatched_path)
    pending_rows = read_csv(pending_path)
    for row in master_rows:
        status = row.get("match_status", "")
        if status in counts:
            counts[status] += 1

    problems: list[str] = []
    qid_games: dict[str, set[str]] = defaultdict(set)
    for row in master_rows:
        qid = row.get("wikidata_id", "").strip()
        if qid:
            qid_games[qid].add(row.get("game_id", ""))
    duplicate_qids = {qid: games for qid, games in qid_games.items() if len(games) > 1}
    if duplicate_qids:
        problems.append(f"{len(duplicate_qids)} Wikidata IDs are assigned to multiple game IDs")

    evidence_free = [
        row for row in ambiguous_rows if not row.get("candidate_1_title") and not row.get("candidate_1_url")
    ]
    if evidence_free:
        problems.append(f"{len(evidence_free)} ambiguous matches lack reviewable candidate evidence")

    transient_markers = ("rate_limited", "lookup_failed", "lookup_deferred", "not_cached")
    operational_unmatched = [
        row for row in unmatched_rows if any(marker in row.get("failure_reason", "") for marker in transient_markers)
    ]
    if operational_unmatched:
        problems.append(
            f"{len(operational_unmatched)} operational lookup failures are misclassified as semantic no-match"
        )

    if len(ambiguous_rows) != counts["ambiguous"]:
        problems.append("ambiguous queue count does not match enriched master status counts")
    if len(unmatched_rows) != counts["unmatched"]:
        problems.append("unmatched queue count does not match enriched master status counts")
    if len(pending_rows) != counts["pending"]:
        problems.append("pending queue count does not match enriched master status counts")
    return problems, counts


def write_report(
    *,
    paths: AuditPaths,
    local_head: str,
    remote_head: str,
    local_count: int,
    remote_count: int,
    tracked: list[str],
    tracked_findings: list[tuple[str, str]],
    mojibake: dict[str, int],
    noise_hits: list[tuple[str, str, str]],
    counts: dict[str, int],
    readme_counts: dict[str, int] | None,
    published_readme_counts: dict[str, int] | None,
    readme_table_rows: list[tuple[str, str, str]],
    master_rows: list[dict[str, str]],
    sample_rows: list[dict[str, object]],
    late_issue_pick: str,
    determinism: dict[str, str],
    remote_sync_verified: bool,
    require_remote_sync: bool,
    coverage_problems: list[str],
    enrichment_problems: list[str],
    enrichment_counts: dict[str, int],
    contract_problems: list[str],
) -> str:
    expected = expected_tracked(paths)
    expected_missing = sorted(expected - set(tracked))
    unexpected_tracked = sorted(
        path
        for path in set(tracked) - expected - OPTIONAL_TRACKED
        if not is_allowed_preserved_release_file(path) and not is_allowed_project_file(path)
    )

    readme_counts_consistent = (
        all(readme_counts.get(key) == counts.get(key) for key in ("master_titles", "issue_rows", "unresolved"))
        if readme_counts is not None
        else False
    )
    published_readme_counts_consistent = (
        all(
            published_readme_counts.get(key) == counts.get(key) for key in ("master_titles", "issue_rows", "unresolved")
        )
        if published_readme_counts is not None
        else False
    )
    readme_consistent = readme_table_consistent(readme_table_rows, master_rows)
    near_variants = near_variant_groups(master_rows)

    blockers: list[str] = []
    caveats: list[str] = []

    if require_remote_sync and not remote_sync_verified:
        blockers.append("Repo is not at the same commit locally and on origin/master.")
    if unexpected_tracked or expected_missing:
        blockers.append("Tracked public tree does not match the intended file set.")
    if tracked_findings:
        blockers.append("Tracked files contain unsafe paths, personal identifiers, or secret-like literals.")
    if any(value != 0 for value in mojibake.values()):
        blockers.append("Tracked public outputs still contain mojibake.")
    if noise_hits:
        blockers.append("Tracked public outputs still contain known UI/resource noise markers.")
    if not all(value == "match" for value in determinism.values()):
        blockers.append("Fresh generation does not exactly reproduce the checked-in publishable snapshot.")
    blockers.extend(coverage_problems)
    blockers.extend(enrichment_problems)
    blockers.extend(contract_problems)
    if not readme_counts_consistent:
        blockers.append("README content is inconsistent with the tracked publishable CSVs.")
    if not published_readme_counts_consistent:
        blockers.append(
            f"{relpath(paths.published_dir / 'README.md', paths.root)} is inconsistent "
            "with the tracked publishable CSVs."
        )

    if counts["unresolved"] > 0:
        caveats.append(f"{counts['unresolved']} unresolved issues remain and are documented as a retry queue.")
    if enrichment_counts["pending"] > 0:
        caveats.append(
            f"{enrichment_counts['pending']} reference lookups remain pending and are not "
            "classified as semantic no-match."
        )
    uncertain_rows = [row for row in sample_rows if row["classification"] == "uncertain"]
    if uncertain_rows:
        caveats.append(f"{len(uncertain_rows)} sampled rows remain uncertain and need future human review.")
    if near_variants:
        caveats.append(f"{len(near_variants)} near-variant title groups remain after current cleanup.")

    if blockers:
        verdict = "not ready"
    elif caveats:
        verdict = "ready with caveats"
    else:
        verdict = "ready"

    sample_summary: dict[str, int] = defaultdict(int)
    for row in sample_rows:
        sample_summary[str(row["classification"])] += 1
    readme_disclaimer_present = "No affiliation with, endorsement by, or sponsorship from" in (
        paths.root / "README.md"
    ).read_text(encoding="utf-8")

    lines = [
        "# Final Release Audit",
        "",
        f"Date: `{paths.audit_date}`",
        "",
        f"Published dir: `{relpath(paths.published_dir, paths.root)}`",
        f"Raw dir: `{relpath(paths.raw_dir, paths.root)}`",
        f"Enriched dir: `{relpath(paths.enriched_dir, paths.root) if paths.enriched_dir else 'none'}`",
        "",
        f"Verdict: **{verdict}**",
        "",
        "## Summary",
        "",
        f"- local HEAD: `{local_head}`",
        f"- remote HEAD: `{remote_head}`",
        f"- local commit count: `{local_count}`",
        f"- remote-tracking commit count: `{remote_count}`",
        f"- tracked files: `{len(tracked)}`",
        f"- publishable master titles: `{counts['master_titles']}`",
        f"- publishable issue/title rows: `{counts['issue_rows']}`",
        f"- unresolved issues: `{counts['unresolved']}`",
        f"- source archives inventoried: `{counts['source_archives']}`",
        f"- source archives with public game rows: `{counts['published_archives']}`",
        "- enrichment matched / ambiguous / unmatched / pending: "
        f"`{enrichment_counts['matched']} / {enrichment_counts['ambiguous']} / "
        f"{enrichment_counts['unmatched']} / {enrichment_counts['pending']}`",
        "",
        "## Repo Integrity",
        "",
        f"- tracked tree matches expected set: `{not unexpected_tracked and not expected_missing}`",
        f"- expected tracked files missing: `{len(expected_missing)}`",
        f"- unexpected tracked files: `{len(unexpected_tracked)}`",
        f"- remote sync checked: `{remote_head != 'not checked'}`",
        f"- remote sync verified: `{remote_sync_verified}`",
        "",
        "## Legal, Privacy, and Compliance",
        "",
        f"- unsafe path or personal/secret findings in tracked files: `{len(tracked_findings)}`",
        f"- licenses present: `{(paths.root / 'LICENSE').exists() and (paths.root / 'LICENSE-DATA.md').exists()}`",
        f"- README disclaimer present: `{readme_disclaimer_present}`",
        "",
        "## Dataset Quality",
        "",
        *[f"- mojibake count `{name}`: `{count}`" for name, count in mojibake.items()],
        f"- known UI/resource-noise hits in tracked public outputs: `{len(noise_hits)}`",
        f"- near-variant title groups: `{len(near_variants)}`",
        f"- sample review rows: `{len(sample_rows)}`",
        f"- sample review keep: `{sample_summary.get('keep', 0)}`",
        f"- sample review drop: `{sample_summary.get('drop', 0)}`",
        f"- sample review uncertain: `{sample_summary.get('uncertain', 0)}`",
        f"- late-year deterministic sample issue: `{late_issue_pick or 'none'}`",
        "",
        "## Reproducibility",
        "",
        *[f"- `{name}` reproducible: `{status == 'match'}`" for name, status in determinism.items()],
        f"- README snapshot counts consistent: `{readme_counts_consistent}`",
        f"- published-results README counts consistent: `{published_readme_counts_consistent}`",
        f"- README appendix table consistent with publishable master CSV: `{readme_consistent}`",
        f"- machine-readable release contract valid: `{not contract_problems}`",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Caveats", ""])
    if caveats:
        lines.extend(f"- {item}" for item in caveats)
    else:
        lines.append("- none")

    lines.extend(["", "## Sample Review Findings", ""])
    if uncertain_rows:
        for row in uncertain_rows[:10]:
            lines.append(
                f"- `{row['representative_title']}` (`{row['sample_bucket']}`): "
                f"`{row['classification']}` — {row['reason']}"
            )
    else:
        lines.append("- no uncertain rows in the deterministic review sample")

    if near_variants:
        lines.extend(["", "## Near-Variant Examples", ""])
        for group in near_variants[:10]:
            lines.append(f"- {' | '.join(group)}")

    paths.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return verdict


def run_audit(args: argparse.Namespace, *, root: Path = ROOT) -> int:
    paths = build_paths(args, root=root)
    tracked = git_tracked_files(paths.root)
    local_head = run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.root).strip()
    if args.skip_git_fetch:
        remote_head = "not checked"
        remote_count = -1
        remote_sync_verified = False
    else:
        run(["git", "fetch", "origin", "master"], cwd=paths.root)
        remote_head = run(["git", "rev-parse", "--short", "origin/master"], cwd=paths.root).strip()
        remote_count = int(run(["git", "rev-list", "--count", "origin/master"], cwd=paths.root).strip())
        remote_sync_verified = local_head == remote_head
    local_count = int(run(["git", "rev-list", "--count", "HEAD"], cwd=paths.root).strip())

    tracked_findings = tracked_text_findings(paths.root, tracked)
    counts = current_counts(paths.published_dir)
    master_rows = read_csv(paths.published_dir / "publishable_master_games.csv")
    issue_rows = read_csv(paths.published_dir / "publishable_issue_titles.csv")
    sample_rows, late_issue_pick = build_sample(master_rows, issue_rows)
    write_csv(
        paths.sample_path,
        sample_rows,
        [
            "sample_bucket",
            "row_kind",
            "issue_code",
            "archive_name",
            "normalized_title",
            "representative_title",
            "issue_count",
            "source_kinds",
            "classification",
            "reason",
        ],
    )

    mojibake = count_mojibake(
        paths.root,
        [
            paths.root / "README.md",
            paths.published_dir / "publishable_master_games.csv",
            paths.published_dir / "publishable_issue_titles.csv",
        ],
    )
    noise_hits = keyword_noise_hits(paths.root, paths.published_dir)
    readme_counts = readme_snapshot_counts(paths.root)
    published_readme_counts = published_readme_snapshot_counts(paths.published_dir)
    readme_table_rows = parse_readme_table(paths.root)
    determinism = compare_generator_outputs(paths.root, paths.raw_dir, paths.published_dir)
    coverage_problems = source_coverage_problems(paths.published_dir)
    enrichment_problems, enrichment_counts = enrichment_quality(paths.enriched_dir)
    contract_problems = (
        check_contract(
            raw_dir=paths.raw_dir,
            published_dir=paths.published_dir,
            enriched_dir=paths.enriched_dir,
        )
        if paths.enriched_dir is not None
        else []
    )

    verdict = write_report(
        paths=paths,
        local_head=local_head,
        remote_head=remote_head,
        local_count=local_count,
        remote_count=remote_count,
        tracked=tracked,
        tracked_findings=tracked_findings,
        mojibake=mojibake,
        noise_hits=noise_hits,
        counts=counts,
        readme_counts=readme_counts,
        published_readme_counts=published_readme_counts,
        readme_table_rows=readme_table_rows,
        master_rows=master_rows,
        sample_rows=sample_rows,
        late_issue_pick=late_issue_pick,
        determinism=determinism,
        remote_sync_verified=remote_sync_verified,
        require_remote_sync=args.require_remote_sync,
        coverage_problems=coverage_problems,
        enrichment_problems=enrichment_problems,
        enrichment_counts=enrichment_counts,
        contract_problems=contract_problems,
    )
    return 1 if verdict == "not ready" else 0


def main(argv: list[str] | None = None) -> int:
    return run_audit(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
