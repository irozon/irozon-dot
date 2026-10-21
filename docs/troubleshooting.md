# Troubleshooting

- **Dot is not found:** Enter its IP from your router in the Windows app's **Advanced settings**. This firmware does not advertise itself for discovery.
- **No live usage:** Keep the PC awake. Check that Codex CLI is signed in as the same Windows user. Run `codex login status`.
- **Pairing fails:** Use a data USB cable. Tap RESET/EN, then pair within 60 seconds. Do not use BOOT for pairing.
- **The screen still glows in standby:** Expected. The current display wiring cannot turn off its backlight.
- **Home Assistant is unavailable:** Check the secret and device address. Do not re-pair or replace a working token just to test the connection.

For private or security issues, see [SECURITY.md](../SECURITY.md). Do not share local settings, keys, HA secrets or logs with credentials.
