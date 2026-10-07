"""allowed_versions: optional per-language policy in index.json (default primary + fallback)."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
LANGS = json.loads((ROOT / "index.json").read_text("utf-8"))["languages"]


@pytest.mark.parametrize("lang", sorted(LANGS))
def test_allowed_versions_are_declared_versions_and_include_primary_and_fallback(lang):
    entry = LANGS[lang]
    allowed = entry.get("allowed_versions")
    if allowed is None:
        return  # default: [primary, fallback]
    assert set(allowed) <= set(entry["versions"])
    assert {entry["primary_version"], entry["fallback_version"]} <= set(allowed)


def test_english_content_may_cite_kj2000():
    assert LANGS["en"]["allowed_versions"] == ["KJV", "NIV", "KJ2000"]


def test_languages_without_the_field_keep_the_default():
    assert all("allowed_versions" not in v for lang, v in LANGS.items() if lang != "en")
