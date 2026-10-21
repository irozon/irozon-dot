# Home Assistant (optional)

Use the ready-made [package](../home-assistant/irozon-dot.example.yaml). It adds a display switch, a four-mode selector and an optional light follower.

1. Finish [Windows setup](windows-installation.md).
2. In the app's **Advanced settings**, click **Download private HA secret**. Keep the downloaded file private.
3. Copy its `irozon_dot_authorization` entry into Home Assistant's `secrets.yaml`.
4. Copy the example package to `config/packages/irozon_dot.yaml`.
5. In the package, replace `192.168.1.20` with Dot's router IP.
6. To follow a light, replace every `light.example_room` with your light or group.
7. If you do not want a light follower, remove the package's `automation:` section.
8. If packages are not enabled yet, add this under your existing `homeassistant:` section:

   ```yaml
   packages: !include_dir_named packages
   ```

9. Check the Home Assistant configuration.
10. Restart Home Assistant if the check passes.

The follower tracks actual light state, including dashboard changes. It also syncs at Home Assistant startup and when Dot reconnects. Keep one follower for the light. The display switch and mode selector report confirmed device state. OFF sleeps the screen but does not turn off its backlight.

Do not publish the downloaded secret or expose device port 8080 to the internet. The HTTP connection is not encrypted; use a trusted private network.
