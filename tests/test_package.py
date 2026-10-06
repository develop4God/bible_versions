"""Package-level guarantees: bundled SOT, no network, lifecycle, API surface."""

import json
from pathlib import Path

import pytest

import bible_resolver
from bible_resolver import Resolution, VerseResolver, load_books_sot, load_title_aliases

pytestmark = pytest.mark.filterwarnings("ignore::bible_resolver.UnmappedBookWarning")

ROOT = Path(__file__).parent.parent


def test_every_sot_name_round_trips_through_parser():
    for name in load_books_sot():
        assert bible_resolver.parse_en_ref(f"{name} 1:1") == (name, 1, 1, 1)


def test_public_api_is_importable():
    for name in bible_resolver.__all__:
        assert hasattr(bible_resolver, name)


def test_title_aliases_exposed():
    assert load_title_aliases("ar")["رؤيا يوحنا اللاهوتي"] == "الرؤيا"
    assert load_title_aliases("xx") == {} and load_title_aliases(None) == {}


def test_resolution_unpacks_as_tuple(make_db):
    with VerseResolver(make_db([(10, "Genesis")], [(10, 1, 1, "a")])) as r:
        res = r.resolve("Genesis 1:1")
        assert isinstance(res, Resolution)
        assert tuple(res) == ("Genesis 1:1", "a", None) and res.cita == "Genesis 1:1"


def test_use_after_close_raises_clear_error(make_db):
    r = VerseResolver(make_db([(10, "Genesis")], [(10, 1, 1, "a")]))
    r.close()
    r.close()  # idempotent
    with pytest.raises(RuntimeError, match="closed"):
        r.resolve("Genesis 1:1")


def test_second_resolver_with_different_sot_path_is_honoured(make_db, tmp_path):
    custom = tmp_path / "sot.json"
    custom.write_text(json.dumps({"books": {"Genesis": {"book_number": 99}}}))
    path = make_db([(99, "Gen")], [(99, 1, 1, "x")])
    with VerseResolver(path, books_sot_path=str(custom)) as r:
        assert r.resolve("Genesis 1:1")[0] == "Gen 1:1"
    with VerseResolver(path) as r:
        assert r.resolve("Genesis 1:1")[2] is not None
