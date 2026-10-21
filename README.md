# Irozon Dot

Irozon Dot shows your Codex five-hour and weekly usage on a small round screen. A Windows app reads usage from the signed-in Codex CLI and sends it to the ESP32. It does not read or bundle your Codex credentials.

## Pictures

| Green Dashboard | Blue Minimal |
| --- | --- |
| ![Green Dashboard](docs/mode-green.png) | ![Blue Minimal](docs/mode-blue.png) |

| Orange Numbers | Classic Rings |
| --- | --- |
| ![Orange Numbers](docs/mode-orange.png) | ![Classic Rings](docs/mode-classic.png) |

## What you need

| Part | Notes | Example |
| --- | --- | --- |
| ESP32-C3 Super Mini | 4 MB flash | [Buy](https://www.aliexpress.us/item/3256807018729495.html) |
| Round LCD | 1.28-inch GC9A01, 240×240 | [Buy](https://pl.aliexpress.com/item/1005004482028005.html) |
| Jumper wires | Seven | — |
| USB cable | Must carry data | — |

## Connect the seven wires

Unplug USB first. Follow the labels on your display.

| Display | ESP32-C3 |
| --- | --- |
| VCC | 3V3 |
| GND | GND |
| RST | GPIO0 |
| CS | GPIO1 |
| DC | GPIO10 |
| SDA / MOSI | GPIO3 |
| SCL / SCLK | GPIO4 |

SDA and SCL carry SPI data here. They are not I²C. Leave other display pins unconnected. Do not connect unknown pins to 5 V.

## Download and print the enclosure

Get the STL files and assembly reference from [MakerWorld](https://makerworld.com/en/models/2872376-esp32-plane-radar-live-ads-b-on-a-round-display?from=recommend#profileId-3207083). Print the parts using the model's instructions. Fit the display in the front opening. Secure the board inside. Route wires so they are not pinched when you close the case. The STL files are not included here.

## Flash the ESP32

Install [PlatformIO Core](https://docs.platformio.org/en/latest/core/installation/index.html). Open PowerShell in this folder.

```powershell
pio run -e supermini
pio device list
pio run -e supermini -t upload --upload-port COM7
```

Replace `COM7` with your board's port. Do not erase flash; that removes saved Wi-Fi and display settings. On first boot, join `Irozon-Dot-Setup` and open `http://192.168.4.1`. Enter your 2.4 GHz Wi-Fi details. Keep setup to a trusted place; the temporary setup network has no password.

## Download and run the Windows app

Follow the [Windows setup steps](docs/windows-installation.md). The app is a ZIP with `IrozonDot.exe`; Python is not needed. Install Codex CLI separately and sign in. The app opens its settings in your browser.

## Optional Home Assistant

Follow [Home Assistant setup](docs/home-assistant.md) to add a display switch and mode selector. It can also follow one light or light group. This is optional.

## Known limitations and credits

- OFF blanks and sleeps the LCD controller. The seven-wire display has no backlight control, so its LEDs stay lit. No safe backlight modification is known for this display board.
- BOOT tap cycles modes. Hold about 2 seconds to toggle display power. Hold about 8 seconds to clear Wi-Fi settings. To enter the bootloader, hold BOOT while tapping RESET/EN. Hardware tests confirmed BOOT standby and wake, Home Assistant power and mode controls, and all four layouts.
- The tested setup is ESP32-C3 Super Mini, 4 MB flash, GC9A01 display and Windows 11 x64. Other boards and systems are untested.
- The original display adapter and hardware configuration are credited in [third-party notices](THIRD_PARTY_NOTICES.md). Keep those notices with copies. Firmware binary redistribution still has open license requirements; see [license notes](docs/licenses.md).

If setup fails, see [Troubleshooting](docs/troubleshooting.md).
