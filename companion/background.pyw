"""Silent start/stop/restart launcher, also usable with python.exe for console status."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import subprocess
import sys
import time
from windows_control import running, request_stop

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'restart', 'status'), nargs='?', default='start')
    parser.add_argument('--config', default=str(ROOT / 'local.json'))
    args = parser.parse_args()
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[
        RotatingFileHandler(logs / 'launcher.log', maxBytes=131072, backupCount=2, encoding='utf-8')])
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
                raise RuntimeError('Stop timed out; no duplicate was started')
            time.sleep(.2)
        logging.info('Companion stopped')
    if args.action in ('start', 'restart'):
        if running(args.config):
            logging.info('Companion already running')
            return
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        if not pythonw.is_file():
            raise RuntimeError('pythonw.exe not found beside this Python installation')
        subprocess.Popen([str(pythonw), str(ROOT / 'monitor.py'), '--background', '--config', args.config],
                         cwd=ROOT.parent, creationflags=subprocess.CREATE_NO_WINDOW)
        logging.info('Background companion launch requested')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Never log account responses, credentials, config contents or raw exceptions.
        logging.error('Background control failed; run monitor.py --check or inspect installation')
        if sys.stderr:
            print('Background control failed; see companion/logs/launcher.log', file=sys.stderr)
        sys.exit(1)
