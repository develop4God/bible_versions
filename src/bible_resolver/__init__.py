"""Shared Bible verse resolver for the bible_versions SQLite databases."""

from .book_name_normalizer import load_title_aliases, sanitize_book_name
from .resolver import (
    Resolution,
    VerseResolver,
    clean_verse_text,
    fetch_text,
    load_books_sot,
    load_versification_shifts,
    parse_en_ref,
)

__all__ = [
    "Resolution",
    "VerseResolver",
    "clean_verse_text",
    "fetch_text",
    "load_books_sot",
    "load_title_aliases",
    "load_versification_shifts",
    "parse_en_ref",
    "sanitize_book_name",
]
