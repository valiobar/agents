from __future__ import annotations

import re


def normalize_search_key(value: str | None) -> str | None:
    if value is None:
        return None
    compact = re.sub(r"[^0-9A-Za-z]+", "", value)
    normalized = compact.upper()
    return normalized or None


def normalize_search_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.casefold().strip().split())
    return normalized or None


def build_search_text(*parts: str | None) -> str:
    normalized_parts = [normalize_search_text(part) for part in parts]
    compact = [part for part in normalized_parts if part]
    return " ".join(compact)
