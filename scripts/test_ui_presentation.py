"""Pinned-font bounds/pixel checks; physical panel acceptance still needs a flash."""
import unittest
import math
from PIL import Image, ImageChops, ImageDraw
from preview import ROOT, heading_font, layout, render, blink_at, mouth_offset_at, gauge_text_boxes


class PresentationChecks(unittest.TestCase):
    def test_heading_bounds_and_ink(self):
        # Wide glyphs, narrow names, descenders, punctuation, and every supported
        # printable ASCII glyph repeated to both supported length boundaries.
        cases = ['D', 'Dot', 'Irozon Dot', 'ABCDEFGHIJKLMNOPQR', 'gjpqy.,-_!?']
        cases += ['W'*length for length in range(1, 19)]
        cases += [chr(c)*length for c in range(32, 127) for length in (1, 18)]
        for mode in ('green', 'blue', 'orange', 'classic'):
            for name in cases:
                font, scale, rect = heading_font(name, mode)
                x, y, w, h = rect
                radius = layout['ClassicHeadingSafeRadius' if mode == 'classic' else 'HeadingSafeRadius']
                for xx in (x, x+w-1):
                    for yy in (y, y+h-1):
                        self.assertLess((xx-120)**2+(yy-120)**2, radius**2, (name, mode, rect))
                note = layout['ClassicNoteY' if mode == 'classic' else 'NoteY']
                self.assertLess(y+h, note-5, (name, mode))
                image = Image.new('RGB', (240, 240))
                font.draw_scaled(image, name, 120,
                                 layout['ClassicHeadingY' if mode == 'classic' else 'HeadingY'],
                                 (255, 255, 255), scale)
                bounds = image.getbbox()
                if bounds:
                    self.assertGreaterEqual(bounds[0], x, (name, mode, rect, bounds))
                    self.assertGreaterEqual(bounds[1], y, (name, mode, rect, bounds))
                    self.assertLessEqual(bounds[2], x+w, (name, mode, rect, bounds))
                    self.assertLessEqual(bounds[3], y+h, (name, mode, rect, bounds))
            font, scale, _ = heading_font('Dot', mode)
            self.assertGreater(font.height * scale, 22)

    def test_animation_changes_only_mouth_and_preserves_unreliable_face(self):
        for session in (82, 50, 30, None):
            for status in ('', 'PARTIAL', 'STALE', 'OFFLINE', 'NO DATA', 'WIFI SETUP'):
                for mode in ('green', 'blue', 'orange', 'classic'):
                    rest = render(session=session, status=status, mode=mode)
                    moved = render(session=session, status=status, mode=mode, mouth_offset=7)
                    bounds = ImageChops.difference(rest, moved).getbbox()
                    if mode != 'green' or session is None or status not in ('', 'PARTIAL'):
                        self.assertIsNone(bounds, (session, status, mode))
                    else:
                        self.assertIsNotNone(bounds)
                        self.assertGreaterEqual(bounds[0], 120-layout['ValueWidth']//2)
                        self.assertGreaterEqual(bounds[1], layout['MouthY']-layout['MouthBufferOriginY'])
                        self.assertLessEqual(bounds[2], 120+layout['ValueWidth']//2)
                        self.assertLessEqual(bounds[3], layout['MouthY']-layout['MouthBufferOriginY']+layout['ValueHeight'])

    def test_hidden_heading_removes_only_heading_pixels_in_all_layouts(self):
        for mode in ('green', 'blue', 'orange', 'classic'):
            difference = ImageChops.difference(render(mode=mode), render(mode=mode, heading='')).getbbox()
            self.assertIsNotNone(difference)
            self.assertLess(difference[3], layout['ClassicNoteY' if mode == 'classic' else 'NoteY']-5)

    def test_firmware_heading_persistence_contract_includes_standby_and_presence(self):
        # Source contract only: physical NVS power-cycle acceptance needs a flash.
        source = (ROOT / 'src/ui.cpp').read_text()
        draw = source.split('void ui::draw(', 1)[1]
        self.assertLess(draw.index('data.heading.configured'), draw.index('if (!displayEnabled)'))
        self.assertIn('prefs.putString("heading", displayHeading.text)', draw)
        self.assertIn('prefs.isKey("heading")', source)
        self.assertIn('displayHeading.assign(prefs.getString("heading", "").c_str())', source)
        self.assertIn('heading(displayHeading.text, classic, changedMode)', draw)
        self.assertNotIn('data.heading[0] ?', source)

    def test_blink_keeps_all_text_pixels_stationary_and_restores_exactly(self):
        for weekly, session in ((0, 82), (25, 50), (68, 30), (100, 100)):
            rest = render(weekly, session, '')
            for t in (*range(0, 1001, 80), 500, 1000):
                frame = render(weekly, session, '', mouth_offset=mouth_offset_at(t), blink=blink_at(t))
                for cx in (layout['LeftX'], layout['RightX']):
                    for x, y, w, h in gauge_text_boxes(cx):
                        self.assertEqual(rest.crop((x, y, x+w, y+h)).tobytes(),
                                         frame.crop((x, y, x+w, y+h)).tobytes(), (weekly, session, t))
                difference = ImageChops.difference(rest, frame)
                draw = ImageDraw.Draw(difference)
                for cx in (layout['LeftX'], layout['RightX']):
                    r = layout['Radius']
                    draw.rectangle((cx-r, layout['GaugeY']-r, cx+r, layout['GaugeY']+r), fill=0)
                draw.rectangle((80, 183, 159, 212), fill=0)
                self.assertIsNone(difference.getbbox(), (weekly, session, t))
                if t in (0, 1000):
                    self.assertEqual(rest.tobytes(), frame.tobytes())

    def test_blink_endpoint_preserves_original_logical_progress(self):
        # Independently invert the transformed endpoint for every whole percent
        # and every discrete compression, including quadrant/wrap boundaries.
        for compression in range(36):
            scale = (layout['Radius']-compression)/layout['Radius']
            for value in range(101):
                theta = math.radians(270+3.6*value)
                x, y = math.cos(theta), math.sin(theta)*scale
                physical = math.atan2(y, x)
                mapped = math.atan2(math.sin(physical)/scale, math.cos(physical))
                error = math.atan2(math.sin(mapped-theta), math.cos(mapped-theta))
                self.assertAlmostEqual(error, 0, places=10)
        # Compositor mask includes the original circle's raster edge, and every
        # writable pixel remains inside the outer rim and out of the other eye.
        radius = layout['Radius']
        for cx in (layout['LeftX'], layout['RightX']):
            for dy in range(-radius, radius+1):
                for dx in range(-radius, radius+1):
                    if dx*dx+dy*dy <= radius*(radius+1):
                        self.assertLess((cx+dx-120)**2+dy*dy, layout['RimRadius']**2)

    def test_face_cancels_when_either_reading_is_unreliable_and_other_modes_are_unchanged(self):
        for mode in ('green', 'blue', 'orange', 'classic'):
            for weekly, session, status in ((None, 82, 'PARTIAL'), (68, None, 'PARTIAL'),
                                            (68, 82, 'STALE'), (68, 82, 'OFFLINE'),
                                            (None, None, 'NO DATA'), (68, 82, 'WIFI SETUP')):
                self.assertEqual(render(weekly, session, status, mode=mode).tobytes(),
                                 render(weekly, session, status, mode=mode, mouth_offset=7, blink=35).tobytes())
            if mode != 'green':
                self.assertEqual(render(mode=mode).tobytes(),
                                 render(mode=mode, mouth_offset=7, blink=35).tobytes())


if __name__ == '__main__':
    unittest.main()
