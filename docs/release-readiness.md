# Local release-readiness review

Reviewed 2026-10-21 for **1.0.0-rc.2**. This is a private source/Windows release
candidate, **not stable v1.0 acceptance**. Nothing was flashed or published.

| Area | Result | Evidence and remaining limit |
| --- | --- | --- |
| GitHub | PASS | Authenticated read confirms `irozon/irozon-dot` is private and remote `main` is exactly `8fa385aac297f349e966f7f25969b3a1d0d183f5`. Subsequent readiness fixes are local only. |
| Git integrity | PASS | Current metadata/history is intact; old checkout metadata is retained. No history rewrite or force-push. |
| Firmware source | PASS | Green blink/mouth sequence (10-second interval, one-second duration, 7-pixel mouth change), adaptive/empty headings, all four modes, BOOT gestures and shared HA/button power state are included. |
| Firmware builds | PASS | Both `supermini` and `demo` build. Timing/cancellation/rollover assertions and layout tests pass. |
| Installed firmware | UNVERIFIED | Authenticated HTTP reads report live usage and heading/USB capabilities. No build identifier proves the latest animation, heading persistence or BOOT source is installed. Approved flash and physical acceptance remain necessary. |
| Running Windows installation | PARTIAL | Existing keys match, authenticated ESP32 reads succeed and live usage continues. The enabled startup task launches the executable with the existing settings owner. The installed executable predates the empty-heading UI fix. |
| Rebuilt Windows candidate | PASS | Empty-heading fix is present in the embedded UI. Actual frozen first run, empty-heading save/restart/reload, DPAPI, duplicate exclusion and lifecycle checks pass in isolation. The running installation was not replaced; candidate takeover with real usage remains a deployment acceptance check. |
| Installer/package | PASS | Complete Windows bundle includes the optional installer, license notices and guides. Temporary-directory installation retains notices, creates controls and refuses existing installations; no production startup or shortcut is changed. |
| Security | PASS with local-only caveat | Reviewed source, reachable Git history, exported archives and unpacked executable contain no detected private credentials/configuration. Unreachable local development objects include machine paths/private IPs; preserve locally, never export `.git`, use mirror pushes or archive the entire worktree. |
| Firmware binary licensing | BLOCKED | Embedded FreeSans licensing and the framework corresponding-source/relinking/linked-component obligations are unresolved. Source/Windows archives exclude firmware images; see [license gates](licenses.md). |
| Clean Windows acceptance | PARTIAL | Frozen executable works without external Python on PATH, first-run settings are available without Codex, and installation documentation requires extracting the complete bundle. Actual fresh Windows installation, authenticated new Codex sign-in, first USB enrollment and real Windows sign-in/startup remain manual acceptance checks. |
| Home Assistant | PRESERVED | Shared-state source contracts and the public example pass automated checks; installed HA files/secret are unchanged. Earlier dashboard/physical-button acceptance is recorded separately. No new live light toggles were performed in this review. |

Automated validation: **32 companion tests + 19 repository tests**, actual settings
JavaScript execution, all-mode bitmap/layout checks, both firmware builds,
PyInstaller rebuild/payload audit, frozen lifecycle/empty-heading checks and
source/history/export validation. See [reproduction commands](validation.md).

A final live check observed one transient Codex-unavailable/stale interval in the
installed companion. An independent authenticated app-server read succeeded;
the running companion then recovered to Codex connected/live on its normal polling
without a restart or configuration change. The cause was not established; this
review does not claim an extended runtime stability test.

The Windows candidate is unsigned and needs an external authenticated Codex CLI;
it does not bundle account credentials. Keep all supplied licenses and notices
with the executable. Exact size/hash/dependencies are in its `BUILD-MANIFEST.json`.

Stable release blockers are firmware license clearance (before binary distribution),
approved installation of the newer companion, approved firmware update with physical
acceptance, and fresh-user Windows/Codex/USB/startup acceptance. The verified wiring
still supports panel sleep only; it cannot switch the backlight off. No firmware,
Wi-Fi, Home Assistant, pairing or running-companion configuration was changed.
