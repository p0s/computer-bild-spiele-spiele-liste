#!/usr/bin/env python3
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "vs",
    "am",
    "auf",
    "aus",
    "bei",
    "das",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "ein",
    "eine",
    "einem",
    "einen",
    "einer",
    "eines",
    "fuer",
    "fur",
    "im",
    "ins",
    "mit",
    "nach",
    "ohne",
    "und",
    "vom",
    "von",
    "vor",
    "zum",
    "zur",
    "zu",
    "uber",
    "ueber",
    "rund",
    "ums",
}

VOCAB_BOOST = {
    "age",
    "ages",
    "air",
    "alone",
    "anno",
    "battlefield",
    "berlin",
    "call",
    "captain",
    "chaos",
    "clancy",
    "company",
    "conflict",
    "conquer",
    "dutchmans",
    "empires",
    "enemy",
    "ghost",
    "gold",
    "heroes",
    "island",
    "journey",
    "kingdom",
    "knight",
    "legend",
    "lost",
    "mord",
    "mythology",
    "need",
    "oblivion",
    "pacific",
    "pirates",
    "project",
    "quake",
    "rainbow",
    "recon",
    "rush",
    "sacred",
    "sands",
    "show",
    "simon",
    "soccer",
    "speed",
    "sparta",
    "story",
    "stronghold",
    "territory",
    "the",
    "toledo",
    "underworld",
    "war",
    "wars",
    "wheelsof",
    "world",
    "worldin",
    "x",
    "zoo",
}

NON_GAME_EXACT = {
    "werbung",
    "filme",
    "topdemos",
    "online spiel",
    "onlinespiel",
    "online spiele",
    "loesung",
    "loesungsbuecher",
    "browsergames",
    "browsergames small",
    "demo shield launch",
    "reserved for status bar",
    "reserved for statusbar",
    "code aktionen",
    "codeaktionen",
    "jahresinhalt cbs",
    "kinofilm",
    "kinovorschau",
    "cheats",
}

GUIDE_MEDIA_PATTERNS = [
    r"komplettl",
    r"loesungs",
    r"lösungs",
    r"\btrailer\b",
    r"trailerliste",
    r"bildschirmhintergr",
    r"bildschirmschoner",
    r"screenmate",
    r"spieltricks",
    r"spieltipps",
    r"hintergr",
    r"wallpaper",
    r"kinofilm",
    r"kinovorschau",
    r"\bcheats\b",
]

EDITOR_PATTERNS = [
    r"\beditor\b",
    r"leveleditor",
    r"map editor",
    r"world editor",
    r"construction set",
    r"\bsdk\b",
    r"mod sdk",
    r"modtool",
    r"mod kit",
    r"toolkit",
    r"karten editor",
]

UTILITY_PATTERNS = [
    r"\.net framework",
    r"^net ?framework",
    r"^netframework",
    r"webde.*surfer",
    r"^skype\b",
    r"^skype\d",
    r"team speak",
    r"^teamspeak",
    r"\bfraps\b",
    r"\bxfire\b",
    r"ccleaner",
    r"backup",
    r"optimizer",
    r"firewall",
    r"true image",
    r"drive image",
    r"\bdivx\b",
    r"sharedrive",
    r"passwort safe",
    r"passworte",
    r"phys ?x",
    r"radeon",
    r"nvidia",
    r"ashampoo",
    r"cobian",
    r"comodo",
    r"acronis",
    r"tcp optimizer",
    r"secunia",
    r"sandra",
    r"spybot",
    r"dsl manager",
    r"easytoolz",
    r"chk tooltips",
    r"tooltip handler",
    r"aisuite",
    r"smart surfer",
    r"norton",
    r"sound blaster",
    r"mc afee",
    r"\bstinger\b",
]

EXPANSION_PATTERNS = [
    r"\badd[ -]?on\b",
    r"\baddon\b",
    r"\bexpansion pack\b",
    r"\bmission pack\b",
]

MOD_PATTERNS = [
    r"\bmod\b",
    r"\btotal conversion\b",
]

DISC_DESCRIPTOR_PATTERNS = [
    re.compile(r"\((?:add[ -]?on\s+)?demo\)$", re.IGNORECASE),
    re.compile(r"\((?:full\s*version|vollversion)\)$", re.IGNORECASE),
    re.compile(r"\b(?:full\s*version|vollversion|bonus|extras?)\b$", re.IGNORECASE),
    re.compile(r"\bdemo\b$", re.IGNORECASE),
]

VERSION_SUFFIX_PATTERNS = [
    re.compile(r"\bversion\s*[0-9][0-9a-z ._-]*$", re.IGNORECASE),
    re.compile(r"\bupdate\s*[0-9][0-9a-z ._-]*$", re.IGNORECASE),
    re.compile(r"\bv\s*[0-9][0-9a-z ._-]*$", re.IGNORECASE),
    re.compile(r"(?<=[A-Za-z]{4})v[0-9][0-9a-z._ -]*$", re.IGNORECASE),
    re.compile(r"(?<=[A-Za-z]{4})v$", re.IGNORECASE),
    re.compile(r"\bv$", re.IGNORECASE),
]

SMALL_WORDS_LOWER = STOPWORDS | {"de", "la", "le"}

POST_CLEAN_REPAIRS = [
    (re.compile(r"\bSim on the\b"), "Simon the"),
    (re.compile(r"\bChaosistdashalbe\b"), "Chaos ist das halbe"),
    (re.compile(r"\bOrdendes\b"), "Orden des"),
    (re.compile(r"\bKnigreichdes\b"), "Knigreich des"),
    (re.compile(r"\bEndeder\b"), "Ende der"),
    (re.compile(r"\bRushfor\b"), "Rush for"),
    (re.compile(r"\bSandsof\b"), "Sands of"),
    (re.compile(r"\bKingdomof\b"), "Kingdom of"),
    (re.compile(r"\bGameofthe\b"), "Game of the"),
    (re.compile(r"\bBeyondthe\b"), "Beyond the"),
    (re.compile(r"\bWorldin\b"), "World in"),
    (re.compile(r"\bSwordof\b"), "Sword of"),
    (re.compile(r"\bWheelsof\b"), "Wheels of"),
]

SEGMENT_HINTS = {
    "of",
    "the",
    "and",
    "und",
    "der",
    "die",
    "das",
    "des",
    "im",
    "in",
    "on",
    "von",
    "auf",
    "zum",
    "zur",
    "with",
    "for",
    "durch",
    "nach",
    "ums",
}

RAW_QID_GENERIC_EXCEPTIONS = {"air taxi", "astro man", "the show", "startzeit"}

MATCH_FIELDS = [
    "canonical_title",
    "canonical_slug",
    "match_status",
    "match_confidence",
    "match_method",
    "match_source",
    "match_source_url",
    "match_fetched_at",
    "entity_type",
    "release_year",
    "wikipedia_url",
    "wikidata_id",
    "wikidata_url",
    "categories",
    "genres",
    "themes",
    "category_source",
    "category_source_url",
    "category_fetched_at",
    "category_confidence",
    "rating_value",
    "rating_scale",
    "rating_count",
    "rating_source",
    "rating_url",
    "rating_fetched_at",
    "rating_confidence",
    "metadata_sources",
    "notes",
]


@dataclass(frozen=True)
class CleanTitleResult:
    cleaned_title: str
    normalized_title: str
    cluster_key: str
    flags: list[str]
    content_class: str
    content_form: str


def safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def ascii_fold(text: str) -> str:
    text = safe_text(text)
    text = text.replace("ß", "ss").replace("ẞ", "SS")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def normalize_spaces(text: str) -> str:
    text = safe_text(text)
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for src, dest in replacements.items():
        text = text.replace(src, dest)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,;:!?])", r"\1", text)
    text = re.sub(r"\s*-\s*", " - ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_/")
    return text


def normalize_public_title(text: str) -> str:
    text = ascii_fold(text).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str) -> str:
    text = ascii_fold(text).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return re.sub(r"-+", "-", text)


def build_cluster_key(text: str) -> str:
    text = normalize_public_title(text)
    text = re.sub(r"\b(?:full\s*version|vollversion|bonus|extras?)\b$", "", text).strip()
    text = re.sub(r"\bdemo\b$", "", text).strip()
    text = re.sub(r"\bversion\s*[0-9][0-9a-z ]*$", "", text).strip()
    text = re.sub(r"\bupdate\s*[0-9][0-9a-z ]*$", "", text).strip()
    text = re.sub(r"\bv\s*[0-9][0-9a-z ]*$", "", text).strip()
    text = re.sub(r"\bv$", "", text).strip()
    return re.sub(r"\s+", "", text)


def classify_content(title: str) -> str:
    lower = normalize_public_title(title)
    if lower in NON_GAME_EXACT:
        return "disc_noise"
    if any(re.search(pattern, lower) for pattern in GUIDE_MEDIA_PATTERNS):
        return "guide_media"
    if any(re.search(pattern, lower) for pattern in EDITOR_PATTERNS):
        return "editor_sdk"
    if any(re.search(pattern, lower) for pattern in UTILITY_PATTERNS):
        return "utility"
    if any(re.search(pattern, lower) for pattern in EXPANSION_PATTERNS):
        return "expansion_or_addon"
    if any(re.search(pattern, lower) for pattern in MOD_PATTERNS) and "mod kit" not in lower and "mod sdk" not in lower:
        return "mod_or_conversion"
    return "game"


def content_form_from_kinds(content_kind_value: str, content_class: str) -> str:
    value = safe_text(content_kind_value).strip().lower()
    if content_class in {"utility", "editor_sdk", "guide_media", "disc_noise"}:
        return content_class
    if content_class in {"expansion_or_addon", "mod_or_conversion"}:
        if value == "demo":
            return f"{content_class}_demo"
        return content_class
    if value == "full_version":
        return "full_version_game"
    if value == "demo":
        return "demo_game"
    return "game_title"


def split_camel_and_digits(text: str) -> str:
    parts: list[str] = []
    for token in text.split():
        if re.fullmatch(r"[A-Za-z]\d+", token):
            parts.append(token)
            continue
        token = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", token)
        token = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", token)
        if not re.fullmatch(r"[A-Za-z]\d+", token):
            token = re.sub(r"(?<=[A-Za-z]{2})(?=\d{1,4}\b)", " ", token)
            token = re.sub(r"(?<=\d)(?=[A-Za-z]{2,})", " ", token)
        parts.append(token)
    return normalize_spaces(" ".join(parts))


def strip_suffixes(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    current = text
    changed = True
    while changed:
        changed = False
        for pattern in DISC_DESCRIPTOR_PATTERNS:
            updated = pattern.sub("", current).strip()
            if updated != current:
                current = updated
                flags.append("stripped_disc_descriptor")
                changed = True
        for pattern in VERSION_SUFFIX_PATTERNS:
            updated = pattern.sub("", current).strip()
            if updated != current:
                current = updated
                flags.append("stripped_version_suffix")
                changed = True
        current = normalize_spaces(current)
    return current, flags


def build_vocab(titles: Iterable[str]) -> Counter[str]:
    vocab: Counter[str] = Counter()
    for title in titles:
        title = split_camel_and_digits(normalize_spaces(title))
        for token in re.findall(r"[A-Za-zÀ-ÿ']+", title):
            folded = ascii_fold(token).lower()
            if folded:
                vocab[folded] += 1
    for word in STOPWORDS:
        vocab[word] += 200
    for word in VOCAB_BOOST:
        vocab[word] += 25
    return vocab


def best_segmentation(token: str, vocab: Counter[str]) -> list[str] | None:
    folded = ascii_fold(token).lower()
    if not re.fullmatch(r"[a-z]+", folded):
        return None
    if len(folded) < 6 or vocab[folded] >= 3:
        return None
    max_len = len(folded)

    from functools import lru_cache

    @lru_cache(maxsize=None)
    def solve(index: int) -> tuple[float, tuple[str, ...] | None]:
        if index == max_len:
            return 0.0, tuple()
        best_score = -10**9
        best_parts: tuple[str, ...] | None = None
        for end in range(index + 2, min(max_len, index + 20) + 1):
            part = folded[index:end]
            count = vocab[part]
            if count == 0:
                continue
            tail_score, tail_parts = solve(end)
            if tail_parts is None:
                continue
            score = math.log(count + 1.0) + tail_score - 0.25
            if len(part) == 1:
                score -= 1.0
            if score > best_score:
                best_score = score
                best_parts = (part,) + tail_parts
        return best_score, best_parts

    score, parts = solve(0)
    if not parts or len(parts) < 2:
        return None
    if any(len(part) == 1 for part in parts):
        return None
    if sum(1 for part in parts if vocab[part] >= 2 or part in STOPWORDS) != len(parts):
        return None
    if score < 3.5:
        return None
    return list(parts)


def recase_segment(part: str, original_token: str) -> str:
    if original_token.isupper() and len(original_token) <= 5:
        return part.upper()
    if part in SMALL_WORDS_LOWER:
        return part.lower()
    if original_token[:1].isupper():
        return part.capitalize()
    return part.lower()


def repair_compounds(text: str, vocab: Counter[str]) -> tuple[str, list[str]]:
    flags: list[str] = []
    repaired_parts: list[str] = []
    for token in text.split():
        bare = re.sub(r"[^A-Za-zÀ-ÿ']", "", token)
        folded = ascii_fold(bare).lower()
        hinted = any(hint in folded[1:-1] for hint in SEGMENT_HINTS)
        seg = best_segmentation(bare, vocab) if bare and hinted else None
        if seg and folded not in {"wii", "xfire"}:
            rebuilt = " ".join(recase_segment(part, token) for part in seg)
            token = token.replace(bare, rebuilt)
            flags.append("split_compound_token")
        repaired_parts.append(token)
    return normalize_spaces(" ".join(repaired_parts)), flags


def apply_post_clean_repairs(text: str) -> tuple[str, list[str]]:
    current = text
    applied: list[str] = []
    for pattern, replacement in POST_CLEAN_REPAIRS:
        updated = pattern.sub(replacement, current)
        if updated != current:
            current = updated
            applied.append("manual_token_repair")
    return normalize_spaces(current), applied


def clean_title(title: str, content_kind: str, vocab: Counter[str]) -> CleanTitleResult:
    original = normalize_spaces(title)
    content_class = classify_content(original)
    content_form = content_form_from_kinds(content_kind, content_class)
    current = split_camel_and_digits(original)
    flags: list[str] = []
    current, suffix_flags = strip_suffixes(current)
    flags.extend(suffix_flags)
    current, compound_flags = repair_compounds(current, vocab)
    flags.extend(compound_flags)
    current, repair_flags = apply_post_clean_repairs(current)
    flags.extend(repair_flags)
    current, suffix_flags_2 = strip_suffixes(current)
    flags.extend(suffix_flags_2)
    current = normalize_spaces(current)
    return CleanTitleResult(
        cleaned_title=current,
        normalized_title=normalize_public_title(current),
        cluster_key=build_cluster_key(current),
        flags=sorted(set(flags)),
        content_class=content_class,
        content_form=content_form,
    )


def choose_best_issue_row(rows: list[dict[str, object]]) -> dict[str, object]:
    def score(row: dict[str, object]) -> tuple[object, ...]:
        conf_rank = {"high": 3, "medium": 2, "low": 1}.get(safe_text(row.get("confidence")).lower(), 0)
        source_rank = 0
        source_kinds = set(filter(None, safe_text(row.get("source_kinds")).replace(";", ",").split(",")))
        if "vollversion-fullversion" in source_kinds:
            source_rank += 3
        if "disc-metadata-value" in source_kinds:
            source_rank += 2
        flags = set(filter(None, safe_text(row.get("title_cleanup_flags")).split(";")))
        clean_bonus = 0
        if "split_compound_token" not in flags:
            clean_bonus += 1
        if "stripped_version_suffix" not in flags:
            clean_bonus += 1
        title = safe_text(row.get("representative_title"))
        return (conf_rank, source_rank, clean_bonus, len(title.split()), -len(title), title)

    return max(rows, key=score)


def choose_best_display_title(rows: list[dict[str, object]]) -> tuple[str, list[str], str]:
    def title_score(row: dict[str, object]) -> tuple[object, ...]:
        title = safe_text(row.get("cleaned_title") or row.get("representative_title"))
        flags = set(filter(None, safe_text(row.get("title_cleanup_flags")).split(";")))
        return (
            "stripped_version_suffix" in flags,
            "stripped_disc_descriptor" in flags,
            "split_compound_token" in flags,
            -len(title),
            title,
        )

    candidates = sorted(rows, key=title_score)
    best = candidates[0]
    merged_flags = sorted({flag for row in rows for flag in safe_text(row.get("title_cleanup_flags")).split(";") if flag})
    merge_confidence = "high"
    if "split_compound_token" in merged_flags:
        merge_confidence = "medium"
    cleaned_titles = {safe_text(row.get("cleaned_title")) for row in rows}
    if len(cleaned_titles) > 1 and any("stripped_version_suffix" not in safe_text(row.get("title_cleanup_flags")) for row in rows):
        merge_confidence = "medium"
    return safe_text(best.get("cleaned_title") or best.get("representative_title")), merged_flags, merge_confidence


def is_bad_qid_title(text: str) -> bool:
    return bool(re.fullmatch(r"Q\d+", safe_text(text).strip()))


def to_int(value: object) -> int | None:
    text = safe_text(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def semicolon_join(values: Iterable[object]) -> str:
    cleaned = [safe_text(value).strip() for value in values if safe_text(value).strip()]
    if not cleaned:
        return ""
    return "; ".join(dict.fromkeys(cleaned))


def compute_match_quality(row: dict[str, object], cluster_first_year: int | None) -> tuple[int, list[str]]:
    notes: list[str] = []
    status = safe_text(row.get("match_status"))
    if status == "matched":
        score = 60
    elif status == "ambiguous":
        return 25, ["ambiguous_source_alias"]
    else:
        return 5, ["unmatched_source_alias"]

    canonical_title = safe_text(row.get("canonical_title"))
    if is_bad_qid_title(canonical_title):
        title_text = normalize_public_title(safe_text(row.get("source_title") or row.get("representative_title")))
        token_count = len(title_text.split())
        release_year = to_int(row.get("release_year"))
        can_backfill = (
            safe_text(row.get("entity_type")) == "game"
            and title_text not in RAW_QID_GENERIC_EXCEPTIONS
            and token_count >= 2
            and (cluster_first_year is None or release_year is None or release_year <= cluster_first_year + 3)
        )
        if can_backfill:
            score -= 12
            score += 8
            notes.append("raw_qid_title_backfill_candidate")
        else:
            score -= 45
            notes.append("demoted_raw_qid_title")
    else:
        score += 10

    if safe_text(row.get("wikipedia_url")):
        score += 10
    if safe_text(row.get("wikidata_id")):
        score += 5
    if safe_text(row.get("categories")) or safe_text(row.get("genres")):
        score += 5
    if safe_text(row.get("release_year")):
        score += 5

    release_year = to_int(row.get("release_year"))
    if cluster_first_year is not None and release_year is not None:
        if release_year > cluster_first_year + 3:
            score -= 50
            notes.append("demoted_release_year_conflict")
        elif release_year > cluster_first_year:
            notes.append("release_after_first_issue_possible_preview")

    if "wikidata.org/wiki/Q" in safe_text(row.get("match_source_url")) and not safe_text(row.get("wikipedia_url")):
        score -= 10
        notes.append("wikidata_only_match")

    if safe_text(row.get("alias_rejection_notes")):
        score -= 60
        notes.append("manual_rejection")

    return score, notes


def choose_best_match(rows: list[dict[str, object]], first_issue_year: int | None) -> tuple[dict[str, object], str, list[dict[str, object]]]:
    candidates: list[tuple[int, dict[str, object], list[str]]] = []
    for row in rows:
        quality, notes = compute_match_quality(row, first_issue_year)
        enriched = dict(row)
        enriched["_match_quality"] = quality
        enriched["_match_notes"] = "; ".join(notes)
        candidates.append((quality, enriched, notes))
    candidates.sort(key=lambda item: (item[0], safe_text(item[1].get("canonical_title")), safe_text(item[1].get("wikipedia_url"))), reverse=True)

    if not candidates:
        blank = {field: "" for field in MATCH_FIELDS}
        blank["match_status"] = "unmatched"
        blank["_match_quality"] = 0
        blank["_match_notes"] = "no_source_aliases"
        return blank, "no_alias_match_data", []

    best_quality, best_row, _ = candidates[0]
    matched_candidates = [row for quality, row, _ in candidates if safe_text(row.get("match_status")) == "matched"]
    conflicting = {
        safe_text(row.get("canonical_slug")) or safe_text(row.get("wikidata_id"))
        for row in matched_candidates
        if safe_text(row.get("canonical_slug")) or safe_text(row.get("wikidata_id"))
    }

    action = "retained_best_alias_match"
    if is_bad_qid_title(safe_text(best_row.get("canonical_title"))) and "raw_qid_title_backfill_candidate" in safe_text(best_row.get("_match_notes")):
        best_row["canonical_title"] = safe_text(best_row.get("source_title") or best_row.get("representative_title"))
        best_row["canonical_slug"] = slugify(best_row["canonical_title"])
        best_row["notes"] = semicolon_join([best_row.get("notes"), "canonical_title_backfilled_from_local_title"])

    if best_quality < 50:
        ambiguous_exists = any(safe_text(row.get("match_status")) == "ambiguous" for _, row, _ in candidates)
        blank = {field: "" for field in MATCH_FIELDS}
        blank["match_status"] = "ambiguous" if ambiguous_exists else "unmatched"
        blank["match_confidence"] = "low"
        blank["notes"] = semicolon_join([best_row.get("_match_notes"), best_row.get("notes")])
        blank["_match_quality"] = best_quality
        blank["_match_notes"] = safe_text(best_row.get("_match_notes"))
        return blank, "demoted_weak_alias_match", [row for _, row, _ in candidates]

    if len(conflicting) > 1:
        best_row["notes"] = semicolon_join([best_row.get("notes"), "cluster_has_multiple_canonical_targets"])
        action = "retained_with_cluster_conflict"

    return best_row, action, [row for _, row, _ in candidates]


def compute_data_quality_score(row: dict[str, object]) -> int:
    score = 35
    if safe_text(row.get("content_class")) == "game":
        score += 10
    if safe_text(row.get("merge_confidence")) == "high":
        score += 10
    elif safe_text(row.get("merge_confidence")) == "medium":
        score += 5
    if safe_text(row.get("match_status")) == "matched":
        score += 20
    elif safe_text(row.get("match_status")) == "ambiguous":
        score += 5
    if safe_text(row.get("wikipedia_url")):
        score += 5
    if safe_text(row.get("wikidata_id")):
        score += 5
    if safe_text(row.get("release_year")):
        score += 4
    if safe_text(row.get("categories")) or safe_text(row.get("genres")):
        score += 3
    if safe_text(row.get("rating_value")):
        score += 3
    flags = set(filter(None, safe_text(row.get("cleanup_flags")).split(";")))
    if "split_compound_token" in flags:
        score -= 4
    if "demoted_raw_qid_title" in safe_text(row.get("match_notes")):
        score -= 10
    if "demoted_release_year_conflict" in safe_text(row.get("match_notes")):
        score -= 10
    return max(0, min(100, score))
