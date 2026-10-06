import gzip
import shutil
import sqlite3

import pytest

from bible_resolver import VerseResolver, clean_verse_text, parse_en_ref
from bible_resolver.book_name_normalizer import sanitize_book_name

pytestmark = pytest.mark.filterwarnings("ignore::bible_resolver.UnmappedBookWarning")

HIOV_LONG = {
    "Matthew": (470, "मत्ती रचित सुसमाचार", "मत्ती"),
    "Mark": (480, "मरकुस रचित सुसमाचार", "मरकुस"),
    "Luke": (490, "लूका रचित सुसमाचार", "लूका"),
    "John": (500, "यूहन्ना रचित सुसमाचार", "यूहन्ना"),
}


class TestParseRef:
    def test_single_and_range(self):
        assert parse_en_ref("John 3:16") == ("John", 3, 16, 16)
        assert parse_en_ref("1 Corinthians 13:4-7") == ("1 Corinthians", 13, 4, 7)

    def test_version_suffix_and_devanagari_digits(self):
        assert parse_en_ref("John 3:16 KJV") == ("John", 3, 16, 16)
        assert parse_en_ref("John ३:१६") == ("John", 3, 16, 16)

    def test_unparseable(self):
        assert parse_en_ref("not a ref") is None


class TestCleanVerseText:
    def test_footnote_and_note_elements_dropped_with_content(self):
        assert clean_verse_text("In<f>[3]</f> the<n>〔注：或〕</n> beginning") == "In the beginning"

    def test_note_containing_nested_footnote_is_dropped_whole(self):
        raw = "不能胜过他<n>〔『权柄』原文是『<f>[30]</f>门』〕</n>。"
        assert clean_verse_text(raw) == "不能胜过他。"

    def test_other_tags_keep_content(self):
        assert clean_verse_text("<pb/><t> Car qui </t><J>a connu</J>") == "Car qui a connu"

    def test_circled_markers_and_space_before_punctuation(self):
        assert clean_verse_text("Dieu ① est , bon !") == "Dieu est, bon!"


class TestHindiBookNames:
    @pytest.mark.parametrize("book", HIOV_LONG)
    def test_gospel_long_form_normalized_via_db_language(self, make_db, book):
        number, long_name, short = HIOV_LONG[book]
        path = make_db([(number, long_name)], [(number, 1, 1, "t")], language="hi")
        with VerseResolver(path) as r:
            assert r.language == "hi"
            assert r.resolve(f"{book} 1:1") == (f"{short} 1:1", "t", None)

    def test_explicit_language_overrides_missing_info(self, make_db):
        path = make_db([(490, "लूका रचित सुसमाचार")], [(490, 24, 13, "t")])
        with VerseResolver(path, language="hi") as r:
            assert r.resolve("Luke 24:13")[0] == "लूका 24:13"

    def test_no_language_leaves_db_title_unchanged(self, make_db):
        path = make_db([(490, "लूका रचित सुसमाचार")], [(490, 24, 13, "t")])
        with VerseResolver(path) as r:
            assert r.language is None
            assert r.resolve("Luke 24:13")[0] == "लूका रचित सुसमाचार 24:13"

    def test_unmapped_language_passes_title_through(self, make_db):
        path = make_db([(10, "Genesis")], [(10, 1, 3, "x")], language="xx")
        with VerseResolver(path) as r:
            assert r.resolve("Genesis 1:3")[0] == "Genesis 1:3"


class TestBookNameFallbacks:
    def test_missing_books_table_falls_back_to_english(self, tmp_path):
        path = tmp_path / "m.SQLite3"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE verses (book_number INTEGER, chapter INTEGER, verse INTEGER, text TEXT)")
        conn.execute("INSERT INTO verses VALUES (10, 1, 1, 'x')")
        conn.commit()
        conn.close()
        with VerseResolver(str(path)) as r:
            assert r.resolve("Genesis 1:1") == ("Genesis 1:1", "x", None)

    def test_sanitize_without_language_is_noop(self):
        assert sanitize_book_name("raw", 10, None) == "raw"


class TestVersificationShift:
    def test_german_joel_shift_applies_by_db_filename_and_language(self, make_db):
        path = make_db([(360, "Joel")], [(360, 3, 1, "geist")], language="de", name="LU17_de.SQLite3")
        with VerseResolver(path) as r:
            assert r.resolve("Joel 2:28") == ("Joel 3:1", "geist", None)

    def test_no_shift_for_other_version(self, make_db):
        path = make_db([(360, "Joel")], [(360, 2, 28, "x")], language="de", name="OTHER_de.SQLite3")
        with VerseResolver(path) as r:
            assert r.resolve("Joel 2:28")[0] == "Joel 2:28"


class TestResolveErrors:
    def test_unparseable_unknown_book_and_missing_verse(self, make_db):
        path = make_db([(10, "Genesis")], [(10, 1, 1, "x")])
        with VerseResolver(path) as r:
            assert "could not parse" in r.resolve("garbage")[2]
            assert "unknown book" in r.resolve("Nonexistent 1:1")[2]
            assert "chapter has 1 verses" in r.resolve("Genesis 1:9")[2]

    def test_null_text_cell_is_not_found(self, make_db):
        path = make_db([(10, "Genesis")], [(10, 1, 1, "a"), (10, 1, 2, None)])
        with VerseResolver(path) as r:
            assert r.resolve("Genesis 1:1-2")[0] is None
            assert r.resolve("Genesis 1:1")[0] == "Genesis 1:1"

    def test_range_running_past_chapter_end_is_not_found_not_truncated(self, make_db):
        path = make_db([(10, "Genesis")], [(10, 1, 1, "a"), (10, 1, 2, "b")])
        with VerseResolver(path) as r:
            cita, texto, error = r.resolve("Genesis 1:1-3")
            assert (cita, texto) == (None, None) and "chapter has 2 verses" in error
            assert r.resolve("Genesis 1:1-2")[1] == "a b"

    def test_gap_inside_range_is_not_found(self, make_db):
        path = make_db([(10, "Genesis")], [(10, 1, 1, "a"), (10, 1, 3, "c")])
        with VerseResolver(path) as r:
            assert r.resolve("Genesis 1:1-3")[0] is None

    def test_resolve_many(self, make_db):
        path = make_db([(10, "Genesis")], [(10, 1, 1, "a")])
        with VerseResolver(path) as r:
            out = r.resolve_many(["Genesis 1:1", "Genesis 9:9"])
            assert out[0]["error"] is None and out[1]["error"]


class TestGzipInput:
    def test_gz_db_is_read_in_memory(self, make_db, tmp_path):
        raw = make_db([(10, "Genesis")], [(10, 1, 1, "a")])
        gz = tmp_path / "t.SQLite3.gz"
        with open(raw, "rb") as s, gzip.open(gz, "wb") as d:
            shutil.copyfileobj(s, d)
        before = set(tmp_path.iterdir())
        with VerseResolver(str(gz)) as r:
            assert r.resolve("Genesis 1:1")[2] is None
        assert set(tmp_path.iterdir()) == before

    def test_corrupt_gz_raises_without_leaking(self, tmp_path):
        bad = tmp_path / "bad.SQLite3.gz"
        bad.write_bytes(b"not gzip")
        with pytest.raises(OSError):
            VerseResolver(str(bad))


class TestVersificationRanges:
    def test_range_starting_at_shifted_verse_keeps_length(self, make_db):
        path = make_db(
            [(360, "Joel")],
            [(360, 3, 1, "a"), (360, 3, 2, "b")],
            language="de",
            name="LU17_de.SQLite3",
        )
        with VerseResolver(path) as r:
            assert r.resolve("Joel 2:28-29") == ("Joel 3:1-2", "a b", None)

    def test_unlisted_range_is_untouched(self, make_db):
        path = make_db([(360, "Joel")], [(360, 2, 1, "a")], language="de", name="LU17_de.SQLite3")
        with VerseResolver(path) as r:
            assert r.resolve("Joel 2:1")[0] == "Joel 2:1"


class TestParseRefNegatives:
    @pytest.mark.parametrize("bad", ["", "John", "John 3", "John 3:", "3:16", "John 3:16-", "John 3:16 kjv extra words"])
    def test_rejected(self, bad):
        assert parse_en_ref(bad) is None

    def test_multiword_and_numbered_books(self):
        assert parse_en_ref("Song of Solomon 2:1") == ("Song of Solomon", 2, 1, 1)
        assert parse_en_ref("1 Thessalonians 5:16-18 NIV") == ("1 Thessalonians", 5, 16, 18)


class TestLanguageNormalization:
    @pytest.mark.parametrize("raw", ["zh Simplified", "PT-BR", "hi_IN", " Hi "])
    def test_primary_subtag_is_used(self, make_db, raw):
        path = make_db([(490, "लूका रचित सुसमाचार")], [(490, 1, 1, "t")], language=raw)
        with VerseResolver(path) as r:
            assert r.language == raw.strip().replace("_", "-").split("-")[0].split()[0].lower()
