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

from scripts.improved_release_common import (
    MATCH_FIELDS,
    build_vocab,
    choose_best_display_title,
    choose_best_issue_row,
    choose_best_match,
    clean_title,
    compute_data_quality_score,
    normalize_public_title,
    safe_text,
    semicolon_join,
    slugify,
    to_int,
)
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
    "battlefield2142v150": "Battlefield 2142",
    "codename panzers cold war": "Codename Panzers - Cold War",
    "codename panzers phase2v108": "Codename Panzers Phase 2",
    "command conquer gener le die stunde null": "Command & Conquer Gener\u00e4le Die Stunde Null",
    "command conquer alarmstufe rot 3v 1": "Command & Conquer - Alarmstufe Rot 3 v 1",
    "command conquer3 tiberium warsv108 kane edition": "Command & Conquer 3 Tiberium Wars Kane Edition",
    "command conquer3 tiberium warsv108 standard edition": "Command & Conquer 3 Tiberium Wars Standard Edition",
    "command conquer3 tiberium warsv108 kane": "Command & Conquer 3 Tiberium Wars Kane Edition",
    "command conquer3 tiberium warsv108 standard": "Command & Conquer 3 Tiberium Wars Standard Edition",
    "crazy machines 2 cm": "Crazy Machines 2",
    "das geheimnis der vergessenen h hle": "Das Geheimnis der vergessenen H\u00f6hle",
    "das schwarze auge drakensang": "Das Schwarze Auge - Drakensang",
    "das verm chtnis testament of sin": "Das Verm\u00e4chtnis - Testament of Sin",
    "desperados 2 cooper s revenge": "Desperados 2 - Cooper's Revenge",
    "das erbe der k nige": "Das Erbe der K\u00f6nige",
    "die gilde 2 venedig v 3": "Die Gilde 2 - Venedig v 3",
    "die legenden und m rchen von ash kale 1": "Die Legenden und M\u00e4rchen von Ash'kale 1",
    "die siedler 6 aufstieg eines k nigreichs": "Die Siedler 6 Aufstieg eines K\u00f6nigreichs",
    "die siedler aufstieg eines k nigreichs": "Die Siedler Aufstieg eines K\u00f6nigreichs",
    "die siedler 2 die n chste generation": "Die Siedler 2 Die n\u00e4chste Generation",
    "die siedler das erbe der k nige": "Die Siedler Das Erbe der K\u00f6nige",
    "dikowsk ru land": "Dikowsk, Ru\u00dfland",
    "diverse bildschirmhintergr nde": "Diverse Bildschirmhintergr\u00fcnde",
    "dreamlords the re awakening": "Dreamlords - The Re Awakening",
    "erbe der k nige": "Erbe der K\u00f6nige Demo",
    "fu ball manager08": "Fu\u00dfball Manager 08",
    "fu ball manager09": "Fu\u00dfball Manager 09",
    "fu ball manager2008v 8 0": "Fu\u00dfball Manager 2008 v 8 0",
    "fuball manager2008v802": "Fu\u00dfball Manager 2008",
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
    "quake4v142": "Quake 4",
    "radsport manager pro2007v1010": "Radsport Manager Pro 2007",
    "rainbow six vegas2v103": "Rainbow Six Vegas 2",
    "r ckkehr zur insel": "R\u00fcckkehr zur Insel",
    "sacred 2 fallen angel": "Sacred 2 - Fallen Angel",
    "sacred 2 fallen angel v 2 34 0": "Sacred 2 - Fallen Angel v 2 34 0",
    "sherlock holmes jagt ars ne lupin": "Sherlock Holmes jagt Ars\u00e8ne Lupin",
    "sherlock holmes die spur der erwachten remastered": "Sherlock Holmes - Die Spur der Erwachten - Remastered Edition",
    "sid meier s civilization 4 fall from heaven 2 0": "Sid Meier's Civilization 4 - Fall from Heaven 2 0",
    "siedler das erbe der k nige": "Siedler Das Erbe der K\u00f6nige",
    "stalkerv10003v10004v10005": "STALKER",
    "stronghold2v14": "Stronghold 2",
    "supreme commander forged alliance v 1 5 3596 auf": "Supreme Commander Forged Alliance",
    "supreme commander forged alliance v 1 5 3596 auf v 1 5": "Supreme Commander Forged Alliance",
    "supreme commander forged alliancev153596auf": "Supreme Commander Forged Alliance",
    "supreme commander forged alliancev153596aufv153599": "Supreme Commander Forged Alliance",
    "syberia 2l sungsbuch": "Syberia 2 + L\u00f6sungsbuch",
    "tom clancys ghost recon advanced warfighter2v102": "Tom Clancy's Ghost Recon Advanced Warfighter 2",
    "tom clancys ghost recon advanced warfighter2v104": "Tom Clancy's Ghost Recon Advanced Warfighter 2",
    "tomb raider underworld v 1": "Tomb Raider - Underworld v 1",
    "tomb raider underworld": "Tomb Raider - Underworld",
    "unreal tournament3v12": "Unreal Tournament 3",
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
    parser.add_argument("--baseline-enriched-master", default="results/enriched-20260325/enriched_master_games.csv")
    parser.add_argument("--manual-content-overrides", default="data/manual_content_overrides.csv")
    parser.add_argument("--manual-rejections", default="data/manual_rejections.csv")
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
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def repair_issue_row(row: dict[str, str]) -> dict[str, str]:
    repaired = dict(row)
    replacement = REPRESENTATIVE_TITLE_REPAIRS.get(repaired["normalized_title"])
    if replacement is not None:
        repaired["representative_title"] = replacement

    normalized = normalize_title(repaired["representative_title"])
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
    "loesungsbuecher",
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
    "tcp optimizer",
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
    "acronis",
    "abylon",
    "aware",
    "adobe",
    "ashampoo",
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
    "sound blaster",
    "sandra",
    "drive image",
    "loesungsbuch",
    "loesungsbuecher",
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


def read_baseline_match_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["normalized_title"]: row for row in read_csv(path) if row.get("normalized_title")}


def read_manual_content_overrides(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["game_id"]: row for row in read_csv(path) if row.get("game_id")}


def read_rejections(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        if row.get("normalized_title"):
            grouped[row["normalized_title"]].append(row)
    return grouped


def rejection_reason_for_match(match_row: dict[str, str], rejections: list[dict[str, str]]) -> str:
    if not match_row or not rejections:
        return ""
    canonical_title = safe_text(match_row.get("canonical_title")).casefold()
    canonical_slug = safe_text(match_row.get("canonical_slug")).casefold()
    source = safe_text(match_row.get("match_source")).casefold()
    reasons: list[str] = []
    for rejection in rejections:
        rejected = safe_text(rejection.get("rejected_candidate")).casefold()
        rejected_source = safe_text(rejection.get("source")).casefold()
        if rejected_source and source and rejected_source not in source:
            continue
        if rejected and (rejected == canonical_title or rejected == canonical_slug):
            reasons.append(safe_text(rejection.get("reason")) or "manual rejection")
    return semicolon_join(reasons)


def build_improved_publishable_outputs(
    source_rows: list[dict[str, str]],
    *,
    baseline_match_map: dict[str, dict[str, str]],
    manual_content_overrides: dict[str, dict[str, str]],
    rejection_map: dict[str, list[dict[str, str]]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    vocab = build_vocab(
        [row["representative_title"] for row in source_rows]
        + [
            row["canonical_title"]
            for row in baseline_match_map.values()
            if row.get("canonical_title") and not re.fullmatch(r"Q\d+", row["canonical_title"])
        ]
    )

    prepared_issue_rows: list[dict[str, object]] = []
    excluded_issue_rows: list[dict[str, object]] = []
    for row in source_rows:
        source_title = safe_text(row["representative_title"])
        clean = clean_title(source_title, safe_text(row.get("content_kind")), vocab)
        prepared: dict[str, object] = dict(row)
        prepared["source_title"] = source_title
        prepared["cleaned_title"] = clean.cleaned_title
        prepared["source_normalized_title"] = safe_text(row["normalized_title"])
        prepared["legacy_normalized_title"] = safe_text(row["normalized_title"])
        prepared["representative_title"] = clean.cleaned_title
        prepared["normalized_title"] = clean.normalized_title
        prepared["game_id"] = clean.cluster_key
        prepared["title_cleanup_flags"] = "; ".join(clean.flags)
        prepared["content_class"] = clean.content_class
        prepared["content_form"] = clean.content_form

        match_row = baseline_match_map.get(safe_text(row["normalized_title"]), {})
        for field in MATCH_FIELDS:
            prepared[f"alias_{field}"] = safe_text(match_row.get(field, ""))
        prepared["alias_rejection_notes"] = rejection_reason_for_match(
            match_row,
            rejection_map.get(safe_text(row["normalized_title"]), []),
        )

        override = manual_content_overrides.get(clean.cluster_key)
        publishable = True
        if override:
            if override.get("content_class"):
                prepared["content_class"] = override["content_class"]
            publishable = safe_text(override.get("publishable", "true")).strip().lower() not in {"0", "false", "no"}
            prepared["manual_content_reason"] = safe_text(override.get("reason"))

        if not publishable or prepared["content_class"] in {"disc_noise", "guide_media", "editor_sdk", "utility"}:
            excluded_issue_rows.append(prepared)
        else:
            prepared_issue_rows.append(prepared)

    existing_game_ids = {safe_text(row["game_id"]) for row in prepared_issue_rows}
    for row in prepared_issue_rows:
        game_id = safe_text(row["game_id"])
        if game_id.endswith("0") and game_id[:-1] in existing_game_ids:
            row["game_id"] = game_id[:-1]
            row["title_cleanup_flags"] = semicolon_join([row.get("title_cleanup_flags"), "merged_trailing_zero_ocr"])

    issue_clustered: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in prepared_issue_rows:
        issue_clustered[(safe_text(row["issue_code"]), safe_text(row["game_id"]))].append(row)

    improved_issue_rows: list[dict[str, object]] = []
    per_game_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (issue_code, game_id), rows in sorted(issue_clustered.items()):
        best_issue_row = dict(choose_best_issue_row(rows))
        representative_title, merged_flags, merge_confidence = choose_best_display_title(rows)
        best_issue_row["representative_title"] = representative_title
        best_issue_row["normalized_title"] = normalize_public_title(representative_title)
        best_issue_row["occurrence_count_in_issue"] = len(rows)
        best_issue_row["observed_title_variants"] = semicolon_join(row["source_title"] for row in rows)
        best_issue_row["source_normalized_variants"] = semicolon_join(row["source_normalized_title"] for row in rows)
        best_issue_row["source_kinds"] = semicolon_join(
            sorted(
                {
                    kind.strip()
                    for row in rows
                    for kind in safe_text(row["source_kinds"]).replace(";", ",").split(",")
                    if kind.strip()
                }
            )
        )
        best_issue_row["confidence"] = max(
            rows,
            key=lambda item: {"high": 3, "medium": 2, "low": 1}.get(safe_text(item["confidence"]).lower(), 0),
        )["confidence"]
        best_issue_row["title_cleanup_flags"] = semicolon_join(
            flag for row in rows for flag in safe_text(row["title_cleanup_flags"]).split(";")
        )
        best_issue_row["content_kinds_merged"] = semicolon_join(
            sorted({safe_text(row["content_kind"]) for row in rows if safe_text(row["content_kind"])})
        )
        best_issue_row["content_forms_merged"] = semicolon_join(
            sorted({safe_text(row["content_form"]) for row in rows if safe_text(row["content_form"])})
        )
        best_issue_row["merge_confidence"] = merge_confidence
        best_issue_row["cleanup_flags"] = "; ".join(merged_flags)
        improved_issue_rows.append(best_issue_row)
        per_game_rows[game_id].append(best_issue_row)

    improved_master_rows: list[dict[str, object]] = []
    for game_id, rows in sorted(per_game_rows.items()):
        representative_title, merged_flags, merge_confidence = choose_best_display_title(rows)
        first_row = min(rows, key=lambda row: (safe_text(row["year"]), safe_text(row["issue_code"]), safe_text(row["archive_name"])))
        last_row = max(rows, key=lambda row: (safe_text(row["year"]), safe_text(row["issue_code"]), safe_text(row["archive_name"])))
        first_year = to_int(first_row.get("year"))

        alias_match_rows: list[dict[str, object]] = []
        for row in rows:
            alias = {field: safe_text(row.get(f"alias_{field}", "")) for field in MATCH_FIELDS}
            alias["normalized_title"] = safe_text(row.get("source_normalized_title"))
            alias["source_title"] = safe_text(row.get("source_title"))
            alias["alias_rejection_notes"] = safe_text(row.get("alias_rejection_notes"))
            alias_match_rows.append(alias)

        best_match, match_action, _ranked_candidates = choose_best_match(alias_match_rows, first_year)
        content_classes = {safe_text(row.get("content_class")) for row in rows if safe_text(row.get("content_class"))}
        content_class = "game"
        if "expansion_or_addon" in content_classes:
            content_class = "expansion_or_addon"
        elif "mod_or_conversion" in content_classes:
            content_class = "mod_or_conversion"

        notes_parts = [best_match.get("notes"), best_match.get("_match_notes")]
        if match_action != "retained_best_alias_match":
            notes_parts.append(match_action)

        master_row: dict[str, object] = {
            "normalized_title": normalize_public_title(representative_title),
            "representative_title": representative_title,
            "first_seen_issue": safe_text(first_row["issue_code"]),
            "issue_count": len(rows),
            "occurrence_count": sum(to_int(row.get("occurrence_count_in_issue")) or 1 for row in rows),
            "best_confidence": max(
                rows,
                key=lambda row: {"high": 3, "medium": 2, "low": 1}.get(safe_text(row["confidence"]).lower(), 0),
            )["confidence"],
            "source_kinds": semicolon_join(
                sorted(
                    {
                        kind.strip()
                        for row in rows
                        for kind in safe_text(row["source_kinds"]).split(";")
                        if kind.strip()
                    }
                )
            ),
            "game_id": game_id,
            "first_seen_year": safe_text(first_row["year"]),
            "last_seen_issue": safe_text(last_row["issue_code"]),
            "last_seen_year": safe_text(last_row["year"]),
            "alias_count": len({safe_text(row["source_title"]) for row in rows}),
            "alias_titles": semicolon_join(sorted({safe_text(row["source_title"]) for row in rows})),
            "legacy_normalized_titles": semicolon_join(
                sorted({safe_text(row["source_normalized_title"]) for row in rows})
            ),
            "observed_content_kinds": semicolon_join(
                sorted({safe_text(row["content_kind"]) for row in rows if safe_text(row["content_kind"])})
            ),
            "observed_content_forms": semicolon_join(
                sorted({safe_text(row["content_form"]) for row in rows if safe_text(row["content_form"])})
            ),
            "content_class": content_class,
            "cleanup_flags": "; ".join(merged_flags),
            "merge_confidence": merge_confidence,
            "match_status": safe_text(best_match.get("match_status")),
            "match_confidence": safe_text(best_match.get("match_confidence")),
            "canonical_title": safe_text(best_match.get("canonical_title")),
            "canonical_slug": safe_text(best_match.get("canonical_slug"))
            or (slugify(safe_text(best_match.get("canonical_title"))) if safe_text(best_match.get("canonical_title")) else ""),
            "entity_type": safe_text(best_match.get("entity_type")),
            "release_year": safe_text(best_match.get("release_year")),
            "wikipedia_url": safe_text(best_match.get("wikipedia_url")),
            "wikidata_id": safe_text(best_match.get("wikidata_id")),
            "wikidata_url": safe_text(best_match.get("wikidata_url")),
            "categories": safe_text(best_match.get("categories")),
            "genres": safe_text(best_match.get("genres")),
            "themes": safe_text(best_match.get("themes")),
            "rating_value": safe_text(best_match.get("rating_value")),
            "rating_scale": safe_text(best_match.get("rating_scale")),
            "rating_count": safe_text(best_match.get("rating_count")),
            "rating_source": safe_text(best_match.get("rating_source")),
            "rating_url": safe_text(best_match.get("rating_url")),
            "metadata_sources": safe_text(best_match.get("metadata_sources")),
            "match_action": match_action,
            "match_notes": semicolon_join(notes_parts),
        }
        if (
            master_row["match_status"] == "matched"
            and master_row["canonical_title"]
            and not re.fullmatch(r"Q\d+", master_row["canonical_title"])
            and clean_title(safe_text(master_row["canonical_title"]), "", vocab).cluster_key == game_id
            and master_row["representative_title"] != master_row["canonical_title"]
        ):
            master_row["representative_title"] = master_row["canonical_title"]
            master_row["normalized_title"] = normalize_public_title(master_row["representative_title"])
            master_row["cleanup_flags"] = semicolon_join([master_row["cleanup_flags"], "display_title_backfilled_from_canonical"])
        master_row["data_quality_score"] = compute_data_quality_score(master_row)
        improved_master_rows.append(master_row)

    master_by_game = {row["game_id"]: row for row in improved_master_rows}
    for row in improved_issue_rows:
        master = master_by_game[row["game_id"]]
        row["normalized_title"] = master["normalized_title"]
        row["representative_title"] = master["representative_title"]
        row["content_class"] = master["content_class"]
        row["cleanup_flags"] = master["cleanup_flags"]
        row["merge_confidence"] = master["merge_confidence"]
        for field in [
            "match_status",
            "match_confidence",
            "canonical_title",
            "canonical_slug",
            "entity_type",
            "release_year",
            "wikipedia_url",
            "wikidata_id",
            "wikidata_url",
            "categories",
            "genres",
            "themes",
            "match_action",
            "match_notes",
            "data_quality_score",
        ]:
            row[field] = master.get(field, "")

    excluded_by_game: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in excluded_issue_rows:
        excluded_by_game[safe_text(row["game_id"])].append(row)
    excluded_non_game_rows: list[dict[str, object]] = []
    for game_id, rows in sorted(excluded_by_game.items()):
        representative_title, _, _ = choose_best_display_title(rows)
        excluded_non_game_rows.append(
            {
                "game_id": game_id,
                "representative_title": representative_title,
                "content_class": safe_text(rows[0].get("content_class")),
                "issue_count": len({safe_text(row["issue_code"]) for row in rows}),
                "occurrence_count": len(rows),
                "alias_titles": semicolon_join(sorted({safe_text(row["source_title"]) for row in rows})),
                "source_kinds": semicolon_join(
                    sorted(
                        {
                            kind.strip()
                            for row in rows
                            for kind in safe_text(row["source_kinds"]).replace(";", ",").split(",")
                            if kind.strip()
                        }
                    )
                ),
            }
        )
    return improved_master_rows, improved_issue_rows, excluded_non_game_rows


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


def write_report(
    path: Path,
    *,
    raw_master: int,
    cleaned_master: int,
    raw_issue: int,
    cleaned_issue: int,
    dropped_count: int,
    unresolved_count: int,
    publishable_master_count: int,
    publishable_issue_count: int,
    excluded_count: int,
) -> None:
    text = f"""# Published Result Set Audit

- raw master rows: {raw_master}
- cleaned master rows: {cleaned_master}
- raw issue/title rows: {raw_issue}
- cleaned issue/title rows: {cleaned_issue}
- publishable clustered master rows: {publishable_master_count}
- publishable clustered issue/title rows: {publishable_issue_count}
- excluded non-game/media clusters: {excluded_count}
- dropped noisy rows: {dropped_count}
- unresolved issues: {unresolved_count}

Cleaning rules used:
- drop obvious issue-code/track rows like `CBS0100 (Track 01)`
- drop obvious UI/settings/manual/software noise
- keep multi-word titles that survive the blacklist
- keep title-cased single-word titles only when they are not obvious noise

Publishable tier:
- clusters aliases under a stable `game_id`
- normalizes disc-only version/demo suffixes for clustering
- excludes utilities, editors/SDKs, guide media, and disc-noise rows
- carries conservative cluster-level match/audit columns from the prior enriched release

Original raw data remains untouched in the source snapshot.
"""
    path.write_text(text, encoding="utf-8")


def write_unresolved_summary(path: Path, unresolved_rows: list[dict[str, str]]) -> None:
    root_causes = Counter(row["root_cause"] for row in unresolved_rows)
    lines = [
        "# Unresolved Summary",
        "",
        f"- unresolved issues: {len(unresolved_rows)}",
    ]
    for cause, count in sorted(root_causes.items()):
        lines.append(f"- `{cause}`: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_published_readme(path: Path, *, input_dir: Path, master_count: int, issue_count: int, unresolved_count: int, excluded_count: int) -> None:
    text = f"""# Published Results ({path.parent.name.rsplit('-', 1)[-1]})

This directory is the public-facing clustered result set for the Computer Bild Spiele title reconstruction project.

It is derived from the preserved raw snapshot in:
- `{input_dir}`

## Which file should be used publicly?

Use:
- `publishable_master_games.csv`

That is the best current public game list.

For issue-level detail, use:
- `publishable_issue_titles.csv`

## Files

- `publishable_master_games.csv`
  - one row per clustered game keyed by `game_id`
  - includes audit columns and conservative carried match status

- `publishable_issue_titles.csv`
  - one row per `issue_code + game_id`
  - preserves observed-title provenance and carried cluster match fields

- `excluded_non_game_titles.csv`
  - auditable list of utilities, editors, guide media, and disc-noise clusters removed from the canonical public game tables

- `final_unresolved_issues.csv`
  - unresolved tail from the raw extraction run

- `audit_summary.md`
  - summary of the publishable cleanup and clustering pass

- `unresolved_summary.md`
  - short summary of the unresolved tail

## Current counts

- `publishable_master_games.csv`: {master_count} rows
- `publishable_issue_titles.csv`: {issue_count} rows
- `excluded_non_game_titles.csv`: {excluded_count} rows
- `final_unresolved_issues.csv`: {unresolved_count} rows

## Important caveat

This is a best-effort public game catalog. Observed CBS titles remain distinct from external canonical entity fields, and blank metadata is preferred over weak guesses.
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
    baseline_match_map = read_baseline_match_map(Path(args.baseline_enriched_master))
    manual_content_overrides = read_manual_content_overrides(Path(args.manual_content_overrides))
    rejection_map = read_rejections(Path(args.manual_rejections))

    cleaned_issue_rows, dropped_rows = clean_issue_rows(issue_rows)
    cleaned_issue_rows = [repair_issue_row(row) for row in cleaned_issue_rows]
    cleaned_master_rows = rebuild_master(cleaned_issue_rows)
    publishable_source_rows = publishable_issue_rows(cleaned_issue_rows)
    publishable_source_rows = [repair_issue_row(row) for row in publishable_source_rows]
    publishable_master_rows, publishable_rows, excluded_non_game_rows = build_improved_publishable_outputs(
        publishable_source_rows,
        baseline_match_map=baseline_match_map,
        manual_content_overrides=manual_content_overrides,
        rejection_map=rejection_map,
    )
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
            "game_id",
            "source_title",
            "source_normalized_title",
            "observed_title_variants",
            "source_normalized_variants",
            "occurrence_count_in_issue",
            "content_class",
            "content_form",
            "content_kinds_merged",
            "content_forms_merged",
            "cleanup_flags",
            "merge_confidence",
            "match_status",
            "match_confidence",
            "canonical_title",
            "canonical_slug",
            "entity_type",
            "release_year",
            "wikipedia_url",
            "wikidata_id",
            "wikidata_url",
            "categories",
            "genres",
            "themes",
            "match_action",
            "match_notes",
            "data_quality_score",
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
            "game_id",
            "first_seen_year",
            "last_seen_issue",
            "last_seen_year",
            "alias_count",
            "alias_titles",
            "legacy_normalized_titles",
            "observed_content_kinds",
            "observed_content_forms",
            "content_class",
            "cleanup_flags",
            "merge_confidence",
            "match_status",
            "match_confidence",
            "canonical_title",
            "canonical_slug",
            "entity_type",
            "release_year",
            "wikipedia_url",
            "wikidata_id",
            "wikidata_url",
            "categories",
            "genres",
            "themes",
            "rating_value",
            "rating_scale",
            "rating_count",
            "rating_source",
            "rating_url",
            "metadata_sources",
            "match_action",
            "match_notes",
            "data_quality_score",
        ],
    )
    write_csv(
        output_dir / "excluded_non_game_titles.csv",
        excluded_non_game_rows,
        [
            "game_id",
            "representative_title",
            "content_class",
            "issue_count",
            "occurrence_count",
            "alias_titles",
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
        publishable_master_count=len(publishable_master_rows),
        publishable_issue_count=len(publishable_rows),
        excluded_count=len(excluded_non_game_rows),
    )
    write_unresolved_summary(output_dir / "unresolved_summary.md", analyzed_unresolved)
    write_published_readme(
        output_dir / "README.md",
        input_dir=input_dir,
        master_count=len(publishable_master_rows),
        issue_count=len(publishable_rows),
        unresolved_count=len(analyzed_unresolved),
        excluded_count=len(excluded_non_game_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
