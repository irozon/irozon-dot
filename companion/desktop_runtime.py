"""One HTTP server instance, LAN usage and loopback settings on separate sockets."""
import hmac
import json
import logging
from pathlib import Path
import select
import secrets
import socket
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit
import settings
import device
import startup
import pairing

STATIC = Path(__file__).with_name('web')


class Runtime:
    def __init__(self, path, source):
        self.path = Path(path).resolve()
        self.config = settings.import_legacy(self.path)
        self.source = source
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.refresh = threading.Event()
        self.provider_status = 'Not configured'
        self.lan_error = False
        self.legacy_startup = startup.legacy_startup()
        self.server = None
        self.device_state = None
        self.device_error = ''
        self.device_checked = 0
        self.device_refresh = threading.Event()
        self.probe_lock = threading.Lock()

    def snapshot_config(self):
        with self.lock:
            return dict(self.config)

    def apply(self, fields):
        with self.lock:
            config = dict(self.config)
            for key, value in fields.items():
                if key in settings.SECRET_KEYS and not value:
                    continue  # Empty password controls preserve stored keys.
                config[key] = value
            config = settings.validate(config)
            # Verify/reserve changed LAN binding before replacing the saved configuration.
            self.server.configure_lan(config, commit=lambda: settings.save(self.path, config))
            if any(config[key] != self.config[key] for key in ('bind', 'esp32_ip', *settings.SECRET_KEYS)):
                self.device_state, self.device_error, self.device_checked = None, '', 0
            self.config = config
            self.lan_error = False
        self.refresh.set()
        self.device_refresh.set()

    def probe(self):
        with self.probe_lock:
            config = self.snapshot_config()
            state, error = None, ''
            if settings.paired(config) and config['control_token']:
                try:
                    state = device.test(config)
                except Exception as failure:
                    error = device.error_message(failure)
            with self.lock:
                if config == self.config:
                    self.device_state, self.device_error = state, error
                    self.device_checked = int(time.time())
        return state

    def watch_device(self):
        while not self.stop.is_set():
            self.probe()
            self.device_refresh.wait(10)
            self.device_refresh.clear()

    def status(self):
        config = self.snapshot_config()
        with self.lock:
            state, error = self.device_state, self.device_error
        if not settings.paired(config) or not config['control_token']:
            connection, message = 'needs_setup', 'Connect an existing setup or pair your new device.'
        elif self.lan_error:
            connection, message = 'disconnected', 'Another companion owns the usage port, or the PC address is unavailable.'
        elif error:
            connection, message = 'disconnected', error
        elif state:
            connection, message = 'connected', 'Device authenticated. Existing pairing is ready.'
        else:
            connection, message = 'connecting', 'Checking the device connection…'
        snapshot = self.source.snapshot('0' * 32)
        return {'connection': connection, 'connection_message': message,
                'device': state, 'device_checked': self.device_checked,
                'usage': {k: snapshot[k] for k in ('status', 'sampled_at', 'weekly', 'session')}}

    def poll(self):
        from monitor import codex_command
        current_command = None
        next_read = 0
        try:
            while not self.stop.is_set():
                config = self.snapshot_config()
                if settings.paired(config) and time.monotonic() >= next_read:
                    try:
                        command = codex_command(getattr(self, 'codex_override', None) or config['codex_path'] or None)
                        if command != current_command:
                            self.source.close()
                            self.source.command = command
                            current_command = command
                        self.source.refresh(self.stop)
                        self.provider_status = 'Codex connected' if not self.source.error else 'Codex sign-in or limits unavailable'
                    except Exception:
                        self.provider_status = 'Codex executable unavailable; install Codex CLI and sign in'
                    next_read = time.monotonic() + 60
                elif not settings.paired(config):
                    self.provider_status = 'Complete device pairing first'
                self.refresh.wait(max(.1, next_read - time.monotonic()) if settings.paired(config) else 60)
                self.refresh.clear()
        finally:
            self.source.close()


def handler_for(runtime):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200, content_type='application/json', cookie=False, download=None):
            body = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="' + download + '"')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if cookie:
                self.send_header('Set-Cookie', 'irozon_session=' + self.server.session + '; HttpOnly; SameSite=Strict; Path=/')
            self.end_headers()
            self.wfile.write(body)

        def local(self, allow_navigation=False):
            if self.connection.getsockname()[0] != '127.0.0.1' or self.client_address[0] != '127.0.0.1':
                return False
            port = self.server.server_port
            allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            navigation = (allow_navigation and self.headers.get('Sec-Fetch-Mode') == 'navigate'
                          and self.headers.get('Sec-Fetch-Dest') == 'document')
            return (host in allowed and (origin is None or origin == 'http://' + host)
                    and (navigation or self.headers.get('Sec-Fetch-Site', '') != 'cross-site'))

        def session_ok(self):
            cookies = self.headers.get('Cookie', '').split(';')
            return any(hmac.compare_digest(c.strip(), 'irozon_session=' + self.server.session) for c in cookies)

        def do_GET(self):
            url = urlsplit(self.path)
            if self.connection.getsockname()[0] != '127.0.0.1':
                if url.path != '/usage':
                    self.reply({'error': 'not_found'}, 404)
                    return
                from monitor import handler_for as usage_handler
                config = runtime.snapshot_config()
                usage_handler(runtime.source, bytes.fromhex(config['pairing_key']), config['esp32_ip'],
                              heading=config['heading']).do_GET(self)
                return
            if not self.local(allow_navigation=url.path == '/'):
                self.reply({'error': 'local_origin_required'}, 403)
                return
            if url.path in ('/', '/app.js', '/style.css'):
                filename, mime = {'/': ('index.html', 'text/html; charset=utf-8'),
                                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                                  '/style.css': ('style.css', 'text/css; charset=utf-8')}[url.path]
                self.reply((STATIC / filename).read_bytes(), content_type=mime, cookie=url.path == '/')
                return
            if not self.session_ok():
                self.reply({'error': 'open_settings_page_first'}, 403)
                return
            if url.path == '/api/state':
                config = runtime.snapshot_config()
                self.reply({'config': settings.redacted(config), 'csrf': self.server.csrf,
                            'application': 'irozon-dot', **runtime.status(),
                            'paired': settings.paired(config), 'provider_status': runtime.provider_status,
                            'lan_error': runtime.lan_error,
                            'startup': startup.config_enabled(runtime.path),
                            'legacy_startup': runtime.legacy_startup,
                            'legacy_candidates': settings.legacy_candidates(),
                            'config_path': str(runtime.path), 'heading_limit': settings.HEADING_LIMIT})
            else:
                self.reply({'error': 'not_found'}, 404)

        def do_POST(self):
            if (not self.local() or not self.session_ok() or
                    not hmac.compare_digest(self.headers.get('X-Irozon-CSRF', ''), self.server.csrf)):
                self.reply({'error': 'local_session_required'}, 403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    self.reply({'error': 'invalid_request'}, 400)
                    return
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected a JSON object')
                path = urlsplit(self.path).path
                if path == '/api/save':
                    runtime.apply(data)
                    self.reply({'ok': True, 'message': 'Settings saved'})
                elif path == '/api/import':
                    from windows_control import running
                    source = Path(data['path']).resolve()
                    if source == runtime.path or running(source):
                        raise ValueError('Stop the existing installation explicitly before migration; it has not been changed')
                    imported = settings.import_legacy(source)
                    runtime.apply(imported)
                    self.reply({'ok': True, 'message': 'Imported a copy; original file and startup unchanged'})
                elif path == '/api/discover':
                    candidates = device.discover(runtime.snapshot_config())
                    suggested = device.local_address(candidates[0]) if len(candidates) == 1 else ''
                    self.reply({'candidates': candidates, 'bind': suggested,
                                'message': 'Candidates only; authenticate with Test connection'})
                elif path == '/api/ports':
                    self.reply({'ports': pairing.ports()})
                elif path == '/api/pair':
                    config = runtime.snapshot_config()
                    if not config['bind'] or not config['esp32_ip']:
                        raise ValueError('Save PC and device LAN addresses first')
                    # Stage durable recovery keys, but do not activate an unconfirmed link.
                    pending = runtime.path.with_name('pairing-pending.json')
                    recovery = settings.load(pending) if pending.exists() else config
                    if any(recovery[k] != config[k] for k in ('bind', 'esp32_ip')):
                        raise ValueError('Pending pairing belongs to different addresses; review its private recovery file first')
                    keys = {key: config[key] or recovery[key] or secrets.token_hex(32)
                            for key in settings.SECRET_KEYS}
                    settings.save(pending, {**config, **keys})
                    pairing.pair(data['port'], config['bind'], **keys)
                    try:
                        runtime.apply(keys)
                    except Exception:
                        raise ValueError('Device confirmed pairing, but Windows could not save it. Protected recovery keys remain in pairing-pending.json; retry without resetting the device.') from None
                    pending.unlink(missing_ok=True)
                    self.reply({'ok': True, 'message': 'Device confirmed USB pairing. Test connection next.'})
                elif path == '/api/test':
                    state = runtime.probe()
                    if not state:
                        raise ValueError(runtime.device_error or 'Import your existing setup or complete first-time pairing.')
                    self.reply({'ok': True, 'state': {k: state.get(k) for k in
                                ('display_on', 'mode', 'connection', 'usage_status', 'power_control', 'capabilities')}})
                elif path == '/api/display':
                    config = runtime.snapshot_config()
                    if set(data) == {'mode'} and data['mode'] in settings.MODES:
                        key, wanted = 'mode', data['mode']
                        route = '/api/display/mode/' + wanted
                    elif set(data) == {'on'} and type(data['on']) is bool:
                        key, wanted = 'display_on', data['on']
                        route = '/api/display/' + ('on' if wanted else 'off')
                    else:
                        raise ValueError('Choose a display mode or power setting')
                    device.request(config['esp32_ip'], config['control_token'], route, 'POST')
                    deadline = time.monotonic() + 12
                    while time.monotonic() < deadline:
                        state = device.test(config)
                        if state[key] == wanted:
                            if key == 'mode':
                                runtime.apply({'mode': wanted})
                            runtime.probe()
                            self.reply({'ok': True, 'message': 'Device confirmed the change', 'state': state})
                            return
                        time.sleep(.25)
                    raise ValueError('Change was queued but not confirmed; test connection')
                elif path == '/api/startup':
                    if type(data.get('enabled')) is not bool:
                        raise ValueError('Expected a startup choice')
                    startup.set_enabled(data['enabled'], runtime.path)
                    self.reply({'ok': True, 'message': 'Start-with-Windows updated'})
                elif path == '/api/export-ha':
                    token = runtime.snapshot_config()['control_token']
                    if not token:
                        raise ValueError('No device control token is configured')
                    content = ('irozon_dot_authorization: "Bearer ' + token + '"\n').encode()
                    self.reply(content, content_type='application/yaml', download='irozon-dot-private-secret.yaml')
                elif path == '/api/exit':
                    self.reply({'ok': True, 'message': 'Companion is exiting; this page can be closed'})
                    runtime.stop.set()
                else:
                    self.reply({'error': 'not_found'}, 404)
            except ValueError as error:
                # All ValueError messages originate from fixed validation strings, never upstream bodies.
                self.reply({'error': str(error) if type(error) is ValueError else 'Invalid settings'}, 400)
            except Exception:
                logging.warning('Settings operation failed; no private details logged')
                self.reply({'error': device.error_message(None)}, 400)
    return Handler


class CompanionServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, runtime, port=8788):
        self.session, self.csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.lan = None
        self.lan_address = None
        self.lan_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(12)
        # Exactly one server object: settings socket is always loopback-only.
        super().__init__(('127.0.0.1', port), handler_for(runtime))
        runtime.server = self
        try:
            self.configure_lan(runtime.config)
        except OSError:
            # Preserve the settings UI so an address/port conflict can be repaired.
            runtime.provider_status = 'LAN bind failed; another installation may own port 8787'
            runtime.lan_error = True
            logging.warning('LAN listener unavailable; existing listener was not replaced')

    def configure_lan(self, config, commit=lambda: None):
        desired = (config['bind'], config['port']) if settings.paired(config) else None
        with self.lan_lock:
            if desired == self.lan_address:
                commit()
                return
            replacement = None
            if desired:
                replacement = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                        replacement.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    replacement.bind(desired)
                    replacement.listen(8)
                except Exception:
                    replacement.close()
                    raise
            try:
                commit()
            except Exception:
                if replacement:
                    replacement.close()
                raise
            previous, self.lan = self.lan, replacement
            self.lan_address = desired
            if previous:
                previous.close()

    def get_request(self):
        connection, address = self.active_socket.accept()
        connection.settimeout(3)
        return connection, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, *_):
        logging.warning('HTTP request failed; no private details logged')

    def run(self, stop_requested):
        while not stop_requested():
            with self.lan_lock:
                listeners = [self.socket] + ([self.lan] if self.lan else [])
            try:
                ready, _, _ = select.select(listeners, [], [], .25)
                for listener in ready:
                    self.active_socket = listener
                    self._handle_request_noblock()
            except (OSError, ValueError):
                continue  # A settings transaction may have replaced the LAN socket.

    def server_close(self):
        if self.lan:
            self.lan.close()
            self.lan = None
        super().server_close()


def run(args, source, instance):
    runtime = Runtime(args.config, source)
    runtime.codex_override = getattr(args, 'codex', None)
    server = CompanionServer(runtime, getattr(args, 'settings_port', 8788))
    worker = threading.Thread(target=runtime.poll, daemon=True)
    worker.start()
    device_worker = threading.Thread(target=runtime.watch_device, daemon=True)
    device_worker.start()
    try:
        callback = getattr(args, 'ready', None)
        if callback:
            callback(server.server_port)
        logging.info('Companion started; localhost settings ready')
        server.run(lambda: runtime.stop.is_set() or instance.stop_requested())
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop.set()
        runtime.refresh.set()
        runtime.device_refresh.set()
        server.server_close()
        source.close()  # Unblock an in-flight owned RPC before joining the worker.
        worker.join(timeout=35)
        device_worker.join(timeout=5)
        logging.info('Companion stopped cleanly')
