# Irozon Dot release audit

## Security and release contents

Release validation scans source candidates and recoverable Git objects for known
device keys, credential patterns, private addresses and personal machine paths.
Audit output contains categories, filenames and counts, never secret values.
This is a bounded scan, not a guarantee that every possible secret is absent.

Local private headers, companion settings, Home Assistant configuration and
secrets, logs and build caches are excluded from release archives. Installed
private configuration is preserved. Git metadata and recoverable editor snapshots
are retained locally and excluded from distribution; do not mirror-push tool
snapshot refs or upload a checkout including hidden metadata.

The source archive contains reviewed source, portable examples, documentation and
required licenses. The Windows archive contains the audited executable, manifest,
checksums, documentation and notices. It excludes Codex credentials, personal
configuration and firmware binaries. Screenshots contain synthetic device data
or a settings view without account credentials or personal machine paths.

## Licensing

Irozon Dot contributions are MIT licensed. Required third-party acknowledgment,
provenance and the complete hardware-source copyright/license notice are in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Unmodified dependency notices
remain in licenses/. The [license inventory](licenses.md) records nested library
terms and the unresolved firmware font/framework redistribution requirements.

Both release packages include the central notices and complete component license
files. Legacy source-inspection notes are not part of the product documentation.
No attribution is removed from third-party source or dependency license files.

## Distribution checks

Keep private headers, settings, HA secrets, Codex credentials, logs, Git metadata
and locally configured firmware out of archives. Review the current firmware
binary redistribution requirements in [the license inventory](licenses.md).
The Windows executable is unsigned. Network limitations are described in
[SECURITY.md](../SECURITY.md).
