"""Locate the Bible SQLite databases published in this repo, without copying them.

``database_path("hi", "HERV")`` returns the path to ``hi/HERV_hi.SQLite3.gz``:

1. from a local checkout of ``bible_versions`` when one is available: the
   ``BIBLE_VERSIONS_DIR`` environment variable, or the checkout the package
   itself runs from.  The file is read in place, nothing is copied, and its
   hash is compared with that checkout's ``index.json`` (a mismatch warns);
2. otherwise downloaded from ``main`` using the ``url`` and ``hash`` in the
   remote ``index.json``, verified, and cached on disk.  A hash mismatch raises;
   with no network a previously cached copy is used.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

from . import books_sot


class DatabaseNotFoundError(LookupError):
    """The language/version is not listed in index.json (or its file is missing)."""


class DatabaseIntegrityError(RuntimeError):
    """A database could not be fetched, or failed hash validation."""


def _local_root(root: str | os.PathLike | None) -> Path | None:
    explicit = root or os.environ.get("BIBLE_VERSIONS_DIR")
    if explicit:
        path = Path(explicit).expanduser()
        if not (path / "index.json").is_file():
            raise DatabaseNotFoundError(f"no index.json in bible_versions checkout {path}")
        return path
    return books_sot._checkout_root()


def _entry(index: dict, language: str, version: str) -> dict:
    try:
        return index["languages"][language.lower()]["versions"][version]
    except KeyError:
        raise DatabaseNotFoundError(
            f"{version!r} ({language!r}) is not listed in bible_versions index.json"
        ) from None


def _from_checkout(root: Path, language: str, version: str) -> Path:
    entry = _entry(json.loads((root / "index.json").read_bytes()), language, version)
    path = root / language.lower() / entry["file"]
    if not path.is_file():
        raise DatabaseNotFoundError(f"{path} is listed in index.json but missing")
    actual = books_sot.content_hash(path.read_bytes())
    if actual != entry["hash"]:
        warnings.warn(
            f"{path.name} differs from index.json (index {entry['hash']}, file {actual}); "
            "run scripts/generate_index.py",
            stacklevel=3,
        )
    return path


def _from_remote(language: str, version: str) -> Path:
    cache_dir = books_sot._cache_path().parent / "dbs"
    try:
        index = json.loads(books_sot._fetch(books_sot.INDEX_URL))
        entry = _entry(index, language, version)
    except OSError as exc:
        cached = list(cache_dir.glob(f"{version}_{language.lower()}.SQLite3.gz"))
        if cached:
            return cached[0]
        raise DatabaseIntegrityError(
            f"cannot reach {books_sot.INDEX_URL} and no cached copy of {version} exists: {exc}"
        ) from exc
    target = cache_dir / entry["file"]
    if target.is_file() and books_sot.content_hash(target.read_bytes()) == entry["hash"]:
        return target
    try:
        data = books_sot._fetch(entry["url"])
    except OSError as exc:
        raise DatabaseIntegrityError(f"cannot download {entry['url']}: {exc}") from exc
    if books_sot.content_hash(data) != entry["hash"]:
        raise DatabaseIntegrityError(
            f"{entry['file']} hash {books_sot.content_hash(data)} does not match "
            f"index.json ({entry['hash']}); main is mid-update or the download is corrupt"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    part.write_bytes(data)
    part.replace(target)
    return target


def database_path(
    language: str, version: str, *, root: str | os.PathLike | None = None
) -> Path:
    """Path to the ``.SQLite3.gz`` for *version* in *language* (e.g. ``"hi"``, ``"HERV"``)."""
    local = _local_root(root)
    if local is not None:
        return _from_checkout(local, language, version)
    return _from_remote(language, version)
