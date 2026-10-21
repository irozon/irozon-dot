# Explicit allowlist: never collect local.json, headers, logs or account credentials.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'app.py')], pathex=[str(root)],
             binaries=[], datas=[(str(root / 'web' / name), 'web') for name in
                                  ('index.html', 'app.js', 'style.css')],
             hiddenimports=['serial.tools.list_ports_windows'], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['tkinter', 'pytest', 'PIL', 'yaml'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='IrozonDot', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=True, uac_admin=False)
