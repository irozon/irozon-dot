# Licenses

## Public source repository

**The source repository can be public.** Irozon Dot source is MIT licensed. The repository keeps the original adapter's full MIT notice and the project dependency notices in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). PlatformIO fetches framework, library and font files into the ignored `.pio` directory. Those files are not in Git history or source archives.

The UI uses `FreeSansBold9pt7b.h`, `FreeSansBold12pt7b.h`, `FreeSansBold18pt7b.h` and `FreeSansBold24pt7b.h` from LovyanGFX 1.2.7. The Windows app does not use them. The font headers are fetched at build time; this repository does not redistribute them. The README pictures are rendered screen previews, not font files.

## Firmware binaries

**Do not distribute compiled firmware yet.** The FreeSans glyphs originate from GNU FreeFont, licensed GPL-3.0-or-later with an exception for embedding fonts in documents. That exception does not resolve embedding these glyph tables in a firmware executable. The firmware's combined-work licensing still needs a decision or separate permission. See the [FreeFont license](https://www.gnu.org/software/freefont/license.html) and [FAQ](https://www.gnu.org/software/freefont/FAQ.html).

Arduino-ESP32 also needs its corresponding source and a working relinking path for a redistributed firmware image. The exact linked ESP-IDF components and their notices need an inventory. These are binary distribution tasks; they do not block publication of this source-only repository. Keep firmware binaries out of the release until they are resolved.

The Windows companion ZIP includes its required licenses and notices. Codex CLI is installed separately.
