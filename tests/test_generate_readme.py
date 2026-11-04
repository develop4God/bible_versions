"""scripts/generate_readme.py: credit table is generated from config disclaimers."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location(
    "generate_readme", ROOT / "scripts" / "generate_readme.py"
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def langs(**versions):
    return {"es": {"name": "Español", "versions": versions}}


def test_credits_listed_from_disclaimer_without_url():
    table = gen.build_bibliatodo_credits(
        langs(
            NTBT={
                "source": "bibliatodo",
                "disclaimer": "Santa Biblia (NTBT). Publicada por X. https://x.example/a",
            },
            RVR={"name": "r", "disclaimer": "public domain"},
        )
    )
    assert "| NTBT | `es` | Santa Biblia (NTBT). Publicada por X. |" in table
    assert "RVR" not in table and "http" not in table


def test_no_tagged_versions_gives_header_only():
    assert gen.build_bibliatodo_credits(langs(A={"disclaimer": "d"})).count("\n") == 1


def test_tagged_version_without_disclaimer_exits():
    with pytest.raises(SystemExit):
        gen.build_bibliatodo_credits(langs(NTBT={"source": "bibliatodo"}))


def test_readme_credit_block_is_in_sync_with_config():
    config = gen.load_config()["languages"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert gen.build_bibliatodo_credits(config) in readme
