# bible_versions
Bible versions assets for bible core apps

## Available Bible Versions

This repository contains SQLite database files for various Bible translations in multiple languages.
All files are stored in a flat structure at the root of the repository, named `{VERSION}_{LANG}.SQLite3[.gz]`.

A machine-readable index of all versions is available in [`index.json`](index.json).

### English (`en`)
| ID | Name | File |
|----|------|------|
| KJV | King James Version | `KJV_en.SQLite3.gz` |
| NIV | New International Version | `NIV_en.SQLite3.gz` |
| ESV | English Standard Version | `ESV_en.SQLite3.gz` |

### Spanish (`es`)
| ID | Name | File |
|----|------|------|
| NVI | Nueva Versión Internacional | `NVI_es.SQLite3.gz` |
| RVR1960 | Reina-Valera 1960 | `RVR1960_es.SQLite3.gz` |
| NTV | Nueva Traducción Viviente | `NTV_es.SQLite3.gz` |

### French (`fr`)
| ID | Name | File |
|----|------|------|
| LSG1910 | Louis Segond 1910 | `LSG1910_fr.SQLite3.gz` |
| BDS | Bible du Semeur | `BDS_fr.SQLite3.gz` |
| NBS | Nouvelle Bible Segond | `NBS_fr.SQLite3.gz` |

### Japanese (`ja`)
| ID | Name | File |
|----|------|------|
| SK2003 | 新改訳2003 | `SK2003_ja.SQLite3.gz` |
| JCB | リビングバイブル | `JCB_ja.SQLite3.gz` |

### Portuguese (`pt`)
| ID | Name | File |
|----|------|------|
| ARC | Almeida Revista e Corrigida | `ARC_pt.SQLite3.gz` |
| NVI | Nova Versão Internacional | `NVI_pt.SQLite3.gz` |

### Chinese (`zh`)
| ID | Name | File |
|----|------|------|
| CUV1919 | 和合本1919 | `CUV1919_zh.SQLite3.gz` |
| CNVS | 新译本 | `CNVS_zh.SQLite3.gz` |

### Hindi (`hi`)
| ID | Name | File |
|----|------|------|
| HIOV | पवित्र बाइबिल (ओ.वी.) | `HIOV_hi.SQLite3.gz` |
| HERV | पवित्र बाइबिल (HERV) | `HERV_hi.SQLite3.gz` |

### German (`de`)
| ID | Name | File |
|----|------|------|
| LU17 | Lutherbibel 2017 | `LU17_de.SQLite3.gz` |
| SCH2000 | Schlachter 2000 | `SCH2000_de.SQLite3.gz` |

## File Naming Convention

Files follow the pattern: `{VERSION}_{LANG}.SQLite3[.gz]`

- `{VERSION}` — Bible version abbreviation (e.g., `KJV`, `NVI`, `RVR1960`)
- `{LANG}` — ISO 639-1 language code (e.g., `en`, `es`, `fr`, `ja`, `pt`, `zh`, `hi`, `de`)

## File Formats

Each Bible version is available in two formats:

**Compressed files** (`.SQLite3.gz`) — Gzip-compressed for efficient downloads (~65–70% smaller)


To decompress a `.gz` file:
```bash
gunzip <filename>.SQLite3.gz
```

Or use gzip-compatible decompression libraries in your application.
