"""Development-only YAML/Jinja checks; run in .pio/ha-validation, not on ESP32."""
from pathlib import Path
import unittest
import yaml
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[1]


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor('!secret', lambda loader, node: ('secret', loader.construct_scalar(node)))


class HomeAssistantChecks(unittest.TestCase):
    def setUp(self):
        self.config = yaml.load((ROOT/'home-assistant/irozon-dot.example.yaml').read_text(), Loader=Loader)
        self.env = NativeEnvironment()
        self.env.filters['bool'] = lambda value, default=False: value if isinstance(value, bool) else default

    def test_secret_headers_and_rest_routes(self):
        for item in self.config['rest']+list(self.config['rest_command'].values()):
            self.assertEqual(item['headers']['Authorization'], ('secret', 'irozon_dot_authorization'))
        routes = self.config['rest_command']
        for item in routes.values():
            self.assertEqual(item['method'], 'POST')
        for name, slug in [('Stacked Numbers','green'),('Classic Split Arc','classic'),
                           ('Companion','companion'),('Analog Clock','analog')]:
            url = self.env.from_string(routes['irozon_dot_mode']['url']).render(mode=name)
            self.assertEqual(url, 'http://192.168.1.20:8080/api/display/mode/'+slug)

    def test_confirmed_state_and_offline_availability(self):
        for entity in (self.config['template'][0]['switch'][0], self.config['template'][0]['select'][0]):
            for state in ('connected','unavailable','unknown','offline'):
                self.assertEqual(self.env.from_string(entity['availability']).render(
                    is_state=lambda name, expected: state == expected), state == 'connected')
        switch = self.config['template'][0]['switch'][0]
        for on in (True, False):
            self.assertEqual(self.env.from_string(switch['state']).render(state_attr=lambda *a: on), on)
        select = self.config['template'][0]['select'][0]
        options = self.env.from_string(select['options']).render()
        self.assertEqual(options, ['Stacked Numbers','Classic Split Arc','Companion','Analog Clock'])
        for option in options:
            self.assertEqual(self.env.from_string(select['state']).render(state_attr=lambda *a: option), option)

    def test_single_follower_preserves_lights_and_restores_on_start_or_recovery(self):
        self.assertEqual(len(self.config['automation']), 1)
        follower = self.config['automation'][0]
        triggers = follower['triggers']
        light_triggers = [t for t in triggers if t.get('entity_id') == 'light.example_room']
        self.assertEqual({t['to'] for t in light_triggers}, {'on', 'off'})
        self.assertIn({'trigger': 'homeassistant', 'event': 'start'}, triggers)
        self.assertIn({'trigger': 'state', 'entity_id': 'sensor.irozon_dot_control', 'to': 'connected'}, triggers)
        action = follower['actions'][-1]
        self.assertEqual(action['target'], {'entity_id': 'switch.irozon_dot_display'})
        for on in (True, False):
            expected = 'switch.turn_on' if on else 'switch.turn_off'
            self.assertEqual(self.env.from_string(action['action']).render(is_state=lambda *args: on), expected)
        self.assertEqual(follower['mode'], 'restart')


if __name__ == '__main__':
    unittest.main()
