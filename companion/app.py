"""Source and PyInstaller entry point. Never reads Codex credential files."""
import argparse
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time
import webbrowser
from urllib.request import build_opener, ProxyHandler, Request
import settings
from windows_control import Instance, running, request_stop


def existing_settings(url):
    """Recognize the existing local companion; never start a second UI owner."""
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as response:
            cookie = response.headers.get('Set-Cookie', '').split(';')[0]
        with opener.open(Request(url + 'api/state', headers={'Cookie': cookie}), timeout=2) as response:
            state = json.loads(response.read(16384))
        if (state.get('heading_limit') == 18 and 'config_path' in state and
                'pairing_key_configured' in state.get('config', {}) and running(state['config_path'])):
            return True
    except Exception:
        pass
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='start', choices=('start', 'settings', 'stop', 'restart', 'status'))
    parser.add_argument('--config', default=str(settings.default_path()))
    parser.add_argument('--settings-port', type=int, default=8788)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    args.config = str(Path(args.config).resolve())
    args.background = True
    logs = Path(args.config).parent / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[
        RotatingFileHandler(logs / 'companion.log', maxBytes=131072, backupCount=2, encoding='utf-8')])
    url = f'http://127.0.0.1:{args.settings_port}/'
    if args.action == 'status':
        state = 'running' if running(args.config) else 'stopped'
        if sys.stdout:
            print('Irozon Dot:', state)
        return
    if args.action in ('stop', 'restart'):
        request_stop(args.config)
        deadline = time.monotonic() + 45
        while running(args.config):
            if time.monotonic() >= deadline:
                raise RuntimeError('Stop timed out; no duplicate started')
            time.sleep(.2)
        if args.action == 'stop':
            return
    instance = Instance(args.config)
    if not instance.acquired:
        instance.close()
        logging.info('Duplicate companion ignored')
        if not args.no_browser:
            webbrowser.open(url)
        return
    from providers import create_source
    from desktop_runtime import run
    args.ready = lambda port: None if args.no_browser else webbrowser.open(f'http://127.0.0.1:{port}/')
    try:
        try:
            run(args, create_source(), instance)
        except OSError:
            if not existing_settings(url):
                raise
            logging.info('An existing companion owns localhost settings; opened its configuration')
            if not args.no_browser:
                webbrowser.open(url)
    finally:
        instance.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.error('Companion could not start; check private config, settings port ownership and local permissions')
        if '--no-browser' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None,
                'Irozon Dot could not start. Check the companion.log beside your configuration. '
                'An existing installation may already own the settings port. No credentials were logged.',
                'Irozon Dot', 0x10)
        raise SystemExit(1)
