"""Data-driven book-title sanitation for Bible database citations.

Each language has a JSON file in ``book_name_sanitizers/``.  A configuration
maps canonical MyBible book numbers to the display title used in seeds (or sets
``"passthrough": true`` when each DB's own titles should be kept; ``keep_db_title``
lists book numbers whose spelling legitimately differs per edition, e.g. French
"Éphésiens"/"Ephésiens", so each DB keeps its own), and may
optionally declare ``aliases`` for title-level variants that no DB column
carries.  The resolver supplies the language and book number; this module has no
SQLite or reference-parsing responsibilities.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent / "data" / "book_name_sanitizers"


@lru_cache(maxsize=None)
def _load_config(language: str) -> dict:
    path = _CONFIG_DIR / f"{language.lower()}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def _load_language(language: str) -> dict[str, str]:
    """Return the ``book_number`` → canonical title map for *language*."""
    return _load_config(language).get("book_names", {})


def load_title_aliases(language: str | None) -> dict[str, str]:
    """Return the optional ``variant title`` → ``canonical title`` map.

    ``book_names`` is keyed by book_number, so it can only correct the titles a
    DB itself produces. A seed may also contain variants no DB column carries —
    e.g. Arabic "رؤيا يوحنا اللاهوتي" for Revelation while the canonical citation
    form is "الرؤيا". Declaring them here lets the repair pass normalize those
    titles instead of having to leave them unmatched.
    """
    if not language:
        return {}
    return _load_config(language).get("aliases", {})


def normalize_title(title: str) -> str:
    """Collapse stray whitespace (newlines, hair spaces, trailing blanks) in a DB title."""
    title = "".join(" " if unicodedata.category(c) == "Zs" else c for c in title)
    return re.sub(r"\s+", " ", title).strip()


def is_passthrough(language: str | None) -> bool:
    """True when the language deliberately keeps each DB's own titles (e.g. ``ja``)."""
    return bool(language) and bool(_load_config(language).get("passthrough"))


def resolve_book_title(
    raw_name: str, book_number: int, language: str | None
) -> tuple[str, str]:
    """Return ``(title, source)`` where *source* says why that title was chosen.

    ``mapped``       the language map has this book number;
    ``passthrough``  the language declares DB titles are kept as-is;
    ``unmapped``     a config exists but lacks this book (title is the raw one);
    ``no-config``    no config for the language (title is the raw one).

    Raw titles are always whitespace-normalized.
    """
    if language:
        mapped = _load_language(language).get(str(book_number))
        if mapped:
            return mapped, "mapped"
        if book_number in _load_config(language).get("keep_db_title", ()):
            return normalize_title(raw_name), "passthrough"
        if is_passthrough(language):
            return normalize_title(raw_name), "passthrough"
        if _load_config(language):
            return normalize_title(raw_name), "unmapped"
    return normalize_title(raw_name), "no-config"


def sanitize_book_name(raw_name: str, book_number: int, language: str | None) -> str:
    """Return the configured readable title, or the normalized ``raw_name``."""
    return resolve_book_title(raw_name, book_number, language)[0]
