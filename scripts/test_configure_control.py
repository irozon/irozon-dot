"""Isolated credential setup tests; never touch actual configuration or devices."""
from pathlib import Path
import tempfile
import unittest
from configure_control import configure


class ControlSetupChecks(unittest.TestCase):
    def test_generation_rerun_and_allowlist_preserve_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configure(root)
            initial = (root/'home-assistant/secrets.local.yaml').read_bytes()
            configure(root, '192.168.1.30')
            self.assertEqual(initial, (root/'home-assistant/secrets.local.yaml').read_bytes())
            header = (root/'include/control_config.h').read_bytes()
            configure(root)
            self.assertEqual(header, (root/'include/control_config.h').read_bytes())

    def test_invalid_ip_does_not_create_credentials(self):
        for invalid in ('not-an-ip', '8.8.8.8', '127.0.0.1', '0.0.0.0', '224.0.0.1', '240.0.0.1'):
            with self.subTest(ip=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    configure(root, invalid)
                self.assertFalse((root/'include/control_config.h').exists())

    def test_mismatched_ha_secret_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configure(root)
            before = (root/'include/control_config.h').read_bytes()
            (root/'home-assistant/secrets.local.yaml').write_text('custom secret')
            with self.assertRaises(ValueError):
                configure(root, '192.168.1.30')
            self.assertEqual(before, (root/'include/control_config.h').read_bytes())


if __name__ == '__main__':
    unittest.main()
