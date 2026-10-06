"""Regression checks against the real gzipped DBs shipped in this repo.

Covers every language: Hindi (HIOV long forms), Chinese (CNVS/CUV1919),
Portuguese (ARC/ARA/NVI long and honorific names), Arabic, German, Japanese...
"""

import glob
import unicodedata
from pathlib import Path

import pytest

from bible_resolver import VerseResolver, load_books_sot

ROOT = Path(__file__).parent.parent
ALL_DBS = sorted(glob.glob(str(ROOT / "*/*.SQLite3.gz")))
CANON = {n: b for n, b in load_books_sot().items() if b <= 730 and n not in {"Psalm", "Song of Songs"}}
# Languages with a sanitizer config: citations must be short and free of descriptive wrappers.
LONG_FORM_MARKERS = {
    "hi": ["नामक", "पुस्तक", "रचित", "सुसमाचार", "वृत्तान्त", "पत्री"],
    "pt": ["Livro", "Evangelho", "Epístola", "S. ", "chamado", " de João"],
    "de": ["Buch", "Brief", "Evangelium", "(", "Das ", "Der ", "Die "],
    "ar": ["سفر", "إنجيل", "رسالة", "انجيل"],
}


# Data gaps in the shipped DBs (not resolver bugs); tests pin them so a fix is noticed.
KNOWN_EMPTY_BOOKS: dict[str, set[str]] = {}


def _id(path):
    return Path(path).name.removesuffix(".SQLite3.gz")


def _open(rel):
    return VerseResolver(str(ROOT / rel))


# ── Hindi ──────────────────────────────────────────────────────────────────
def test_hiov_gospels_use_short_names_and_language_from_db():
    with _open("hi/HIOV_hi.SQLite3.gz") as r:
        assert r.language == "hi"
        assert r.resolve("John 3:16")[0] == "यूहन्ना 3:16"
        assert r.resolve("Psalms 23:1")[0] == "भजन संहिता 23:1"


@pytest.mark.parametrize(
    "ref,expected",
    [
        ("1 Samuel 3:10", "1 शमूएल 3:10"),
        ("2 Kings 2:11", "2 राजाओं 2:11"),
        ("1 Chronicles 4:10", "1 इतिहास 4:10"),
        ("Isaiah 53:5", "यशायाह 53:5"),
        ("Acts 1:8", "प्रेरितों के काम 1:8"),
        ("Revelation 21:4", "प्रकाशितवाक्य 21:4"),
    ],
)
def test_hiov_long_names_are_shortened(ref, expected):
    with _open("hi/HIOV_hi.SQLite3.gz") as r:
        cita, texto, error = r.resolve(ref)
        assert error is None and cita == expected and texto


# ── Chinese ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("db", ["zh/CNVS_zh.SQLite3.gz", "zh/CUV1919_zh.SQLite3.gz"])
class TestChinese:
    def test_language_primary_subtag_and_native_citation(self, db):
        with _open(db) as r:
            assert r.language == "zh"  # DB says "zh Simplified"
            assert r.resolve("John 3:16")[0] == "约翰福音 3:16"
            assert r.resolve("Genesis 1:1")[0] == "创世记 1:1"

    def test_range_text_is_clean_cjk(self, db):
        with _open(db) as r:
            cita, texto, error = r.resolve("1 Corinthians 13:4-7")
            assert error is None and cita == "哥林多前书 13:4-7"
            assert not any(c in texto for c in "<>①②③")
            assert "  " not in texto

    def test_verse_notes_are_stripped_across_whole_bible(self, db):
        with _open(db) as r:
            r.cursor.execute("SELECT book_number, chapter, verse FROM verses LIMIT 4000")
            for book, chapter, verse in r.cursor.fetchall()[::40]:
                text = r.cursor.execute(
                    "SELECT text FROM verses WHERE book_number=? AND chapter=? AND verse=?",
                    (book, chapter, verse),
                ).fetchone()[0]
                from bible_resolver import clean_verse_text

                assert "<" not in clean_verse_text(text)


# ── Portuguese: ARC / ARA / NVI ────────────────────────────────────────────
@pytest.mark.parametrize(
    "db,ref,expected",
    [
        ("pt/ARC_pt.SQLite3.gz", "Matthew 5:3", "Mateus 5:3"),  # raw: "S. Mateus"
        ("pt/ARC_pt.SQLite3.gz", "1 Peter 5:7", "1 Pedro 5:7"),  # raw: "1 S. Pedro"
        ("pt/ARC_pt.SQLite3.gz", "Song of Solomon 2:1", "Cantares 2:1"),
        ("pt/ARC_pt.SQLite3.gz", "Hosea 6:6", "Oséias 6:6"),
        ("pt/ARA_pt.SQLite3.gz", "Genesis 1:1", "Gênesis 1:1"),  # raw: "O Primeiro Livro de Moisés chamado Gênesis"
        ("pt/ARA_pt.SQLite3.gz", "John 3:16", "João 3:16"),  # raw: "O Evangelho segundo João"
        ("pt/ARA_pt.SQLite3.gz", "Romans 8:28", "Romanos 8:28"),  # raw: "Epístola de Paulo aos Romanos"
        ("pt/ARA_pt.SQLite3.gz", "1 Thessalonians 5:16", "1 Tessalonicenses 5:16"),
        ("pt/ARA_pt.SQLite3.gz", "Revelation 22:21", "Apocalipse 22:21"),  # raw: "Apocalipse de João"
        ("pt/NVI_pt.SQLite3.gz", "Ezra 7:10", "Esdras 7:10"),  # raw has Cyrillic "Е"
        ("pt/NVI_pt.SQLite3.gz", "Amos 5:24", "Amós 5:24"),  # raw has Cyrillic "А"
        ("pt/NVI_pt.SQLite3.gz", "Micah 6:8", "Miqueias 6:8"),  # raw has Cyrillic "М"
    ],
)
def test_portuguese_long_and_irregular_names(db, ref, expected):
    with _open(db) as r:
        cita, texto, error = r.resolve(ref)
        assert error is None and cita == expected and texto


def test_arc_range_and_texts_resolve():
    with _open("pt/ARC_pt.SQLite3.gz") as r:
        cita, texto, error = r.resolve("1 Corinthians 13:4-7")
        assert error is None and cita == "1 Coríntios 13:4-7" and "amor" in texto.lower()


# ── Arabic / German / French regressions ───────────────────────────────────
@pytest.mark.parametrize("db", ["ar/NAV_ar.SQLite3.gz", "ar/SVDA_ar.SQLite3.gz"])
def test_arabic_vocalized_and_descriptive_names_normalize(db):
    with _open(db) as r:
        assert r.resolve("John 3:16")[0] == "يوحنا 3:16"
        assert r.resolve("Acts 1:8")[0] == "أعمال الرسل 1:8"


def test_lsg1910_romans_11_33_34_split_is_correct():
    with _open("fr/LSG1910_fr.SQLite3.gz") as r:
        assert r.resolve("Romans 11:33")[1].endswith("incompréhensibles!")
        assert r.resolve("Romans 11:34")[1].startswith("Car qui a connu")


@pytest.mark.parametrize("db", ["de/LU17_de.SQLite3.gz", "de/SCH2000_de.SQLite3.gz"])
def test_german_shifts_and_short_names(db):
    with _open(db) as r:
        cita, texto, error = r.resolve("Joel 2:28")
        assert error is None and cita.endswith("3:1") and texto
        assert r.resolve("Genesis 1:1")[0] == "1. Mose 1:1"  # raw: "Das erste Buch Mose (Genesis)"
        assert r.resolve("Malachi 4:2")[2] is None


# ── Every shipped DB, every canonical book ─────────────────────────────────
@pytest.mark.parametrize("db", ALL_DBS, ids=_id)
class TestEveryDatabase:
    def test_all_66_books_have_unique_nonempty_short_citations(self, db):
        with VerseResolver(db) as r:
            names = {}
            for en, number in CANON.items():
                r.cursor.execute(
                    "SELECT 1 FROM verses WHERE book_number=? LIMIT 1", (number,)
                )
                if en in KNOWN_EMPTY_BOOKS.get(_id(db), ()):
                    assert not r.cursor.fetchone(), f"{en} gap fixed in {db}: drop it from KNOWN_EMPTY_BOOKS"
                else:
                    assert r.cursor.fetchone(), f"{en} missing in {db}"
                names[en] = r._native_book_name(number, en)
            assert len(CANON) == 66
            assert all(n.strip() for n in names.values())
            assert len(set(names.values())) == 66, "two books share a citation title"
            for marker in LONG_FORM_MARKERS.get(r.language, []):
                offenders = [n for n in names.values() if marker in n]
                assert not offenders, f"long-form {marker!r} left in {offenders}"
            if r.language in {"pt", "de", "es", "fr", "en", "hi", "ar"}:
                for n in names.values():  # no Latin/Cyrillic homoglyph mixing
                    scripts = {unicodedata.name(c).split()[0] for c in n if c.isalpha()}
                    assert len(scripts) == 1, f"mixed scripts in {n!r}: {scripts}"

    def test_first_verse_of_every_book_resolves(self, db):
        with VerseResolver(db) as r:
            for en in CANON:
                if en in KNOWN_EMPTY_BOOKS.get(_id(db), ()):
                    continue
                r.cursor.execute(
                    "SELECT chapter, verse FROM verses WHERE book_number=? AND TRIM(text) != '' ORDER BY chapter, verse LIMIT 1",
                    (CANON[en],),
                )
                chapter, verse = r.cursor.fetchone()
                cita, texto, error = r.resolve(f"{en} {chapter}:{verse}")
                assert error is None, error
                assert texto and "<" not in texto and "&quot;" not in texto


def test_empty_verse_in_db_is_an_error_not_blank_text():
    """HERV_hi ships 1 Chronicles 1:1 with an empty text cell."""
    with _open("hi/HERV_hi.SQLite3.gz") as r:
        cita, texto, error = r.resolve("1 Chronicles 1:1")
        assert cita is None and texto is None and "empty" in error


def test_herv_titus_is_complete():
    """Titus was missing from HERV_hi; restored from Hindi ERV (46 verses)."""
    with _open("hi/HERV_hi.SQLite3.gz") as r:
        assert r.verse_count() == 31102
        for chapter, last in ((1, 16), (2, 15), (3, 15)):
            assert r.resolve(f"Titus {chapter}:{last}")[2] is None
            assert r.resolve(f"Titus {chapter}:{last + 1}")[2] is not None
        cita, texto, _ = r.resolve("Titus 3:9")
        assert cita == "तीतुस 3:9" and "वंशावली" in texto and texto.endswith("।")


def test_range_past_end_of_titus_is_an_error_not_truncated():
    with _open("hi/HERV_hi.SQLite3.gz") as r:
        assert r.resolve("Titus 3:15")[2] is None
        assert r.resolve("Titus 3:15-16")[0] is None
