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


def make_source(path, schema="3", empty=False, meta=None, mutate=None):
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
    values = {
        "schema": schema,
        "idioma": "es",
        "version": "TST",
        "atribucion": "Crédito\nlínea 2",
    }
    values.update(meta or {})
    s.executemany(
        "INSERT INTO metadatos VALUES(?,?)",
        [(k, v) for k, v in values.items() if v is not None],
    )
    if mutate:
        mutate(s)
    s.commit()
    s.close()


@pytest.fixture
def read(tmp_path):
    """Open a converted .gz as sqlite; connections are closed at teardown."""
    opened = []

    def _read(out):
        db_file = tmp_path / f"read{len(opened)}.db"
        db_file.write_bytes(gzip.decompress(out.read_bytes()))
        opened.append(sqlite3.connect(db_file))
        return opened[-1]

    yield _read
    for conn in opened:
        conn.close()


def test_converts_to_repo_layout(tmp_path, read):
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


def test_optional_title_columns_may_be_absent(tmp_path, read):
    """EN/PT text editions ship versiculos(libro, capitulo, versiculo, texto) only."""
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


def convert(tmp_path, lang=None, version=None):
    return conv.convert(tmp_path / "src.sqlite", lang, version, tmp_path / "o")


def test_lang_and_version_overrides(tmp_path):
    make_source(tmp_path / "src.sqlite")
    out = convert(tmp_path, lang="pt", version="X-1")
    assert out == tmp_path / "o" / "pt" / "X-1_pt.SQLite3.gz"


@pytest.mark.parametrize(
    "lang, version", [("ES", "TST"), ("es", "../evil"), ("es", "a b"), ("e", "TST"), ("es", "-rf"), ("es", "--")]
)
def test_rejects_unsafe_lang_or_version(tmp_path, lang, version):
    make_source(tmp_path / "src.sqlite")
    with pytest.raises(SystemExit, match="bad version/lang"):
        convert(tmp_path, lang=lang, version=version)


@pytest.mark.parametrize("missing", ["idioma", "version"])
def test_missing_metadata_exits_cleanly(tmp_path, missing):
    make_source(tmp_path / "src.sqlite")
    s = sqlite3.connect(tmp_path / "src.sqlite")
    s.execute("DELETE FROM metadatos WHERE clave=?", (missing,))
    s.commit()
    s.close()
    with pytest.raises(SystemExit, match="lacks idioma/version"):
        convert(tmp_path)


def test_rejects_non_canonical_book_order(tmp_path):
    make_source(
        tmp_path / "src.sqlite",
        mutate=lambda s: s.execute("UPDATE libros SET orden=2 WHERE codigo='GEN'"),
    )
    with pytest.raises(SystemExit):
        convert(tmp_path)


def test_rejects_null_verse_text(tmp_path):
    make_source(
        tmp_path / "src.sqlite",
        mutate=lambda s: s.execute(
            "UPDATE versiculos SET texto=NULL WHERE libro='GEN'"
        ),
    )
    with pytest.raises(SystemExit):
        convert(tmp_path)


def test_rejects_duplicate_verses(tmp_path):
    def dup(s):
        s.execute("INSERT INTO versiculos VALUES('GEN',1,1,'dup',NULL,NULL,NULL,NULL)")

    make_source(tmp_path / "src.sqlite", mutate=dup)
    with pytest.raises(SystemExit):
        convert(tmp_path)


def test_rejects_unknown_book_code(tmp_path):
    def add(s):
        s.execute("INSERT INTO versiculos VALUES('XXX',1,1,'x',NULL,NULL,NULL,NULL)")

    make_source(tmp_path / "src.sqlite", mutate=add)
    with pytest.raises(SystemExit, match="unknown books"):
        convert(tmp_path)


def test_source_connection_is_released_on_failure(tmp_path, monkeypatch):
    make_source(tmp_path / "src.sqlite", schema="2")
    opened = []
    real_connect = sqlite3.connect

    def spy(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(conv.sqlite3, "connect", spy)
    with pytest.raises(SystemExit):
        convert(tmp_path)
    assert opened
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")  # raises only if the connection was closed


def test_rejects_book_without_verses(tmp_path):
    make_source(
        tmp_path / "src.sqlite",
        mutate=lambda s: s.execute("DELETE FROM versiculos WHERE libro='REV'"),
    )
    with pytest.raises(SystemExit):
        convert(tmp_path)


@pytest.mark.parametrize("attribution", ["", "   ", None])
def test_empty_attribution_falls_back_to_version(tmp_path, read, attribution):
    make_source(tmp_path / "src.sqlite", meta={"atribucion": attribution})
    db = read(convert(tmp_path))
    assert db.execute("SELECT value FROM info WHERE name='description'").fetchone() == (
        "TST",
    )


def test_history_without_identificacion(tmp_path, read):
    make_source(tmp_path / "src.sqlite")
    db = read(convert(tmp_path))
    (history,) = db.execute(
        "SELECT value FROM info WHERE name='history_of_changes'"
    ).fetchone()
    assert history == "converted by scripts/convert_bibliatodo.py"


def test_history_with_identificacion(tmp_path, read):
    make_source(
        tmp_path / "src.sqlite", meta={"identificacion": "BibliaTodo NTBT 2024"}
    )
    db = read(convert(tmp_path))
    (history,) = db.execute(
        "SELECT value FROM info WHERE name='history_of_changes'"
    ).fetchone()
    assert (
        history == "BibliaTodo NTBT 2024 (converted by scripts/convert_bibliatodo.py)"
    )
