"""Exercise the real PowerShell installer in temporary directories; never launch it."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerChecks(unittest.TestCase):
    def test_bundle_notices_shortcuts_and_existing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'bundle'
            bundle.mkdir()
            script = bundle / 'install-executable.ps1'
            script.write_bytes((ROOT / 'companion/install-executable.ps1').read_bytes())
            for name in ('IrozonDot.exe', 'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md',
                         'THIRD-PARTY-NOTICES.txt', 'SECURITY.md', 'README.md',
                         'BUILD-MANIFEST.json', 'SHA256SUMS.txt'):
                (bundle / name).write_text('isolated fixture: ' + name)
            for name in ('docs', 'licenses', 'home-assistant'):
                (bundle / name).mkdir()
            (bundle / 'docs/guide.md').write_text('guide')
            (bundle / 'licenses/copyright.txt').write_text('required notice')
            (bundle / 'home-assistant/irozon-dot.example.yaml').write_text('example')
            (bundle / 'home-assistant/secrets.local.yaml').write_text('private fixture')
            (bundle / 'local.json').write_text('private fixture')
            destination, shortcuts = root / 'installed', root / 'shortcuts'
            command = ['powershell', '-NoProfile', '-File', str(script),
                       '-Destination', str(destination), '-ShortcutsDirectory', str(shortcuts)]
            # An incomplete bundle must fail before creating a destination or shortcuts.
            notice = bundle / 'NOTICE'
            original = notice.read_bytes()
            notice.unlink()
            result = subprocess.run(command, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(destination.exists())
            self.assertFalse(shortcuts.exists())
            notice.write_bytes(original)
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual((destination / 'IrozonDot.exe').read_bytes(),
                             (bundle / 'IrozonDot.exe').read_bytes())
            self.assertEqual((destination / 'licenses/copyright.txt').read_text(), 'required notice')
            self.assertTrue((destination / 'NOTICE').exists())
            self.assertTrue((destination / 'docs/guide.md').exists())
            self.assertTrue((destination / 'home-assistant/irozon-dot.example.yaml').exists())
            self.assertFalse((destination / 'home-assistant/secrets.local.yaml').exists())
            self.assertFalse((destination / 'local.json').exists())
            self.assertEqual(len(list(shortcuts.glob('*.lnk'))), 4)
            before = {p.relative_to(root): p.read_bytes() for folder in (destination, shortcuts)
                      for p in folder.rglob('*') if p.is_file()}
            result = subprocess.run(command, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes()
                                     for folder in (destination, shortcuts)
                                     for p in folder.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
