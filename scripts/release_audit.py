#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import random
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_DIR = ROOT / "results" / "published-20260324"
RAW_SNAPSHOT_DIR = ROOT / "results" / "vps-linux-full-20260324"
REPORT_PATH = ROOT / "FINAL-RELEASE-AUDIT.md"
SAMPLE_PATH = ROOT / "FINAL-RELEASE-SAMPLE.csv"

EXPECTED_TRACKED = {
    ".gitignore",
    "LICENSE",
    "LICENSE-DATA.md",
    "README.md",
    "data/manual_alias_overrides.csv",
    "data/manual_entity_overrides.csv",
    "data/manual_rejections.csv",
    "data/manual_url_overrides.csv",
    "results/enriched-20260324/README.md",
    "results/enriched-20260324/ambiguous_matches.csv",
    "results/enriched-20260324/enriched_issue_titles.csv",
    "results/enriched-20260324/enriched_master_games.csv",
    "results/enriched-20260324/source_attribution.csv",
    "results/enriched-20260324/title_aliases.csv",
    "results/enriched-20260324/unmatched_titles.csv",
    "results/published-20260324/README.md",
    "results/published-20260324/audit_summary.md",
    "results/published-20260324/final_unresolved_issues.csv",
    "results/published-20260324/publishable_issue_titles.csv",
    "results/published-20260324/publishable_master_games.csv",
    "results/published-20260324/unresolved_summary.md",
    "scripts/__init__.py",
    "scripts/build_enriched_release.py",
    "scripts/enrich_reference_links.py",
    "scripts/index_cbs_exes.py",
    "scripts/prepare_publishable_results.py",
    "scripts/release_audit.py",
    "scripts/vps_worker_common.sh",
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
}

OPTIONAL_TRACKED = {
    "FINAL-RELEASE-AUDIT.md",
    "FINAL-RELEASE-SAMPLE.csv",
}

PERSONAL_LITERAL_PATTERNS = (
    "/Users/",
    "/home/",
    ".takopi/",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "ssh-ed25519 AAAA",
)

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
    "m chten sie das spiel verlassen",
    "ip hinzuf gen",
    "browsergames",
    "passworte",
    "physx",
    "phys x",
    "radeon",
    "sandra",
    "tutorial",
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


def run(args: list[str], *, cwd: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def git_tracked_files() -> list[str]:
    return sorted(path for path in run(["git", "ls-files"]).splitlines() if path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def tracked_text_findings(paths: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for rel in paths:
        if rel == "scripts/release_audit.py":
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in PERSONAL_LITERAL_PATTERNS:
            if pattern in text:
                findings.append((rel, pattern))
    return findings


def current_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, path in {
        "master_titles": PUBLISHED_DIR / "publishable_master_games.csv",
        "issue_rows": PUBLISHED_DIR / "publishable_issue_titles.csv",
        "unresolved": PUBLISHED_DIR / "final_unresolved_issues.csv",
    }.items():
        with path.open(encoding="utf-8", newline="") as handle:
            counts[key] = max(sum(1 for _ in csv.reader(handle)) - 1, 0)
    return counts


def count_mojibake(paths: list[Path]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        counts[str(path.relative_to(ROOT))] = text.count("�") + text.count("Ã") + text.count("Â")
    return counts


def keyword_noise_hits() -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    for rel in [
        "results/published-20260324/publishable_master_games.csv",
        "results/published-20260324/publishable_issue_titles.csv",
        "README.md",
    ]:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for pattern in KNOWN_PUBLIC_NOISE_PATTERNS:
            if pattern in lower:
                hits.append((rel, pattern, "matched"))
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
    if any(fragment in lower for fragment in SAMPLE_DROP_SUBSTRINGS):
        return "drop", "obvious non-game or resource/tool string"
    if re.search(r"\bv\s*\d", lower) or re.search(r"v\d{2,}", lower):
        return "uncertain", "looks like version/build metadata"
    if any(fragment in lower for fragment in SAMPLE_SUSPICIOUS_SUBSTRINGS):
        return "uncertain", "looks like concatenated or malformed extracted metadata"
    if re.search(r"[A-Za-z]{18,}", title):
        return "uncertain", "contains very long unbroken token"
    return "keep", "looks like a plausible game title"


def build_sample(master_rows: list[dict[str, str]], issue_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], str]:
    sorted_master = sorted(
        master_rows,
        key=lambda row: (-int(row["issue_count"]), -int(row["occurrence_count"]), row["representative_title"].casefold()),
    )
    top_master = sorted_master[:100]
    remainder = sorted_master[100:]
    rng = random.Random(1)
    random_master = rng.sample(remainder, min(100, len(remainder)))

    noisy_issue_codes = {"CBS122004DVD", "CBS012005DVD", "CBS122008DVD", "CBS122008DVDGold"}
    late_issue_codes = sorted({row["issue_code"] for row in issue_rows if row["year"] >= "2007"})
    late_issue_pick = random.Random(1).choice(late_issue_codes) if late_issue_codes else ""
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

    sample_rows.sort(key=lambda row: (row["sample_bucket"], row["row_kind"], row["issue_code"], row["representative_title"].casefold()))
    return sample_rows, late_issue_pick


def parse_readme_table() -> list[tuple[str, str, str]]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
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


def readme_snapshot_counts() -> dict[str, int] | None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    match_master = re.search(r"master titles: `(\d+)`", text)
    match_issue = re.search(r"issue/title rows: `(\d+)`", text)
    match_unresolved = re.search(r"unresolved issues: `(\d+)`", text)
    if not (match_master and match_issue and match_unresolved):
        return None
    return {
        "master_titles": int(match_master.group(1)),
        "issue_rows": int(match_issue.group(1)),
        "unresolved": int(match_unresolved.group(1)),
    }


def published_readme_snapshot_counts() -> dict[str, int] | None:
    text = (PUBLISHED_DIR / "README.md").read_text(encoding="utf-8")
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


def compare_generator_outputs() -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="cbs-audit-a-") as left_dir, tempfile.TemporaryDirectory(prefix="cbs-audit-b-") as right_dir:
        for out_dir in (left_dir, right_dir):
            run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "prepare_publishable_results.py"),
                    "--input-dir",
                    str(RAW_SNAPSHOT_DIR),
                    "--output-dir",
                    out_dir,
                ]
            )
        result: dict[str, str] = {}
        for name in [
            "publishable_master_games.csv",
            "publishable_issue_titles.csv",
            "final_unresolved_issues.csv",
        ]:
            left = Path(left_dir) / name
            right = Path(right_dir) / name
            result[name] = "match" if sha256_file(left) == sha256_file(right) else "mismatch"
        return result


def write_report(
    *,
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
    issue_rows: list[dict[str, str]],
    sample_rows: list[dict[str, object]],
    late_issue_pick: str,
    determinism: dict[str, str],
) -> None:
    expected_missing = sorted(set(EXPECTED_TRACKED) - set(tracked))
    unexpected_tracked = sorted(set(tracked) - set(EXPECTED_TRACKED) - set(OPTIONAL_TRACKED))
    readme_csv_rows = sorted(
        (row["representative_title"], row["first_seen_issue"], row["issue_count"])
        for row in master_rows
    )
    readme_consistent = sorted(readme_table_rows) == readme_csv_rows
    readme_counts_consistent = readme_counts == counts if readme_counts is not None else False
    published_readme_counts_consistent = published_readme_counts == counts if published_readme_counts is not None else False
    near_variants = near_variant_groups(master_rows)

    blockers: list[str] = []
    caveats: list[str] = []

    if local_count != 1 or remote_count != 1 or local_head != remote_head:
        blockers.append("Public Git state is not a single matching commit locally and on origin/master.")
    if unexpected_tracked or expected_missing:
        blockers.append("Tracked public tree does not match the intended file set.")
    if tracked_findings:
        blockers.append("Tracked files still contain personal identifiers or secret-like literals.")
    if any(value != 0 for value in mojibake.values()):
        blockers.append("Tracked public outputs still contain mojibake.")
    if noise_hits:
        blockers.append("Tracked public outputs still contain known UI/resource noise markers.")
    if not all(value == "match" for value in determinism.values()):
        blockers.append("Publishable output generation is not deterministic from the preserved snapshot.")
    if not readme_consistent or not readme_counts_consistent:
        blockers.append("README content is inconsistent with the tracked publishable CSVs.")
    if not published_readme_counts_consistent:
        blockers.append("results/published-20260324/README.md is inconsistent with the tracked publishable CSVs.")

    if counts["unresolved"] > 0:
        caveats.append(f"{counts['unresolved']} unresolved late-year issues remain and are documented as a retry queue.")
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

    lines = [
        "# Final Release Audit",
        "",
        f"Date: `2026-03-24`",
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
        "",
        "## Repo Integrity",
        "",
        f"- tracked tree matches expected set: `{not unexpected_tracked and not expected_missing}`",
        f"- expected tracked files missing: `{len(expected_missing)}`",
        f"- unexpected tracked files: `{len(unexpected_tracked)}`",
        f"- ignored local raw/intermediate files remain outside Git: `assumed yes; not tracked in git ls-files`",
        "",
        "## Legal, Privacy, and Compliance",
        "",
        f"- personal/secret literal findings in tracked files: `{len(tracked_findings)}`",
        f"- unofficial mirror references in tracked files: `{sum(1 for rel, pattern in tracked_findings if 'myrient' in pattern.lower())}`",
        f"- licenses present: `{(ROOT / 'LICENSE').exists() and (ROOT / 'LICENSE-DATA.md').exists()}`",
        f"- README disclaimer present: `{'No affiliation with, endorsement by, or sponsorship from' in (ROOT / 'README.md').read_text(encoding='utf-8')}`",
        f"- descriptive user agent in direct HTTP text fetches: `{'HTTP_USER_AGENT' in (ROOT / 'scripts' / 'index_cbs_exes.py').read_text(encoding='utf-8')}`",
        f"- descriptive user agent in archive downloads: `{'-A' in (ROOT / 'scripts' / 'index_cbs_exes.py').read_text(encoding='utf-8')}`",
        "",
        "## Dataset Quality",
        "",
        *[f"- mojibake count `{path}`: `{count}`" for path, count in mojibake.items()],
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

    uncertain_examples = uncertain_rows[:10]
    lines.extend(["", "## Sample Review Findings", ""])
    if uncertain_examples:
        for row in uncertain_examples:
            lines.append(
                f"- `{row['representative_title']}` (`{row['sample_bucket']}`): `{row['classification']}` — {row['reason']}"
            )
    else:
        lines.append("- no uncertain rows in the deterministic review sample")

    if near_variants:
        lines.extend(["", "## Near-Variant Examples", ""])
        for group in near_variants[:10]:
            lines.append(f"- {' | '.join(group)}")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    tracked = git_tracked_files()
    local_head = run(["git", "rev-parse", "--short", "HEAD"]).strip()
    run(["git", "fetch", "origin", "master"])
    remote_head = run(["git", "rev-parse", "--short", "origin/master"]).strip()
    local_count = int(run(["git", "rev-list", "--count", "HEAD"]).strip())
    remote_count = int(run(["git", "rev-list", "--count", "origin/master"]).strip())
    tracked_findings = tracked_text_findings(tracked)
    counts = current_counts()
    master_rows = read_csv(PUBLISHED_DIR / "publishable_master_games.csv")
    issue_rows = read_csv(PUBLISHED_DIR / "publishable_issue_titles.csv")
    sample_rows, late_issue_pick = build_sample(master_rows, issue_rows)
    write_csv(
        SAMPLE_PATH,
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
        [
            ROOT / "README.md",
            PUBLISHED_DIR / "publishable_master_games.csv",
            PUBLISHED_DIR / "publishable_issue_titles.csv",
        ]
    )
    noise_hits = keyword_noise_hits()
    readme_counts = readme_snapshot_counts()
    published_readme_counts = published_readme_snapshot_counts()
    readme_table_rows = parse_readme_table()
    determinism = compare_generator_outputs()
    write_report(
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
        issue_rows=issue_rows,
        sample_rows=sample_rows,
        late_issue_pick=late_issue_pick,
        determinism=determinism,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
