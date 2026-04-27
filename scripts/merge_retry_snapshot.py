#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.prepare_publishable_results import rebuild_master


ISSUE_TITLE_FIELDS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "normalized_title",
    "representative_title",
    "source_kinds",
    "confidence",
    "content_kind",
]

MASTER_GAME_FIELDS = [
    "normalized_title",
    "representative_title",
    "first_seen_issue",
    "issue_count",
    "occurrence_count",
    "best_confidence",
    "source_kinds",
]

UNRESOLVED_FIELDS = [
    "archive_item",
    "archive_name",
    "issue_code",
    "year",
    "variant",
    "title_strategy",
    "resolution_path",
    "reason",
    "status",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay a retry snapshot onto the immutable March 24 full snapshot and emit a comparison report."
    )
    parser.add_argument("--base-dir", default="results/vps-linux-full-20260324")
    parser.add_argument("--retry-dir", default="results/vps-linux-retry-20260325")
    parser.add_argument("--base-published-unresolved", default="results/published-20260324/final_unresolved_issues.csv")
    parser.add_argument("--output-dir", default="results/vps-linux-merged-20260325")
    parser.add_argument("--comparison-report", default=None)
    return parser.parse_args(argv)


def read_csv_with_header(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return list(reader.fieldnames or []), rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def ensure_header(path: Path, actual: list[str], expected: list[str]) -> None:
    if actual != expected:
        raise SystemExit(f"{path} schema mismatch: expected {expected}, got {actual}")


def archive_names_from_rows(rows: Iterable[dict[str, str]]) -> set[str]:
    return {row["archive_name"] for row in rows if row.get("archive_name")}


def load_retry_archive_names(retry_dir: Path, issue_rows: list[dict[str, str]], unresolved_rows: list[dict[str, str]]) -> set[str]:
    archive_names = archive_names_from_rows(issue_rows) | archive_names_from_rows(unresolved_rows)
    all_candidates_path = retry_dir / "all_title_candidates.csv"
    if all_candidates_path.exists():
        header, rows = read_csv_with_header(all_candidates_path)
        if "archive_name" in header:
            archive_names.update(archive_names_from_rows(rows))
    return archive_names


def merged_issue_rows(base_rows: list[dict[str, str]], retry_rows: list[dict[str, str]], retry_archive_names: set[str]) -> list[dict[str, str]]:
    kept = [row for row in base_rows if row["archive_name"] not in retry_archive_names]
    merged = kept + [dict(row) for row in retry_rows]
    merged.sort(
        key=lambda row: (
            row["archive_name"],
            row["normalized_title"],
            row["representative_title"].casefold(),
            row["source_kinds"],
        )
    )
    return merged


def merged_unresolved_rows(
    base_rows: list[dict[str, str]],
    retry_rows: list[dict[str, str]],
    retry_archive_names: set[str],
) -> list[dict[str, str]]:
    kept = [row for row in base_rows if row["archive_name"] not in retry_archive_names]
    merged = kept + [dict(row) for row in retry_rows]
    merged.sort(key=lambda row: (row["archive_name"], row["issue_code"], row["status"], row["reason"]))
    return merged


def rows_by_archive(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["archive_name"]].append(row)
    return grouped


def title_set(rows: Iterable[dict[str, str]]) -> set[str]:
    return {row["normalized_title"] for row in rows if row.get("normalized_title")}


def build_report(
    *,
    base_dir: Path,
    retry_dir: Path,
    base_issue_rows: list[dict[str, str]],
    retry_issue_rows: list[dict[str, str]],
    merged_issue_rows_: list[dict[str, str]],
    base_unresolved_rows: list[dict[str, str]],
    retry_unresolved_rows: list[dict[str, str]],
    merged_unresolved_rows_: list[dict[str, str]],
    base_master_rows: list[dict[str, str]],
    merged_master_rows: list[dict[str, object]],
    retry_archive_names: set[str],
    output_dir: Path,
) -> str:
    base_issue_by_archive = rows_by_archive(base_issue_rows)
    retry_issue_by_archive = rows_by_archive(retry_issue_rows)
    merged_issue_by_archive = rows_by_archive(merged_issue_rows_)

    base_unresolved = archive_names_from_rows(base_unresolved_rows)
    retry_unresolved = archive_names_from_rows(retry_unresolved_rows)
    merged_unresolved = archive_names_from_rows(merged_unresolved_rows_)

    recovered_archives = sorted(retry_archive_names - retry_unresolved)
    still_unresolved_archives = sorted(retry_archive_names & retry_unresolved)

    base_titles = title_set(base_master_rows)
    merged_titles = title_set(merged_master_rows)
    added_titles = sorted(merged_titles - base_titles)
    removed_titles = sorted(base_titles - merged_titles)

    lines = [
        "# Retry Snapshot Comparison",
        "",
        f"- base raw snapshot: `{base_dir}`",
        f"- retry raw snapshot: `{retry_dir}`",
        f"- merged output dir: `{output_dir}`",
        f"- retry snapshot archives detected: `{len(retry_archive_names)}`",
        f"- recovered archives: `{len(recovered_archives)}`",
        f"- still unresolved after overlay: `{len(still_unresolved_archives)}`",
        f"- added normalized titles: `{len(added_titles)}`",
        f"- removed normalized titles: `{len(removed_titles)}`",
        "",
        "## Archive Coverage",
        "",
    ]
    if recovered_archives:
        lines.extend(f"- recovered: `{name}`" for name in recovered_archives)
    else:
        lines.append("- recovered: none")
    if still_unresolved_archives:
        lines.extend(f"- still unresolved: `{name}`" for name in still_unresolved_archives)
    else:
        lines.append("- still unresolved: none")

    lines.extend(["", "## Per-Archive Deltas", ""])
    for archive_name in sorted(retry_archive_names):
        lines.append(
            "- `{archive}`: base issue rows `{base_issue}`, retry issue rows `{retry_issue}`, merged issue rows `{merged_issue}`, unresolved before `{before}`, unresolved after `{after}`".format(
                archive=archive_name,
                base_issue=len(base_issue_by_archive.get(archive_name, [])),
                retry_issue=len(retry_issue_by_archive.get(archive_name, [])),
                merged_issue=len(merged_issue_by_archive.get(archive_name, [])),
                before=str(archive_name in base_unresolved).lower(),
                after=str(archive_name in merged_unresolved).lower(),
            )
        )

    lines.extend(["", "## Title Deltas", ""])
    if added_titles:
        lines.extend(f"- added: `{title}`" for title in added_titles[:100])
        if len(added_titles) > 100:
            lines.append(f"- added: `{len(added_titles) - 100}` more not shown")
    else:
        lines.append("- added: none")
    if removed_titles:
        lines.extend(f"- removed: `{title}`" for title in removed_titles[:100])
        if len(removed_titles) > 100:
            lines.append(f"- removed: `{len(removed_titles) - 100}` more not shown")
    else:
        lines.append("- removed: none")
    return "\n".join(lines) + "\n"


def run_merge(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    retry_dir = Path(args.retry_dir)
    output_dir = Path(args.output_dir)
    comparison_report = Path(args.comparison_report) if args.comparison_report else output_dir / "comparison_report.md"

    base_issue_header, base_issue_rows = read_csv_with_header(base_dir / "issue_titles.csv")
    retry_issue_header, retry_issue_rows = read_csv_with_header(retry_dir / "issue_titles.csv")
    base_master_header, base_master_rows = read_csv_with_header(base_dir / "master_games.csv")
    retry_master_header, _retry_master_rows = read_csv_with_header(retry_dir / "master_games.csv")
    base_unresolved_header, base_unresolved_rows = read_csv_with_header(base_dir / "unresolved_issues.csv")
    retry_unresolved_header, retry_unresolved_rows = read_csv_with_header(retry_dir / "unresolved_issues.csv")

    ensure_header(base_dir / "issue_titles.csv", base_issue_header, ISSUE_TITLE_FIELDS)
    ensure_header(retry_dir / "issue_titles.csv", retry_issue_header, ISSUE_TITLE_FIELDS)
    ensure_header(base_dir / "master_games.csv", base_master_header, MASTER_GAME_FIELDS)
    ensure_header(retry_dir / "master_games.csv", retry_master_header, MASTER_GAME_FIELDS)
    ensure_header(base_dir / "unresolved_issues.csv", base_unresolved_header, UNRESOLVED_FIELDS)
    ensure_header(retry_dir / "unresolved_issues.csv", retry_unresolved_header, UNRESOLVED_FIELDS)

    published_unresolved_header, published_unresolved_rows = read_csv_with_header(Path(args.base_published_unresolved))
    if "archive_name" not in published_unresolved_header:
        raise SystemExit(f"{args.base_published_unresolved} is missing archive_name")
    expected_retry_queue = archive_names_from_rows(published_unresolved_rows)

    retry_archive_names = load_retry_archive_names(retry_dir, retry_issue_rows, retry_unresolved_rows)
    if not retry_archive_names:
        raise SystemExit(f"{retry_dir} did not expose any retry archive names")

    unexpected_archives = sorted(retry_archive_names - expected_retry_queue)
    if unexpected_archives:
        raise SystemExit(
            "retry snapshot contains archives outside the March 24 published unresolved queue: "
            + ", ".join(unexpected_archives)
        )

    merged_issue = merged_issue_rows(base_issue_rows, retry_issue_rows, retry_archive_names)
    merged_unresolved = merged_unresolved_rows(base_unresolved_rows, retry_unresolved_rows, retry_archive_names)
    merged_master = rebuild_master(merged_issue)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "issue_titles.csv", merged_issue, ISSUE_TITLE_FIELDS)
    write_csv(output_dir / "unresolved_issues.csv", merged_unresolved, UNRESOLVED_FIELDS)
    write_csv(output_dir / "master_games.csv", merged_master, MASTER_GAME_FIELDS)

    report_text = build_report(
        base_dir=base_dir,
        retry_dir=retry_dir,
        base_issue_rows=base_issue_rows,
        retry_issue_rows=retry_issue_rows,
        merged_issue_rows_=merged_issue,
        base_unresolved_rows=base_unresolved_rows,
        retry_unresolved_rows=retry_unresolved_rows,
        merged_unresolved_rows_=merged_unresolved,
        base_master_rows=base_master_rows,
        merged_master_rows=merged_master,
        retry_archive_names=retry_archive_names,
        output_dir=output_dir,
    )
    comparison_report.write_text(report_text, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_merge(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
