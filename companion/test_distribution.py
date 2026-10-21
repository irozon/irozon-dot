"""Isolated Windows/config/HTTP/USB protocol checks; never use production pairing."""
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
import winreg
import settings
import startup
import pairing
from monitor import Source, handler_for
from desktop_runtime import Runtime, CompanionServer


class StorageChecks(unittest.TestCase):
    def test_dpapi_roundtrip_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'local.json'
            value = {**settings.DEFAULTS, 'bind': '192.168.1.10', 'esp32_ip': '192.168.1.20',
                     'pairing_key': 'a' * 64, 'control_token': 'b' * 64, 'heading': 'MY DOT'}
            settings.save(path, value)
            raw = path.read_text()
            self.assertNotIn('a' * 64, raw)
            self.assertNotIn('b' * 64, raw)
            self.assertEqual(settings.load(path), value)
            public = settings.redacted(value)
            self.assertNotIn('pairing_key', public)
            self.assertTrue(public['control_token_configured'])

    def test_legacy_file_is_read_without_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'local.json'
            raw = json.dumps({'bind': '192.168.1.10', 'esp32_ip': '192.168.1.20', 'port': 8787,
                              'pairing_key': 'c' * 64})
            path.write_text(raw)
            value = settings.load(path)
            self.assertEqual(value['pairing_key'], 'c' * 64)
            self.assertEqual(path.read_text(), raw)

    def test_validation_and_no_fake_provider(self):
        for delta in ({'heading': 'x' * 19}, {'heading': '<script>'}, {'heading': 'bad\nname'},
                      {'provider': 'claude'}, {'bind': '0.0.0.0'}, {'esp32_ip': '8.8.8.8'},
                      {'bind': '127.0.0.1'}, {'port': 0}, {'port': 9999}, {'control_token': 'short'}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                settings.validate({**settings.DEFAULTS, **delta})
        self.assertEqual(settings.validate({'heading': 'ABCDEFGHIJKLMNOPQR'})['heading'], 'ABCDEFGHIJKLMNOPQR')

    def test_heading_missing_is_default_but_explicit_empty_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'local.json'
            self.assertEqual(settings.load(path)['heading'], 'IROZON DOT')
            path.write_text('{}')
            self.assertEqual(settings.load(path)['heading'], 'IROZON DOT')
            for heading, expected in (('', ''), (' \t\n ', ''), ('  Dot  ', 'Dot'),
                                      (' ABCDEFGHIJKLMNOPQR ', 'ABCDEFGHIJKLMNOPQR')):
                settings.save(path, {**settings.DEFAULTS, 'heading': heading})
                self.assertEqual(json.loads(path.read_text())['heading'], expected)
                self.assertEqual(Runtime(path, Source([])).snapshot_config()['heading'], expected)

    def test_pasted_addresses_trim_and_errors_are_safe_and_specific(self):
        self.assertEqual(settings.private_ipv4(' 192.168.1.20 '), '192.168.1.20')
        for value in ('host:8080', '192.168.1.999', 123, None):
            with self.subTest(value=value), self.assertRaises(ValueError) as result:
                settings.private_ipv4(value)
            self.assertIs(type(result.exception), ValueError)
            self.assertNotIn(str(value), str(result.exception))

    def test_failed_replace_keeps_old_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'local.json'
            settings.save(path, settings.DEFAULTS)
            before = path.read_bytes()
            with patch('settings.os.replace', side_effect=OSError('synthetic')):
                with self.assertRaises(OSError):
                    settings.save(path, {**settings.DEFAULTS, 'heading': 'new'})
            self.assertEqual(path.read_bytes(), before)

    def test_import_copies_existing_control_token_without_modifying_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'companion').mkdir(); (root / 'include').mkdir()
            path = root / 'companion/local.json'
            path.write_text(json.dumps({'pairing_key': 'a' * 64}))
            header = root / 'include/control_config.h'
            header.write_text('#define IROZON_CONTROL_TOKEN "' + 'b' * 64 + '"\n')
            before = path.read_bytes(), header.read_bytes()
            imported = settings.import_legacy(path)
            self.assertEqual(imported['control_token'], 'b' * 64)
            self.assertEqual(before, (path.read_bytes(), header.read_bytes()))

    def test_frozen_startup_command_quotes_paths(self):
        with patch('startup.sys.frozen', True, create=True), patch('startup.sys.executable', 'C:\\Program Files\\Dot\\IrozonDot.exe'):
            value = startup.command(Path('C:/My Settings/local.json'))
        self.assertTrue(value.startswith('"C:\\Program Files\\Dot\\IrozonDot.exe" start'))
        self.assertIn('--no-browser', value)

    def test_startup_registration_uses_isolated_registry_key(self):
        key = 'Software\\IrozonDotTests\\' + secrets.token_hex(8)
        try:
            with tempfile.TemporaryDirectory(prefix='irozon space ') as directory:
                config = Path(directory) / 'local.json'
                startup.set_enabled(True, config, key=key)
                command = startup.enabled(key=key)
                self.assertIn('--no-browser', command)
                self.assertIn(str(config.resolve()), command)
                startup.set_enabled(False, config, key=key)
                self.assertFalse(startup.enabled(key=key))
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)

    def test_legacy_startup_is_not_overwritten(self):
        with patch('startup.legacy_startup', return_value=True), self.assertRaises(ValueError):
            startup.set_enabled(True, Path('not-production.json'))

    def test_task_xml_console_encoding_and_managed_executable(self):
        xml = '''<?xml version="1.0" encoding="UTF-16"?><Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Settings><Enabled>true</Enabled></Settings><Actions><Exec><Command>C:\\Dot\\IrozonDot.exe</Command></Exec></Actions></Task>'''
        for encoding in ('utf-8', 'utf-16'):
            result = type('Result', (), {'returncode': 0, 'stdout': xml.encode(encoding)})()
            with patch('startup.subprocess.run', return_value=result):
                actual = startup.scheduled_startup()
                self.assertTrue(actual['exists'] and actual['enabled'] and actual['managed'])
                self.assertTrue(actual['config'].endswith('local.json'))

    def test_startup_reports_only_its_own_configuration(self):
        owner = str(Path('owner/local.json').resolve())
        task = {'exists': True, 'enabled': True, 'managed': True, 'config': owner}
        with patch('startup.scheduled_startup', return_value=task), patch('startup.enabled', return_value=''):
            self.assertTrue(startup.config_enabled(owner))
            self.assertFalse(startup.config_enabled('other/local.json'))


class HttpChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(Path(self.temp.name) / 'local.json', Source([]))
        self.server = CompanionServer(self.runtime, 0)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.server.run, args=(self.stop.is_set,), daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.stop.set()
        self.thread.join(timeout=4)
        self.server.server_close()
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None, port=None, address='127.0.0.1'):
        connection = http.client.HTTPConnection(address, port or self.port, timeout=5)
        body = None if data is None else json.dumps(data)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        value = response.read()
        result = response.status, dict(response.getheaders()), value
        connection.close()
        return result

    def session(self):
        status, headers, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        cookie = headers['Set-Cookie'].split(';')[0]
        status, _, body = self.request('GET', '/api/state', headers={'Cookie': cookie})
        state = json.loads(body)
        return {'Cookie': cookie, 'Content-Type': 'application/json', 'X-Irozon-CSRF': state['csrf']}

    def test_first_run_no_lan_no_account_and_assets(self):
        self.assertIsNone(self.server.lan)
        self.assertIsNone(self.runtime.source.rpc)
        self.assertFalse(self.runtime.path.exists())
        self.assertEqual(self.request('GET', '/app.js')[0], 200)
        self.assertEqual(self.request('GET', '/style.css')[0], 200)
        headers = self.session()
        status, _, body = self.request('GET', '/api/state', headers={'Cookie': headers['Cookie']})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)['paired'])

    def test_configured_does_not_mean_connected_and_rejected_token_is_explained(self):
        self.runtime.config = {**settings.DEFAULTS, 'bind': '192.168.1.10',
                               'esp32_ip': '192.168.1.20', 'pairing_key': 'a'*64,
                               'control_token': 'b'*64}
        self.assertEqual(self.runtime.status()['connection'], 'connecting')
        from urllib.error import HTTPError
        with patch('device.test', side_effect=HTTPError('',401,'',None,None)):
            self.assertIsNone(self.runtime.probe())
        status = self.runtime.status()
        self.assertEqual(status['connection'], 'disconnected')
        self.assertIn('rejected', status['connection_message'])
        with patch('device.test', return_value={'display_on': True, 'mode': 'green'}):
            self.runtime.probe()
        self.assertEqual(self.runtime.status()['connection'], 'connected')

    def test_failed_usb_enrollment_does_not_activate_new_credentials(self):
        # Only a simulated serial handshake; never open a physical port.
        config = {**settings.DEFAULTS, 'bind': '192.168.1.10', 'esp32_ip': '192.168.1.20'}
        self.runtime.config = config
        with patch('pairing.pair', side_effect=ValueError('USB pairing window closed')):
            response = self.request('POST', '/api/pair', {'port': 'COM98'}, self.session())
        self.assertEqual(response[0], 400)
        self.assertFalse(settings.paired(self.runtime.config))
        self.assertFalse(self.runtime.config['control_token'])
        pending = self.runtime.path.with_name('pairing-pending.json')
        self.assertTrue(pending.exists())
        recovery = settings.load(pending)
        self.assertTrue(recovery['pairing_key'])
        self.assertNotIn(recovery['pairing_key'], pending.read_text())

    def test_power_control_waits_for_device_confirmation_without_second_power_setting(self):
        state = {'display_on': False, 'mode': 'green', 'connection': 'connected'}
        with patch('device.request') as send, patch('device.test', return_value=state):
            code, _, body = self.request('POST', '/api/display', {'on': False}, self.session())
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(body)['state']['display_on'])
        self.assertEqual(send.call_args.args[2:4], ('/api/display/off', 'POST'))
        self.assertNotIn('display_on', self.runtime.config)

    def test_host_origin_csrf_and_missing_session_denied(self):
        self.assertEqual(self.request('GET', '/', headers={'Host': 'attacker.invalid'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Sec-Fetch-Site': 'cross-site',
                         'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'})[0], 200)
        self.assertEqual(self.request('GET', '/api/state')[0], 403)
        headers = self.session()
        self.assertEqual(self.request('POST', '/api/save', {'heading': 'Hello'})[0], 403)
        bad = {**headers, 'Origin': 'https://attacker.invalid'}
        self.assertEqual(self.request('POST', '/api/save', {'heading': 'Hello'}, bad)[0], 403)
        bad = {**headers, 'X-Irozon-CSRF': 'wrong'}
        self.assertEqual(self.request('POST', '/api/save', {'heading': 'Hello'}, bad)[0], 403)
        good = {**headers, 'Origin': f'http://127.0.0.1:{self.port}'}
        self.assertEqual(self.request('POST', '/api/save', {'heading': 'Hello'}, good)[0], 200)
        self.assertEqual(settings.load(self.runtime.path)['heading'], 'Hello')

    def test_body_limit_and_no_secret_readback(self):
        headers = self.session()
        self.assertEqual(self.request('POST', '/api/save', {'heading': 'x' * 17000}, headers)[0], 400)
        self.assertEqual(self.request('POST', '/api/save', {'pairing_key': 'a' * 64}, headers)[0], 200)
        _, _, body = self.request('GET', '/api/state', headers={'Cookie': headers['Cookie']})
        self.assertNotIn(('a' * 64).encode(), body)

    def test_private_ha_export_requires_explicit_authenticated_post(self):
        headers = self.session()
        self.assertEqual(self.request('POST', '/api/save', {'control_token': 'b' * 64}, headers)[0], 200)
        self.assertEqual(self.request('GET', '/api/export-ha', headers={'Cookie': headers['Cookie']})[0], 404)
        self.assertEqual(self.request('POST', '/api/export-ha', {})[0], 403)
        status, reply_headers, body = self.request('POST', '/api/export-ha', {}, headers)
        self.assertEqual(status, 200)
        self.assertIn('attachment;', reply_headers['Content-Disposition'])
        self.assertEqual(body, ('irozon_dot_authorization: "Bearer ' + 'b' * 64 + '"\n').encode())

    def test_single_server_usage_socket_cannot_serve_settings(self):
        # Loopback alias stands in for a LAN socket only inside this isolated test.
        config = {**settings.DEFAULTS, 'bind': '127.0.0.2', 'esp32_ip': '127.0.0.1',
                  'pairing_key': 'a' * 64, 'heading': ''}
        self.runtime.config = config
        self.server.configure_lan(config)
        self.assertEqual(self.request('GET', '/', address='127.0.0.2', port=8787)[0], 404)
        self.assertEqual(self.request('POST', '/api/exit', {}, self.session(), port=8787, address='127.0.0.2')[0], 403)
        status, headers, body = self.request('GET', '/usage?nonce=' + '0' * 32, address='127.0.0.2', port=8787)
        self.assertEqual(status, 200)
        signature = hmac.new(bytes.fromhex('a' * 64), body, hashlib.sha256).hexdigest()
        self.assertEqual(headers['X-Irozon-Signature'], signature)
        self.assertEqual(json.loads(body)['heading'], '')

    def test_heading_save_and_settings_reload_keep_explicit_empty(self):
        headers = self.session()
        for value, expected in ((' Dot ', 'Dot'), ('', ''), ('   ', '')):
            self.assertEqual(self.request('POST', '/api/save', {'heading': value}, headers)[0], 200)
            status, _, body = self.request('GET', '/api/state', headers={'Cookie': headers['Cookie']})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['config']['heading'], expected)
            self.assertEqual(settings.load(self.runtime.path)['heading'], expected)

    def test_existing_owner_import_does_not_stop_or_rewrite(self):
        from windows_control import Instance
        source = Path(self.temp.name) / 'legacy.json'
        source.write_text(json.dumps({**settings.DEFAULTS, 'heading': 'old'}))
        before = source.read_bytes()
        owner = Instance(source)
        try:
            response = self.request('POST', '/api/import', {'path': str(source)}, self.session())
            self.assertEqual(response[0], 400)
            self.assertFalse(owner.stop_requested())
            self.assertEqual(source.read_bytes(), before)
        finally:
            owner.close()


class PairingChecks(unittest.TestCase):
    def test_usb_challenge_and_keys_not_echoed(self):
        class FakeSerial:
            def __init__(self, **kwargs): self.sent = []; self.closed = False
            def open(self): pass
            def close(self): self.closed = True
            def reset_input_buffer(self): pass
            def write(self, value): self.sent.append(json.loads(value))
            def readline(self, limit):
                return json.dumps({'irozon_probe': 1, 'nonce': 'f' * 32} if len(self.sent) == 1 else
                                  {'irozon_pair': 1, 'accepted': True}).encode()
        stream = FakeSerial()
        with patch('serial.Serial', return_value=stream):
            result = pairing.pair('COM98', '192.168.1.10')
        self.assertEqual(len(result['pairing_key']), 64)
        self.assertEqual(stream.sent[1]['nonce'], 'f' * 32)
        self.assertFalse(stream.dtr)
        self.assertFalse(stream.rts)
        self.assertTrue(stream.closed)


if __name__ == '__main__':
    unittest.main()
