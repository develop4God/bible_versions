"""Shared English-reference resolver for native Bible SQLite databases.

Reference parsing and verse-text cleanup live here.  Language-specific book
title sanitation is intentionally delegated to ``book_name_normalizer``.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.request
from typing import Self

from pathlib import Path

from .book_name_normalizer import sanitize_book_name


BOOKS_SOT_URL = (
    "https://raw.githubusercontent.com/develop4god/bible_versions"
    "/refs/heads/main/bible_books.json"
)
_DEVA = str.maketrans("०१२३४५६७८९", "0123456789")
_books_sot_cache: dict[str, int] | None = None
_VERSIFICATION_SHIFTS_PATH = Path(__file__).parent / "data" / "versification_shifts.json"
_versification_shifts_cache: dict | None = None


def load_versification_shifts(language: str | None, db_version: str) -> dict[str, str]:
    """Load known English->native chapter:verse remaps for *language*/*db_version*.

    ``language`` is the seed's language code (e.g. ``de``); ``db_version`` is
    the Bible DB's filename stem (e.g. ``LU17_de`` for ``Bibles/DE/LU17_de.SQLite3``).
    Covers cases where a DB's chapter numbering diverges from the English
    source references seeds are built from (e.g. German Joel/Malachi's
    different chapter splits). Missing language/version is a safe no-op.
    """
    global _versification_shifts_cache
    if not language:
        return {}
    if _versification_shifts_cache is None:
        if _VERSIFICATION_SHIFTS_PATH.exists():
            with open(_VERSIFICATION_SHIFTS_PATH, encoding="utf-8") as source:
                _versification_shifts_cache = json.load(source)
        else:
            _versification_shifts_cache = {}
    return _versification_shifts_cache.get(language.upper(), {}).get(db_version, {})


def load_books_sot(local_path: str | None = None) -> dict[str, int]:
    """Load the English-name to canonical-book-number source of truth."""
    global _books_sot_cache
    if _books_sot_cache is not None:
        return _books_sot_cache
    if local_path and os.path.exists(local_path):
        with open(local_path, encoding="utf-8") as source:
            data = json.load(source)
    else:
        with urllib.request.urlopen(BOOKS_SOT_URL) as response:
            data = json.loads(response.read())
    _books_sot_cache = {
        name: entry["book_number"] for name, entry in data["books"].items()
    }
    return _books_sot_cache


def parse_en_ref(cita: str) -> tuple[str, int, int, int] | None:
    """Parse ``John 3:16`` and ``1 Corinthians 13:4-7`` references."""
    cita = cita.strip().translate(_DEVA)
    cita = re.sub(r"\s+[A-Z0-9]{2,6}$", "", cita).strip()
    match = re.match(
        r"^((?:\d\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(\d+):(\d+)(?:-(\d+))?$",
        cita,
    )
    if not match:
        return None
    return (
        match.group(1).strip(),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)) if match.group(4) else int(match.group(3)),
    )


def clean_verse_text(text: str) -> str:
    """Strip database markup and editorial notes while preserving verse text."""
    # The backreference pairs each open tag with its own close tag, so a note
    # that nests another element (<n>…<f>[30]</f>…</n>) is dropped whole.
    text = re.sub(r"<(f|n|S|m)>.*?</\1>", "", text)
    text = text.replace("&quot;", '"')
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[①-⓿]", "", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([,;:.!?])", r"\1", text).strip()


def fetch_text(
    cursor: sqlite3.Cursor,
    book_number: int,
    chapter: int,
    v_start: int,
    v_end: int,
) -> str | None:
    """Fetch and sanitize a complete verse range, or return ``None``."""
    cursor.execute(
        "SELECT text FROM verses "
        "WHERE book_number=? AND chapter=? AND verse>=? AND verse<=? "
        "ORDER BY verse",
        (book_number, chapter, v_start, v_end),
    )
    rows = cursor.fetchall()
    if not rows or any(row[0] is None for row in rows):
        return None
    return clean_verse_text(" ".join(row[0] for row in rows))


class VerseResolver:
    """Resolve English references into sanitized native citations and text.

    ``language`` selects a JSON configuration in ``book_name_sanitizers``.
    When omitted, the language is read from the database's own info table
    (language row), so titles are sanitized by content, not by file name.
    A database with neither returns its titles unchanged.
    """

    def __init__(
        self,
        sqlite_path: str,
        books_sot_path: str | None = None,
        language: str | None = None,
    ) -> None:
        self.books_sot = load_books_sot(books_sot_path)
        db_version = os.path.basename(sqlite_path)
        if db_version.lower().endswith(".gz"):
            db_version = db_version[: -len(".gz")]
        db_version = os.path.splitext(db_version)[0]
        self._temp_path: str | None = None
        if sqlite_path.lower().endswith(".gz"):
            fd, self._temp_path = tempfile.mkstemp(suffix=".SQLite3")
            os.close(fd)
            with gzip.open(sqlite_path, "rb") as source, open(
                self._temp_path, "wb"
            ) as destination:
                shutil.copyfileobj(source, destination)
            sqlite_path = self._temp_path
        self.conn: sqlite3.Connection | None = sqlite3.connect(sqlite_path)
        self.cursor: sqlite3.Cursor | None = self.conn.cursor()
        self.language = (language or self._db_language() or "").lower() or None
        self.versification_shifts = load_versification_shifts(self.language, db_version)

    def _db_language(self) -> str | None:
        """Read the ``language`` row of the DB's ``info`` table, if present."""
        assert self.cursor is not None
        try:
            self.cursor.execute("SELECT value FROM info WHERE name = 'language'")
        except sqlite3.OperationalError:
            return None
        row = self.cursor.fetchone()
        return row[0] if row and row[0] else None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.cursor = None
        if self._temp_path:
            os.unlink(self._temp_path)
            self._temp_path = None

    def _native_book_name(self, book_number: int, fallback: str) -> str:
        assert self.cursor is not None
        try:
            self.cursor.execute(
                "SELECT long_name FROM books WHERE book_number = ?", (book_number,)
            )
            row = self.cursor.fetchone()
        except sqlite3.OperationalError:
            row = None
        return (
            sanitize_book_name(row[0], book_number, self.language)
            if row and row[0]
            else fallback
        )

    def resolve(self, cita_en: str) -> tuple[str | None, str | None, str | None]:
        parsed = parse_en_ref(cita_en)
        if parsed is None:
            return None, None, f"could not parse reference: '{cita_en}'"
        book_en, chapter, v_start, v_end = parsed
        book_number = self.books_sot.get(book_en)
        if book_number is None:
            return None, None, f"unknown book: '{book_en}' — not in bible_books.json SOT"

        if v_start == v_end:
            shift = self.versification_shifts.get(f"{book_en} {chapter}:{v_start}")
            if shift:
                chapter, _, verse = shift.partition(":")
                chapter, v_start = int(chapter), int(verse)
                v_end = v_start

        assert self.cursor is not None
        local_name = self._native_book_name(book_number, book_en)
        texto = fetch_text(self.cursor, book_number, chapter, v_start, v_end)
        range_suffix = f"{v_start}-{v_end}" if v_start != v_end else str(v_start)
        if texto is None:
            self.cursor.execute(
                "SELECT MAX(verse) FROM verses WHERE book_number=? AND chapter=?",
                (book_number, chapter),
            )
            row = self.cursor.fetchone()
            max_verse = row[0] if row and row[0] else "unknown"
            return (
                None,
                None,
                f"verse not found: '{cita_en}' → {local_name} {chapter}:{range_suffix} "
                f"(chapter has {max_verse} verses)",
            )
        return f"{local_name} {chapter}:{range_suffix}", texto, None

    def resolve_many(self, refs: list[str]) -> list[dict[str, str | None]]:
        return [
            {"ref": ref, "cita": cita, "texto": text, "error": error}
            for ref in refs
            for cita, text, error in [self.resolve(ref)]
        ]

    def verse_count(self) -> int:
        assert self.cursor is not None
        self.cursor.execute("SELECT COUNT(*) FROM verses")
        return self.cursor.fetchone()[0]
