# License inventory and redistribution gates

Original Irozon Dot source is MIT, copyright 2026 Irozon Dot contributors.
This does not relicense dependencies. Preserve LICENSE, THIRD_PARTY_NOTICES.md and supplied
license texts in source distributions; preserve the companion notices/licenses
with Windows binary distributions. Codex CLI is external, not bundled.

## Firmware

| Component | Pinned version / origin | Terms and action |
| --- | --- | --- |
| Display adapter and hardware configuration | Pinned provenance in [third-party notices](../THIRD_PARTY_NOTICES.md) | MIT; complete copyright/license retained there |
| LovyanGFX | 1.2.7 | MIT/BSD family; full upstream license.txt retained, including Adafruit and TFT_eSPI notices |
| WiFiManager | 2.0.17 | MIT; license retained |
| ArduinoJson | 7.4.2 | MIT; license retained |
| Arduino-ESP32 framework | PlatformIO package 3.20014.231204 / core 2.0.14 | LGPL-2.1-or-later; provide corresponding library source and a compliant relinking path when distributing a linked binary |
| ESP-IDF underlying framework | 4.4.6 | Apache-2.0 plus component-specific licenses, ROM/proprietary radio libraries and toolchain runtime terms; inventory the actual linked components before binary redistribution |
| FreeSans GFX bitmap fonts used through LovyanGFX | FreeSansBold 9/12/18/24 point | GNU FreeFont provenance requires review; do not assume the library-level BSD notice replaces font terms |

Component provenance and required acknowledgment are recorded in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Library notices were copied
from the exact installed pins, not inferred from badges.

GNU FreeFont publishes GPL-3.0-or-later with an embedding exception for documents.
Its FAQ explicitly distinguishes documents from software incorporating font elements:
distribution of the latter requires GPL-compatible licensing of the combined work.
Our converted bitmap fonts are compiled into firmware; the document exception does
not clear this use. LovyanGFX's permissive library license does not establish a
separate permission from the font authors. A verified font permission or a compliant
combined-work licensing plan, plus complete framework corresponding-source/relinking
materials and an actual-linked SDK component inventory, remain an **open gate for
firmware binary redistribution**. Project MIT notices alone do not resolve it. Do not ship
locally built firmware.bin, ELF, bootloader images or merged flash bundles as
part of this RC. Source-only release does not vendor those font/framework files;
developers fetch the pinned dependencies separately. No fonts were changed to
work around licensing in working firmware.

Sources:
[LovyanGFX 1.2.7](https://github.com/lovyan03/LovyanGFX/tree/1.2.7),
[Arduino LGPL text](https://github.com/espressif/arduino-esp32/blob/2.0.14/LICENSE.md),
[ESP-IDF 4.4.6](https://github.com/espressif/esp-idf/tree/v4.4.6),
[GNU FreeFont license and exception](https://www.gnu.org/software/freefont/license.html),
[GNU FreeFont FAQ on incorporation into software](https://www.gnu.org/software/freefont/FAQ.html).

## Windows executable

The explicit payload contains CPython 3.14.6, pySerial 3.5, required Python
standard-library/native runtime modules, OpenSSL, libffi and Microsoft VC runtime
DLLs. CPython's combined license includes notices for incorporated components;
the remaining upstream texts are under licenses/companion. PyInstaller 6.22.3
bootloader/loader terms include its distribution exception; Apache runtime-hook
terms are included in its COPYING file. The project does not become GPL merely
because it was frozen with the unmodified PyInstaller bootloader.

Build tools are pinned in companion/requirements-build.txt and are not installed
as user prerequisites. The generated BUILD-MANIFEST.json lists actual bundled
DLL/PYD names. No Codex executable, account data or device configuration is bundled.
The executable is unsigned. Review unsigned downloads under your normal policy;
the supplied SHA-256 detects accidental changes but is not a publisher signature.

## Development tools

Pillow, PyYAML and Jinja2 are optional test/preview dependencies, installed by the
developer and not bundled into the companion. Generated PNG examples show rendered
glyphs, not redistributable font source. Personal emails in unmodified upstream
license texts are attribution contacts, not project account credentials; retain
them rather than redacting the license.
