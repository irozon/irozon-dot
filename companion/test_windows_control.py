"""Isolated real Windows mutex/event tests. No listener, account access or production stop."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from windows_control import running, request_stop

CHILD = '''
import sys,time
from windows_control import Instance
i=Instance(sys.argv[1])
print('owner' if i.acquired else 'duplicate',flush=True)
try:
 if i.acquired:
  while not i.stop_requested(): time.sleep(.02)
finally: i.close()
'''


class WindowsControlChecks(unittest.TestCase):
    def spawn(self, config):
        child = subprocess.Popen([sys.executable, '-u', '-c', CHILD, str(config)],
                                 cwd=Path(__file__).parent, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup, child)
        return child

    @staticmethod
    def cleanup(child):
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        child.stdout.close()
        child.stderr.close()

    def test_singleton_duplicate_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'isolated.json'
            child = self.spawn(config)
            self.assertEqual(child.stdout.readline().strip(), 'owner')
            self.assertTrue(running(config))
            duplicate = self.spawn(config)
            self.assertEqual(duplicate.stdout.readline().strip(), 'duplicate')
            duplicate.wait(timeout=5)
            self.assertTrue(request_stop(config))
            child.wait(timeout=5)
            self.assertFalse(running(config))

    def test_crash_recovery_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'isolated.json'
            child = self.spawn(config)
            self.assertEqual(child.stdout.readline().strip(), 'owner')
            child.terminate()
            child.wait(timeout=5)
            replacement = self.spawn(config)
            self.assertEqual(replacement.stdout.readline().strip(), 'owner')
            self.assertTrue(request_stop(config))
            replacement.wait(timeout=5)
            self.assertFalse(running(config))

    def test_stop_is_scoped_and_probe_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'isolated.json'
            child = self.spawn(config)
            self.assertEqual(child.stdout.readline().strip(), 'owner')
            self.assertFalse(request_stop(Path(directory) / 'other.json'))
            self.assertTrue(running(config))
            self.assertIsNone(child.poll())
            self.assertTrue(request_stop(config))
            child.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
