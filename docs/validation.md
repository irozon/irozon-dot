# Verification and experimental status

This is **1.0.0-rc.2**, repaired and tested locally, not a public v1.0 acceptance claim.
See [actual Windows/device results](windows-integration-results.md).
The [current readiness review](release-readiness.md) distinguishes the running
installation from the newer candidate and records the remaining release blockers.

| Area | Evidence / limit |
| --- | --- |
| Existing live usage | Previously verified on the development ESP32 and signed-in Windows installation |
| Existing HTTP and HA integration | Previously verified power/modes, dashboard light changes and physical light-button interactions; working server configuration is unchanged |
| Final BOOT firmware | Both firmware environments compile; production timing static_asserts cover debounce, thresholds, rollover, startup-held/overflow cases; source-contract tests cover shared persisted power and Wi-Fi-only reset |
| USB pairing and heading | Current device advertises support; existing keys were reused. Fresh USB enrollment and physical heading confirmation remain user-assisted acceptance checks |
| Standalone Windows companion | First run, DPAPI persistence, redaction, duplicate exclusion, Stop/Restart/Exit and existing-install preservation tested with the actual frozen executable |
| Settings UI | Existing installed executable passed real Chrome connection/name/address and outage checks; latest empty-heading reload/submit semantics also pass JavaScript and isolated HTTP/storage tests |
| Windows startup | Registration/removal and quoting tested in an isolated HKCU key; existing task migrated with user approval and all non-action XML settings preserved; actual task launch and duplicate exclusion passed; real sign-in has not been exercised |
| HA example | YAML/Jinja and follower structure validated locally; new generic example is not deployed to a server |
| Display layouts | Adaptive/empty headings and synchronized Green blink/mouth movement are prepared but unflashed; all four resting previews are unchanged, with fixed text checked through every animation frame; see [face validation](face-animation.md) and [heading validation](display-presentation.md); not an SPI/hardware emulator |
| Backlight | Existing illumination observed; wiring and pinned driver confirm no software LED shutdown path |
| Security | Release candidates and unpacked executable scanned; historical Git objects also scanned; this is not a penetration-test guarantee |

## Reproduce

Local release validation on 2026-10-21 passed **32 companion tests and 19 repository
checks**, plus the settings JavaScript check and complete bitmap preview checks.
Both current firmware environments build successfully:

| Environment | Static RAM | Application flash |
| --- | --- | --- |
| supermini | 43,300 bytes | 1,020,202 bytes |
| demo | 43,100 bytes | 982,036 bytes |

The known upstream Arduino `esp32-hal-uart.c` return-without-value warning
remains; no project build error occurred. The rebuilt Windows executable passed
its payload privacy/path audit and isolated lifecycle tests. Release source
passed sensitive-file and local-link validation. SHA-256 and exact executable
size are in BUILD-MANIFEST.json (about 9 MiB).

The four resting mode previews match fresh rendering byte-for-byte. The native
240 by 240 face GIF preserves text pixels throughout its ten-second loop and
returns to its exact original frame.
The source-only exported checkout also passes all 51 Python tests, the JavaScript
check and preview rendering; both firmware environments build without private
headers or local configuration. The latest frozen executable candidate passes
its isolated lifecycle/privacy checks without changing the running installation.
PyInstaller reports ignored macOS serial-framework imports during analysis;
the Windows port backend is included and its isolated protocol checks pass.

Install requirements-dev.txt in a development virtual environment, then run:

```powershell
python -m unittest discover -s companion -v
python -m unittest discover -s scripts -p 'test_*.py' -v
pio run -e supermini -e demo
python scripts/preview.py
node scripts/check_heading_ui.cjs
powershell -NoProfile -File companion/build-windows.ps1
python scripts/check_windows_executable.py
python scripts/release_audit.py --export
```

The clean source export must also build both firmware environments without any
private headers, and its tests must pass independently of local HA configuration.
Release checks validate local links, portable examples, secret exclusions and
the source archive. No test here resets live Wi-Fi, changes HA configuration,
flashes the ESP32 or replaces the running companion.

Before a stable public release: perform the physical acceptance in firmware.md,
complete an actual new-user Windows sign-in test and resolve the firmware binary
license gates in licenses.md. Firmware binaries are intentionally excluded from
the private source/Windows RC. A clean source archive is not a backup of .git.
