"""Fail closed on release-file findings; inspect Git objects without printing data.

Exports reviewed source only, never .git, ignored site settings or firmware bins.
This is a focused guardrail, not a substitute for manual review of new secrets.
"""
import argparse
from collections import Counter
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = {'local.json', 'secrets.local.yaml', 'companion_config.h',
                 'control_config.h', 'auth.json', 'irozon-dot.yaml', 'pairing-pending.json'}
PRIVATE_SUFFIXES = {'.bin', '.elf', '.exe', '.log', '.pyc', '.pyo', '.tar', '.zip', '.7z', '.pem', '.key', '.pfx'}
EMAIL = re.compile(rb'[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}')
CREDENTIAL = re.compile(rb'(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
IP = re.compile(rb'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


def private_markers(root):
    secrets, paths = [], []
    for name in ('include/control_config.h', 'include/companion_config.h', 'companion/local.json'):
        path = root / name
        if path.exists():
            data = path.read_bytes()
            secrets.extend(re.findall(rb'[0-9a-f]{64}', data))
    # Known checkout/user paths, both separator spellings. Never echo their values.
    for path in (str(ROOT), str(Path.home())):
        for value in (path.replace('\\', '/'), path.replace('/', '\\'), path.replace('/', '\\').replace('\\', '\\\\')):
            paths.append(value.encode().lower())
    return secrets, paths


def scan(data, markers, attribution=False):
    findings = set()
    secrets, paths = markers
    if any(marker in data for marker in secrets):
        findings.add('known-private-key')
    if any(marker in data.lower() for marker in paths):
        findings.add('personal-machine-path')
    if CREDENTIAL.search(data):
        findings.add('credential-shape')
    for value in re.findall(rb'''(?i)(?:password|passwd|wifi_password|pairing_key|control_token)["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']''', data):
        if len(set(value)) > 3 and not value.startswith((b'REPLACE_', b'Not configured', b'Stored securely')):
            findings.add('literal-credential-review')
    if not attribution:
        if any(not value.lower().endswith((b'@example.com', b'@example.invalid',
                                           b'@users.noreply.github.com'))
               for value in EMAIL.findall(data)):
            findings.add('personal-email-review')
        for value in IP.findall(data):
            try:
                address = ipaddress.IPv4Address(value.decode())
            except ValueError:
                continue
            # Documentation/test subnet, standard range constants, setup and loopback.
            allowed = (address in ipaddress.IPv4Network('192.168.1.0/24') or address.is_loopback or
                       str(address) in ('192.168.4.1', '10.0.0.0', '172.16.0.0', '192.168.0.0'))
            private = any(address in ipaddress.IPv4Network(net) for net in
                          ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
            if private and not allowed:
                findings.add('private-ip-review')
    return sorted(findings)


def source_files(root):
    names = git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
    return sorted(set(name for name in names if name and (root / name).is_file()))


def audit_sources(root, markers):
    files = source_files(root)
    findings = []
    for name in files:
        path = root / name
        reasons = []
        if (path.name in PRIVATE_NAMES or path.suffix.lower() in PRIVATE_SUFFIXES or
                any(part in ('.git', '.pio', 'dist', '__pycache__', '.venv') for part in path.relative_to(root).parts)):
            reasons.append('private-or-generated-file')
        reasons += scan(path.read_bytes(), markers, name.startswith('licenses/'))
        if path.is_symlink():
            reasons.append('symlink-review')
        if reasons:
            findings.append({'file': name, 'reasons': reasons})
        if path.suffix == '.md':
            for target in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', path.read_text(encoding='utf-8')):
                if ':' in target or target.startswith('#'):
                    continue
                resolved = path.parent / target.split('#')[0]
                if not resolved.exists():
                    findings.append({'file': name, 'reasons': ['broken-local-link'], 'target': target})
    return files, findings


def audit_git(root, markers):
    types, sensitive, reachable_findings = Counter(), Counter(), Counter()
    reachable, attribution = set(), set()
    for row in git(root, 'rev-list', '--objects', '--all').decode().splitlines():
        oid, _, name = row.partition(' ')
        reachable.add(oid)
        if name.startswith('licenses/'):
            attribution.add(oid)
    reachable.update(git(root, 'for-each-ref', '--format=%(objectname)').decode().splitlines())
    for row in git(root, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)').decode().splitlines():
        oid, kind = row.split()
        types[kind] += 1
        if kind in ('blob', 'commit', 'tag'):
            data = git(root, 'cat-file', kind, oid)
            for finding in scan(data, markers):
                sensitive[finding] += 1
            if oid in reachable:
                for finding in scan(data, markers, oid in attribution):
                    reachable_findings[finding] += 1
    commits = git(root, 'rev-list', '--all', '--count').decode().strip()
    return {'objects': dict(types), 'all_object_review_counts': dict(sensitive),
            'reachable_review_counts': dict(reachable_findings),
            'reachable_commits': int(commits or 0),
            'remote_count': len(git(root, 'remote').splitlines()),
            'branch_count': len(git(root, 'for-each-ref', 'refs/heads', 'refs/remotes').splitlines()),
            'reflog_entries': len(git(root, 'reflog', 'show', '--all', '--format=%H').splitlines())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--old-repo', type=Path, help='Optional previous checkout; read-only metadata scan')
    args = parser.parse_args()
    markers = private_markers(ROOT)
    files, findings = audit_sources(ROOT, markers)
    report = {'version': (ROOT / 'VERSION').read_text().strip(), 'source_files': len(files),
              'source_findings': findings, 'git': audit_git(ROOT, markers)}
    if args.old_repo:
        report['old_git'] = audit_git(args.old_repo.resolve(), markers)
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    (output / 'SOURCE-AUDIT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))  # Filenames/categories/counts only, never matched values.
    if findings or report['git']['reachable_review_counts']:
        raise SystemExit('Release source audit failed; no archive created')
    if args.export:
        version = report['version']
        archive = output / f'irozon-dot-{version}-source.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for name in files:
                bundle.write(ROOT / name, f'irozon-dot-{version}/{name}')
        # Recheck actual exported names and bytes, not just the input list.
        with zipfile.ZipFile(archive) as bundle:
            assert len(bundle.namelist()) == len(files)
            for name in bundle.namelist():
                relative = name.split('/', 1)[1]
                assert not scan(bundle.read(name), markers, relative.startswith('licenses/'))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
        print('PASS: source export contains reviewed files only; no Git metadata or firmware binaries')
        windows = output / ('windows-' + version)
        if windows.exists():
            manifest = json.loads((windows / 'BUILD-MANIFEST.json').read_text())
            executable = windows / 'IrozonDot.exe'
            assert manifest['private_payload_audit'] == 'passed'
            assert hashlib.sha256(executable.read_bytes()).hexdigest() == manifest['sha256']
            top = {'IrozonDot.exe', 'BUILD-MANIFEST.json', 'SHA256SUMS.txt',
                   'LICENSE', 'NOTICE', 'README.md', 'THIRD-PARTY-NOTICES.txt',
                   'THIRD_PARTY_NOTICES.md', 'SECURITY.md', 'install-executable.ps1'}
            windows_archive = output / f'irozon-dot-{version}-windows-x64.zip'
            with zipfile.ZipFile(windows_archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(windows.rglob('*')):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(windows).as_posix()
                    assert not path.is_symlink()
                    assert relative in top or relative.startswith(('docs/', 'licenses/', 'home-assistant/'))
                    assert path.name not in PRIVATE_NAMES
                    if path != executable:
                        assert path.suffix.lower() not in PRIVATE_SUFFIXES
                        assert not scan(path.read_bytes(), markers, relative.startswith('licenses/'))
                    bundle.write(path, relative)
            checksum = hashlib.sha256(windows_archive.read_bytes()).hexdigest()
            (output / (windows_archive.name + '.sha256')).write_text(checksum + '  ' + windows_archive.name + '\n')
            print('PASS: versioned Windows RC archived with notices/docs; legacy running executable excluded')


if __name__ == '__main__':
    main()
