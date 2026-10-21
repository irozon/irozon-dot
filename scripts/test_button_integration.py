"""Source-contract checks complement the production C++ timing static_asserts.

These do not emulate SPI, NVS, or the unflashed firmware on physical hardware.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ButtonIntegrationChecks(unittest.TestCase):
    def test_button_and_http_share_persisted_power(self):
        main = (ROOT / 'src/main.cpp').read_text()
        control = (ROOT / 'src/control.cpp').read_text()
        ui = (ROOT / 'src/ui.cpp').read_text()
        self.assertIn('ui::setDisplayOn(!ui::displayOn());', main)
        self.assertIn('ui::setDisplayOn(command == Command::On)', control)
        self.assertIn('next.on = ui::displayOn();', control)
        self.assertLess(control.index('ui::setDisplayOn('), control.index('next.on ='))
        self.assertIn('prefs.begin("irozon-ui", false)', ui)
        self.assertIn('prefs.getBool("power", true)', ui)
        self.assertIn('prefs.putBool("power", enabled)', ui)
        self.assertIn('if (enabled == displayEnabled) return;', ui)
        self.assertIn('tft.sleep();', ui)
        self.assertIn('tft.wakeup();', ui)

    def test_reset_is_exclusive_and_only_erases_wifi(self):
        main = (ROOT / 'src/main.cpp').read_text()
        self.assertEqual(main.count('wifi.resetSettings();'), 1)
        self.assertEqual(main.count('ESP.restart();'), 1)
        reset = main.split('if (gesture.resetWifi) {', 1)[1].split('}', 1)[0]
        self.assertIn('wifi.resetSettings();', reset)
        self.assertIn('ESP.restart();', reset)
        self.assertIn('return;', reset)
        self.assertNotIn('cycleMode', reset)
        self.assertNotIn('setDisplayOn', reset)
        for path in (ROOT / 'src').glob('*.cpp'):
            source = path.read_text()
            self.assertNotIn('nvs_flash_erase', source)
            self.assertNotIn('prefs.clear()', source)

    def test_boot_input_and_overflow_safety(self):
        source = (ROOT / 'src/button.cpp').read_text()
        self.assertIn('pinMode(config::kBootPin, INPUT_PULLUP)', source)
        self.assertNotIn('digitalWrite(config::kBootPin', source)
        self.assertEqual(source.count('logic.cancelUntilRelease('), 2)
        self.assertIn('if (action & Power) ++result.powerToggles;', source)
        self.assertIn('if (action & Reset) result.resetWifi = true;', source)
        self.assertIn('#include "button_checks.h"', source)
        self.assertIn('if (gesture.taps)', (ROOT / 'src/main.cpp').read_text())


if __name__ == '__main__':
    unittest.main()
