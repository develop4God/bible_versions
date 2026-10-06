"""Citation rules must be explicit: nothing may silently fall back to a raw DB title."""

import glob
import json
import warnings
from pathlib import Path

import pytest

from bible_resolver import UnmappedBookWarning, VerseResolver, load_books_sot, resolve_book_title
from bible_resolver.book_name_normalizer import normalize_title

ROOT = Path(__file__).parent.parent
ALL_DBS = sorted(glob.glob(str(ROOT / "*/*.SQLite3.gz")))
CANON = sorted({b for b in load_books_sot().values() if b <= 730})
GOLDEN = ROOT / "tests" / "golden_citations.json"


def _id(path):
    return Path(path).name.removesuffix(".SQLite3.gz")


def citations(db):
    with VerseResolver(db, strict=True) as r:
        out = {}
        for en, number in sorted(load_books_sot().items(), key=lambda kv: kv[1]):
            if number > 730 or en == "Psalm":
                continue
            out[str(number)] = r._native_book_name(number, en)
        return out


@pytest.mark.parametrize("db", ALL_DBS, ids=_id)
def test_every_book_is_covered_by_a_rule(db):
    """No raw fallback: each book is 'mapped' or its language declares passthrough."""
    with VerseResolver(db) as r:
        report = r.coverage()
    assert "unmapped" not in report and "no-config" not in report, report


def test_golden_citations_match():
    """Review diffs of this file to see exactly what a rule change does.

    Regenerate with: UPDATE_GOLDEN=1 uv run pytest tests/test_coverage.py -k golden
    """
    import os

    current = {_id(db): citations(db) for db in ALL_DBS}
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert current == json.loads(GOLDEN.read_text("utf-8"))


def test_unconfigured_language_warns_once_per_book(make_db):
    path = make_db([(10, "Genesis")], [(10, 1, 1, "x")], language="xx")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with VerseResolver(path) as r:
            r.resolve("Genesis 1:1")
            r.resolve("Genesis 1:1")
    assert [w.category for w in caught] == [UnmappedBookWarning]
    assert "no-config" in str(caught[0].message)


def test_strict_raises_on_fallback(make_db):
    path = make_db([(10, "Genesis")], [(10, 1, 1, "x")], language="xx")
    with VerseResolver(path, strict=True) as r:
        with pytest.raises(LookupError, match="raw DB title"):
            r.resolve("Genesis 1:1")


def test_coverage_report_shape(make_db):
    path = make_db([(10, "Genesis"), (999, "Odd")], [(10, 1, 1, "x")], language="en")
    with VerseResolver(path) as r:
        report = r.coverage()
    assert report["language"] == "en" and report["mapped"] == [10] and report["unmapped"] == [999]


@pytest.mark.parametrize(
    "raw,expected",
    [("Lamentations\n", "Lamentations"), ("腓立比书 ", "腓立比书"), ("Mga Gawa", "Mga Gawa"), ("  A   B ", "A B")],
)
def test_title_whitespace_is_normalized(raw, expected):
    assert normalize_title(raw) == expected


def test_passthrough_keeps_db_title_but_normalizes():
    assert resolve_book_title("腓立比书 ", 570, "zh") == ("腓立比书", "passthrough")
    assert resolve_book_title("マタイの福音書", 470, "ja") == ("マタイの福音書", "passthrough")


@pytest.mark.parametrize("lang", ["ar", "de", "en", "es", "fr", "fil", "hi", "pt"])
def test_language_maps_are_complete_and_unique(lang):
    names = json.loads((ROOT / f"src/bible_resolver/data/book_name_sanitizers/{lang}.json").read_text("utf-8"))["book_names"]
    keep = set(json.loads((ROOT / f"src/bible_resolver/data/book_name_sanitizers/{lang}.json").read_text("utf-8")).get("keep_db_title", []))
    assert not keep & {int(k) for k in names}, "a book is both mapped and keep_db_title"
    assert {int(k) for k in names} | keep >= set(CANON) - {10000}
    canon_names = [names[str(b)] for b in CANON if str(b) in names]
    assert all(n == normalize_title(n) and n for n in canon_names)
    assert len(set(canon_names)) == len(canon_names), "duplicate citation titles"


def test_keep_db_title_keeps_each_editions_own_spelling():
    """Editions spell some books differently (Éphésiens/Ephésiens); '=' keeps each DB's own."""
    assert resolve_book_title("Éphésiens ", 560, "fr") == ("Éphésiens", "passthrough")
    assert resolve_book_title("Ephésiens", 560, "fr") == ("Ephésiens", "passthrough")
    assert resolve_book_title("Aux Romains", 520, "fr") == ("Romains", "mapped")


def test_filipino_db_metadata_tl_resolves_to_fil_config(make_db):
    """ASND/MBB05 store language 'tl' in their info table; that metadata maps to 'fil'."""
    path = make_db([(10, "Genesis")], [(10, 1, 1, "x")], language="tl")
    with VerseResolver(path, strict=True) as r:
        assert r.language == "fil" and r.coverage()["mapped"] == [10]


@pytest.mark.parametrize("explicit", ["tl", "TL", "tl-PH"])
def test_explicit_tl_is_a_hard_error(make_db, explicit):
    path = make_db([(10, "Genesis")], [(10, 1, 1, "x")], language="tl")
    with pytest.raises(ValueError, match="use 'fil'"):
        VerseResolver(path, language=explicit)


def test_explicit_fil_works(make_db):
    path = make_db([(10, "Genesis")], [(10, 1, 1, "x")], language="tl")
    with VerseResolver(path, language="fil", strict=True) as r:
        assert r.language == "fil" and r.coverage()["mapped"] == [10]
