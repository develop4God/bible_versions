"""Regression checks against the real gzipped DBs shipped in this repo."""

from pathlib import Path

import pytest

from bible_resolver import VerseResolver

ROOT = Path(__file__).parent.parent


def _open(rel):
    return VerseResolver(str(ROOT / rel))


def test_hiov_gospels_use_short_names_and_language_from_db():
    with _open("hi/HIOV_hi.SQLite3.gz") as r:
        assert r.language == "hi"
        assert r.resolve("John 3:16")[0] == "यूहन्ना 3:16"
        assert r.resolve("Psalms 23:1")[0] == "भजन संहिता 23:1"


def test_lsg1910_romans_11_33_34_split_is_correct():
    with _open("fr/LSG1910_fr.SQLite3.gz") as r:
        assert r.resolve("Romans 11:33")[1].endswith("incompréhensibles!")
        assert r.resolve("Romans 11:34")[1].startswith("Car qui a connu")


def test_german_joel_shift_on_real_db():
    with _open("de/LU17_de.SQLite3.gz") as r:
        cita, texto, error = r.resolve("Joel 2:28")
        assert error is None and cita.endswith("3:1") and texto
