"""Shared English-reference resolver for native Bible SQLite databases.

Reference parsing and verse-text cleanup live here.  Language-specific book
title sanitation is intentionally delegated to ``book_name_normalizer``.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Self

from .book_name_normalizer import sanitize_book_name

_DATA_DIR = Path(__file__).parent / "data"
BOOKS_SOT_PATH = _DATA_DIR / "bible_books.json"
_DEVA = str.maketrans("०१२३४५६७८९", "0123456789")
_VERSIFICATION_SHIFTS_PATH = _DATA_DIR / "versification_shifts.json"


class Resolution(NamedTuple):
    """Outcome of resolving one reference; unpacks as ``(cita, texto, error)``."""

    cita: str | None
    texto: str | None
    error: str | None


@lru_cache(maxsize=None)
def _load_shifts_file() -> dict:
    with open(_VERSIFICATION_SHIFTS_PATH, encoding="utf-8") as source:
        return json.load(source)


def load_versification_shifts(language: str | None, db_version: str) -> dict[str, str]:
    """Load known English->native chapter:verse remaps for *language*/*db_version*.

    ``language`` is the seed's language code (e.g. ``de``); ``db_version`` is
    the Bible DB's filename stem (e.g. ``LU17_de`` for ``Bibles/DE/LU17_de.SQLite3``).
    Covers cases where a DB's chapter numbering diverges from the English
    source references seeds are built from (e.g. German Joel/Malachi's
    different chapter splits). Missing language/version is a safe no-op.
    """
    if not language:
        return {}
    return _load_shifts_file().get(language.upper(), {}).get(db_version, {})


@lru_cache(maxsize=None)
def _load_books_file(path: str) -> dict[str, int]:
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    return {name: entry["book_number"] for name, entry in data["books"].items()}


def load_books_sot(local_path: str | None = None) -> dict[str, int]:
    """Load the English-name to canonical-book-number source of truth.

    Reads the copy bundled with the package unless *local_path* is given.
    Never touches the network, so results depend only on the installed version.
    """
    return _load_books_file(str(local_path or BOOKS_SOT_PATH))


def _primary_language(code: str | None) -> str | None:
    """Reduce DB language values such as ``zh Simplified`` / ``pt-BR`` to ``zh`` / ``pt``."""
    tokens = re.split(r"[\s_-]+", (code or "").strip().lower())
    return tokens[0] or None


def parse_en_ref(cita: str) -> tuple[str, int, int, int] | None:
    """Parse ``John 3:16`` and ``1 Corinthians 13:4-7`` references."""
    cita = cita.strip().translate(_DEVA)
    cita = re.sub(r"\s+[A-Z][A-Z0-9]{1,5}$", "", cita).strip()
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
    Values like ``zh Simplified`` use their primary subtag (``zh``).
    A database with neither returns its titles unchanged.

    ``.gz`` databases are decompressed into memory; nothing is written to disk.
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
        self.conn: sqlite3.Connection | None = self._connect(sqlite_path)
        try:
            self.cursor: sqlite3.Cursor | None = self.conn.cursor()
            self.language = _primary_language(language or self._db_language())
            self.versification_shifts = load_versification_shifts(
                self.language, db_version
            )
        except Exception:
            self.close()
            raise

    @staticmethod
    def _connect(sqlite_path: str) -> sqlite3.Connection:
        if not sqlite_path.lower().endswith(".gz"):
            return sqlite3.connect(sqlite_path)
        with gzip.open(sqlite_path, "rb") as source:
            data = source.read()
        conn = sqlite3.connect(":memory:")
        conn.deserialize(data)
        return conn

    def _require_cursor(self) -> sqlite3.Cursor:
        if self.cursor is None:
            raise RuntimeError("VerseResolver is closed")
        return self.cursor

    def _db_language(self) -> str | None:
        """Read the ``language`` row of the DB's ``info`` table, if present."""
        cursor = self._require_cursor()
        try:
            cursor.execute("SELECT value FROM info WHERE name = 'language'")
        except sqlite3.OperationalError:
            return None
        row = cursor.fetchone()
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

    def _native_book_name(self, book_number: int, fallback: str) -> str:
        cursor = self._require_cursor()
        try:
            cursor.execute(
                "SELECT long_name FROM books WHERE book_number = ?", (book_number,)
            )
            row = cursor.fetchone()
        except sqlite3.OperationalError:
            row = None
        return (
            sanitize_book_name(row[0], book_number, self.language)
            if row and row[0]
            else fallback
        )

    def _apply_shift(
        self, book_en: str, chapter: int, v_start: int, v_end: int
    ) -> tuple[int, int, int]:
        """Remap a range whose start verse is a known versification shift.

        The end verse follows its own shift entry when it has one; otherwise the
        range length is preserved (``Joel 2:28-29`` -> ``3:1-2``).
        """
        shift = self.versification_shifts.get(f"{book_en} {chapter}:{v_start}")
        if not shift:
            return chapter, v_start, v_end
        new_chapter, _, verse = shift.partition(":")
        new_start = int(verse)
        end_shift = self.versification_shifts.get(f"{book_en} {chapter}:{v_end}")
        if end_shift and end_shift.partition(":")[0] == new_chapter:
            new_end = int(end_shift.partition(":")[2])
        else:
            new_end = new_start + (v_end - v_start)
        return int(new_chapter), new_start, new_end

    def resolve(self, cita_en: str) -> Resolution:
        parsed = parse_en_ref(cita_en)
        if parsed is None:
            return Resolution(None, None, f"could not parse reference: '{cita_en}'")
        book_en, chapter, v_start, v_end = parsed
        book_number = self.books_sot.get(book_en)
        if book_number is None:
            return Resolution(
                None, None, f"unknown book: '{book_en}' — not in bible_books.json SOT"
            )

        chapter, v_start, v_end = self._apply_shift(book_en, chapter, v_start, v_end)

        cursor = self._require_cursor()
        local_name = self._native_book_name(book_number, book_en)
        texto = fetch_text(cursor, book_number, chapter, v_start, v_end)
        range_suffix = f"{v_start}-{v_end}" if v_start != v_end else str(v_start)
        if texto is None:
            cursor.execute(
                "SELECT MAX(verse) FROM verses WHERE book_number=? AND chapter=?",
                (book_number, chapter),
            )
            row = cursor.fetchone()
            max_verse = row[0] if row and row[0] else "unknown"
            return Resolution(
                None,
                None,
                f"verse not found: '{cita_en}' → {local_name} {chapter}:{range_suffix} "
                f"(chapter has {max_verse} verses)",
            )
        if not texto:
            return Resolution(
                None,
                None,
                f"verse text is empty: '{cita_en}' → {local_name} {chapter}:{range_suffix}",
            )
        return Resolution(f"{local_name} {chapter}:{range_suffix}", texto, None)

    def resolve_many(self, refs: list[str]) -> list[dict[str, str | None]]:
        return [
            {"ref": ref, "cita": cita, "texto": text, "error": error}
            for ref in refs
            for cita, text, error in [self.resolve(ref)]
        ]

    def verse_count(self) -> int:
        cursor = self._require_cursor()
        cursor.execute("SELECT COUNT(*) FROM verses")
        return cursor.fetchone()[0]
