"""Canonical configuration; source installs keep local.json, frozen installs use AppData.

Codex credentials are never read here. Pairing/control keys use per-user Windows DPAPI.
"""
import base64
import ctypes
from ctypes import wintypes
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MODES = {'green': 'Stacked Numbers', 'classic': 'Classic Split Arc',
         'companion': 'Companion'}
HEADING_LIMIT = 18
SECRET_KEYS = ('pairing_key', 'control_token')
DEFAULTS = dict(bind='', esp32_ip='', port=8787, provider='codex', codex_path='',
                heading='IROZON DOT', mode='green', pairing_key='', control_token='')


def default_path():
    if getattr(sys, 'frozen', False):
        return Path(os.environ['LOCALAPPDATA']) / 'Irozon Dot' / 'local.json'
    return Path(__file__).with_name('local.json')


def private_ipv4(value):
    if not isinstance(value, str):
        raise ValueError('Enter a LAN IPv4 address, for example 192.168.1.20')
    try:
        ip = ipaddress.IPv4Address(value.strip())
    except ipaddress.AddressValueError:
        raise ValueError('Enter a LAN IPv4 address, for example 192.168.1.20') from None
    if not any(ip in net for net in (ipaddress.ip_network('10.0.0.0/8'),
               ipaddress.ip_network('172.16.0.0/12'), ipaddress.ip_network('192.168.0.0/16'))):
        raise ValueError('Use an RFC1918 LAN IPv4 address')
    return str(ip)


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('Unknown settings')
    result = {**DEFAULTS, **value}
    if result['provider'] != 'codex':
        raise ValueError('Only Codex is supported')
    for name in ('bind', 'esp32_ip'):
        if result[name]:
            result[name] = private_ipv4(result[name])
    if type(result['port']) is not int or result['port'] != 8787:
        raise ValueError('The current device usage port is 8787')
    if isinstance(result['heading'], str):
        result['heading'] = result['heading'].strip()
    if not isinstance(result['heading'], str) or not re.fullmatch(r'[A-Za-z0-9 ._-]{0,18}', result['heading']):
        raise ValueError('Heading: at most 18 ASCII letters, numbers, spaces, . _ -')
    if result['mode'] not in MODES:
        result['mode'] = 'green'
    for key in SECRET_KEYS:
        if not isinstance(result[key], str) or (result[key] and not re.fullmatch('[0-9a-f]{64}', result[key])):
            raise ValueError('Keys must be 64 lowercase hexadecimal characters')
    if not isinstance(result['codex_path'], str) or '\x00' in result['codex_path']:
        raise ValueError('Invalid Codex executable')
    return result


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    """DPAPI user scope; never fall back to plaintext on failure."""
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError('Windows private storage unavailable')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def restrict(path):
    # SID from the process token, not a shell-expanded account name.
    import subprocess
    result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True,
                            text=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    match = re.search(r'S-1-5-[0-9-]+', result.stdout)
    if not match:
        raise RuntimeError('Cannot determine Windows user')
    subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                    '*' + match[0] + ':(OI)(CI)F' if Path(path).is_dir() else '*' + match[0] + ':F',
                    '*S-1-5-18:(OI)(CI)F' if Path(path).is_dir() else '*S-1-5-18:F'],
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True)


def load(path):
    path = Path(path)
    if not path.exists():
        return dict(DEFAULTS)
    raw = json.loads(path.read_text(encoding='utf-8'))
    encrypted = raw.pop('secrets_dpapi', None)
    if encrypted:
        raw.update(json.loads(protect(base64.b64decode(encrypted, validate=True), decrypt=True)))
    return validate(raw)


def save(path, value):
    path = Path(path).resolve()
    value = validate(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not change ACLs of an existing source checkout. DPAPI still protects files there.
    if path.parent.name == 'Irozon Dot' and path.parent.parent == Path(os.environ.get('LOCALAPPDATA', '')):
        restrict(path.parent)
    public = {k: v for k, v in value.items() if k not in SECRET_KEYS}
    public['secrets_dpapi'] = base64.b64encode(protect(json.dumps(
        {k: value[k] for k in SECRET_KEYS}).encode())).decode()
    descriptor, temporary = tempfile.mkstemp(prefix='.settings-', dir=path.parent)
    try:
        os.close(descriptor)
        restrict(temporary)
        with open(temporary, 'w', encoding='utf-8') as stream:
            json.dump(public, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def redacted(value):
    return {**{k: v for k, v in value.items() if k not in SECRET_KEYS},
            **{k + '_configured': bool(value[k]) for k in SECRET_KEYS}}


def import_legacy(path):
    path = Path(path).resolve()
    value = load(path)
    # Explicit import of an existing repo install may copy its dedicated device
    # control header too. Never scan Codex/account directories or modify sources.
    header = path.parent.parent / 'include' / 'control_config.h'
    if path.name == 'local.json' and path.parent.name == 'companion' and not value['control_token'] and header.is_file():
        match = re.search(r'^#define IROZON_CONTROL_TOKEN "([0-9a-f]{64})"$',
                          header.read_text(encoding='utf-8'), re.MULTILINE)
        if match:
            value['control_token'] = match[1]
    return validate(value)


def paired(value):
    return bool(value['bind'] and value['esp32_ip'] and value['pairing_key'])


def legacy_candidates():
    roots = [Path(__file__).resolve().parent.parent]
    if getattr(sys, 'frozen', False):
        roots.extend(list(Path(sys.executable).resolve().parents)[:4])
    return sorted({str(root / 'companion/local.json') for root in roots
                   if (root / 'companion/local.json').is_file()})
