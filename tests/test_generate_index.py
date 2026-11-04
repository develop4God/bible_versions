"""scripts/generate_index.py: config validation for version IDs and `source` tags."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location(
    "generate_index", ROOT / "scripts" / "generate_index.py"
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def cfg(version_id="NTBT", **version):
    return {"es": {"versions": {version_id: {"name": "n", "strong": False, **version}}}}


def disk(version_id="NTBT"):
    return {f"es/{version_id}_es.SQLite3.gz"}


def test_valid_config_passes(capsys):
    assert gen.validate(cfg(source="bibliatodo", disclaimer="d"), disk())
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "version_id", ["NTB_BR", "ntbt", "A", "A" * 11, "NTB-", "2024"]
)
def test_unstrippable_version_id_is_an_error(version_id, capsys):
    assert not gen.validate(cfg(version_id), disk(version_id))
    assert "BAD VERSION ID" in capsys.readouterr().out


def test_unknown_source_is_an_error(capsys):
    assert not gen.validate(cfg(source="biblia_todo"), disk())
    assert "BAD source 'biblia_todo'" in capsys.readouterr().out


def test_source_without_disclaimer_is_an_error(capsys):
    assert not gen.validate(cfg(source="bibliatodo"), disk())
    assert "MISSING disclaimer" in capsys.readouterr().out


def test_declared_version_without_file_is_an_error(capsys):
    assert not gen.validate(cfg(), set())
    assert "MISSING FILE" in capsys.readouterr().out


def test_non_string_version_id_is_a_clean_error(capsys):
    assert not gen.validate(
        {"es": {"versions": {2024: {"name": "n"}}}}, {"es/2024_es.SQLite3.gz"}
    )
    assert "BAD VERSION ID" in capsys.readouterr().out


def test_empty_version_entry_is_a_clean_error(capsys):
    assert not gen.validate({"es": {"versions": {"NTBT": None}}}, disk())
    assert "BAD ENTRY" in capsys.readouterr().out
