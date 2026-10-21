"""Canonical Codex usage implementation. Standard-library usage path; no credential-file access."""
import argparse
import hmac
import ipaddress
import json
import math
import platform
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import hashlib
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def codex_command(path=None):
    path = path or shutil.which('codex.cmd') or shutil.which('codex')
    if not path:
        raise RuntimeError('Codex CLI not found')
    if str(path).lower().endswith(('.cmd', '.ps1')):
        root = Path(path).parent / 'node_modules/@openai/codex'
        arch = 'arm64' if platform.machine().lower() in ('arm64', 'aarch64') else 'x64'
        triple = ('aarch64' if arch == 'arm64' else 'x86_64') + '-pc-windows-msvc'
        for vendor in (root / f'node_modules/@openai/codex-win32-{arch}/vendor', root / 'vendor'):
            executable = vendor / triple / 'bin/codex.exe'
            if executable.is_file():
                return [str(executable)]
        raise RuntimeError('Pass --codex with the native codex.exe path')
    return [str(path)]


class Rpc:
    def __init__(self, command):
        self.process = subprocess.Popen(command + ['app-server', '--listen', 'stdio://'],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.messages = queue.Queue()
        self.next_id = 0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call('initialize', {'clientInfo': {'name': 'irozon_dot',
                        'title': 'Irozon Dot', 'version': '1.0.0-rc.2'}})
            self.send({'method': 'initialized'})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    pass
        finally:
            self.messages.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def call(self, method, params=None):
        self.next_id += 1
        request_id = self.next_id
        self.send({'id': request_id, 'method': method, 'params': params or {}})
        deadline = time.monotonic() + 30
        while True:
            message = self.messages.get(timeout=max(.001, deadline - time.monotonic()))
            if message is None:
                raise RuntimeError('Codex app-server closed')
            if message.get('id') == request_id:
                if 'error' in message:
                    # Do not log upstream error bodies or private account details.
                    raise RuntimeError('Codex RPC failed')
                return message['result']
            if 'id' in message and 'method' in message:
                self.send({'id': message['id'], 'error': {'code': -32601,
                           'message': 'Unsupported by read-only usage monitor'}})
            if time.monotonic() >= deadline:
                raise TimeoutError('Codex RPC timeout')

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def normalize(result, now):
    """Map only the two duration values verified locally. Never infer from position."""
    buckets = result.get('rateLimitsByLimitId')
    bucket = buckets.get('codex') if isinstance(buckets, dict) else result.get('rateLimits')
    if not isinstance(bucket, dict) or bucket.get('limitId') != 'codex':
        raise ValueError('Codex bucket unavailable')
    mapped = {'weekly': None, 'session': None}
    seen = set()
    for position in ('primary', 'secondary'):
        window = bucket.get(position)
        if not isinstance(window, dict):
            continue
        duration = window.get('windowDurationMins')
        name = {300: 'session', 10080: 'weekly'}.get(duration) if type(duration) is int else None
        if name is None:
            continue
        if name in seen:
            raise ValueError('Ambiguous quota windows')
        seen.add(name)
        used, reset = window.get('usedPercent'), window.get('resetsAt')
        if (type(used) not in (float, int) or not math.isfinite(used) or not 0 <= used <= 100
                or type(reset) is not int or not now < reset <= now + duration * 60 + 300):
            continue
        mapped[name] = {'remaining': 100 - used, 'reset_at': reset}
    return mapped


class Source:
    """One persistent CLI child, one upstream read per minute; no disk usage cache."""
    def __init__(self, command):
        self.command = command
        self.rpc = None
        self.lock = threading.Lock()
        self.sample = None
        self.sample_time = 0
        self.error = True

    def refresh(self, stopping=None):
        try:
            if self.rpc is None:
                self.rpc = Rpc(self.command)
            if stopping and stopping.is_set():
                return
            account = self.rpc.call('account/read', {'refreshToken': False}).get('account')
            if not account or account.get('type') != 'chatgpt':
                raise RuntimeError('ChatGPT-managed sign-in unavailable')
            if stopping and stopping.is_set():
                return
            result = self.rpc.call('account/rateLimits/read')
            now = int(time.time())
            sample = normalize(result, now)
            with self.lock:
                self.sample, self.sample_time, self.error = sample, now, False
        except Exception:
            with self.lock:
                self.error = True
            self.close()

    def close(self):
        rpc, self.rpc = self.rpc, None
        if rpc:
            rpc.close()

    def snapshot(self, nonce):
        with self.lock:
            now = int(time.time())
            sample = dict(self.sample or {'weekly': None, 'session': None})
            age = now - self.sample_time
            fresh = not self.error and 0 <= age <= 150
            # Expired readings must not be presented as current after a reset.
            for name, window in sample.items():
                if window and window['reset_at'] <= now:
                    sample[name] = None
            return {'version': 1, 'source': 'codex', 'test_data': False,
                    'nonce': nonce, 'server_time': now, 'sampled_at': self.sample_time,
                    'status': 'live' if fresh else 'stale' if self.sample else 'unavailable',
                    **sample}


def handler_for(source, key, allowed_ip, heading=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.connection.settimeout(3)
            url = urlsplit(self.path)
            nonce = parse_qs(url.query).get('nonce', [''])[0]
            if self.client_address[0] != allowed_ip:
                self.send_error(403)
                return
            if url.path != '/usage' or len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
                self.send_error(400)
                return
            snapshot = source.snapshot(nonce)
            if heading is not None:
                snapshot['heading'] = heading
            payload = json.dumps(snapshot, separators=(',', ':'), allow_nan=False).encode()
            signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Irozon-Signature', signature)
            self.end_headers()
            self.wfile.write(payload)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', help='Installed Codex executable or npm wrapper')
    parser.add_argument('--check', action='store_true', help='Read once; no LAN listener')
    parser.add_argument('--config', default=str(Path(__file__).with_name('local.json')))
    parser.add_argument('--background', action='store_true', help='Silent Windows launch with bounded local logs')
    args = parser.parse_args()
    if args.background:
        logs = Path(__file__).with_name('logs')
        logs.mkdir(exist_ok=True)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[
            RotatingFileHandler(logs / 'companion.log', maxBytes=131072, backupCount=2, encoding='utf-8')])
    if args.check:
        source = Source(codex_command(args.codex))
        try:
            source.refresh()
            print(json.dumps(source.snapshot('0' * 32), indent=2))
            if source.error:
                raise SystemExit('Codex sign-in or limits unavailable; no private error details logged')
        finally:
            source.close()
        return
    from windows_control import Instance
    instance = Instance(args.config)
    if not instance.acquired:
        instance.close()
        if args.background:
            logging.info('Duplicate companion ignored')
        else:
            print('Irozon Dot is already running')
        return
    try:
        serve(args, Source(codex_command(args.codex)), instance)
    finally:
        instance.close()


def serve(args, source, instance):
    # Source and packaged entry points use the same server/configuration owner.
    from desktop_runtime import run
    return run(args, source, instance)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if '--background' not in __import__('sys').argv:
            raise
        logging.error('Companion stopped unexpectedly; check configuration, port ownership and Codex sign-in')
        raise SystemExit(1)
