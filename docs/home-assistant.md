# Home Assistant setup

Use [irozon-dot.example.yaml](../home-assistant/irozon-dot.example.yaml), which
contains the REST sensor/commands, confirmed-state display switch, four-mode
selector and one optional light follower. It uses only built-in HA functionality.
The separate ignored irozon-dot.yaml is an installed-site configuration and
is not distributed. No working HA server configuration was changed for this RC.

1. Pair the device and verify its HTTP connection in Windows settings. Replace
   the example device address 192.168.1.20 in the public YAML with yours.
2. Download the private HA secret through Windows settings. Merge its entry
   into HA's secrets.yaml; do not put the token directly in the package or Git.
   Existing source users can generate/preserve a dedicated token with
   `python scripts/configure_control.py`; never regenerate a working credential
   merely to install the package. A changed compiled token requires a flash.
3. Put your edited copy in HA's packages/irozon_dot.yaml and enable packages
   under the existing homeassistant mapping:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

   Merge with an existing mapping; do not add another duplicate key. Inspect
   existing package/entity/automation IDs before installation.
4. For light following, replace every light.example_room with the actual light
   entity or group your existing script/scene controls. Otherwise remove the
   example's automation section. Preserve existing light actions/scripts.
5. Run HA's configuration check and restart only if it passes. YAML/Jinja tests
   in this repository do not replace HA's own configuration validation.
6. Add switch.irozon_dot_display, select.irozon_dot_mode and
   sensor.irozon_dot_control to a dashboard. Entity names may differ if HA has
   an existing entity with the same name; adjust references accordingly.

The follower watches **actual light state**, so dashboard changes and physical
buttons both work. It also synchronizes on HA startup and device sensor recovery.
It changes only display power, never light power. Direct display overrides last
until the next light transition/startup/recovery. Do not add a second button-event
automation for the same purpose.

The REST sensor polls every 10 seconds; switches/selects reflect confirmed
device attributes, not optimistic state. Standby keeps networking active.
Unavailable devices make controls unavailable. Custom heading is a companion
setting, not an extra HA integration. OFF is panel sleep, **not backlight shutdown**.

## HTTP reference

All endpoints require Authorization: Bearer followed by the private device token:

| Method | Path | Behavior |
| --- | --- | --- |
| GET | /api/state | Confirmed power, mode, connectivity, usage and power capabilities |
| POST | /api/display/on | Queue ON |
| POST | /api/display/off | Queue OFF |
| POST | /api/display/mode/green | Queue Green; also blue, orange, classic |

Accepted commands return 202. Poll state to confirm application. Invalid commands
must not alter settings. The optional compiled source allowlist must permit HA's
actual IP; USB pairing does not change that allowlist. Do not expose port 8080
outside a trusted LAN: bearer HTTP is not encrypted.

For an explicitly authorized device test:

```powershell
python scripts/check_control.py --host 192.168.1.20
# This changes modes/power temporarily and restores the initial state:
python scripts/check_control.py --host 192.168.1.20 --exercise
```

The script reads a private local header or IROZON_CONTROL_TOKEN environment
variable; do not pass secrets on the command line. It rejects redirects and
does not print the credential. No live mutation tests were run during RC cleanup.
