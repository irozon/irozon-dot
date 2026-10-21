# Build, flash and pair firmware

The release candidate source includes final BOOT gestures, USB pairing and a
custom heading. The owner reports current firmware installed and the API advertises heading/USB
capabilities. No flash was performed during the Windows repair. Its Home Assistant
setup remains in place; see windows-integration-results.md for physical acceptance.

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
   Heading appears on the next authenticated usage fetch. Blank retains IROZON DOT.

Fresh public source builds without private headers and waits for USB pairing;
it must not contain shared default credentials. Existing builds with private
headers retain them as a fallback until runtime enrollment is present. Existing
users should import their keys and avoid re-pairing unless needed. An optional
compiled HA source allowlist remains in force after USB enrollment.

## BOOT and persistence

The gesture table in the README is classified on debounced release, including
the two- and eight-second thresholds. Releasing a long hold performs only its
one action. A button held during application startup is ignored until released;
holding BOOT across reset still invokes the ROM bootloader. Lost ISR edges
discard a pending gesture and require a stable release. HTTP waits may defer
visible response, but queued edge timestamps preserve duration classification.

Standby and mode use the unchanged `irozon-ui` namespace. New pairing uses its
own `irozon-link` namespace. Wi-Fi reset calls WiFiManager's Wi-Fi credential
reset, not a global NVS erase. It preserves display settings and link keys.
The eight-second gesture deliberately removes Wi-Fi credentials: test it only
with a way to provision again. No destructive reset was tested on the live unit.

## Acceptance after an approved flash

Verify all four modes, heading lengths 0 and 18, USB success/timeout/retry,
reboot persistence and loss of PC connectivity. Check releases around 1.9,
2.1 and 7.9 seconds: no long release may cycle mode or reset Wi-Fi prematurely.
Check button standby → HA state and HA standby → panel state; confirm usage
updates never wake standby. HA's state polling can take 10 seconds.
Test an 8.1-second Wi-Fi reset only with explicit approval and reprovisioning ready.
