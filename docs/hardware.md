# Hardware and supported devices

The verified target is an **ESP32-C3 Super Mini** with native USB, 4 MB flash and
a **1.28-inch 240×240 GC9A01 SPI display**. `esp32-c3-devkitm-1` is the PlatformIO
board definition used for this Super Mini; it is not a claim that every board
using that definition or every GC9A01 module has identical wiring.

Disconnect power before wiring. Use the display's printed pin labels:

| Display | ESP32-C3 Super Mini |
| --- | --- |
| VCC | 3V3 |
| GND | GND |
| RST | GPIO0 |
| CS | GPIO1 |
| DC | GPIO10 |
| SDA / MOSI | GPIO3 |
| SCL / SCLK | GPIO4 |

SDA/SCL here are SPI signals, not an I²C connection. There is no MISO wire.
BOOT uses onboard GPIO9, active LOW with input pull-up. The display driver uses
SPI2, 40 MHz, BGR/inversion enabled, rotation 0. The adapter and wiring are
defined in `include/hardware/lgfx_config.hpp` and `include/config.h`.
Do not connect unknown module power/control inputs to 5 V based on this guide.

Supported network: 2.4 GHz Wi-Fi and private IPv4 LAN. The Windows x64 companion
was tested on Windows 11. ESP32-S3, classic ESP32, CYD rectangular displays,
touch input, battery operation, OTA updates, Windows ARM, macOS/Linux packaging,
IPv6 and other AI providers are not verified or provided. The partition layout
has one application slot and no OTA slot.

## Backlight

The current seven-wire module's VCC is permanently connected to 3V3. There is
no BL/LED enable signal in the original wiring or `lgfx_config.hpp`, and no
LovyanGFX `ILight`/`Light_PWM` object. In pinned LovyanGFX 1.2.7,
`Panel_Device::setBrightness()` delegates only when a light object exists.
GC9A01 sleep sends SLPIN/SLPOUT; it does not disconnect the LED supply.
Therefore display OFF blacks the image and sleeps the controller while the
backlight can remain visibly illuminated. Firmware cannot provide true LED
shutdown with this verified wiring. RST and CS are not backlight enables.

A documented alternative is the Waveshare 1.28inch LCD Module, **SKU 19192**:
the [manufacturer specification](https://www.waveshare.com/product/1.28inch-lcd-module.htm)
and [pin table](https://docs.waveshare.net/1.28inch_LCD_Module/) expose a BL input.
This verifies that module's capability, not a drop-in replacement for the current
unidentified PCB. A future design must verify its exact revision, BL polarity
and voltage/current requirements, available MCU pins, enclosure fit and driver
light configuration before selecting any GPIO.

There is no verified retrofit for the existing module. Its PCB schematic, LED
pads/current path and any onboard transistor are unknown. An extra wire, trace
cut, transistor choice or GPIO assignment would be speculation. Whole-module
power switching is also unverified: SPI back-powering and reinitialization must
be resolved. No hardware changes were implemented.
