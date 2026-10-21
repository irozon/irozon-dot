# Security

Use only on a trusted private LAN. The usage feed has integrity/replay protection,
not encryption; ESP32 bearer HTTP control credentials can be observed on that LAN.
Do not expose device/companion ports to the internet. Local settings assume a
trusted Windows computer. Provision the open Wi-Fi setup AP in a trusted physical
environment. ESP32 link keys are not protected against physical extraction.

Keep local JSON, generated private headers, HA secrets, paired firmware binaries,
logs and Git metadata backups out of releases and issue attachments. Use only
generic addresses in examples. See docs/architecture.md for the boundaries and
docs/release-audit.md for current findings.

For a security issue, arrange a private channel with the maintainer before sharing
sensitive details. Do not post live tokens or credentials in a public issue.
If an actual credential is exposed, revoke/rotate it deliberately and update its
consumers; deleting the visible file alone does not revoke a credential.

Release preparation is local only. Run scripts/release_audit.py before creating
a distributable source archive; re-audit all reachable history before a later push.
