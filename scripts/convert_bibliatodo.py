#!/usr/bin/env python3
"""Convert a BibliaTodo "schema 3" SQLite (NTBT / BTNT / NTB-BR) to this repo's layout.

BibliaTodo ships ``libros / versiculos / metadatos / formato_capitulos`` keyed by USFM
code.  The repo (and ``bible_resolver``) use the MySword layout keyed by ``book_number``:
``info / books / books_all / verses / stories``.  Conversion is lossless for the Bible
text: ``texto`` is copied verbatim (the license requires the wording and its brackets to
be preserved).  Section titles become ``stories`` rows (order: encabezado, titulo,
subtitulo).  Not carried over: ``referencias`` (HTML links), ``formato_capitulos``
(paragraph/poetry structure) and, in the study edition, ``intro`` / ``nota``.

Usage (needs the project installed, hence ``uv run``):
    uv run python scripts/convert_bibliatodo.py NTBT.sqlite            # -> es/NTBT_es.SQLite3.gz
    uv run python scripts/convert_bibliatodo.py NTBT.sqlite --out-dir /tmp/out --version NTBT

Language and version come from the source's ``metadatos`` (``idioma`` / ``version``);
``--lang`` / ``--version`` override them.  The result is written as
``{lang}/{VERSION}_{lang}.SQLite3.gz`` (deterministic gzip, so re-runs keep the same hash).
After converting, add the version to ``.github/bible_versions_config.yml`` (with its
attribution as ``disclaimer``) and run ``scripts/generate_index.py`` and
``scripts/generate_readme.py``.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from contextlib import closing
from pathlib import Path

from bible_resolver.resolver import VERSION_ID_PATTERN

REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical order of the 66 books (USFM codes); ``libros.orden`` must follow it.
USFM_ORDER = [
    "GEN",
    "EXO",
    "LEV",
    "NUM",
    "DEU",
    "JOS",
    "JDG",
    "RUT",
    "1SA",
    "2SA",
    "1KI",
    "2KI",
    "1CH",
    "2CH",
    "EZR",
    "NEH",
    "EST",
    "JOB",
    "PSA",
    "PRO",
    "ECC",
    "SNG",
    "ISA",
    "JER",
    "LAM",
    "EZK",
    "DAN",
    "HOS",
    "JOL",
    "AMO",
    "OBA",
    "JON",
    "MIC",
    "NAM",
    "HAB",
    "ZEP",
    "HAG",
    "ZEC",
    "MAL",
    "MAT",
    "MRK",
    "LUK",
    "JHN",
    "ACT",
    "ROM",
    "1CO",
    "2CO",
    "GAL",
    "EPH",
    "PHP",
    "COL",
    "1TH",
    "2TH",
    "1TI",
    "2TI",
    "TIT",
    "PHM",
    "HEB",
    "JAS",
    "1PE",
    "2PE",
    "1JN",
    "2JN",
    "3JN",
    "JUD",
    "REV",
]

# More empty verses than this means a truncated or broken export (real editions omit only a few).
MAX_EMPTY_VERSES = 50

# MySword book colours, by book_number upper bound (same palette as the other DBs).
COLORS = (
    (50, "#ccccff"),
    (190, "#ffcc99"),
    (260, "#66ff99"),
    (340, "#ff9fb4"),
    (460, "#ffff99"),
    (500, "#ff6600"),
    (510, "#00ffff"),
    (650, "#ffff00"),
    (720, "#00ff00"),
    (730, "#ff7c80"),
)


def book_numbers() -> list[int]:
    """The 66 canonical MySword numbers, ascending == canonical order (``bible_books.json``)."""
    data = json.loads((REPO_ROOT / "bible_books.json").read_text("utf-8"))
    nums = sorted(
        {entry["book_number"] for entry in data["books"].values()}
    )  # aliases share a number
    if len(nums) != 66:
        sys.exit(f"bible_books.json must list 66 books, found {len(nums)}")
    return nums


def color_for(number: int) -> str:
    try:
        return next(c for upper, c in COLORS if number <= upper)
    except StopIteration:
        raise ValueError(
            f"book number {number} is above the last colour band"
        ) from None


def has_accents(texts) -> bool:
    """True if any text has a combining mark once decomposed (é -> e + U+0301)."""
    return any(
        unicodedata.combining(c)
        for text in texts
        for c in unicodedata.normalize("NFD", text)
    )


def read_source(s: sqlite3.Connection, lang: str | None, version: str | None):
    """Validate the BibliaTodo source and return ``(lang, version, meta, libros, verses)``; exits cleanly if bad."""
    meta = dict(s.execute("SELECT clave, valor FROM metadatos"))
    if meta.get("schema") != "3":
        sys.exit(f"unsupported BibliaTodo schema {meta.get('schema')!r} (expected '3')")
    lang = lang or meta.get("idioma")
    version = version or meta.get("version")
    if not lang or not version:
        sys.exit("source metadatos lacks idioma/version; pass --lang and --version")
    # A version ID must be one the resolver can strip from a reference (VERSION_ID_PATTERN).
    if not re.fullmatch(VERSION_ID_PATTERN, version) or not re.fullmatch(
        r"[a-z]{2,3}", lang
    ):
        sys.exit(f"bad version/lang: {version!r}/{lang!r}")

    libros = s.execute(
        "SELECT codigo, orden, nombre FROM libros ORDER BY orden"
    ).fetchall()
    if [c for c, _, _ in libros] != USFM_ORDER or [o for _, o, _ in libros] != list(
        range(1, 67)
    ):
        sys.exit("libros is not the 66 canonical books in canonical order")

    # encabezado / titulo / subtitulo / referencias are optional columns: BibliaTodo only
    # includes them when the edition has data (the EN and PT text editions have none).
    have = {r[1] for r in s.execute("PRAGMA table_info(versiculos)")}
    opt = [c if c in have else "NULL" for c in ("encabezado", "titulo", "subtitulo")]
    verses = s.execute(
        f"SELECT libro, capitulo, versiculo, texto, {', '.join(opt)} "
        "FROM versiculos ORDER BY libro, capitulo, versiculo"
    ).fetchall()
    # NULL and whitespace-only text are both stored as ''
    verses = [(*v[:3], v[3] if (v[3] or "").strip() else "", *v[4:]) for v in verses]
    empty = [v[:3] for v in verses if not v[3].strip()]
    if not verses or len(empty) == len(verses):
        sys.exit("source has no verses or all verse text is empty")
    if len(empty) > MAX_EMPTY_VERSES:
        sys.exit(
            f"{len(empty)} of {len(verses)} verses are empty: source looks truncated"
        )
    if empty:
        # Some editions omit verses on purpose; they stay '' and the resolver reports them as empty.
        print(
            f"⚠️  {len(empty)} verses have empty or blank text (kept as in the source): {empty[:5]}",
            file=sys.stderr,
        )
    keys = [v[:3] for v in verses]
    if len(set(keys)) != len(keys):
        sys.exit("source contains duplicate (libro, capitulo, versiculo) rows")
    present = {v[0] for v in verses}
    if present - set(USFM_ORDER):
        sys.exit(
            f"source has verses for unknown books: {sorted(present - set(USFM_ORDER))}"
        )
    missing = set(USFM_ORDER) - present
    if missing:
        sys.exit(f"source has no verses for books: {sorted(missing)}")
    return lang, version, meta, libros, verses


def convert(src: Path, lang: str | None, version: str | None, out_dir: Path) -> Path:
    if not src.is_file():
        sys.exit(f"source not found: {src}")
    with closing(
        sqlite3.connect(src.resolve().as_uri() + "?mode=ro", uri=True)
    ) as source:
        lang, version, meta, libros, verses = read_source(source, lang, version)
    number = {code: n for (code, _, _), n in zip(libros, book_numbers())}

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "out.db"
        d = sqlite3.connect(db_path)
        d.executescript(
            """
            CREATE TABLE info(name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(name));
            CREATE TABLE books_all(book_number NUMERIC NOT NULL, book_color TEXT NOT NULL,
              short_name TEXT NOT NULL, long_name TEXT NOT NULL, is_present BOOLEAN NOT NULL,
              PRIMARY KEY(book_number));
            CREATE TABLE books(book_number NUMERIC NOT NULL, book_color TEXT NOT NULL,
              short_name TEXT NOT NULL, long_name TEXT NOT NULL, PRIMARY KEY(book_number));
            CREATE TABLE verses(book_number NUMERIC NOT NULL, chapter NUMERIC NOT NULL,
              verse NUMERIC NOT NULL, text TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(book_number, chapter, verse));
            CREATE TABLE stories(book_number NUMERIC NOT NULL, chapter NUMERIC NOT NULL,
              verse NUMERIC NOT NULL, order_if_several NUMERIC NOT NULL DEFAULT 0,
              title TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(book_number, chapter, verse, order_if_several));
            """
        )
        attribution = (meta.get("atribucion") or "").strip()
        ident = (meta.get("identificacion") or "").strip()
        history = (
            f"{ident} (converted by scripts/convert_bibliatodo.py)"
            if ident
            else "converted by scripts/convert_bibliatodo.py"
        )
        info = {
            "description": attribution.splitlines()[0] if attribution else version,
            "language": lang,
            "detailed_info": attribution,
            "history_of_changes": history,
            "contains_accents": str(has_accents(v[3] for v in verses)).lower(),
        }
        d.executemany("INSERT INTO info VALUES(?,?)", info.items())
        for code, _, name in libros:
            row = (number[code], color_for(number[code]), name, name)
            d.execute("INSERT INTO books_all VALUES(?,?,?,?,1)", row)
            d.execute("INSERT INTO books VALUES(?,?,?,?)", row)
        d.executemany(
            "INSERT INTO verses VALUES(?,?,?,?)",
            ((number[c], ch, vs, text) for c, ch, vs, text, *_ in verses),
        )
        stories = [
            (number[code], ch, vs, i, t)
            for code, ch, vs, _, *heads in verses
            for i, t in enumerate(h.strip() for h in heads if h and h.strip())
        ]
        d.executemany("INSERT INTO stories VALUES(?,?,?,?,?)", stories)
        d.commit()
        d.execute("VACUUM")
        d.close()

        out = out_dir / lang / f"{version}_{lang}.SQLite3.gz"
        out.parent.mkdir(parents=True, exist_ok=True)
        with (
            open(db_path, "rb") as src_db,
            open(out, "wb") as raw,
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz,
        ):
            shutil.copyfileobj(src_db, gz)
    print(f"✅ {out}  ({len(verses)} verses, {len(stories)} section titles)")
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "source", type=Path, help="BibliaTodo *-sqlite NTBT.sqlite (text edition)"
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT,
        help="repo root to write {lang}/ into",
    )
    p.add_argument("--lang")
    p.add_argument("--version")
    a = p.parse_args()
    convert(a.source.resolve(), a.lang, a.version, a.out_dir.resolve())


if __name__ == "__main__":
    main()
