#!/usr/bin/env python3
"""Convert a BibliaTodo "schema 3" SQLite (NTBT / BTNT / NTB-BR) to this repo's layout.

BibliaTodo ships ``libros / versiculos / metadatos / formato_capitulos`` keyed by USFM
code.  The repo (and ``bible_resolver``) use the MySword layout keyed by ``book_number``:
``info / books / books_all / verses / stories``.  Conversion is lossless for the Bible
text: ``texto`` is copied verbatim (the license requires the wording and its brackets to
be preserved).  Section titles become ``stories`` rows (order: encabezado, titulo,
subtitulo).  Not carried over: ``referencias`` (HTML links), ``formato_capitulos``
(paragraph/poetry structure) and, in the study edition, ``intro`` / ``nota``.

Usage:
    python scripts/convert_bibliatodo.py NTBT.sqlite            # -> es/NTBT_es.SQLite3.gz
    python scripts/convert_bibliatodo.py NTBT.sqlite --out-dir /tmp/out --version NTBT

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
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical order of the 66 books (USFM codes); ``libros.orden`` must follow it.
USFM_ORDER = (
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG "
    "ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL "
    "MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE "
    "1JN 2JN 3JN JUD REV"
).split()

# MySword book colours, by book_number upper bound (same palette as the other DBs).
COLORS = (
    (50, "#ccccff"), (190, "#ffcc99"), (260, "#66ff99"), (340, "#ff9fb4"),
    (460, "#ffff99"), (500, "#ff6600"), (510, "#00ffff"), (650, "#ffff00"),
    (720, "#00ff00"), (730, "#ff7c80"),
)


def book_numbers() -> list[int]:
    """The 66 canonical MySword numbers, ascending == canonical order (``bible_books.json``)."""
    data = json.loads((REPO_ROOT / "bible_books.json").read_text("utf-8"))
    nums = sorted({entry["book_number"] for entry in data["books"].values()})  # aliases share a number
    if len(nums) != 66:
        sys.exit(f"bible_books.json must list 66 books, found {len(nums)}")
    return nums


def color_for(number: int) -> str:
    return next(c for upper, c in COLORS if number <= upper)


def convert(src: Path, lang: str | None, version: str | None, out_dir: Path) -> Path:
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    meta = dict(s.execute("SELECT clave, valor FROM metadatos"))
    if meta.get("schema") != "3":
        sys.exit(f"unsupported BibliaTodo schema {meta.get('schema')!r} (expected '3')")
    lang = lang or meta["idioma"]
    version = version or meta["version"]
    if not re.fullmatch(r"[A-Za-z0-9-]+", version) or not re.fullmatch(r"[a-z]{2,3}", lang):
        sys.exit(f"bad version/lang: {version!r}/{lang!r}")

    libros = s.execute("SELECT codigo, orden, nombre FROM libros ORDER BY orden").fetchall()
    if [c for c, _, _ in libros] != USFM_ORDER or [o for _, o, _ in libros] != list(range(1, 67)):
        sys.exit("libros is not the 66 canonical books in canonical order")
    number = {code: n for (code, _, _), n in zip(libros, book_numbers())}

    verses = s.execute(
        "SELECT libro, capitulo, versiculo, texto, encabezado, titulo, subtitulo "
        "FROM versiculos ORDER BY libro, capitulo, versiculo"
    ).fetchall()
    if not verses or any(not v[3].strip() for v in verses):
        sys.exit("source has no verses or contains empty verse text")

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
        info = {
            "description": meta.get("atribucion", version).splitlines()[0],
            "language": lang,
            "detailed_info": meta.get("atribucion", ""),
            "history_of_changes": f"{meta.get('identificacion', '')} (converted by scripts/convert_bibliatodo.py)",
            "contains_accents": "true",
        }
        d.executemany("INSERT INTO info VALUES(?,?)", info.items())
        for code, _, name in libros:
            row = (number[code], color_for(number[code]), name, name)
            d.execute("INSERT INTO books_all VALUES(?,?,?,?,1)", row)
            d.execute("INSERT INTO books VALUES(?,?,?,?)", row)
        stories = []
        for code, ch, vs, text, enc, tit, sub in verses:
            n = number[code]
            d.execute("INSERT INTO verses VALUES(?,?,?,?)", (n, ch, vs, text))
            titles = [t.strip() for t in (enc, tit, sub) if t and t.strip()]
            stories += [(n, ch, vs, i, t) for i, t in enumerate(titles)]
        d.executemany("INSERT INTO stories VALUES(?,?,?,?,?)", stories)
        d.commit()
        d.execute("VACUUM")
        d.close()

        out = out_dir / lang / f"{version}_{lang}.SQLite3.gz"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
            gz.write(db_path.read_bytes())
    print(f"✅ {out}  ({len(verses)} verses, {len(stories)} section titles)")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", type=Path, help="BibliaTodo *-sqlite NTBT.sqlite (text edition)")
    p.add_argument("--out-dir", type=Path, default=REPO_ROOT, help="repo root to write {lang}/ into")
    p.add_argument("--lang")
    p.add_argument("--version")
    a = p.parse_args()
    convert(a.source.resolve(), a.lang, a.version, a.out_dir.resolve())


if __name__ == "__main__":
    main()
