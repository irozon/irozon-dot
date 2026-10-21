"""Per-user startup; do not silently replace legacy scheduled-task installations."""
from pathlib import Path
import subprocess
import sys
import winreg
import xml.etree.ElementTree as ET
import os
import re

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE = 'Irozon Dot Companion'


def scheduled_startup():
    task = subprocess.run(['schtasks', '/Query', '/TN', 'Irozon Dot', '/XML'], capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if task.returncode:
        return {'exists': False, 'enabled': False, 'managed': False, 'config': ''}
    try:
        encoding = 'utf-16' if task.stdout.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
        root = ET.fromstring(task.stdout.decode(encoding))
        flag = root.find('.//{*}Settings/{*}Enabled')
        executable = root.find('.//{*}Actions/{*}Exec/{*}Command')
        managed = executable is not None and Path(executable.text or '').name.lower() == 'irozondot.exe'
        arguments = root.find('.//{*}Actions/{*}Exec/{*}Arguments')
        arguments = arguments.text or '' if arguments is not None else ''
        explicit = re.search(r'--config\s+(?:"([^"]+)"|(\S+))', arguments)
        script = re.search(r'"([^"]+\.py)"|(\S+\.py)', arguments)
        if explicit:
            config = explicit[1] or explicit[2]
        elif managed:
            config = str(Path(os.environ['LOCALAPPDATA']) / 'Irozon Dot/local.json')
        elif script:
            config = str(Path(script[1] or script[2]).parent / 'local.json')
        else:
            config = ''
        return {'exists': True, 'enabled': flag is None or flag.text == 'true', 'managed': managed, 'config': config}
    except (ET.ParseError, UnicodeError):
        return {'exists': True, 'enabled': False, 'managed': False, 'config': ''}


def legacy_shortcut():
    return (Path.home() / 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Irozon Dot.lnk').exists()


def legacy_startup():
    task = scheduled_startup()
    return (task['exists'] and not task['managed']) or legacy_shortcut()


def legacy_enabled():
    return scheduled_startup()['enabled'] or legacy_shortcut()


def config_enabled(config):
    identity = str(Path(config).resolve()).casefold()
    task = scheduled_startup()
    task_matches = task['config'] and str(Path(task['config']).resolve()).casefold() == identity
    return bool(identity in enabled().casefold() or (task['enabled'] and task_matches))


def command(config):
    if getattr(sys, 'frozen', False):
        args = [sys.executable, 'start', '--config', str(Path(config).resolve()), '--no-browser']
    else:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        args = [str(pythonw), str(Path(__file__).with_name('app.py')), 'start',
                '--config', str(Path(config).resolve()), '--no-browser']
    return subprocess.list2cmdline(args)


def enabled(key=RUN_KEY, name=VALUE):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return winreg.QueryValueEx(handle, name)[0]
    except FileNotFoundError:
        return ''


def set_enabled(enable, config, key=RUN_KEY, name=VALUE):
    if enable and key == RUN_KEY and legacy_startup():
        raise ValueError('Legacy startup exists; migrate it explicitly before enabling this executable')
    task = scheduled_startup() if key == RUN_KEY else None
    if task and task['managed']:
        if str(Path(task['config']).resolve()).casefold() != str(Path(config).resolve()).casefold():
            raise ValueError('Startup belongs to another configuration; it has not been changed')
        if enabled():
            raise ValueError('Two startup entries exist; review them before changing startup')
        subprocess.run(['schtasks', '/Change', '/TN', 'Irozon Dot', '/ENABLE' if enable else '/DISABLE'],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
        if enable:
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, command(config))
        else:
            try:
                winreg.DeleteValue(handle, name)
            except FileNotFoundError:
                pass
