# Irozon Dot third-party notices

Irozon Dot contributions are covered by LICENSE. Third-party code retains its
original copyright and license terms; this file does not relicense it.
Keep this file and the complete component license files with redistribution.
Notices present in individual dependency/source files must also be preserved.

## Hardware adapter and configuration

Irozon Dot acknowledges MatixYo's ESP32 Plane Radar for the GC9A01 display
adapter and hardware/partition configuration used as its baseline. The adapter
is retained unchanged; Irozon Dot's application behavior is developed separately.

Source: https://github.com/MatixYo/ESP32-Plane-Radar
Pinned commit: `139a3ac7d173d0f1a03ac66d121e2dc8aba35718`.

The complete required notice follows, reproduced without changing its text:

```text
MIT License

Copyright (c) 2026 MatixYo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Firmware dependencies

Complete copyright, permission and disclaimer notices are retained verbatim in
the linked files. These files accompany both source and Windows release packages;
the Windows executable does not contain the firmware libraries.

| Component | Complete notices |
| --- | --- |
| LovyanGFX 1.2.7, including its Adafruit and TFT_eSPI-derived components | [License and copyright notices](licenses/firmware/LovyanGFX-1.2.7.txt) |
| WiFiManager 2.0.17 | [MIT license and copyright](licenses/firmware/WiFiManager-2.0.17.txt) |
| ArduinoJson 7.4.2 | [MIT license and copyright](licenses/firmware/ArduinoJson-7.4.2.txt) |
| Arduino-ESP32 2.0.14 | [LGPL text](licenses/firmware/Arduino-ESP32-2.0.14-LGPL.md) |
| ESP-IDF 4.4.6 | [Apache license text](licenses/firmware/ESP-IDF-4.4.6-Apache.txt) |

The framework, linked ESP-IDF components and converted FreeSans fonts require
additional corresponding-source/relinking and provenance review before firmware
binary redistribution. This inventory is not a claim that those gates are
resolved. See [redistribution limits](docs/licenses.md). Source releases fetch
pinned dependencies rather than vendoring their source or fonts.

## Windows executable components

| Component | Complete notices |
| --- | --- |
| CPython 3.14.6, incorporated components, libffi and Microsoft runtime terms | [Combined Python license](licenses/companion/Python-3.14.6-LICENSE.txt) |
| pySerial 3.5 | [BSD license and copyright](licenses/companion/pyserial-3.5-LICENSE.txt) |
| PyInstaller 6.22.3 loader/bootloader, distribution exception and Apache runtime-hook terms | [COPYING](licenses/companion/PyInstaller-6.22.3-COPYING.txt) |
| OpenSSL used by CPython TLS | [License and notices](licenses/companion/OpenSSL-LICENSE.txt) |

This product includes software developed by the OpenSSL Project for use in the
OpenSSL Toolkit (https://www.openssl.org/).

Codex CLI is an external prerequisite; neither it nor account credentials are
bundled. Development-only dependencies are not installed as user prerequisites.
