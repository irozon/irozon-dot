"""Explicit private-LAN device operations; no redirects, proxies, or subnet scans."""
import json
import socket
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from settings import private_ipv4, MODES


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def request(ip, token, path='/api/state', method='GET', data=None):
    ip = private_ipv4(ip)
    headers = {'Authorization': 'Bearer ' + token}
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode()
    req = Request(f'http://{ip}:8080{path}', headers=headers, method=method, data=data)
    with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=3) as response:
        body = response.read(4097)
        if len(body) > 4096:
            raise ValueError('Device response too large')
        return json.loads(body)


def test(config):
    if not config['control_token']:
        raise ValueError('Supply the device HTTP control token to verify its identity')
    result = request(config['esp32_ip'], config['control_token'])
    if (type(result.get('display_on')) is not bool or result.get('mode') not in MODES
            or result.get('power_control') != 'panel_sleep'):
        raise ValueError('Unexpected device response')
    return {k: result.get(k) for k in ('display_on', 'mode', 'mode_name', 'connection',
                                     'usage_status', 'power_control', 'backlight_control', 'capabilities')}


def error_message(error):
    if isinstance(error, HTTPError) and error.code == 401:
        return 'The device rejected the saved credential. Import the working setup; do not reset or re-pair it.'
    if isinstance(error, HTTPError) and error.code == 403:
        return 'The device does not allow this PC address. Check its existing source allowlist.'
    if isinstance(error, (OSError, TimeoutError)):
        return 'Device unreachable. Check its address and Wi-Fi; existing pairing has not been changed.'
    return 'The operation could not finish. Check Advanced settings and local logs; no credential values were logged.'


def discover(config):
    candidates = set()
    if config['esp32_ip']:
        candidates.add(config['esp32_ip'])
    try:
        candidates.add(private_ipv4(socket.gethostbyname('irozon-dot.local')))
    except (OSError, ValueError):
        pass
    return sorted(candidates)


def local_address(device_ip):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect((private_ipv4(device_ip), 9))  # Route lookup only; sends no datagram.
        return private_ipv4(route.getsockname()[0])
