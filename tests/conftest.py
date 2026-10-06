import sqlite3
from pathlib import Path

import pytest

import bible_resolver.resolver as resolver_mod

REPO_ROOT = Path(__file__).parent.parent
BOOKS_JSON = REPO_ROOT / "bible_books.json"


@pytest.fixture(autouse=True)
def local_books_sot(monkeypatch):
    """Use the repo's bible_books.json so no test touches the network."""
    monkeypatch.setattr(resolver_mod, "_books_sot_cache", None)
    resolver_mod.load_books_sot(str(BOOKS_JSON))
    yield
    monkeypatch.setattr(resolver_mod, "_books_sot_cache", None)


@pytest.fixture
def make_db(tmp_path):
    """Build a minimal Bible SQLite DB: books, verses and optional info.language."""

    def _make(books, verses, language=None, name="test.SQLite3"):
        path = tmp_path / name
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE books (book_number INTEGER PRIMARY KEY, long_name TEXT)")
        conn.execute(
            "CREATE TABLE verses (book_number INTEGER, chapter INTEGER, verse INTEGER, text TEXT)"
        )
        conn.execute("CREATE TABLE info (name TEXT, value TEXT)")
        conn.executemany("INSERT INTO books VALUES (?, ?)", books)
        conn.executemany("INSERT INTO verses VALUES (?, ?, ?, ?)", verses)
        if language:
            conn.execute("INSERT INTO info VALUES ('language', ?)", (language,))
        conn.commit()
        conn.close()
        return str(path)

    return _make
