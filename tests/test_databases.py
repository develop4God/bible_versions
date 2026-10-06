"""database_path: read the DBs in place from a checkout, else download + verify + cache."""

import gzip
import json
import warnings
from pathlib import Path

import pytest

from bible_resolver import (
    DatabaseIntegrityError,
    DatabaseNotFoundError,
    VerseResolver,
    database_path,
)
from bible_resolver import books_sot as sot

ROOT = Path(__file__).parent.parent
INDEX = json.loads((ROOT / "index.json").read_text("utf-8"))
ALL = [
    (lang, version, entry)
    for lang, ldata in INDEX["languages"].items()
    for version, entry in ldata["versions"].items()
]


@pytest.fixture(autouse=True)
def cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("BIBLE_VERSIONS_DIR", raising=False)


@pytest.mark.parametrize("lang,version,entry", ALL, ids=[f"{v}_{lang}" for lang, v, _ in ALL])
def test_every_listed_database_resolves_in_place_with_matching_hash(lang, version, entry):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        path = database_path(lang, version)
    assert path == ROOT / lang / entry["file"]  # the repo's own file, not a copy
    assert sot.content_hash(path.read_bytes()) == entry["hash"]


def test_database_is_usable_by_the_resolver():
    with VerseResolver(str(database_path("hi", "HERV")), strict=True) as r:
        assert r.resolve("Titus 2:11")[0] == "तीतुस 2:11"


def test_unknown_version_and_language():
    with pytest.raises(DatabaseNotFoundError, match="not listed"):
        database_path("hi", "NOPE")
    with pytest.raises(DatabaseNotFoundError):
        database_path("xx", "HERV")


def test_env_var_selects_another_checkout(monkeypatch, tmp_path):
    (tmp_path / "es").mkdir()
    blob = gzip.compress(b"db")
    (tmp_path / "es" / "X_es.SQLite3.gz").write_bytes(blob)
    (tmp_path / "index.json").write_text(json.dumps({"languages": {"es": {"versions": {"X": {
        "file": "X_es.SQLite3.gz", "hash": sot.content_hash(blob), "url": "u"}}}}}))
    monkeypatch.setenv("BIBLE_VERSIONS_DIR", str(tmp_path))
    assert database_path("es", "X") == tmp_path / "es" / "X_es.SQLite3.gz"


def test_checkout_hash_drift_warns(tmp_path):
    (tmp_path / "es").mkdir()
    (tmp_path / "es" / "X_es.SQLite3.gz").write_bytes(b"changed")
    (tmp_path / "index.json").write_text(json.dumps({"languages": {"es": {"versions": {"X": {
        "file": "X_es.SQLite3.gz", "hash": "deadbeef", "url": "u"}}}}}))
    with pytest.warns(UserWarning, match="differs from index.json"):
        database_path("es", "X", root=tmp_path)


def test_bad_explicit_root_is_a_clear_error(tmp_path):
    with pytest.raises(DatabaseNotFoundError, match="no index.json"):
        database_path("hi", "HERV", root=tmp_path)


def fake_remote(monkeypatch, blob, *, hash_=None, offline=False):
    calls = []
    index = {"languages": {"es": {"versions": {"X": {
        "file": "X_es.SQLite3.gz", "hash": hash_ or sot.content_hash(blob), "url": "https://x/db"}}}}}

    def fetch(url):
        calls.append(url)
        if offline:
            raise OSError("offline")
        return json.dumps(index).encode() if url == sot.INDEX_URL else blob

    monkeypatch.setattr(sot, "_fetch", fetch)
    monkeypatch.setattr(sot, "_checkout_root", lambda: None)
    return calls


def test_remote_downloads_verifies_and_caches(monkeypatch):
    blob = gzip.compress(b"db")
    calls = fake_remote(monkeypatch, blob)
    path = database_path("es", "X")
    assert path.read_bytes() == blob and path.parent.name == "dbs"
    calls.clear()
    assert database_path("es", "X") == path
    assert calls == [sot.INDEX_URL]  # cached file reused, DB not downloaded again


def test_remote_hash_mismatch_raises_and_is_not_cached(monkeypatch):
    fake_remote(monkeypatch, gzip.compress(b"db"), hash_="0" * 16)
    with pytest.raises(DatabaseIntegrityError, match="does not match"):
        database_path("es", "X")
    assert not list((sot._cache_path().parent / "dbs").glob("*"))


def test_remote_offline_uses_cache_else_clear_error(monkeypatch):
    blob = gzip.compress(b"db")
    fake_remote(monkeypatch, blob, offline=True)
    with pytest.raises(DatabaseIntegrityError, match="no cached copy"):
        database_path("es", "X")
    cached = sot._cache_path().parent / "dbs" / "X_es.SQLite3.gz"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(blob)
    assert database_path("es", "X") == cached
