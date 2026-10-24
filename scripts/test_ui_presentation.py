"""Host-side checks for the four current 240x240 display previews."""
import unittest

from preview import ROOT, render


class PresentationChecks(unittest.TestCase):
    def test_each_display_preview_is_round_screen_sized(self):
        for mode in ('green', 'classic', 'companion', 'analog'):
            with self.subTest(mode=mode):
                self.assertEqual(render(mode).size, (240, 240))

    def test_companion_preview_covers_distinct_expression_examples(self):
        happy = render('companion', expression='happy')
        for expression in ('curious', 'surprised', 'sad', 'sleepy', 'sleeping', 'waking'):
            with self.subTest(expression=expression):
                self.assertNotEqual(happy.tobytes(), render('companion', expression=expression).tobytes())

    def test_four_modes_keep_the_saved_identifiers(self):
        source = (ROOT / 'include/ui.h').read_text()
        self.assertIn('Green = 0, Classic = 3, Companion = 4, AnalogClock = 5', source)
        settings = (ROOT / 'companion/settings.py').read_text()
        self.assertIn("'analog': 'Analog Clock'", settings)

    def test_clock_draws_hands_and_only_erases_local_previous_hand_pixels(self):
        source = (ROOT / 'src/ui.cpp').read_text()
        clock = source.split('void drawAnalogClock(', 1)[1].split('\nvoid heading(', 1)[0]
        self.assertIn('clockHand(clockSecondX, clockSecondY, 1.5f, classicBackground)', clock)
        self.assertIn('clockHand(clockSecondX, clockSecondY, 1.5f, clockCyan)', clock)
        self.assertNotIn('fillScreen', clock)
        main = (ROOT / 'src/main.cpp').read_text()
        self.assertIn('CET-1CEST,M3.5.0/2,M10.5.0/3', main)


if __name__ == '__main__':
    unittest.main()
