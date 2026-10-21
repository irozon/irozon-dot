# Build, flash and pair firmware

The firmware provides four display modes, adaptive or intentionally empty
headings, Green Dashboard face animation, BOOT controls, USB pairing and the
Home Assistant HTTP controls. The current source samples GPIO9 on every main
loop in addition to processing ISR timestamps. The regression covers button
standby then wake and missed-edge recovery. A previously flashed image failed
BOOT wake; physical confirmation of the source fix still requires flashing it.

Install PlatformIO Core and run from the repository root:

```powershell
pio run -e supermini -e demo
pio device list
# Flash only after choosing the actual board's port:
pio run -e supermini -t upload --upload-port COM7
```

`supermini` is live-only; `demo` uses simulated data labelled TEST DATA and does
not poll the companion. Do not distribute a locally configured binary: private
headers can be compiled into it. The source RC includes no firmware binary.
See [binary redistribution obligations](licenses.md).

PlatformIO handles binary offsets. `firmware.bin` is not a merged image for
offset 0x0. No filesystem upload is needed. If automatic entry fails, hold BOOT,
tap RESET/EN, release BOOT and check the port again. Do not use erase-flash when
preserving Wi-Fi/mode/power/link NVS, and keep the existing partition layout.

## New device setup

1. On first boot, join `Irozon-Dot-Setup` and open `http://192.168.4.1`.
   Enter a 2.4 GHz Wi-Fi network. This local setup AP is not password-protected;
   provision in a trusted physical environment. It closes after connection.
2. Find the device's LAN address in the router. Reserve PC and device addresses
   to avoid DHCP changes. No permanent LAN Wi-Fi configuration portal is enabled.
3. Start the Windows companion, save its PC/device addresses, choose the USB
   serial port, tap RESET/EN and pair within 60 seconds. Pairing confirms storage
   before application restart. Then use Test connection. mDNS discovery is best
   effort; this firmware does not advertise an mDNS service, so use manual IP.
4. Optionally choose a heading (18 safe ASCII characters) and display mode.
   The unconfigured default is `IROZON DOT`. Saving an empty or whitespace-only
   heading intentionally displays no heading. Other input is trimmed. The heading
   arrives on the next authenticated usage fetch and is then persisted on the device,
   including an intentionally empty value. Existing settings are not reset on update.

Fresh public source builds without private headers and waits for USB pairing;
it must not contain shared default credentials. Existing builds with private
headers retain them as a fallback until runtime enrollment is present. Existing
users should import their keys and avoid re-pairing unless needed. An optional
compiled HA source allowlist remains in force after USB enrollment.

## BOOT and persistence

The gesture table in the README is classified on debounced release, including
the two- and eight-second thresholds. Releasing a long hold performs only its
one action. A button held during application startup is ignored until released;
holding BOOT across reset still invokes the ROM bootloader. GPIO9 sampling
reconciles the pin with its interrupt events; ISR queue overflow discards the
pending gesture and waits for a stable release. HTTP waits may defer visible
response, but queued edge timestamps preserve duration classification.

Standby and mode use the unchanged `irozon-ui` namespace. New pairing uses its
own `irozon-link` namespace. Wi-Fi reset calls WiFiManager's Wi-Fi credential
reset, not a global NVS erase. It preserves display settings and link keys.
The eight-second gesture deliberately removes Wi-Fi credentials: test it only
with a way to provision again. No destructive reset was tested on the live unit.
