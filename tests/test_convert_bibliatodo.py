"""scripts/convert_bibliatodo.py: BibliaTodo schema 3 -> repo (MySword) layout."""

import gzip
import importlib.util
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("convert_bibliatodo", ROOT / "scripts" / "convert_bibliatodo.py")
conv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conv)


def make_source(path, schema="3", empty=False):
    s = sqlite3.connect(path)
    s.executescript(
        "CREATE TABLE libros(codigo TEXT PRIMARY KEY, orden INTEGER, nombre TEXT);"
        "CREATE TABLE versiculos(libro TEXT, capitulo INT, versiculo INT, texto TEXT,"
        " encabezado TEXT, titulo TEXT, subtitulo TEXT, referencias TEXT);"
        "CREATE TABLE metadatos(clave TEXT PRIMARY KEY, valor TEXT);"
    )
    for i, code in enumerate(conv.USFM_ORDER, 1):
        s.execute("INSERT INTO libros VALUES(?,?,?)", (code, i, f"Libro {code}"))
        s.execute(
            "INSERT INTO versiculos VALUES(?,?,?,?,?,?,?,NULL)",
            (code, 1, 1, "" if empty else f"[Texto] {code}", "Enc" if i == 19 else None, "Tit", None),
        )
    s.executemany(
        "INSERT INTO metadatos VALUES(?,?)",
        [("schema", schema), ("idioma", "es"), ("version", "TST"), ("atribucion", "Crédito\nlínea 2")],
    )
    s.commit()
    s.close()


def read(out):
    import tempfile

    tmp = Path(tempfile.mkdtemp()) / "x.db"
    tmp.write_bytes(gzip.decompress(out.read_bytes()))
    return sqlite3.connect(tmp)  # closed on garbage collection; tmp dir is throwaway


def test_converts_to_repo_layout(tmp_path):
    make_source(tmp_path / "src.sqlite")
    out = conv.convert(tmp_path / "src.sqlite", None, None, tmp_path / "o")
    assert out == tmp_path / "o" / "es" / "TST_es.SQLite3.gz"
    db = read(out)
    assert db.execute("SELECT value FROM info WHERE name='language'").fetchone() == ("es",)
    assert db.execute("SELECT COUNT(*) FROM books").fetchone() == (66,)
    # USFM -> MySword numbers: GEN=10, PSA=230 (gaps in the numbering), REV=730
    nums = dict(db.execute("SELECT long_name, book_number FROM books"))
    assert (nums["Libro GEN"], nums["Libro PSA"], nums["Libro REV"]) == (10, 230, 730)
    # text is verbatim, brackets included
    assert db.execute("SELECT text FROM verses WHERE book_number=10").fetchone() == ("[Texto] GEN",)
    # Psalms: encabezado then titulo, ordered
    assert db.execute(
        "SELECT order_if_several, title FROM stories WHERE book_number=230 ORDER BY 1"
    ).fetchall() == [(0, "Enc"), (1, "Tit")]


def test_output_is_deterministic(tmp_path):
    make_source(tmp_path / "src.sqlite")
    a = conv.convert(tmp_path / "src.sqlite", None, None, tmp_path / "a").read_bytes()
    b = conv.convert(tmp_path / "src.sqlite", None, None, tmp_path / "b").read_bytes()
    assert a == b


@pytest.mark.parametrize("kw", [{"schema": "2"}, {"empty": True}])
def test_rejects_bad_sources(tmp_path, kw):
    make_source(tmp_path / "src.sqlite", **kw)
    with pytest.raises(SystemExit):
        conv.convert(tmp_path / "src.sqlite", None, None, tmp_path / "o")


def test_optional_title_columns_may_be_absent(tmp_path):
    """EN/PT text editions ship versiculos(libro, capitulo, versiculo, texto) only."""
    make_source(tmp_path / "full.sqlite")
    s = sqlite3.connect(tmp_path / "src.sqlite")
    s.executescript(
        "CREATE TABLE libros(codigo TEXT PRIMARY KEY, orden INTEGER, nombre TEXT);"
        "CREATE TABLE versiculos(libro TEXT, capitulo INT, versiculo INT, texto TEXT);"
        "CREATE TABLE metadatos(clave TEXT PRIMARY KEY, valor TEXT);"
    )
    for i, code in enumerate(conv.USFM_ORDER, 1):
        s.execute("INSERT INTO libros VALUES(?,?,?)", (code, i, code))
        s.execute("INSERT INTO versiculos VALUES(?,1,1,'t')", (code,))
    s.executemany("INSERT INTO metadatos VALUES(?,?)", [("schema", "3"), ("idioma", "en"), ("version", "BTNT")])
    s.commit()
    s.close()
    db = read(conv.convert(tmp_path / "src.sqlite", None, None, tmp_path / "o"))
    assert db.execute("SELECT COUNT(*) FROM stories").fetchone() == (0,)
