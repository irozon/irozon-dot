# Windows setup

1. Download the Windows ZIP from [GitHub Releases](https://github.com/irozon/irozon-dot/releases).
2. Extract the whole ZIP and run `IrozonDot.exe`. Python is not needed.
3. Install [Codex CLI](https://developers.openai.com/codex/cli) if needed. In PowerShell, run `codex login` and finish sign-in. Check with `codex login status`.
4. Connect the ESP32 to this PC with a data USB cable.
5. In Dot's settings, click **Set up USB pairing**. Select the serial port. Tap RESET/EN, then click **Pair attached device** within 60 seconds. Already paired? Click **Use existing setup** or import the existing `local.json` in **Advanced settings**. Do not pair again.
6. Connect Dot to Wi-Fi using the [first-boot steps](../README.md#flash-the-esp32). Click **Find device**. If it is not found, enter Dot's router IP under **Advanced settings** and click **Save connection details**. Click **Test connection**. Look for **Connected** and live usage.
7. To start Dot when you sign in, check **Start automatically when I sign in**.

The PC and Dot must be on the same private network. Keep the PC awake for live updates. For help, see [Troubleshooting](troubleshooting.md).
