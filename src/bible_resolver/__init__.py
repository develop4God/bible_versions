"""Shared Bible verse resolver for the bible_versions SQLite databases."""

from .resolver import (
    VerseResolver,
    clean_verse_text,
    fetch_text,
    load_books_sot,
    parse_en_ref,
)

__all__ = [
    "VerseResolver",
    "clean_verse_text",
    "fetch_text",
    "load_books_sot",
    "parse_en_ref",
]
