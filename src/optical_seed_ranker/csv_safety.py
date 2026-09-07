from __future__ import annotations

from unicodedata import category

FORMULA_PREFIXES = frozenset("=+-@\t\r\n")
TEXT_ENCODING_FIELD = "_text_encoding"
TEXT_ENCODING_VALUE = "spreadsheet-safe-v1"


def has_spreadsheet_unsafe_prefix(value: str) -> bool:
    if not value:
        return False
    first = value[0]
    return (
        first in FORMULA_PREFIXES
        or first.isspace()
        or category(first) in {"Cc", "Cf"}
    )


def spreadsheet_safe_text(value: str) -> str:
    """Encode a text cell so spreadsheet applications cannot evaluate it."""

    if has_spreadsheet_unsafe_prefix(value) or value.startswith("'"):
        return "'" + value
    return value


def restore_spreadsheet_text(value: str, *, encoded: bool) -> str:
    """Reverse text written by :func:`spreadsheet_safe_text`."""

    if not encoded:
        return value
    if value.startswith("''"):
        return value[1:]
    if value.startswith("'") and has_spreadsheet_unsafe_prefix(value[1:]):
        return value[1:]
    return value


def spreadsheet_safe_path(value: str) -> str:
    """Protect a path without breaking consumers that use it as a filesystem path."""

    if has_spreadsheet_unsafe_prefix(value):
        return f"./{value}"
    return value
