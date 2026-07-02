"""
verse_resolver.py
─────────────────
Agnostic verse resolver. Resolves English Bible references to
target-language citations and verse text from a SQLite Bible DB.

Book lookup uses the bible_books.json SOT (github.com/develop4God/bible_versions)
to confirm the EN book name and get its book_number. The native book name is
then read directly from the DB's own `books` table — no manual per-language
mapping file is required.

Reusable by any pipeline script — no content-type assumptions.

Usage:
    from verse_resolver import VerseResolver

    # SQLite path is the only required argument
    with VerseResolver("path/to/bible.db") as r:
        cita, texto, error = r.resolve("1 Corinthians 13:4-7")
    # On success : ("1 Korinther 13:4-7", "Die Liebe ist...", None)
    # On failure : (None, None, "reason string")

    # Optional: supply a local bible_books.json to avoid a network fetch
    with VerseResolver("path/to/bible.db", books_sot_path="devocionales_scripts/bible_books.json") as r:
        cita, texto, error = r.resolve("John 3:16")
"""

import gzip
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.request

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

BOOKS_SOT_URL = (
    "https://raw.githubusercontent.com/develop4god/bible_versions"
    "/refs/heads/main/bible_books.json"
)

# Devanagari digit → ASCII digit (for Hindi references)
_DEVA = str.maketrans("०१२३४५६७८९", "0123456789")

# Module-level cache — fetched once per Python process
_books_sot_cache: dict | None = None


# ─────────────────────────────────────────────────────────────────────────────
# LOW-LEVEL HELPERS  (module-level, usable without instantiation)
# ─────────────────────────────────────────────────────────────────────────────

def load_books_sot(local_path: str | None = None) -> dict:
    """
    Load the bible_books.json SOT.
    Returns flat dict: EN book name → book_number (int)

    Priority:
      1. Module-level cache (subsequent calls are instant)
      2. local_path if provided and the file exists
      3. Remote fetch from BOOKS_SOT_URL
    """
    global _books_sot_cache
    if _books_sot_cache is not None:
        return _books_sot_cache

    if local_path and os.path.exists(local_path):
        with open(local_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        with urllib.request.urlopen(BOOKS_SOT_URL) as resp:
            data = json.loads(resp.read())

    _books_sot_cache = {
        name: entry["book_number"]
        for name, entry in data["books"].items()
    }
    return _books_sot_cache


def parse_en_ref(cita: str) -> tuple[str, int, int, int] | None:
    """
    Parse an English Bible reference string.

    Accepts:
      - "John 3:16"
      - "1 Corinthians 13:4-7"
      - References with trailing version codes ("John 3:16 KJV")
      - Devanagari digits

    Returns:
      (book_name, chapter, verse_start, verse_end)  on success
      None                                           on failure
    """
    cita = cita.strip().translate(_DEVA)
    cita = re.sub(r'\s+[A-Z0-9]{2,6}$', '', cita).strip()  # strip version code
    m = re.match(
        r'^((?:\d\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(\d+):(\d+)(?:-(\d+))?$',
        cita,
    )
    if not m:
        return None
    return (
        m.group(1).strip(),
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)) if m.group(4) else int(m.group(3)),
    )


def fetch_text(
    cursor: sqlite3.Cursor,
    book_number: int,
    chapter: int,
    v_start: int,
    v_end: int,
) -> str | None:
    """
    Fetch and clean verse text from a SQLite Bible DB.

    Expected schema:
      verses(book_number INTEGER, chapter INTEGER, verse INTEGER, text TEXT)

    Returns cleaned combined text, or None if not found.
    """
    cursor.execute(
        "SELECT text FROM verses "
        "WHERE book_number=? AND chapter=? AND verse>=? AND verse<=? "
        "ORDER BY verse",
        (book_number, chapter, v_start, v_end),
    )
    rows = cursor.fetchall()
    if not rows:
        return None
    combined = " ".join(r[0] for r in rows)
    combined = re.sub(r"<[^>]+>", "", combined)            # strip XML tags
    combined = re.sub(r"[\u2460-\u24FF]", "", combined)    # strip Unicode ref markers
    combined = re.sub(r"\s+", " ", combined).strip()
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# VERSE RESOLVER CLASS
# ─────────────────────────────────────────────────────────────────────────────

class VerseResolver:
    """
    Stateful verse resolver. Holds an open SQLite connection and the
    bible_books.json SOT so callers do not manage them directly.

    Book numbers come from the bible_books.json SOT (EN name → book_number).
    Native book names are read directly from the DB's `books` table, so no
    per-language mapping file is needed.

    Parameters
    ----------
    sqlite_path    : path to SQLite Bible database
    books_sot_path : optional path to a local bible_books.json for offline use;
                     if absent, the SOT is fetched from BOOKS_SOT_URL once and
                     cached for the lifetime of the process.

    Example
    -------
    with VerseResolver("bible.db") as r:
        cita, texto, error = r.resolve("1 Corinthians 13:4-7")
        # cita  → native-language citation, e.g. "1. Korinther 13:4-7"
        # texto → verse text from the DB
    """

    def __init__(
        self,
        sqlite_path: str,
        books_sot_path: str | None = None,
    ) -> None:
        self.books_sot   = load_books_sot(books_sot_path)
        self._temp_path  = None

        if sqlite_path.endswith(".gz"):
            fd, self._temp_path = tempfile.mkstemp(suffix=".SQLite3")
            os.close(fd)
            with gzip.open(sqlite_path, "rb") as src, open(self._temp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            sqlite_path = self._temp_path

        self.conn      = sqlite3.connect(sqlite_path)
        self.cursor    = self.conn.cursor()

    # ── context manager support ───────────────────────────────────────────────

    def __enter__(self) -> "VerseResolver":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        """Close the SQLite connection."""
        if self.conn:
            self.conn.close()
            self.conn   = None
            self.cursor = None
        if self._temp_path:
            os.remove(self._temp_path)
            self._temp_path = None

    # ── internal helpers ──────────────────────────────────────────────────────

    def _native_book_name(self, book_number: int, fallback: str) -> str:
        """
        Query the DB's `books` table for the long_name of this book_number.
        Returns fallback (the EN book name) if the table is absent or the
        row is missing — ensuring citation building never fails silently.
        """
        try:
            self.cursor.execute(
                "SELECT long_name FROM books WHERE book_number = ?",
                (book_number,),
            )
            row = self.cursor.fetchone()
            if row and row[0]:
                return row[0]
        except sqlite3.OperationalError:
            pass  # `books` table absent in some minimal DB builds
        return fallback

    # ── public API ────────────────────────────────────────────────────────────

    def resolve(
        self,
        cita_en: str,
    ) -> tuple[str | None, str | None, str | None]:
        """
        Resolve an English Bible reference to native-language citation + text.

        Parameters
        ----------
        cita_en : English reference, e.g. "John 3:16" or "1 Corinthians 13:4-7"

        Returns
        -------
        (local_cita, texto, None)      on success
        (None,       None,  reason)    on failure

        Failure reasons:
          - "could not parse reference: '...'"
          - "unknown book: '...' — not in bible_books.json SOT"
          - "verse not found: '...' (chapter has N verses)"
        """
        parsed = parse_en_ref(cita_en)
        if parsed is None:
            return None, None, f"could not parse reference: '{cita_en}'"

        book_en, chapter, v_start, v_end = parsed

        # Confirm EN book name against SOT and get book_number
        book_number = self.books_sot.get(book_en)
        if book_number is None:
            return None, None, f"unknown book: '{book_en}' — not in bible_books.json SOT"

        # Get native book name directly from the DB (no manual mapping needed)
        local_name = self._native_book_name(book_number, fallback=book_en)

        texto = fetch_text(self.cursor, book_number, chapter, v_start, v_end)
        if texto is None:
            self.cursor.execute(
                "SELECT MAX(verse) FROM verses WHERE book_number=? AND chapter=?",
                (book_number, chapter),
            )
            row       = self.cursor.fetchone()
            max_verse = row[0] if row and row[0] else "unknown"
            range_str = f"{v_start}-{v_end}" if v_start != v_end else str(v_start)
            return None, None, (
                f"verse not found: '{cita_en}' → {local_name} {chapter}:{range_str} "
                f"(chapter has {max_verse} verses)"
            )

        range_suffix = f"{v_start}-{v_end}" if v_start != v_end else str(v_start)
        local_cita   = f"{local_name} {chapter}:{range_suffix}"
        return local_cita, texto, None

    def resolve_many(
        self,
        refs: list[str],
    ) -> list[dict]:
        """
        Resolve a list of English references in one call.

        Returns list of dicts:
          {"ref": original, "cita": local_cita, "texto": texto, "error": None}
          {"ref": original, "cita": None,       "texto": None,  "error": reason}
        """
        results = []
        for ref in refs:
            cita, texto, error = self.resolve(ref)
            results.append({
                "ref":   ref,
                "cita":  cita,
                "texto": texto,
                "error": error,
            })
        return results

    def verse_count(self) -> int:
        """Return total number of verses in the connected DB."""
        self.cursor.execute("SELECT COUNT(*) FROM verses")
        return self.cursor.fetchone()[0]
