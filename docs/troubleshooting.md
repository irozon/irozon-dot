# Troubleshooting

| Symptom | Checks |
| --- | --- |
| No device discovered | Enter the router's device IPv4 manually. The current firmware does not advertise mDNS. Ensure PC and device share a reachable private LAN. |
| Connection test fails | Save the correct device IP and existing control token; verify port 8080 and any compiled source allowlist. Do not reset Wi-Fi merely because a request times out. |
| Usage is unavailable | Install Codex CLI, sign in with the same Windows user, and set its executable path if auto-detection fails. API-key-only sign-in or unsupported quota windows are unavailable. |
| STALE / OFFLINE | Check PC sleep, Wi-Fi, DHCP address changes, Codex sign-in and private-network firewall policy. The last reading remains visibly stale. |
| NO DATA / WIFI SETUP | No authenticated sample has arrived / the Wi-Fi captive portal is active. Join Irozon-Dot-Setup only for provisioning. |
| TEST DATA | The explicit demo environment is flashed. Build the live supermini environment for account usage. |
| OFF still glows | Expected with the seven-wire module. Panel sleep cannot switch its fixed LED supply. See the hardware guide. |
| Heading does not change | Test capabilities: old firmware lacks heading support. New firmware fetches every 30 seconds. Use at most 18 allowed ASCII characters. |
| USB pairing unavailable | Use compatible firmware, a data-capable cable, the correct COM port and the 60-second RESET/EN window. Close serial monitors. Do not use BOOT for normal pairing. |
| Companion will not start | Check bounded logs beside its config, localhost port 8788 and LAN port 8787 ownership. A second installation must not replace the first. |
| Duplicate/startup warning | Stop the old installation explicitly, import a copy of settings, and deliberately migrate its old task/shortcut. The new app refuses duplicate legacy startup. |
| DPAPI config fails on another account | Encryption belongs to the original Windows user. Import original plaintext keys privately or re-pair deliberately. |
| HA unavailable or lagging | Check HA configuration, bearer secret, source allowlist and device reachability. REST updates can take 10 seconds. Use one light-state follower. |
| BOOT hold does not wake the display | This failed on the previously flashed image. Updated source now samples GPIO9 on every main-loop poll to recover a missed interrupt edge; physical confirmation still requires flashing it. HTTP and Home Assistant wake work on the tested unit. |

Windows executable users need no Python. Codex CLI is still required and owns
account sign-in. The PC must stay awake. Windows may warn about the unsigned
executable; verify the supplied SHA-256 and source rather than bypassing warnings
automatically. No firewall or router changes are performed by the companion.

Logs rotate at 128 KiB with two backups. Never attach private JSON, generated
headers, HA secrets, paired firmware binaries or raw Codex authentication files
to an issue. Review even sanitized logs and screenshots before sharing.
