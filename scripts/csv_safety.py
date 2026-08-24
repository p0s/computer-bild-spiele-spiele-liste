from __future__ import annotations

FORMULA_PREFIXES = ("=", "+", "-", "@")


def is_unsafe_spreadsheet_cell(value: object) -> bool:
    normalized = str(value or "").lstrip("\ufeff \t\r\n")
    return bool(normalized) and normalized.startswith(FORMULA_PREFIXES)
