#!/usr/bin/env python3
"""
generate_readme.py
─────────────────────────────────────────────────────────────────────────────
Reads bible_versions_config.yml → regenerates the badges and per-language
version tables in README.md between AUTO-GENERATED marker comments.

Run from repo root:
  python3 scripts/generate_readme.py

Exit codes:
  0  → README.md written (or unchanged)
  1  → config not found
─────────────────────────────────────────────────────────────────────────────
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ PyYAML not found. Run: pip install pyyaml --break-system-packages")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / ".github" / "bible_versions_config.yml"
README_PATH = REPO_ROOT / "README.md"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ Config not found: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def replace_marker_block(text: str, marker: str, new_block: str) -> str:
    """Replaces content between AUTO-GENERATED:{marker}:START/END comments."""
    pattern = re.compile(
        rf"(<!-- AUTO-GENERATED:{marker}:START -->\n)(.*?)(\n<!-- AUTO-GENERATED:{marker}:END -->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        print(f"⚠️  README marker '{marker}' not found — skipping")
        return text
    return pattern.sub(lambda m: m.group(1) + new_block + m.group(3), text)


def build_version_tables(languages: dict) -> str:
    """Builds the per-language markdown tables from config."""
    blocks = []
    for lang, lang_data in languages.items():
        rows = [f"### {lang_data['name']} (`{lang}`)", "| ID | Name | File |", "|----|------|------|"]
        for version_id, version_name in lang_data["versions"].items():
            filename = f"{version_id}_{lang}.SQLite3.gz"
            rows.append(f"| {version_id} | {version_name} | `{filename}` |")
        blocks.append("\n".join(rows))
    return "\n\n".join(blocks)


def build_badges(languages: dict) -> str:
    version_count = sum(len(ld["versions"]) for ld in languages.values())
    return (
        "![License](https://img.shields.io/badge/license-MIT-blue.svg)\n"
        f"![Languages](https://img.shields.io/badge/languages-{len(languages)}-brightgreen.svg)\n"
        f"![Versions](https://img.shields.io/badge/versions-{version_count}-brightgreen.svg)"
    )


def update_readme(languages: dict) -> bool:
    """Regenerates the version tables and badges in README.md. Returns True if changed."""
    if not README_PATH.exists():
        print(f"❌ README.md not found: {README_PATH}")
        sys.exit(1)

    original = README_PATH.read_text(encoding="utf-8")
    updated = replace_marker_block(original, "BADGES", build_badges(languages))
    updated = replace_marker_block(updated, "VERSION-TABLES", build_version_tables(languages))

    if updated == original:
        print("✅ README.md unchanged — no commit needed")
        return False

    README_PATH.write_text(updated, encoding="utf-8")
    print(f"✅ README.md updated → {README_PATH}")
    return True


def main():
    print("─── generate_readme.py ──────────────────────────────────")
    config = load_config()
    update_readme(config["languages"])
    print("─────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
