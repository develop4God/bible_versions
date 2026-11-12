"""Shared Bible verse resolver for the bible_versions SQLite databases."""

from .book_name_normalizer import (
    load_title_aliases,
    resolve_book_title,
    sanitize_book_name,
)
from .books_sot import BooksSotError, load_books_sot
from .databases import DatabaseIntegrityError, DatabaseNotFoundError, database_path
from .resolver import (
    Resolution,
    UnmappedBookWarning,
    VerseResolver,
    clean_verse_text,
    fetch_text,
    load_versification_shifts,
    parse_en_ref,
)

__all__ = [
    "BooksSotError",
    "DatabaseIntegrityError",
    "DatabaseNotFoundError",
    "Resolution",
    "UnmappedBookWarning",
    "VerseResolver",
    "clean_verse_text",
    "database_path",
    "fetch_text",
    "load_books_sot",
    "load_title_aliases",
    "load_versification_shifts",
    "parse_en_ref",
    "resolve_book_title",
    "sanitize_book_name",
]
