#pragma once
// Generate include/control_config.h with scripts/configure_control.py.
// Independent of Codex authentication and the companion pairing key.
#define IROZON_CONTROL_TOKEN "REPLACE_WITH_RANDOM_64_LOWERCASE_HEX_DIGITS"
// Optional single Home Assistant IPv4 address; empty = authenticated STA subnet.
#define IROZON_CONTROL_ALLOWED_IP ""
