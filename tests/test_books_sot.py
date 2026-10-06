"""bible_books.json: single root copy, validated by the hash recorded in index.json."""

import json
import warnings
from pathlib import Path

import pytest

from bible_resolver import BooksSotError
from bible_resolver import books_sot as sot

ROOT = Path(__file__).parent.parent
BOOKS = (ROOT / "bible_books.json").read_bytes()
GOOD_INDEX = json.dumps({"meta": {"books_sot": {"hash": sot.content_hash(BOOKS)}}}).encode()


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    sot._load_default.cache_clear()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    yield
    sot._load_default.cache_clear()


def fake_net(monkeypatch, books=BOOKS, index=GOOD_INDEX, offline=False):
    calls = []

    def fetch(url):
        calls.append(url)
        if offline:
            raise OSError("offline")
        return books if url == sot.BOOKS_URL else index

    monkeypatch.setattr(sot, "_fetch", fetch)
    monkeypatch.setattr(sot, "_checkout_root", lambda: None)
    return calls


def test_repo_has_a_single_copy_of_the_file():
    assert [p for p in ROOT.rglob("bible_books.json") if ".venv" not in p.parts] == [
        ROOT / "bible_books.json"
    ]


def test_index_hash_matches_root_file():
    """Fails when bible_books.json changes without regenerating index.json."""
    meta = json.loads((ROOT / "index.json").read_text("utf-8"))["meta"]["books_sot"]
    assert meta["hash"] == sot.content_hash(BOOKS)
    assert meta["url"] == sot.BOOKS_URL


def test_content_hash_matches_generate_index_scheme():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gi", ROOT / "scripts" / "generate_index.py")
    gi = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(gi)
    except SystemExit:  # PyYAML missing in this env
        pytest.skip("generate_index needs PyYAML")
    assert gi.file_hash(ROOT / "bible_books.json") == sot.content_hash(BOOKS)


def test_checkout_is_used_without_network(monkeypatch):
    monkeypatch.setattr(sot, "_fetch", lambda u: pytest.fail("network used"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert sot.load_books_sot()["John"] == 500


def test_checkout_hash_drift_warns(monkeypatch, tmp_path):
    (tmp_path / "bible_books.json").write_bytes(BOOKS)
    (tmp_path / "index.json").write_text('{"meta": {"books_sot": {"hash": "deadbeef"}}}')
    monkeypatch.setattr(sot, "_checkout_root", lambda: tmp_path)
    with pytest.warns(UserWarning, match="differs from index.json"):
        assert sot.load_books_sot()["John"] == 500


def test_remote_downloads_validates_and_caches(monkeypatch):
    calls = fake_net(monkeypatch)
    assert sot.load_books_sot()["John"] == 500
    assert calls == [sot.BOOKS_URL, sot.INDEX_URL]
    assert sot._cache_path().read_bytes() == BOOKS


def test_remote_hash_mismatch_raises_and_is_not_cached(monkeypatch):
    fake_net(monkeypatch, books=BOOKS.replace(b"John", b"Jahn"))
    with pytest.raises(BooksSotError, match="does not match"):
        sot.load_books_sot()
    assert not sot._cache_path().exists()


def test_remote_index_without_entry_skips_validation(monkeypatch):
    fake_net(monkeypatch, index=b'{"meta": {}}')
    assert sot.load_books_sot()["John"] == 500


def test_offline_uses_cache_else_clear_error(monkeypatch):
    fake_net(monkeypatch, offline=True)
    with pytest.raises(BooksSotError, match="no cached copy"):
        sot.load_books_sot()
    sot._cache_path().parent.mkdir(parents=True)
    sot._cache_path().write_bytes(BOOKS)
    sot._load_default.cache_clear()
    assert sot.load_books_sot()["John"] == 500


def test_malformed_remote_file_raises(monkeypatch):
    bad = b'{"nope": 1}'
    fake_net(monkeypatch, books=bad, index=json.dumps({"meta": {"books_sot": {"hash": sot.content_hash(bad)}}}).encode())
    with pytest.raises(BooksSotError, match="malformed"):
        sot.load_books_sot()
