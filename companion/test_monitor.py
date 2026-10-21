"""Focused normalization, freshness and signed loopback HTTP checks. No LAN bind."""
import copy
import hashlib
import hmac
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer
from monitor import normalize, Source, handler_for

NOW = 1792503506


def fixture():
    return {'rateLimitsByLimitId': {'codex': {'limitId': 'codex',
            'primary': {'usedPercent': 15, 'windowDurationMins': 300, 'resetsAt': NOW + 7200},
            'secondary': {'usedPercent': 18, 'windowDurationMins': 10080, 'resetsAt': NOW + 500000}}}}


class UsageChecks(unittest.TestCase):
    def test_used_to_remaining_and_swap(self):
        value = fixture()
        expected = normalize(value, NOW)
        self.assertEqual(expected['session']['remaining'], 85)
        self.assertEqual(expected['weekly']['remaining'], 82)
        bucket = value['rateLimitsByLimitId']['codex']
        bucket['primary'], bucket['secondary'] = bucket['secondary'], bucket['primary']
        self.assertEqual(normalize(value, NOW), expected)

    def test_unknown_and_nullable_windows(self):
        value = fixture()
        bucket = value['rateLimitsByLimitId']['codex']
        bucket['primary']['windowDurationMins'] = 60
        bucket['secondary'] = None
        self.assertEqual(normalize(value, NOW), {'session': None, 'weekly': None})

    def test_malformed_values_and_expiry(self):
        for bad in (None, True, -1, 101, float('nan'), float('inf'), '15'):
            value = fixture()
            value['rateLimitsByLimitId']['codex']['primary']['usedPercent'] = bad
            self.assertIsNone(normalize(value, NOW)['session'])
        for bad in (None, True, NOW, NOW - 1, NOW + 99999999, str(NOW + 60)):
            value = fixture()
            value['rateLimitsByLimitId']['codex']['primary']['resetsAt'] = bad
            self.assertIsNone(normalize(value, NOW)['session'])

    def test_zero_full_fractional_and_bucket(self):
        for used in (0, 100, 17.25):
            value = fixture()
            value['rateLimitsByLimitId']['codex']['primary']['usedPercent'] = used
            self.assertEqual(normalize(value, NOW)['session']['remaining'], 100 - used)
        with self.assertRaises(ValueError):
            normalize({'rateLimitsByLimitId': {'other': fixture()}}, NOW)
        value = fixture()['rateLimitsByLimitId']['codex']
        self.assertEqual(normalize({'rateLimits': value}, NOW)['weekly']['remaining'], 82)
        value['secondary'] = copy.deepcopy(value['primary'])
        with self.assertRaises(ValueError):
            normalize({'rateLimits': value}, NOW)

    def test_freshness_failure_and_no_refill(self):
        source = Source([])
        with patch('monitor.time.time', return_value=NOW):
            self.assertEqual(source.snapshot('x')['status'], 'unavailable')
        source.sample = normalize(fixture(), NOW)
        source.sample_time, source.error = NOW, False
        for age, status in ((0, 'live'), (150, 'live'), (151, 'stale'), (-1, 'stale')):
            with patch('monitor.time.time', return_value=NOW + age):
                self.assertEqual(source.snapshot('x')['status'], status)
        source.error = True
        with patch('monitor.time.time', return_value=NOW):
            self.assertEqual(source.snapshot('x')['status'], 'stale')
        with patch('monitor.time.time', return_value=NOW + 7200):
            self.assertIsNone(source.snapshot('x')['session'])

    def test_loopback_signature_scope_and_schema(self):
        source = Source([])
        source.sample, source.sample_time, source.error = normalize(fixture(), NOW), NOW, False
        key = bytes(range(32))  # Synthetic test key, never paired with the device.
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(source, key, '127.0.0.1'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/usage?nonce='
        try:
            bodies = []
            with patch('monitor.time.time', return_value=NOW):
                for nonce in ('a' * 32, 'b' * 32):
                    with urlopen(url + nonce, timeout=3) as response:
                        body = response.read()
                        signature = response.headers['X-Irozon-Signature']
                    self.assertTrue(hmac.compare_digest(signature, hmac.new(key, body, hashlib.sha256).hexdigest()))
                    self.assertFalse(hmac.compare_digest(signature, hmac.new(key, body + b' ', hashlib.sha256).hexdigest()))
                    data = json.loads(body)
                    self.assertEqual(data['nonce'], nonce)
                    self.assertEqual(set(data), {'version', 'source', 'test_data', 'nonce',
                                                'server_time', 'sampled_at', 'status', 'weekly', 'session'})
                    self.assertFalse(data['test_data'])
                    self.assertEqual(data['session']['remaining'], 85)
                    bodies.append(body)
            self.assertNotEqual(bodies[0], bodies[1])  # Fresh nonce prevents response replay.
            with self.assertRaises(HTTPError) as error:
                urlopen(url + 'bad', timeout=3)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        denied = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(source, key, '192.168.1.20'))
        thread = threading.Thread(target=denied.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(f'http://127.0.0.1:{denied.server_port}/usage?nonce=' + 'c' * 32, timeout=3)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        finally:
            denied.shutdown()
            denied.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
