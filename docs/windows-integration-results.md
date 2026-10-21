# Windows connection repair and local acceptance

Prepared on 2026-10-21 for 1.0.0-rc.2. The device owner reports current firmware
installed; its HTTP API advertises heading and USB-pairing capabilities. No
firmware flashing, Wi-Fi reset, credential rotation or HA automation change was
performed during this repair.

## What failed

The source companion and executable used different configuration locations.
The source installation held the working usage key and a separate private
header held the working HTTP control token. The executable's AppData keys did
not match either working credential. Actual authenticated device reads confirmed
that the existing token succeeded and the executable's original token failed.
The Python companion also owned both the LAN usage port and localhost settings
port: seeing its page did not prove the executable was connected.

The source settings runtime did not enrich old JSON with its existing control
header. Its usage feed worked while its settings page lacked HTTP credentials.
Failed USB enrollment could additionally activate newly generated keys before
device acknowledgment, making saved/configured state misleading. This is now
staged encrypted recovery data, not active pairing, until enrollment succeeds.

The old generic Invalid settings response also masked ipaddress.AddressValueError
because it is a ValueError subclass rather than an exact ValueError. Pasted
whitespace is now normalized and invalid addresses return a specific safe error.
The exact historical form input was not logged, so it cannot be reconstructed.
The real browser was tested with invalid and whitespace-padded addresses; the
invalid submission was rejected without changing the saved configuration.

Task Scheduler's XML console bytes can declare UTF-16 while containing UTF-8.
Parsing the raw bytes incorrectly reported enabled startup as off. The parser
now handles both actual encodings; regression tests cover them.

## Repair and ownership

Private rollback copies were secured before changes. The executable received
a verified copy of the existing keys in DPAPI storage; originals were retained.
The old companion was stopped gracefully, and the actual rebuilt executable
then owned both listeners and served live usage. No USB enrollment was needed.
If another valid companion already owns localhost settings, launching a second
copy opens the existing owner's page instead of spawning a competing server.

The normal page shows authenticated connection, Codex synchronization, device
name, immediately applied mode, power and startup status. Technical configuration,
USB, existing-install import and diagnostics remain under Advanced settings.
Device state is polled independently of Codex's one-minute refresh budget.
Physical/button/HA state can update the mode and power controls through that poll.

## Evidence and limits

| Check | Result |
| --- | --- |
| Existing device credential | Actual authenticated reads succeed; rejected credential is distinguished from unreachable device |
| Codex CLI | Authenticated app-server usage read succeeded with live 300-minute/10,080-minute windows and reset timestamps |
| Usage arithmetic | Normalization/freshness tests cover remaining percentages, nullable windows, expiry and malformed values |
| Actual ESP32 power and modes | ON/OFF and all four modes confirmed through HTTP; mode changes while OFF preserve standby; original state restored |
| Browser connection/name | Live page shows Connected; Test connection and Save name succeeded through actual UI |
| Browser power/mode | Standby and Blue mode were confirmed by actual device state; selection while OFF retained standby |
| Browser validation | Invalid address yields actionable error; pasted whitespace is accepted and normalized |
| PC feed outage/recovery | Actual ESP32 usage became stale, then live after companion restart; power/mode were preserved |
| Browser restart recovery | Disconnected appeared during the outage; the page reconnected automatically without a reload |
| Frozen executable lifecycle | First run, private persistence, duplicate exclusion, Stop/Restart/Exit and existing-config preservation passed |
| USB enrollment | Existing keys reused; no physical enrollment or rotation attempted; failed-handshake recovery tested in isolation |
| Home Assistant | Existing token/API remain compatible and installed YAML/secret are preserved; server dashboard/automation acceptance is separate |
| Physical BOOT and heading appearance | User-assisted acceptance requested; do not infer physical appearance from an HTTP acknowledgment |
| Windows startup | User-approved migration completed: existing task launches the verified executable with AppData configuration; every non-action XML setting preserved; launch through Task Scheduler restored live ESP32 usage; duplicate launch retained one owner; real sign-out/sign-in is not automated |
| Backlight | Remains panel sleep only; fixed backlight wiring limitation is unchanged |

See validation.md for builds/tests and licenses.md for firmware binary
redistribution gates. This report separates device/network observations from
simulated serial and source-contract checks. Neither those tests nor an HTML
save acknowledgment proves physical heading rendering or button timing.
