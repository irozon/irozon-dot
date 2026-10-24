"""Audit the explicit frozen payload; emit names/hashes only, never private values."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import marshal
import re
import shutil
import sys
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path)
    args = parser.parse_args()
    version = (ROOT / 'VERSION').read_text().strip()
    path = args.executable or ROOT / 'dist' / ('windows-' + version) / 'IrozonDot.exe'
    archive = CArchiveReader(str(path))
    names = list(archive.toc)
    forbidden = ('local.json', 'secrets.local.yaml', 'control_config.h', 'companion_config.h',
                 'auth.json', 'companion.log', 'launcher.log')
    assert not any(any(part in name.lower() for part in forbidden) for name in names), 'Private filename in payload'
    signatures = []
    for file in [ROOT / 'include/control_config.h', ROOT / 'include/companion_config.h']:
        if file.exists():
            signatures.extend(re.findall(rb'"([0-9a-f]{64})"', file.read_bytes()))
    local = ROOT / 'companion/local.json'
    if local.exists():
        raw = json.loads(local.read_text())
        signatures.extend(raw[key].encode() for key in ('pairing_key', 'control_token') if raw.get(key))
    modules = 0
    machine_paths = []
    for private_path in (str(ROOT), str(Path.home())):
        for value in (private_path.replace('\\', '/'), private_path.replace('/', '\\')):
            machine_paths.append(value.encode().lower())
    def inspect_payload(data):
        assert not any(secret in data for secret in signatures), 'Private value in packaged payload'
        assert not any(path in data.lower() for path in machine_paths), 'Personal build path in packaged payload'
    for name in names:
        if name.startswith('PYZ'):
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc:
                data = marshal.dumps(pyz.extract(module))
                inspect_payload(data)
                modules += 1
        else:
            data = archive.extract(name) or b''
            inspect_payload(data)
    toc = ast.literal_eval((ROOT / '.pio/companion-pyinstaller/IrozonDot/PKG-00.toc').read_text())
    dependencies = []
    def inspect(value):
        if isinstance(value, (list, tuple)):
            if len(value) >= 3 and isinstance(value[0], str) and value[0].lower().endswith(('.dll', '.pyd')):
                assert 'codex-runtimes' not in str(value[1]), 'Unrelated runtime DLL from developer PATH'
                dependencies.append(value[0])
            else:
                for item in value:
                    inspect(item)
    inspect(toc)
    manifest = {'file': path.name, 'bytes': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'version': (ROOT / 'VERSION').read_text().strip(),
                'architecture': 'Windows x64', 'python': '3.14.6', 'pyinstaller': '6.22.3',
                'pyserial': '3.5', 'native_dependencies': sorted(set(dependencies)),
                'private_payload_audit': 'passed', 'python_modules_inspected': modules}
    (path.parent / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (path.parent / 'SHA256SUMS.txt').write_text(manifest['sha256'] + '  ' + path.name + '\n')
    shutil.copyfile(ROOT / 'LICENSE', path.parent / 'LICENSE')
    shutil.copyfile(ROOT / 'companion/THIRD-PARTY-NOTICES.txt', path.parent / 'THIRD-PARTY-NOTICES.txt')
    shutil.copyfile(ROOT / 'NOTICE', path.parent / 'NOTICE')
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.md', path.parent / 'THIRD_PARTY_NOTICES.md')
    shutil.copyfile(ROOT / 'SECURITY.md', path.parent / 'SECURITY.md')
    shutil.copyfile(ROOT / 'companion/install-executable.ps1', path.parent / 'install-executable.ps1')
    shutil.copytree(ROOT / 'licenses', path.parent / 'licenses', dirs_exist_ok=True)
    shutil.rmtree(path.parent / 'docs', ignore_errors=True)
    shutil.copytree(ROOT / 'docs', path.parent / 'docs', dirs_exist_ok=True)
    (path.parent / 'home-assistant').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'home-assistant/irozon-dot.example.yaml',
                    path.parent / 'home-assistant/irozon-dot.example.yaml')
    if (ROOT / 'docs/windows-companion-distribution.md').exists():
        guide = (ROOT / 'docs/windows-companion-distribution.md').read_text(encoding='utf-8')
        (path.parent / 'README.md').write_text(guide, encoding='utf-8')
    else:
        shutil.copyfile(ROOT / 'README.md', path.parent / 'README.md')
    print('PASS: explicit package payload contains no private config, known personal keys or unrelated runtime DLLs')
    print('Executable:', manifest['bytes'], 'bytes;', round(manifest['bytes']/1048576, 2), 'MiB')
    print('SHA256:', manifest['sha256'])


if __name__ == '__main__':
    main()
