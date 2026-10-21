"""Create dedicated local HTTP credentials without printing or reusing secrets."""
import argparse
import ipaddress
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parents[1]


def configure(root, ha_ip=None):
    header = root / 'include/control_config.h'
    secret_file = root / 'home-assistant/secrets.local.yaml'
    old = header.read_text(encoding='utf-8') if header.exists() else ''
    match = re.search(r'#define IROZON_CONTROL_TOKEN "([0-9a-f]{64})"', old)
    if old and not match:
        raise ValueError('Existing control header is invalid; inspect it locally before replacing')
    token = match[1] if match else secrets.token_hex(32)
    existing_ip = re.search(r'#define IROZON_CONTROL_ALLOWED_IP "([^"]*)"', old)
    allowed = existing_ip[1] if ha_ip is None and existing_ip else ha_ip or ''
    if allowed:
        ip = ipaddress.IPv4Address(allowed)
        if not any(ip in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
            raise ValueError('Use a private Home Assistant LAN IPv4 address')
        allowed = str(ip)
    expected_secret = f'irozon_dot_authorization: "Bearer {token}"\n'
    if secret_file.exists() and secret_file.read_text(encoding='utf-8') != expected_secret:
        raise ValueError('Existing HA secret differs; no files changed')
    header.parent.mkdir(parents=True, exist_ok=True)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    header.write_text('#pragma once\n// Private, dedicated display-control credential. Do not commit.\n'
                      f'#define IROZON_CONTROL_TOKEN "{token}"\n'
                      f'#define IROZON_CONTROL_ALLOWED_IP "{allowed}"\n', encoding='utf-8')
    secret_file.write_text(expected_secret, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ha-ip', help='Optional Home Assistant IPv4 source allowlist; preserved if omitted')
    args = parser.parse_args()
    try:
        configure(ROOT, args.ha_ip)
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    print('Local control header and HA secret prepared; token preserved on rerun and not printed.')
