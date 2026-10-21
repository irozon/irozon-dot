# Windows companion distribution

The Python implementation remains canonical. `IrozonDot.exe` is a standalone,
windowed Windows x64 application built with PyInstaller. Python and pySerial are
included; users do not install Python, edit scripts, or install a web framework.
The repaired executable has been exercised with the development device using its
existing credentials. No release has been published and no firmware was flashed
during this repair. See [integration results](windows-integration-results.md).

Executable size, SHA-256 and native dependencies are recorded in the accompanying
BUILD-MANIFEST.json. See [validation](validation.md) for acceptance coverage.

## New installation

1. Install and sign in to the external [Codex CLI](https://developers.openai.com/codex/cli).
   The companion uses its existing app-server integration. Neither Codex itself
   nor account credentials are included in the download.
2. Extract the complete Windows ZIP to a permanent, user-writable folder, keeping
   its notices, licenses and documentation beside `IrozonDot.exe`, then double-click
   the executable. No Python installation is needed. Alternatively, right-click
   the extracted `install-executable.ps1` and choose Run with PowerShell. It copies
   the release bundle to the user's Programs folder and creates Start, Settings,
   Stop and Restart desktop controls. From a source checkout the script is at
   `companion/install-executable.ps1` and uses the versioned build output.
   That optional installer does not launch it or enable Windows startup.
3. The browser opens `http://127.0.0.1:8788/`. Normal use shows Connection,
   Device name, Display mode and Start with Windows. Technical controls live in
   Advanced settings. Connected means the device accepted its HTTP credential;
   saved keys alone do not count as a verified connection. Codex sync has its own
   live/stale status and five-hour/weekly remaining percentages.
4. First setup follows Find device → Pair securely → Test connection → Ready.
   Find device tries the configured address and `irozon-dot.local`, then selects
   this PC's routed address when possible. The current firmware does not advertise
   mDNS, so automatic discovery may fail: Advanced settings then accepts the
   device address from your router. It never scans the subnet or invents a device.
5. Existing users should reuse their working setup, not enroll new keys. Choose
   Use existing setup or the detected configuration in Advanced settings. Stop
   its old owner explicitly before importing. The dedicated HTTP credential is
   copied from its private control header when present. Original files stay intact.
6. For a new device only, use USB pairing under Advanced settings. The serial
   selector preselects a unique ESP32/USB device when available. Tap RESET/EN and
   pair within 60 seconds. This does not flash firmware or change Wi-Fi. A failed
   enrollment keeps new keys in DPAPI-protected pairing-pending.json, never as
   an active confirmed configuration. Successful enrollment activates them only
   after acknowledgment. If the final save fails, retain that recovery file and
   retry; do not erase or rotate credentials.
7. Set the device name and Save name. It allows at most 18 ASCII letters, digits,
   spaces, periods, underscores and hyphens. The initial default is `IROZON DOT`.
   Saving blank or whitespace-only input intentionally hides the heading; leading
   and trailing whitespace is trimmed. The saved value survives companion reload
   and, once received, device restart. The signed heading reaches the device on
   its next fetch, within about 30 seconds. Mode changes apply immediately and
   wait for reported confirmation. The standby button also uses confirmed state.
8. Start with Windows manages a per-user Run entry for new installs. A deliberately
   migrated existing Irozon Dot task can instead be enabled/disabled in place.
   An unmigrated Python task is reported separately and preserved; it must not
   silently become a second startup registration. Keep the executable at a stable
   path. Actual sign-out/sign-in is a separate acceptance test.

The private HA secret download is an explicit credential export for a new HA
installation. Keep the downloaded YAML private. Do not replace a working HA
token or re-pair a working device unnecessarily.

## Existing installations and configuration ownership

There is one settings owner and one HTTP server, with a loopback settings socket
and a separately bound LAN usage socket. The existing `monitor.py` delegates its
server lifecycle to this runtime; Source/Rpc polling and Codex normalization remain
the canonical implementation. `providers.py` selects the concrete Codex Source.
Other provider names are rejected; there is no nonfunctional Claude option.

Source execution defaults to `companion/local.json`. Frozen execution defaults
to `%LOCALAPPDATA%\Irozon Dot\local.json`; `--config` can select another path.
The same configuration path uses the existing Windows mutex/stop-event protocol.
Duplicate launches do not start another worker. A different installation cannot
silently take over a settings or LAN port.

Migration is deliberate and preserves a rollback copy before stopping the old companion.
Stop it with its existing control, run the new executable, and import a **copy**
of its private `companion/local.json`. Explicit repository imports can also copy
the existing dedicated device control token from `include/control_config.h`.
Original files are unchanged. Imports refuse a configuration owned by a running
process. Reuse existing keys to preserve firmware and HA compatibility; no USB
pairing is needed. Remove the old startup registration deliberately before
enabling the new one. The startup setting detects existing Irozon Dot
scheduled tasks/Startup shortcuts and refuses duplicate registration. Existing
tasks are changed only with explicit approval; their trigger/settings are preserved.

Legacy plaintext JSON loads without being rewritten. Saving through the new
settings owner encrypts secrets using Windows DPAPI for the current user and
restricts the new file ACL to that user and SYSTEM. Copying encrypted settings
to another Windows account is not a supported migration method.

## Lifecycle, errors and logs

Closing the browser keeps monitoring active. Settings reopens the page; Stop or
Exit shuts down the companion and its owned Codex child. Restart reloads the
saved configuration. The executable also accepts `start`, `settings`, `stop`,
`restart`, `status`, `--config`, `--settings-port` and `--no-browser`.
The windowed executable's status command has no console output; use Settings.

First run serves settings without a LAN listener or Codex child until configured.
Connection and provider failures remain visible in the page. Startup failures
produce a short Windows message unless `--no-browser` is set. Logs are in
`logs/companion.log` beside the selected JSON, rotated at 128 KiB with two backups.
Logs omit keys, credentials, upstream error bodies and serial pairing messages.
The UI's five-second status refresh does not increase upstream polling: existing
Codex refreshes remain limited to one per minute.

## Security and dependencies

The settings listener binds only to 127.0.0.1. Host and Origin checks, a session
cookie, CSRF tokens, strict resource policy, bounded request sizes and no CORS
protect settings actions from unrelated websites. A top-level browser navigation
to the root is allowed; cross-site API requests are rejected. This assumes a
trusted local Windows account/computer; it does not isolate hostile local
processes. Explicit private secret downloads must be handled as credentials.

LAN `/usage` retains the paired source-IP restriction, nonce and HMAC signature;
the settings UI is unavailable through that socket. Device HTTP controls retain
their existing bearer authentication. LAN transport is not encrypted: use a
trusted private network. No firewall rules, router settings or Wi-Fi settings
are changed automatically. USB pairing does not deliberately assert DTR/RTS or
invoke the bootloader. Existing credentials were reused in the repair; fresh
physical USB enrollment remains untested on this device.

The bundle contains CPython 3.14.6, pySerial 3.5 and necessary native runtime
libraries. PyInstaller 6.22.3 and transitive build dependencies are pinned in
`companion/requirements-build.txt`. Windows and an external signed-in Codex CLI
are runtime prerequisites; no other Python packages need installing. Tested on
Windows 11 x64; ARM/native x86 builds are not provided. This executable is not
code-signed, so Windows may show publisher/SmartScreen warnings.

Only explicitly listed web assets and Python imports enter the bundle. Personal
JSON, private headers, HA secrets, logs, Codex credentials and Codex executables
are excluded. The build audits unpacked Python/native payloads for private
filenames and known personal keys, and rejects unrelated runtime DLLs from the
developer PATH. `BUILD-MANIFEST.json` records size, SHA-256 and native dependency
names; `SHA256SUMS.txt`, LICENSE, third-party notices and license texts accompany
the executable. Keep all supplied notices with redistribution.

## Rebuilding and validation

Run `powershell -File companion/build-windows.ps1` from a Windows source checkout
with Python available. This builds in `.pio/companion-build`, sanitizes DLL search
paths and writes `dist/windows-<VERSION>/`; it does not install or launch the result.
For this candidate that is `dist/windows-1.0.0-rc.2/IrozonDot.exe`. A versioned
output preserves a separately running older executable in the old output location.

Run companion unittest discovery and scripts unittest discovery for storage,
HTTP security, signed usage, polling, Windows controls, USB protocol, HA and BOOT
checks. `scripts/check_windows_executable.py` exercises the actual frozen binary
with an isolated temporary config and no Python/Codex on PATH: first run,
duplicate prevention, encrypted persistence, Stop/Restart/Exit and existing
installation preservation. Startup tests use an isolated registry key, not the
real sign-in entry; an actual Windows sign-in has not been exercised.

Firmware builds cover both configured ESP32-C3 environments. New USB enrollment and physical acceptance require the checks in the integration
report. Device HTTP power/modes and live usage were tested with the executable;
these are separate from simulated serial tests. Home Assistant configuration and
credentials remain unchanged. The Windows companion was replaced with a backed-up,
verified build under explicit authorization.
