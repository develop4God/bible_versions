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


def test_only_trailing_url_is_stripped():
    table = gen.build_bibliatodo_credits(
        langs(
            A={
                "source": "bibliatodo",
                "disclaimer": "See https://x.example for terms. By X. https://x.example/a",
            }
        )
    )
    assert "| See https://x.example for terms. By X. |" in table


def test_trailing_whitespace_after_url_is_stripped():
    table = gen.build_bibliatodo_credits(
        langs(A={"source": "bibliatodo", "disclaimer": "By X. https://x.example/a \n"})
    )
    assert "| By X. |" in table


def test_tagged_version_without_disclaimer_exits():
    with pytest.raises(SystemExit):
        gen.build_bibliatodo_credits(langs(NTBT={"source": "bibliatodo"}))


def test_readme_credit_block_is_in_sync_with_config():
    config = gen.load_config()["languages"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start, end = (
        "<!-- AUTO-GENERATED:BIBLIATODO-CREDITS:START -->",
        "<!-- AUTO-GENERATED:BIBLIATODO-CREDITS:END -->",
    )
    assert start in readme and end in readme, (
        "README lost the BIBLIATODO-CREDITS markers"
    )
    block = readme.split(start, 1)[1].split(end, 1)[0].strip()
    assert block == gen.build_bibliatodo_credits(config)
