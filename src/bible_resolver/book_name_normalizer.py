"""Data-driven book-title sanitation for Bible database citations.

Each language has a JSON file in ``book_name_sanitizers/``.  A configuration
maps canonical MyBible book numbers to the display title used in seeds, and may
optionally declare ``aliases`` for title-level variants that no DB column
carries.  The resolver supplies the language and book number; this module has no
SQLite or reference-parsing responsibilities.
"""

from __future__ import annotations

import json
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


def sanitize_book_name(raw_name: str, book_number: int, language: str | None) -> str:
    """Return the configured readable title, or preserve ``raw_name``.

    ``language`` is deliberately optional so existing callers remain safe
    while a new language configuration is being introduced.
    """
    if not language:
        return raw_name
    return _load_language(language).get(str(book_number), raw_name)
