# bible_versions
Bible versions assets for bible core apps

## Available Bible Versions

This repository contains SQLite database files for various Bible translations in multiple languages:

### English (en/)
- KJV - King James Version
- ESV - English Standard Version
- NIV - New International Version

### Spanish (es/)
- NVI - Nueva Versión Internacional
- NTV - Nueva Traducción Viviente
- RVR1960 - Reina-Valera 1960

### French (fr/)
- LSG1910 - Louis Segond 1910
- NBS - Nouvelle Bible Segond
- BDS - Bible du Semeur

### Japanese (ja/)
- 新改訳2003 - New Japanese Bible 2003
- リビングバイブル - Living Bible

### Portuguese (pt/)
- NVI - Nova Versão Internacional
- ARC - Almeida Revista e Corrigida

## File Formats

Each Bible version is available in two formats:

1. **Original SQLite files** (`.SQLite3`) - For backward compatibility with existing applications
2. **Compressed files** (`.SQLite3.gz`) - Gzip-compressed with maximum compression level (-9) for efficient downloads

The compressed files are approximately 65-70% smaller than the originals, making them ideal for:
- Faster downloads
- Reduced bandwidth usage
- Efficient storage

To use a compressed file, simply decompress it:
```bash
gunzip <filename>.SQLite3.gz
```

Or in your application, use gzip-compatible decompression libraries.
