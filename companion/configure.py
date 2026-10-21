"""Write private pairing files; does not start a server or touch the ESP32."""
import argparse
import ipaddress
import json
from pathlib import Path
import secrets

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pc', required=True, help='PC private LAN IPv4 address')
    parser.add_argument('--esp32', required=True, help='ESP32 private LAN IPv4 address')
    args = parser.parse_args()
    for value in (args.pc, args.esp32):
        ip = ipaddress.IPv4Address(value)
        if not ip.is_private or ip.is_unspecified or ip.is_multicast or ip.is_loopback:
            raise SystemExit('Use private LAN IPv4 addresses')
    root = Path(__file__).resolve().parents[1]
    local = root / 'companion/local.json'
    header = root / 'include/companion_config.h'
    if local.exists() or header.exists():
        raise SystemExit('Pairing files already exist. Keep them, or explicitly remove both to re-pair.')
    key = secrets.token_hex(32)
    local.write_text(json.dumps({'bind': args.pc, 'esp32_ip': args.esp32,
                                'port': 8787, 'pairing_key': key}, indent=2) + '\n')
    header.write_text('#pragma once\n'
                      f'#define IROZON_COMPANION_HOST "{args.pc}"\n'
                      f'#define IROZON_PAIRING_KEY "{key}"\n')
    print('Created companion/local.json and include/companion_config.h (ignored private files).')
    print('No listener started. Rebuild firmware after pairing; flashing remains a separate step.')
