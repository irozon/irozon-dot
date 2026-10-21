"""Post-flash HTTP checks. Defaults to authentication/state reads only.

--exercise temporarily changes power and modes, then restores the initial state.
Never prints the dedicated control token or reads companion/Codex credentials.
"""
import argparse
import json
import ipaddress
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward credentials to a different endpoint.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Device private LAN IPv4 address (no credentials)')
    parser.add_argument('--exercise', action='store_true')
    args = parser.parse_args()
    ip = ipaddress.IPv4Address(args.host)
    if not any(ip in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        parser.error('Use a private LAN IPv4 address')
    token = os.environ.get('IROZON_CONTROL_TOKEN', '')
    if not token:
        header = (ROOT/'include/control_config.h').read_text(encoding='utf-8')
        token = re.search(r'#define IROZON_CONTROL_TOKEN "([0-9a-f]{64})"', header)[1]
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(path, method='GET', auth=True, credential=token):
        headers = {'Authorization': 'Bearer '+credential} if auth else {}
        req = Request(f'http://{ip}:8080'+path, headers=headers, method=method)
        try:
            with opener.open(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def state():
        code, result = request('/api/state')
        assert code == 200, f'State HTTP {code}; verify source allowlist and firmware'
        assert isinstance(result['display_on'], bool)
        assert result['mode'] in ('green', 'blue', 'orange', 'classic')
        assert result['connection'] == 'connected'
        assert result['backlight_control'] is False and result['power_control'] == 'panel_sleep'
        expected = {'display_on', 'mode', 'mode_name', 'connection', 'usage_status',
                    'backlight_control', 'power_control'}
        assert expected <= set(result) <= expected | {'capabilities'}
        if 'capabilities' in result:
            assert result['capabilities'] == ['heading', 'usb_pairing']
        return result

    def command(path, key, value):
        assert request(path, 'POST')[0] == 202
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            if state()[key] == value:
                return
            time.sleep(.2)
        raise AssertionError('Accepted command did not become reported state')

    assert request('/api/state', auth=False)[0] == 401
    wrong_token = ('1' if token[0] == '0' else '0') + token[1:]
    assert request('/api/state', credential=wrong_token)[0] == 401
    initial = state()
    assert request('/api/display/on')[0] == 404  # GET must not mutate state.
    assert request('/api/display/mode/invalid', 'POST')[0] == 404
    after = state()
    assert (after['display_on'], after['mode']) == (initial['display_on'], initial['mode'])
    print('PASS: authentication, JSON contract, invalid command isolation; usage status:', initial['usage_status'])
    if args.exercise:
        try:
            command('/api/display/off', 'display_on', False)
            for mode in ('green', 'blue', 'orange', 'classic'):
                command('/api/display/mode/'+mode, 'mode', mode)
                assert state()['display_on'] is False
            command('/api/display/on', 'display_on', True)
            print('PASS: power commands, four modes and selection while screen is off')
        finally:
            command('/api/display/mode/'+initial['mode'], 'mode', initial['mode'])
            command('/api/display/'+('on' if initial['display_on'] else 'off'),
                    'display_on', initial['display_on'])


if __name__ == '__main__':
    main()
