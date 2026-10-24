"""Host-side checks for the three current 240x240 display previews."""
import unittest

from preview import ROOT, render


class PresentationChecks(unittest.TestCase):
    def test_each_display_preview_is_round_screen_sized(self):
        for mode in ('green', 'classic', 'companion'):
            with self.subTest(mode=mode):
                self.assertEqual(render(mode).size, (240, 240))

    def test_companion_preview_covers_distinct_expression_examples(self):
        happy = render('companion', expression='happy')
        for expression in ('curious', 'surprised', 'sad', 'sleepy', 'sleeping', 'waking'):
            with self.subTest(expression=expression):
                self.assertNotEqual(happy.tobytes(), render('companion', expression=expression).tobytes())

    def test_three_modes_keep_the_saved_identifiers_and_removed_ids_fall_back(self):
        source = (ROOT / 'include/ui.h').read_text()
        self.assertIn('Green = 0, Classic = 3, Companion = 4', source)
        self.assertNotIn('AnalogClock', source)
        firmware = (ROOT / 'src/ui.cpp').read_text()
        self.assertIn('saved == static_cast<uint8_t>(Mode::Companion) ? Mode::Companion : Mode::Green', firmware)
        self.assertNotIn('drawAnalogClock', firmware)


if __name__ == '__main__':
    unittest.main()
