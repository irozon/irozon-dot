"""Exercise the real frozen executable using only temporary config and loopback.

Does not register production startup, access Codex, open serial, or bind the LAN.
"""
from pathlib import Path
import argparse
import hashlib
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'companion'))
from windows_control import running


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path)
    args = parser.parse_args()
    version = (ROOT / 'VERSION').read_text().strip()
    executable = (args.executable or ROOT / 'dist' / ('windows-' + version) / 'IrozonDot.exe').resolve()
    production_paths = [ROOT / 'companion/local.json',
                        Path(os.environ['LOCALAPPDATA']) / 'Irozon Dot/local.json']
    before = [(path, hashlib.sha256(path.read_bytes()).digest() if path.exists() else None,
               running(path)) for path in production_paths]
    with tempfile.TemporaryDirectory(prefix='frozen-check-', dir=ROOT / '.pio') as directory:
        config = Path(directory) / 'local.json'
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        environment = dict(os.environ)
        environment['PATH'] = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
        common = ['--config', str(config), '--settings-port', str(port), '--no-browser']
        children = []
        def launch(action='start'):
            process = subprocess.Popen([str(executable), action, *common], env=environment,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            children.append(process)
            return process
        def request(method, path, data=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            connection.request(method, path, None if data is None else json.dumps(data), headers or {})
            response = connection.getresponse()
            body = response.read()
            result = response.status, dict(response.getheaders()), body
            connection.close()
            return result
        def wait_ready(process):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Frozen executable exited before settings became ready')
                try:
                    return request('GET', '/')
                except OSError:
                    time.sleep(.2)
            raise RuntimeError('Settings listener did not become ready')
        try:
            owner = launch()
            status, headers, body = wait_ready(owner)
            assert status == 200 and b'Irozon Dot' in body
            for mode in (b'green', b'classic', b'companion', b'analog'):
                assert b'data-mode="' + mode + b'"' in body, 'Missing packaged display card: ' + mode.decode()
            for expression in (b'Happy', b'Curious', b'Surprised', b'Sad',
                               b'Sleepy', b'Sleeping', b'Waking'):
                assert expression in body, 'Missing packaged Companion preview: ' + expression.decode()
            assert not config.exists(), 'First launch must not invent device pairing'
            assert request('GET', '/app.js')[0] == 200
            assert request('GET', '/style.css')[0] == 200
            cookie = headers['Set-Cookie'].split(';')[0]
            response = request('GET', '/api/state', headers={'Cookie': cookie})
            state = json.loads(response[2])
            assert not state['paired']
            assert 'pairing_key' not in state['config']
            print('PASS: frozen first run, bundled assets, no external Python/PATH dependency')
            duplicate = launch()
            assert duplicate.wait(timeout=15) == 0
            assert owner.poll() is None and running(config)
            print('PASS: duplicate process exits without disturbing the owner')
            write_headers = {'Cookie': cookie, 'Content-Type': 'application/json', 'X-Irozon-CSRF': state['csrf']}
            assert request('POST', '/api/save', {'heading': 'FIRST RUN', 'pairing_key': 'a' * 64}, write_headers)[0] == 200
            assert ('a' * 64) not in config.read_text()
            logs = config.parent / 'logs/companion.log'
            assert ('a' * 64) not in logs.read_text()
            print('PASS: packaged DPAPI persistence, no secret readback/logging')
            stopper = launch('stop')
            assert stopper.wait(timeout=15) == 0
            assert owner.wait(timeout=15) == 0
            assert not running(config)
            replacement = launch('restart')
            _, headers, _ = wait_ready(replacement)
            cookie = headers['Set-Cookie'].split(';')[0]
            state = json.loads(request('GET', '/api/state', headers={'Cookie': cookie})[2])
            assert state['config']['heading'] == 'FIRST RUN'
            assert state['config']['pairing_key_configured']
            assert not state['paired']  # No LAN addresses, therefore no LAN server/provider.
            write_headers = {'Cookie': cookie, 'Content-Type': 'application/json', 'X-Irozon-CSRF': state['csrf']}
            assert request('POST', '/api/save', {'heading': '  '}, write_headers)[0] == 200
            assert json.loads(config.read_text())['heading'] == ''
            empty_stopper = launch('stop')
            assert empty_stopper.wait(timeout=15) == 0
            assert replacement.wait(timeout=15) == 0
            empty_owner = launch()
            _, headers, _ = wait_ready(empty_owner)
            cookie = headers['Set-Cookie'].split(';')[0]
            state = json.loads(request('GET', '/api/state', headers={'Cookie': cookie})[2])
            assert state['config']['heading'] == ''
            write_headers = {'Cookie': cookie, 'Content-Type': 'application/json', 'X-Irozon-CSRF': state['csrf']}
            print('PASS: packaged explicitly empty heading survives save, process restart and settings reload')
            assert request('POST', '/api/exit', {}, write_headers)[0] == 200
            assert empty_owner.wait(timeout=15) == 0
            print('PASS: Stop, restart, persisted settings and browser Exit')
        finally:
            # Stop only the temporary config's mutex/event scope, never production.
            if running(config):
                subprocess.run([str(executable), 'stop', *common], env=environment, timeout=50,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            for process in children:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
    for path, digest, was_running in before:
        assert (hashlib.sha256(path.read_bytes()).digest() if path.exists() else None) == digest
        assert running(path) == was_running
    print('PASS: existing production config and companion ownership unchanged')


if __name__ == '__main__':
    main()
