#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.index_cbs_exes import normalize_title


BAD_EXACT = {
    "000 000",
    "100 spiele",
    "082009",
    "82009 normal",
    "abbrechen",
    "abfrage",
    "aktualisieren",
    "alternativ",
    "aufl sung",
    "cancel",
    "cdstart",
    "common",
    "daten",
    "details",
    "dll",
    "files",
    "gewicht",
    "icon",
    "internet",
    "karte",
    "kraft",
    "kurzversionen",
    "laden",
    "layout",
    "loader",
    "logo",
    "manual",
    "misc",
    "normal",
    "none",
    "obscure demo",
    "options",
    "overlays",
    "partikel",
    "patch",
    "readme",
    "serverliste",
    "servername",
    "shell exec",
    "sounds",
    "spielart",
    "spieler",
    "spielername",
    "sonstiges",
    "start",
    "swingcd",
    "swingrun",
    "updates",
    "user1",
    "visit play hef com",
    "wichtige informationen",
}

BAD_SUBSTRINGS = (
    " bonus ",
    "track ",
    " autorun",
    "adobe",
    "acrobat",
    "antivir",
    "anti vir",
    "auto run",
    "catalyst",
    "cbs ",
    "cd icon",
    "desktop",
    "direct x",
    "directx",
    "driver",
    "einstellungen",
    "einzelspieler",
    "eula",
    "explorer",
    "folder",
    "handbuch",
    "hilfe",
    "hyperlink",
    "icon",
    "inst ",
    "install",
    "internet explorer",
    "jagdtiger",
    "layerchange",
    "liesmich",
    "manual",
    "media center",
    "media player",
    "mehrspieler",
    "menu",
    "ms internet explorer",
    "options",
    "patch",
    "player",
    "projectfreedom",
    "read me",
    "reader",
    "server",
    "setup",
    "shell exec",
    "span",
    "spellforce2 2 sw",
    "swing",
    "tobicon",
    "treiber",
    "visit ",
    "windows media player",
    "winsock",
    "zone alarm",
    "tuner",
)

MANIFEST_BAD_SUBSTRINGS = (
    "track",
    "manual",
    "readme",
    "liesmich",
    "handbuch",
    "autorun",
    "menu",
    "setup",
    "install",
    "patch",
    "files",
    "common",
    "layout",
    "sounds",
    "desktop",
    "folder",
    "logo",
    "directx",
    "direct x",
    "loader",
    "eula",
    "dll",
    "updates",
    "misc",
    "language",
    "overlays",
    "icon",
)


REPRESENTATIVE_TITLE_REPAIRS = {
    "2 ritter auf der suche nach der hinrei enden herzelinde": "2 Ritter - Auf der Suche nach der hinrei\u00dfenden Herzelinde",
    "adash stadt der magie kapitel11": "Adash - Stadt der Magie - Kapitel 11",
    "apassionata die galanacht der pferde": "Apassionata - Die Galanacht der Pferde",
    "alone in the dark komplettl sung": "Alone in the Dark Komplettl\u00f6sung",
    "ati pr fsoftware": "ATI Pr\u00fcfsoftware",
    "baldur s gate 2 schatten von amn": "Baldur's Gate 2 - Schatten von Amn",
    "baldur s gate 2 thron des bhaal": "Baldur's Gate 2 - Thron des Bhaal",
    "baldur s gate compilation": "Baldur's Gate - Compilation",
    "baldur s gate legenden der schwertk ste": "Baldur's Gate Legenden der Schwertk\u00fcste",
    "bildschirmhintergr nde": "Bildschirmhintergr\u00fcnde",
    "call of duty 4 modern warfare": "Call of Duty 4 - Modern Warfare",
    "codename panzers cold war": "Codename Panzers - Cold War",
    "command conquer alarmstufe rot 3v 1": "Command & Conquer - Alarmstufe Rot 3 v 1",
    "crazy machines 2 cm": "Crazy Machines 2",
    "das geheimnis der vergessenen h hle": "Das Geheimnis der vergessenen H\u00f6hle",
    "das schwarze auge drakensang": "Das Schwarze Auge - Drakensang",
    "das verm chtnis testament of sin": "Das Verm\u00e4chtnis - Testament of Sin",
    "desperados 2 cooper s revenge": "Desperados 2 - Cooper's Revenge",
    "die gilde 2 venedig v 3": "Die Gilde 2 - Venedig v 3",
    "die legenden und m rchen von ash kale 1": "Die Legenden und M\u00e4rchen von Ash'kale 1",
    "die siedler 2 die n chste generation": "Die Siedler 2 Die n\u00e4chste Generation",
    "die siedler das erbe der k nige": "Die Siedler Das Erbe der K\u00f6nige",
    "dikowsk ru land": "Dikowsk, Ru\u00dfland",
    "diverse bildschirmhintergr nde": "Diverse Bildschirmhintergr\u00fcnde",
    "dreamlords the re awakening": "Dreamlords - The Re Awakening",
    "erbe der k nige": "Erbe der K\u00f6nige Demo",
    "fu ball manager08": "Fu\u00dfball Manager 08",
    "fu ball manager09": "Fu\u00dfball Manager 09",
    "fu ball manager2008v 8 0": "Fu\u00dfball Manager 2008 v 8 0",
    "garry die schmei fliege": "Garry die Schmei\u00dffliege",
    "grand ages rome": "Grand Ages - Rome",
    "gta 4 komplettl sung": "GTA 4 Komplettl\u00f6sung",
    "icewind dale herz des winters": "Icewind Dale - Herz des Winters",
    "ip hinzuf gen": "IP HINZUF\u00dcGEN",
    "k nige der wellen": "K\u00f6nige der Wellen",
    "kings bounty the legend": "King's Bounty - The Legend",
    "l schen": "L\u00f6schen",
    "l sungb cher": "L\u00f6sungsb\u00fccher",
    "l sungsb cher": "L\u00f6sungsb\u00fccher",
    "lautst rke musik": "Lautst\u00e4rke Musik",
    "lautst rke sfx": "Lautst\u00e4rke SFX",
    "lego indiana jones die legend ren abenteuer": "Lego Indiana Jones Die legend\u00e4ren Abenteuer",
    "m llabfuhr simulator2008": "M\u00fcllabfuhr Simulator 2008",
    "m chten sie das spiel verlassen": "M\u00f6chten Sie das Spiel verlassen?",
    "mercedes clc dream test drive": "Mercedes CLC Dream - Test Drive",
    "meine tierklinik l wenbaby": "Meine Tierklinik L\u00f6wenbaby",
    "minus aufl sung": "minus Aufl\u00f6sung",
    "moorhuhn schatzj ger 3": "Moorhuhn Schatzj\u00e4ger 3",
    "need for speed underground v 1 1": "Need for Speed - Underground v 1 1",
    "nibiru der bote der g tter": "Nibiru Der Bote der G\u00f6tter",
    "niedrigaufl sende texturen": "Niedrigaufl\u00f6sende Texturen",
    "nikopol die r ckkehr der unsterblichen": "Nikopol Die R\u00fcckkehr der Unsterblichen",
    "post mortem l sungsbuch": "Post Mortem + L\u00f6sungsbuch",
    "plus aufl sung": "plus Aufl\u00f6sung",
    "prim r": "Prim\u00e4r",
    "r ckkehr zur insel": "R\u00fcckkehr zur Insel",
    "sacred 2 fallen angel": "Sacred 2 - Fallen Angel",
    "sacred 2 fallen angel v 2 34 0": "Sacred 2 - Fallen Angel v 2 34 0",
    "sherlock holmes jagt ars ne lupin": "Sherlock Holmes jagt Ars\u00e8ne Lupin",
    "sherlock holmes die spur der erwachten remastered": "Sherlock Holmes - Die Spur der Erwachten - Remastered Edition",
    "sid meier s civilization 4 fall from heaven 2 0": "Sid Meier's Civilization 4 - Fall from Heaven 2 0",
    "siedler das erbe der k nige": "Siedler Das Erbe der K\u00f6nige",
    "syberia 2l sungsbuch": "Syberia 2 + L\u00f6sungsbuch",
    "tomb raider underworld v 1": "Tomb Raider - Underworld v 1",
    "tomb raider underworld": "Tomb Raider - Underworld",
    "turbo strau": "Turbo Strau\u00df",
    "tutorial wasserk hlung": "Tutorial: Wasserk\u00fchlung",
    "velaya geschichte einer kriegerin 1": "Velaya - Geschichte einer Kriegerin 1",
    "waldmeister sause edelwei": "Waldmeister Sause Edelwei\u00df",
    "wickie ylvi ist entf hrt": "Wickie Ylvi ist entf\u00fchrt",
    "zur ck zum spiel": "ZUR\u00dcCK ZUM SPIEL",
    "zur cksetzen": "Zur\u00fccksetzen",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a cleaned publishable result set from a raw VPS snapshot.")
    parser.add_argument("--input-dir", default="results/vps-linux-full-20260324")
    parser.add_argument("--output-dir", default="results/published-20260324")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def repair_issue_row(row: dict[str, str]) -> dict[str, str]:
    repaired = dict(row)
    replacement = REPRESENTATIVE_TITLE_REPAIRS.get(repaired["normalized_title"])
    if replacement is None:
        return repaired
    repaired["representative_title"] = replacement
    normalized = normalize_title(replacement)
    if normalized is not None:
        repaired["normalized_title"] = normalized
    return repaired


def is_short_code(normalized: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{1,4}\d{1,4}[a-z0-9]*", normalized))


def probable_game_title(row: dict[str, str]) -> tuple[bool, str]:
    title = row["representative_title"].strip()
    normalized = row["normalized_title"].strip().lower()
    source_kinds = row["source_kinds"].split(",") if row.get("source_kinds") else []

    if "vollversion-fullversion" in source_kinds:
        return True, "vollversion-fullversion"

    if re.match(r"cbs\d+ track\d+", normalized):
        return False, "issue-track"

    if re.fullmatch(r"\d+", normalized):
        return False, "numeric-only"

    if re.fullmatch(r"\d{4,}", normalized.replace(" ", "")):
        return False, "issue-number-like"

    if normalized in BAD_EXACT:
        return False, "bad-exact"

    lower_title = title.lower()
    if any(fragment in lower_title for fragment in BAD_SUBSTRINGS):
        return False, "bad-substring"

    if "<" in title or ">" in title or "[" in title or "]" in title:
        return False, "markup-noise"

    if "\\" in title or "|" in title:
        return False, "path-or-option"

    if is_short_code(normalized):
        return False, "short-code"

    if normalized.startswith("cbs") and any(ch.isdigit() for ch in normalized):
        return False, "cbs-code"

    if any(token in {"dvd", "cd", "gold", "spiele"} for token in normalized.split()):
        return False, "media-or-magazine-label"

    tokens = [token for token in normalized.split() if token.isalpha()]
    long_tokens = [token for token in tokens if len(token) >= 4]
    short_tokens = [token for token in tokens if len(token) <= 2]
    if normalized[:1].isdigit() and tokens and max((len(token) for token in tokens), default=0) < 4:
        return False, "numeric-leading-weak"

    if any(token in {"normal", "bonus", "sonder", "gold"} for token in normalized.split()) and any(ch.isdigit() for ch in normalized):
        return False, "edition-or-mode-label"

    if tokens and len(long_tokens) == 0:
        return False, "all-short-words"

    if len(tokens) >= 2 and len(short_tokens) == len(tokens):
        return False, "all-short-words"

    if len(tokens) >= 3 and len(long_tokens) == 1 and len(short_tokens) >= 2:
        return False, "mostly-short-words"

    if source_kinds == ["disc-manifest-path"]:
        if any(fragment in lower_title for fragment in MANIFEST_BAD_SUBSTRINGS):
            return False, "manifest-noise"
        if row.get("issue_count") == "1" and " " not in title and (title.isupper() or len(title) < 5):
            return False, "manifest-weak-singleword"
        if row.get("issue_count") == "1" and " " not in title and title[:1].islower():
            return False, "manifest-lowercase-singleword"
        if row.get("issue_count") == "1" and len(long_tokens) == 0:
            return False, "manifest-weak-phrase"

    if " " in title:
        return True, "multiword"

    if title[:1].isupper() and not title.isupper() and len(title) >= 5:
        return True, "singleword-titlecase"

    return False, "weak-singleword"


def clean_issue_rows(issue_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    cleaned: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    for original_row in issue_rows:
        row = repair_issue_row(original_row)
        keep, reason = probable_game_title(row)
        if keep:
            row = dict(row)
            row["clean_reason"] = reason
            cleaned.append(row)
        else:
            dropped.append(
                {
                    "archive_name": row["archive_name"],
                    "issue_code": row["issue_code"],
                    "normalized_title": row["normalized_title"],
                    "representative_title": row["representative_title"],
                    "source_kinds": row["source_kinds"],
                    "confidence": row["confidence"],
                    "drop_reason": reason,
                }
            )
    return cleaned, dropped


STRICT_BAD_EXACT = {
    "aisuite",
    "alpha 1",
    "alpha 2",
    "alpha calosc",
    "ati pr fsoftware",
    "ati radeon",
    "ati radeon notebook",
    "ammo in mag",
    "background led weight",
    "browsergames small",
    "computerbild",
    "computerbild spiele",
    "computer bild spiele",
    "ageia phys x system software",
    "ageia phys xsystem software",
    "ageia physx system software",
    "alle meine passworte",
    "allemeine passworte",
    "ip hinzuf gen",
    "johnnie walker moorhuhnjagd",
    "l schen",
    "l sungb cher",
    "l sungsb cher",
    "lautst rke musik",
    "lautst rke sfx",
    "m chten sie das spiel verlassen",
    "minus aufl sung",
    "niedrigaufl sende texturen",
    "nvidia phys x system software 8 04",
    "nvidia phys xsystem software80425",
    "plus aufl sung",
    "prim r",
    "trailer",
    "trailer01",
    "trailer02",
    "trailerliste",
    "secunia personal software inspector",
    "si software sandra 2005 lite",
    "tutorial wasserk hlung",
    "trailer",
    "trailer01",
    "trailer02",
    "trailerliste",
    "wybierz parametry instalacyjne",
    "www link",
    "www link",
    "zur ck zum spiel",
    "zur cksetzen",
    "zurueck",
    "aukeratu instalazioa egiteko hizkuntza",
}

STRICT_BAD_SUBSTRINGS = (
    "abylon",
    "aware",
    "adobe",
    "reader",
    "windows",
    "media",
    "antivir",
    "player",
    "driver",
    "explorer",
    "spiele",
    "computerbild",
    "computer bild",
    "manual",
    "readme",
    "handbuch",
    "eula",
    "patch",
    "layerchange",
    "icon",
    "logo",
    "keysafe",
    "sharedrive",
    "logon",
    "prüfsoftware",
    "prufsoftware",
    "tuner",
    "endif",
    "hyperlink",
    "span",
    "browsergames",
    "button ",
    "inspector",
    "nvidia ",
    "phys x",
    "physx",
    "radeon",
    "sandra",
    "loesungsbuch",
    "lösungsbuch",
    "lösungsbücher",
    "bildschirmhintergr",
    "bildschirmschoner",
    " trailer",
    "passworte",
    "trailerliste",
    "game trailer",
    "dvdvideo",
    "tutorial",
    "hizkuntza",
    "instalazio",
    "instalacyjne",
    "www link",
)


def publishable_issue_rows(cleaned_issue_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    publishable: list[dict[str, str]] = []
    for row in cleaned_issue_rows:
        normalized = row["normalized_title"].strip().lower()
        title = row["representative_title"].strip()
        source_kinds = set(filter(None, row["source_kinds"].split(",")))

        if "vollversion-fullversion" in source_kinds:
            publishable.append(dict(row))
            continue

        if "disc-metadata-value" not in source_kinds:
            continue

        if normalized in STRICT_BAD_EXACT:
            continue

        lower_title = title.lower()
        if any(fragment in lower_title for fragment in STRICT_BAD_SUBSTRINGS):
            continue

        alpha_tokens = [token for token in normalized.split() if token.isalpha()]
        if alpha_tokens and max(len(token) for token in alpha_tokens) < 4:
            continue

        if len(alpha_tokens) >= 3 and sum(len(token) <= 2 for token in alpha_tokens) >= 2:
            continue

        publishable.append(dict(row))
    return publishable


def rebuild_master(issue_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    issue_sets: dict[str, set[str]] = defaultdict(set)
    for row in issue_rows:
        normalized = row["normalized_title"]
        issue_sets[normalized].add(row["archive_name"])
        current = grouped.get(normalized)
        confidence_rank = {"high": 3, "medium": 2, "low": 1}.get(row["confidence"], 0)
        if current is None:
            grouped[normalized] = {
                "normalized_title": normalized,
                "representative_title": row["representative_title"],
                "first_seen_issue": row["issue_code"],
                "issue_count": 1,
                "occurrence_count": 1,
                "best_confidence": row["confidence"],
                "source_kinds": set(filter(None, row["source_kinds"].split(","))),
                "_rank": confidence_rank,
            }
            continue
        current["occurrence_count"] = int(current["occurrence_count"]) + 1
        current["issue_count"] = len(issue_sets[normalized])
        current["source_kinds"].update(filter(None, row["source_kinds"].split(",")))
        if confidence_rank > int(current["_rank"]):
            current["representative_title"] = row["representative_title"]
            current["best_confidence"] = row["confidence"]
            current["_rank"] = confidence_rank

    final_rows: list[dict[str, object]] = []
    for normalized, row in sorted(grouped.items()):
        final_rows.append(
            {
                "normalized_title": normalized,
                "representative_title": row["representative_title"],
                "first_seen_issue": row["first_seen_issue"],
                "issue_count": len(issue_sets[normalized]),
                "occurrence_count": row["occurrence_count"],
                "best_confidence": row["best_confidence"],
                "source_kinds": ",".join(sorted(row["source_kinds"])),
            }
        )
    return final_rows


def analyze_unresolved(unresolved_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    analyzed: list[dict[str, str]] = []
    for row in unresolved_rows:
        reason = row["reason"]
        lower = reason.lower()
        if "could not resolve host" in lower or "503" in lower or "connection timed out" in lower or "broken pipe" in lower:
            root_cause = "network/download"
            retry = "yes"
            suggestion = "retry on a stable network or with a rerun focused on unresolved issues"
        else:
            root_cause = "other"
            retry = "investigate"
            suggestion = "inspect raw error and source artifact manually"
        analyzed.append(
            {
                **row,
                "root_cause": root_cause,
                "retry_recommended": retry,
                "suggestion": suggestion,
            }
        )
    return analyzed


def write_report(path: Path, *, raw_master: int, cleaned_master: int, raw_issue: int, cleaned_issue: int, dropped_count: int, unresolved_count: int) -> None:
    text = f"""# Published Result Set Audit

- raw master rows: {raw_master}
- cleaned master rows: {cleaned_master}
- raw issue/title rows: {raw_issue}
- cleaned issue/title rows: {cleaned_issue}
- dropped noisy rows: {dropped_count}
- unresolved issues: {unresolved_count}

Cleaning rules used:
- keep all `vollversion-fullversion` rows
- drop obvious issue-code/track rows like `CBS0100 (Track 01)`
- drop obvious UI/settings/manual/software noise
- keep multi-word titles that survive the blacklist
- keep title-cased single-word titles only when they are not obvious noise

Publishable tier:
- keeps all `vollversion-fullversion` rows
- keeps only stronger `disc-metadata-value` rows
- excludes manifest-only and command-only rows from the publishable tier

Original raw data remains untouched in the source snapshot.
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    issue_rows = read_csv(input_dir / "issue_titles.csv")
    unresolved_rows = read_csv(input_dir / "unresolved_issues.csv")
    master_rows = read_csv(input_dir / "master_games.csv")

    cleaned_issue_rows, dropped_rows = clean_issue_rows(issue_rows)
    cleaned_master_rows = rebuild_master(cleaned_issue_rows)
    publishable_rows = publishable_issue_rows(cleaned_issue_rows)
    publishable_master_rows = rebuild_master(publishable_rows)
    analyzed_unresolved = analyze_unresolved(unresolved_rows)

    write_csv(
        output_dir / "final_issue_titles.csv",
        cleaned_issue_rows,
        [
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
            "clean_reason",
        ],
    )
    write_csv(
        output_dir / "final_master_games.csv",
        cleaned_master_rows,
        [
            "normalized_title",
            "representative_title",
            "first_seen_issue",
            "issue_count",
            "occurrence_count",
            "best_confidence",
            "source_kinds",
        ],
    )
    write_csv(
        output_dir / "publishable_issue_titles.csv",
        publishable_rows,
        [
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
            "clean_reason",
        ],
    )
    write_csv(
        output_dir / "publishable_master_games.csv",
        publishable_master_rows,
        [
            "normalized_title",
            "representative_title",
            "first_seen_issue",
            "issue_count",
            "occurrence_count",
            "best_confidence",
            "source_kinds",
        ],
    )
    write_csv(
        output_dir / "dropped_candidates.csv",
        dropped_rows,
        [
            "archive_name",
            "issue_code",
            "normalized_title",
            "representative_title",
            "source_kinds",
            "confidence",
            "drop_reason",
        ],
    )
    write_csv(
        output_dir / "final_unresolved_issues.csv",
        analyzed_unresolved,
        [
            "archive_item",
            "archive_name",
            "issue_code",
            "year",
            "variant",
            "title_strategy",
            "resolution_path",
            "reason",
            "status",
            "root_cause",
            "retry_recommended",
            "suggestion",
        ],
    )
    write_report(
        output_dir / "audit_summary.md",
        raw_master=len(master_rows),
        cleaned_master=len(cleaned_master_rows),
        raw_issue=len(issue_rows),
        cleaned_issue=len(cleaned_issue_rows),
        dropped_count=len(dropped_rows),
        unresolved_count=len(analyzed_unresolved),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
