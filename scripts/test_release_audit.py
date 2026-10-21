"""Prove release gates reject private history and preserve required attribution."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import release_audit


class HistoryChecks(unittest.TestCase):
    def test_deleted_private_data_is_still_reported_in_reachable_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)
            git('init', '-q')
            git('config', 'user.name', 'Test contributors')
            git('config', 'user.email', 'contributors@example.invalid')
            licenses = root / 'licenses'
            licenses.mkdir()
            # Deliberately exercise a non-allowlisted email without a literal
            # address in the source candidate itself (all fixture domains are reserved).
            (licenses / 'notice.txt').write_text('Copyright upstream@' + 'example.org')
            private = root / 'temporary.txt'
            private.write_text('private token sentinel for isolated history test')
            git('add', '.')
            git('commit', '-qm', 'fixture')
            private.unlink()
            git('add', '-u')
            git('commit', '-qm', 'remove fixture')
            report = release_audit.audit_git(root, ([b'private token sentinel'], []))
            self.assertEqual(report['reachable_review_counts'], {'known-private-key': 1})
            # License copyright emails are required attribution, not owner credentials.
            self.assertNotIn('personal-email-review', report['reachable_review_counts'])

    def test_generated_and_private_source_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.check_call(['git', '-C', str(root), 'init', '-q'])
            for name in ('firmware.bin', 'firmware.elf', 'control_config.h',
                         'secrets.local.yaml', 'public.py'):
                (root / name).write_text('isolated fixture')
            files, findings = release_audit.audit_sources(root, ([], []))
            self.assertEqual(len(files), 5)
            self.assertEqual({row['file'] for row in findings},
                             {'firmware.bin', 'firmware.elf', 'control_config.h', 'secrets.local.yaml'})
            self.assertTrue(all('private-or-generated-file' in row['reasons'] for row in findings))


if __name__ == '__main__':
    unittest.main()
