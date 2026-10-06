# 📖 Bible Databases ✝️
### `bible_versions`

<!-- AUTO-GENERATED:BADGES:START -->
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Languages](https://img.shields.io/badge/languages-10-brightgreen.svg)
![Versions](https://img.shields.io/badge/versions-27-brightgreen.svg)
<!-- AUTO-GENERATED:BADGES:END -->

Bible versions assets for [Develop4God](https://www.develop4God.com) ministry apps — for God's glory, in service of our mission (Isaiah 55:10-11).

## Available Bible Versions

This repository contains SQLite database files for various Bible translations in multiple languages.
Files are organized in per-language folders (`{LANG}/{VERSION}_{LANG}.SQLite3[.gz]`), e.g. `en/KJV_en.SQLite3.gz`.

A machine-readable index of all versions is available in [`index.json`](index.json).

<!-- AUTO-GENERATED:VERSION-TABLES:START -->
### `en` — English
| ID | Name | File | Strong's |
|----|------|------|----------|
| KJV | King James Version | `KJV_en.SQLite3.gz` | ✅ |
| NIV | New International Version | `NIV_en.SQLite3.gz` | — |
| KJ2000 | King James 2000 | `KJ2000_en.SQLite3.gz` | — |
| ESV | English Standard Version | `ESV_en.SQLite3.gz` | — |

### `es` — Español
| ID | Name | File | Strong's |
|----|------|------|----------|
| RVR1960 | Reina-Valera 1960 | `RVR1960_es.SQLite3.gz` | — |
| NVI | Nueva Versión Internacional | `NVI_es.SQLite3.gz` | — |
| NTV | Nueva Traducción Viviente | `NTV_es.SQLite3.gz` | — |
| RVR1909 | Reina-Valera 1909 | `RVR1909_es.SQLite3.gz` | ✅ |
| LBLA | La Biblia de las Américas | `LBLA_es.SQLite3.gz` | ✅ |

### `pt` — Português
| ID | Name | File | Strong's |
|----|------|------|----------|
| ARC | Almeida Revista e Corrigida | `ARC_pt.SQLite3.gz` | — |
| NVI | Nova Versão Internacional | `NVI_pt.SQLite3.gz` | — |
| ARA | Almeida Revista e Atualizada | `ARA_pt.SQLite3.gz` | — |

### `fr` — Français
| ID | Name | File | Strong's |
|----|------|------|----------|
| LSG1910 | Louis Segond 1910 | `LSG1910_fr.SQLite3.gz` | — |
| BDS | Bible du Semeur | `BDS_fr.SQLite3.gz` | — |
| NBS | Nouvelle Bible Segond | `NBS_fr.SQLite3.gz` | — |

### `ja` — 日本語
| ID | Name | File | Strong's |
|----|------|------|----------|
| SK2003 | 新改訳2003 | `SK2003_ja.SQLite3.gz` | — |
| JCB | リビングバイブル | `JCB_ja.SQLite3.gz` | — |

### `zh` — 中文
| ID | Name | File | Strong's |
|----|------|------|----------|
| CUV1919 | 和合本1919 | `CUV1919_zh.SQLite3.gz` | — |
| CNVS | 新译本 | `CNVS_zh.SQLite3.gz` | — |

### `hi` — हिन्दी
| ID | Name | File | Strong's |
|----|------|------|----------|
| HIOV | पवित्र बाइबिल (ओ.वी.) | `HIOV_hi.SQLite3.gz` | — |
| HERV | पवित्र बाइबिल | `HERV_hi.SQLite3.gz` | — |

### `de` — Deutsch
| ID | Name | File | Strong's |
|----|------|------|----------|
| LU17 | Luther 2017 | `LU17_de.SQLite3.gz` | — |
| SCH2000 | Schlachter 2000 | `SCH2000_de.SQLite3.gz` | — |

### `ar` — العربية
| ID | Name | File | Strong's |
|----|------|------|----------|
| NAV | الترجمة العربية الجديدة | `NAV_ar.SQLite3.gz` | — |
| SVDA | ترجمة سميث وفاندايك | `SVDA_ar.SQLite3.gz` | — |

### `fil` — Filipino
| ID | Name | File | Strong's |
|----|------|------|----------|
| MBB05 | Magandang Balita Biblia | `MBB05_fil.SQLite3.gz` | — |
| ASND | Ang Salita ng Dios | `ASND_fil.SQLite3.gz` | — |
<!-- AUTO-GENERATED:VERSION-TABLES:END -->

## File Naming Convention

Files live under a per-language folder and follow the pattern: `{LANG}/{VERSION}_{LANG}.SQLite3[.gz]`

- `{LANG}` — language code (ISO 639-1 for most, e.g. `en`, `es`, `fr`, `ja`, `pt`, `zh`, `hi`, `de`, `ar`; `fil` is ISO 639-2 for Filipino)
- `{VERSION}` — Bible version abbreviation (e.g., `KJV`, `NVI`, `RVR1960`)

## File Formats

Each Bible version is available in two formats:

**Compressed files** (`.SQLite3.gz`) — Gzip-compressed for efficient downloads (~65–70% smaller)


To decompress a `.gz` file:
```bash
gunzip <filename>.SQLite3.gz
```

Or use gzip-compatible decompression libraries in your application.

## Verse Resolver

The `bible_resolver` package (in [`src/bible_resolver/`](src/bible_resolver/)) is the **single source of truth** for resolving English Bible references (e.g. `"John 3:16"`, `"1 Corinthians 13:4-7"`) to native-language citations and verse text from any of the SQLite databases in this repo. Do not copy it into other projects — depend on it.

You always call it with the **English** book name, regardless of which language database you're querying. [`bible_books.json`](bible_books.json) is the source of truth mapping EN book names to a `book_number` that's identical across all language DBs (MySword/TheWord standard). The native book name comes from the target DB's own `books` table, then passes through a per-language sanitizer ([`data/book_name_sanitizers/`](src/bible_resolver/data/book_name_sanitizers/)) so citations carry clean names (`यूहन्ना`, not `यूहन्ना रचित सुसमाचार`). The language is read from the DB's `info` table, or passed as `language=`. Known versification differences (e.g. German Joel/Malachi) are remapped via [`versification_shifts.json`](src/bible_resolver/data/versification_shifts.json).

Requires Python 3.12+. `bible_books.json` has a single copy: the repo root, on `main`. In a checkout it is read locally; when installed as a dependency it is downloaded from `main` (10 s timeout, cached under `~/.cache/bible_resolver/`, used offline once cached). Either way its hash is validated against `meta.books_sot.hash` in [`index.json`](index.json); a bad download raises `BooksSotError`. After editing it, run `python3 scripts/generate_index.py` (CI does this on push to `main`). The package does **not** ship the databases: pass the path to a `.SQLite3` or `.SQLite3.gz` file you have downloaded. Empty or missing verses return an `error` instead of blank text.

Add it to a project with [uv](https://docs.astral.sh/uv/):

```bash
uv add "bible-resolver @ git+https://github.com/develop4God/bible_versions"
```

```python
from bible_resolver import VerseResolver

with VerseResolver("hi/HIOV_hi.SQLite3.gz") as r:
    cita, texto, error = r.resolve("John 3:16")
    # cita  -> "यूहन्ना 3:16"
    # texto -> verse text from the DB, markup and footnotes stripped
```

Versification shifts are keyed by language code, then DB filename stem (e.g. `DE` → `LU17_de`), then `"Book Chapter:Verse"` → `"Chapter:Verse"`; a range that starts on a shifted verse keeps its length.

Filipino is `fil`: passing `language="tl"` raises `ValueError` (the two Filipino DBs store `tl` in their own info table, which the resolver maps to `fil`).

Citation titles are never guessed silently: every language has a complete map in `book_name_sanitizers/` (or declares `"passthrough": true`, as `zh` and `ja` do). A book no rule covers emits `UnmappedBookWarning` (or raises with `VerseResolver(..., strict=True)`), and `resolver.coverage()` lists which books are mapped. `tests/golden_citations.json` snapshots all citation titles for every shipped DB; review its diff when you change a rule (`UPDATE_GOLDEN=1 uv run pytest tests/test_coverage.py` regenerates it).

Run the tests with `uv run pytest` (they cover every shipped DB, including long/irregular book names in HIOV, ARA/ARC/NVI and Chinese).

## Contributing

If you'd like to suggest a new version or language, report an issue with the data, or propose an improvement, please open an issue or pull request. Or just contact us!.

**Roadmap:** a hosted API for this data is under consideration.

## Copyright & Disclaimer

The Bible translation databases in this repository are sourced from [MyBible (ph4.org)](https://www.ph4.org/b4_1.php?l=en). Each translation retains its own copyright and license terms as set by its respective publisher/rights holder — some (e.g. KJV, LSG1910) are public domain, while others (e.g. NIV, ESV) are commercially copyrighted with restrictions on redistribution and usage.

This repository does not claim ownership of any Bible text. For authoritative licensing and attribution details on a specific translation, refer to [ph4.org](https://www.ph4.org/b4_1.php?l=en). If you plan to redistribute or use these texts beyond personal/app-internal use, verify the license terms for that specific version first.

The code in this repository (scripts, index generation, tooling) is licensed under the [MIT License](LICENSE).

## Contact

Questions or support: develop4god@gmail.com
Website: [www.develop4God.com](https://www.develop4God.com)
