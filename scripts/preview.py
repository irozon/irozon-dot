"""Host layout check using the pinned LovyanGFX bitmap fonts; never uses USB.

Requires Pillow (development only). Run after `pio run -e supermini`.
This is a layout preview, not an ESP32 / GC9A01 emulator.
"""
import math
import re
from pathlib import Path
import struct
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / '.pio/libdeps/supermini/LovyanGFX/src/lgfx/Fonts'
SOURCE = (ROOT / 'src/ui.cpp').read_text()


def clean(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)


def array(text, name):
    body = re.search(r'\b' + name + r'\[.*?\].*?=\s*\{(.*?)\};', clean(text), re.S)[1]
    return [int(n, 0) for n in re.findall(r'0x[0-9A-Fa-f]+|\b\d+\b', clean(body))]


class BitmapFont:
    def __init__(self, name):
        self.name = name
        if name.startswith('FreeSans'):
            text = (FONTS / f'GFXFF/{name}.h').read_text()
            self.bits = array(text, name + 'Bitmaps')
            body = re.search(name + r'Glyphs\[\].*?=\s*\{(.*?)\};', text, re.S)[1]
            self.glyphs = [list(map(int, re.findall(r'-?\d+', row)))
                           for row in re.findall(r'\{([^{}]+)\}', body)]
            self.above = max(-g[5] for g in self.glyphs)
            self.height = self.above + max(g[2] + g[5] for g in self.glyphs)
        elif name == 'Font2':
            text = (FONTS / 'Font16.h').read_text()
            text = re.sub(r'#else.*?#endif', '', text, flags=re.S)
            self.widths = array(text, 'widtbl_f16')
            self.rows = {int(code, 16): array(text, 'chr_f16_' + code)
                         for code in set(re.findall(r'chr_f16_([0-9A-Fa-f]+)\[', text))}
            self.height = 16
        else:
            self.bits = array((FONTS / 'glcdfont.h').read_text(), 'font')
            self.height = 8

    def advance(self, char):
        if self.name.startswith('FreeSans'):
            return self.glyphs[ord(char) - 32][3]
        return self.widths[ord(char) - 32] if self.name == 'Font2' else 6

    def measured_width(self, text, scale=1):
        # LovyanGFX uses per-glyph 16.16 advances, including ink overhang.
        fixed = int(65536 * scale)
        left = right = 0
        for char in text:
            if self.name.startswith('FreeSans'):
                _, width, _, advance, dx, _ = self.glyphs[ord(char) - 32]
            else:
                width = advance = self.advance(char)
                dx = 0
            offset = dx * fixed >> 16
            if left == right == 0 and dx < 0:
                left = right = -offset
            right = left + max(advance * fixed >> 16, (width * fixed >> 16) + offset)
            left += advance * fixed >> 16
        return right

    def draw_scaled(self, image, text, cx, cy, color, scale):
        fixed = int(65536 * scale)
        x = cx - self.measured_width(text, scale) // 2
        top = cy - (self.height * fixed >> 16) // 2
        if self.name.startswith('FreeSans'):
            dx = self.glyphs[ord(text[0]) - 32][4]
            if dx < 0:
                x += (-dx * fixed) >> 16
        draw = ImageDraw.Draw(image)
        for char in text:
            if self.name.startswith('FreeSans'):
                offset, w, h, advance, dx, dy = self.glyphs[ord(char) - 32]
                yoffset = self.above + dy
                pixels = [(col, row) for row in range(h) for col in range(w)
                          if self.bits[offset + (row*w+col)//8] & (0x80 >> ((row*w+col)%8))]
            elif self.name == 'Font2':
                advance = w = self.advance(char)
                dx = yoffset = 0
                stride = (w + 6) // 8
                pixels = [(col, row) for row in range(16) for col in range(w-1)
                          if self.rows[ord(char)][row*stride+col//8] & (0x80 >> (col%8))]
            else:
                advance, dx, yoffset = 6, 0, 0
                pixels = [(col, row) for col in range(5) for row in range(8)
                          if self.bits[ord(char)*5+col] & (1 << row)]
            for col, row in pixels:
                xx = x + (dx * fixed >> 16) + (col * fixed >> 16)
                yy = top + ((yoffset + row) * fixed >> 16)
                right = x + (dx * fixed >> 16) + ((col+1) * fixed >> 16)
                bottom = top + ((yoffset + row+1) * fixed >> 16)
                # The driver preserves one pixel when downscaling thin strokes.
                draw.rectangle((xx, yy, max(xx, right-1), max(yy, bottom-1)), fill=color)
            x += advance * fixed >> 16

    def draw(self, image, text, x, y, color, box=None):
        width = sum(self.advance(c) for c in text)
        if box:
            assert width <= box[2], (text, width, box)
            assert self.height <= box[3], (self.name, self.height, box)
        x -= width // 2
        top = y - self.height // 2

        def pixel(px, py):
            if box:
                bx, by, bw, bh = box
                assert bx <= px < bx + bw and by <= py < by + bh, (text, px, py, box)
            image.putpixel((px, py), color)

        for char in text:
            if self.name.startswith('FreeSans'):
                offset, w, h, _, dx, dy = self.glyphs[ord(char) - 32]
                for bit in range(w * h):
                    if self.bits[offset + bit // 8] & (0x80 >> (bit % 8)):
                        pixel(x + dx + bit % w, top + self.above + dy + bit // w)
            elif self.name == 'Font2':
                w = self.advance(char)
                stride = (w + 6) // 8
                rows = self.rows[ord(char)]
                for row in range(16):
                    for col in range(w - 1):
                        if rows[row * stride + col // 8] & (0x80 >> (col % 8)):
                            pixel(x + col, top + row)
            else:
                for col in range(5):
                    for row in range(8):
                        if self.bits[ord(char) * 5 + col] & (1 << row):
                            pixel(x + col, top + row)
            x += self.advance(char)


def rgb565(hex_value):
    # Show the actual RGB565 quantization used by the firmware.
    n = int(hex_value, 16)
    return (((n >> 19) & 31) * 255 // 31,
            ((n >> 10) & 63) * 255 // 63, ((n >> 3) & 31) * 255 // 31)


colors = {name: rgb565(value) for name, value in
          re.findall(r'uint16_t (\w+) = rgb\(0x([0-9A-F]+)\)', SOURCE)}
fonts = {n: BitmapFont(n) for n in ('FreeSansBold9pt7b', 'FreeSansBold12pt7b',
                                  'FreeSansBold18pt7b', 'FreeSansBold24pt7b', 'Font2', 'Font0')}
layout = {name: int(value) for name, value in re.findall(
    r'constexpr int k(\w+) = (\d+);', (ROOT / 'include/ui_layout.h').read_text())}


def box(cx, cy, width, height):
    return (cx - width // 2, cy - height // 2, width, height)


def heading_font(value, mode):
    classic = mode == 'classic'
    y = layout['ClassicHeadingY'] if classic else layout['HeadingY']
    radius = layout['ClassicHeadingSafeRadius'] if classic else layout['HeadingSafeRadius']
    maximum = layout['ClassicHeadingHeight'] if classic else layout['HeadingHeight']
    for height in range(maximum, 7, -1):
        dy = 120-y+(height+1)//2+1
        width = 2 * int(math.sqrt(radius*radius-dy*dy))
        for i, name in enumerate(('FreeSansBold12pt7b', 'FreeSansBold9pt7b', 'Font2', 'Font0')):
            font = fonts[name]
            scale = struct.unpack('f', struct.pack('f', height/font.height))[0]
            if scale < (0.75 if i < 2 else 1):
                continue
            measured = font.measured_width(value, scale) + 4
            if measured <= width:
                return font, scale, box(120, y, measured, height+2)
    raise AssertionError(('No heading fit', value, mode))


def mouth_bend(session, status):
    reliable = session is not None and math.isfinite(session) and status in ('', 'PARTIAL', 'TEST DATA')
    return (1 if session > 55 else -1 if session < 45 else 0) if reliable else 0, reliable


def mouth_offset_at(elapsed):
    if elapsed >= 1000:
        return 0
    t = min(elapsed, 1000-elapsed)*2
    return (7*t*t*(3000-2*t)+500000000)//1000000000


def blink_at(elapsed):
    if elapsed <= 200 or elapsed >= 800:
        return 0
    t = min(elapsed-200, 800-elapsed)*1000//300
    return (35*t*t*(3000-2*t)+500000000)//1000000000


def gauge_text_boxes(cx):
    return (box(cx, layout['LabelY'], 24, 22),
            box(cx, layout['PercentY'], layout['ValueWidth'], layout['ValueHeight']),
            box(cx, layout['CountdownY'], layout['CountdownWidth'], layout['CountdownHeight']))


def check_geometry():
    radius = layout['Radius']
    inner = radius - layout['Thickness']
    assert layout['RightX'] - layout['LeftX'] - 2 * radius >= 8
    assert abs(layout['GaugeY'] - 120) + abs(layout['LeftX'] - 120) + radius < layout['RimRadius']
    assert abs(layout['GaugeY'] - 120) + abs(layout['RightX'] - 120) + radius < layout['RimRadius']
    for cx in (layout['LeftX'], layout['RightX']):
        rectangles = [box(cx, layout['LabelY'], 24, 22),
                      box(cx, layout['PercentY'], layout['ValueWidth'], layout['ValueHeight']),
                      box(cx, layout['CountdownY'], layout['CountdownWidth'], layout['CountdownHeight'])]
        for x, y, w, h in rectangles:
            assert max(math.hypot(xx-cx, yy-layout['GaugeY']) for xx in (x, x+w-1)
                       for yy in (y, y+h-1)) < inner, (x, y, w, h)
        for a, b in zip(rectangles, rectangles[1:]):
            assert a[1] + a[3] <= b[1], (a, b)
    assert layout['NoteY'] + 5 < layout['GaugeY'] - radius
    assert layout['HeadingY'] + 8 < layout['NoteY'] - 5
    # Extra modes have no gauges: verify clear regions fit the physical circle
    # and cannot erase a neighboring text region when a value shrinks.
    common = [box(120, layout['HeadingY'], 88, 16), box(120, layout['NoteY'], 88, 10)]
    green = [box(cx, layout['GaugeY'], 2 * radius + 1, 2 * radius + 1)
             for cx in (layout['LeftX'], layout['RightX'])] + [
             (120-layout['ValueWidth']//2, layout['MouthY']-layout['MouthBufferOriginY'],
              layout['ValueWidth'], layout['ValueHeight'])]
    blue = [box(120, layout['BlueLabelY'], 24, 16),
            box(120, layout['BlueValueY'], layout['BlueWidth'], layout['BlueHeight']),
            box(120, layout['BlueResetY'], 64, 16), box(120, layout['BlueHourY'], 128, 30),
            box(120, layout['BlueHourResetY'], 64, 16)]
    orange = [rectangle for cx in (layout['LeftX'], layout['RightX']) for rectangle in (
              box(cx, layout['OrangeLabelY'], 24, 22),
              box(cx, layout['OrangeValueY'], layout['OrangeWidth'], layout['OrangeHeight']),
              box(cx, layout['OrangeResetY'], 64, 16))]
    for rectangles in (common + green, common + blue, common + orange):
        for x, y, w, h in rectangles:
            assert max(math.hypot(xx-120, yy-120) for xx in (x, x+w-1)
                       for yy in (y, y+h-1)) < 118, (x, y, w, h)
        for i, a in enumerate(rectangles):
            for b in rectangles[i+1:]:
                assert (a[0]+a[2] <= b[0] or b[0]+b[2] <= a[0] or
                        a[1]+a[3] <= b[1] or b[1]+b[3] <= a[1]), (a, b)
    # Classic clear rectangles stay wholly inside the inner ring, including
    # full-width percentage clears; countdown updates cannot erase either arc.
    assert layout['ClassicOuterRadius'] < 118
    assert layout['ClassicOuterRadius'] - layout['Thickness'] - layout['ClassicInnerRadius'] >= 6
    classic = [box(120, layout['ClassicHeadingY'], 88, 16),
               box(120, layout['ClassicNoteY'], 88, 10)] + [
        rectangle for value_y, reset_y in (
            (layout['ClassicWeekY'], layout['ClassicWeekResetY']),
            (layout['ClassicHourY'], layout['ClassicHourResetY'])) for rectangle in (
                box(120, value_y, layout['ClassicValueWidth'], layout['ClassicValueHeight']),
                box(120, reset_y, layout['CountdownWidth'], layout['CountdownHeight']))]
    for x, y, w, h in classic:
        assert max(math.hypot(xx-120, yy-120) for xx in (x, x+w-1)
                   for yy in (y, y+h-1)) < layout['ClassicInnerRadius']-layout['Thickness']
    for a, b in zip(classic, classic[1:]):
        assert a[1]+a[3] <= b[1], (a, b)


def render(weekly=68, session=82, status='TEST DATA', due=False, mode='green',
           heading='IROZON DOT', mouth_offset=0, blink=0):
    background, first, second = {'green': ('bg', 'lime', 'green'),
                                 'blue': ('blueBg', 'blue', 'cyan'),
                                 'orange': ('orangeBg', 'orange', 'gold'),
                                 'classic': ('bg', 'lime', 'green')}[mode]
    image = Image.new('RGB', (240, 240), colors[background])
    draw = ImageDraw.Draw(image)
    stale = status in ('STALE', 'OFFLINE')
    # The whole face cancels if either gauge is unreliable. Static H expression
    # still follows H independently when only W is missing.
    face_reliable = (weekly is not None and math.isfinite(weekly) and mouth_bend(session, status)[1])
    blink = blink if mode == 'green' and face_reliable else 0
    if not face_reliable:
        mouth_offset = 0
    rim = layout['RimRadius']
    if mode == 'green':
        draw.ellipse((120-rim, 120-rim, 120+rim, 120+rim), outline=colors['rim'], width=1)
    for cx, value, color, radius in (
            [(layout['LeftX'], weekly or 0, first, layout['Radius']),
             (layout['RightX'], session or 0, second, layout['Radius'])] if mode == 'green' else
            [(120, weekly or 0, first, layout['ClassicOuterRadius']),
             (120, session or 0, second, layout['ClassicInnerRadius'])] if mode == 'classic' else []):
        cy = layout['GaugeY']
        if stale:
            color = 'muted'
        vertical = radius-blink if mode == 'green' else radius
        inner = radius-layout['Thickness']
        inner_y = (inner*vertical+radius//2)//radius
        scale = vertical/radius
        for y in range(240):
            for x in range(240):
                in_ring = (inner <= math.hypot(x-cx, y-cy) <= radius) if not blink else (
                    (x-cx)**2/radius**2+(y-cy)**2/vertical**2 <= 1 and
                    (x-cx)**2/inner**2+(y-cy)**2/inner_y**2 >= 1)
                if in_ring:
                    angle = (math.degrees(math.atan2((y-cy)/scale, x-cx)) + 90) % 360
                    image.putpixel((x, y), colors[color if angle <= value * 3.6 and value else 'track'])
        if value:
            for angle in (-90, value * 3.6 - 90):
                a = math.radians(angle)
                x, y = round(cx + math.cos(a) * (radius - layout['Thickness'] / 2)), round(cy + math.sin(a) * (radius - layout['Thickness'] / 2)*scale)
                cap_y = 1 if scale < 0.75 else 2
                draw.ellipse((x-2, y-cap_y, x+2, y+cap_y), fill=colors[color])
    if mode == 'green':
        for cx in (layout['LeftX'], layout['RightX']):
            for x, y, w, h in gauge_text_boxes(cx):
                draw.rectangle((x, y, x+w-1, y+h-1), fill=colors[background])
    heading_y = layout['ClassicHeadingY'] if mode == 'classic' else layout['HeadingY']
    note_y = layout['ClassicNoteY'] if mode == 'classic' else layout['NoteY']
    if heading:
        font, scale, _ = heading_font(heading, mode)
        font.draw_scaled(image, heading, 120, heading_y, colors['white'], scale)
    fonts['Font0'].draw(image, status, 120, note_y, colors['white' if status == 'TEST DATA' else 'amber'],
                        box=box(120, note_y, 88, 10))
    texts = ['--' if weekly is None else 'DUE' if due else '3d 12h',
             '--' if session is None else 'DUE' if due else '2h 24m']
    def paint(text, font, cx, y, width, height, color):
        fonts[font].draw(image, text, cx, y, colors['muted' if stale else color], box=box(cx, y, width, height))

    if mode == 'blue':
        paint('W', 'Font2', 120, layout['BlueLabelY'], 24, 16, first)
        paint('--' if weekly is None else f'{weekly}%', 'FreeSansBold24pt7b', 120,
              layout['BlueValueY'], layout['BlueWidth'], layout['BlueHeight'], first)
        paint(texts[0], 'Font2', 120, layout['BlueResetY'], 64, 16, 'muted')
        paint('H ' + ('--' if session is None else f'{session}%'), 'FreeSansBold12pt7b', 120,
              layout['BlueHourY'], 128, 30, second)
        paint(texts[1], 'Font2', 120, layout['BlueHourResetY'], 64, 16, 'muted')
    if mode == 'classic':
        for label, value, color, value_y, reset_y, countdown in zip(
                ('W', 'H'), (weekly, session), (first, second),
                (layout['ClassicWeekY'], layout['ClassicHourY']),
                (layout['ClassicWeekResetY'], layout['ClassicHourResetY']), texts):
            text = label + ' ' + ('--' if value is None else f'{value}%')
            paint(text, 'FreeSansBold12pt7b', 120, value_y,
                  layout['ClassicValueWidth'], layout['ClassicValueHeight'], color)
            paint(countdown, 'Font2', 120, reset_y, layout['CountdownWidth'], layout['CountdownHeight'], 'muted')
    for cx, label, value, color, countdown in (zip((layout['LeftX'], layout['RightX']), ('W', 'H'),
                                               (weekly, session), (first, second), texts) if mode in ('green', 'orange') else []):
        text = '--' if value is None else f'{value}%'
        if mode == 'orange':
            paint(label, 'FreeSansBold9pt7b', cx, layout['OrangeLabelY'], 24, 22, color)
            paint(text, 'FreeSansBold18pt7b', cx, layout['OrangeValueY'], layout['OrangeWidth'], layout['OrangeHeight'], color)
            paint(countdown, 'Font2', cx, layout['OrangeResetY'], 64, 16, 'muted')
            continue
        color = colors['muted' if stale else color]
        fonts['FreeSansBold9pt7b'].draw(image, label, cx, layout['LabelY'], color,
                                       box=box(cx, layout['LabelY'], 24, 22))
        fonts['FreeSansBold12pt7b'].draw(image, text, cx, layout['PercentY'], color,
                                       box=box(cx, layout['PercentY'], layout['ValueWidth'], layout['ValueHeight']))
        fonts['Font2'].draw(image, countdown, cx, layout['CountdownY'], colors['muted'],
                            box=box(cx, layout['CountdownY'], layout['CountdownWidth'], layout['CountdownHeight']))
    if mode == 'green':
        bend, reliable = mouth_bend(session, status)
        color = colors['track' if not reliable else 'amber' if bend < 0 else 'green']
        half, depth = layout['MouthHalfWidth'], layout['MouthDepth']
        offset = mouth_offset if reliable else 0
        half += offset
        curve = bend*depth + (-offset if bend < 0 else offset)
        def y(x):
            return layout['MouthY'] + math.trunc(curve * (half*half-x*x) / (half*half))
        for x in range(-half, half):
            for stroke in (0, 1):
                draw.line((120+x, y(x)+stroke, 121+x, y(x+1)+stroke), fill=color)
    return image


if __name__ == '__main__':
    output = ROOT / '.pio' / 'previews'
    output.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    check_geometry()
    comparison = Image.new('RGB', (960, 240), colors['bg'])
    for column, mode in enumerate(('green', 'blue', 'orange', 'classic')):
        preview = render(mode=mode)
        preview.save(output / f'mode-{mode}.png')
        comparison.paste(preview, (240 * column, 0))
        cases = [render(mode=mode), render(83, 90, '', mode=mode), render(82, 85, 'STALE', mode=mode),
                 render(None, 85, 'PARTIAL', mode=mode), render(None, None, 'OFFLINE', mode=mode),
                 render(100, 100, '', mode=mode), render(0, 0, 'TEST DATA', due=True, mode=mode), render(1, 99, mode=mode),
                 render(81, None, 'PARTIAL', mode=mode), render(None, None, 'NO DATA', mode=mode),
                 render(None, None, 'WIFI SETUP', mode=mode), render(82, 85, 'OFFLINE', mode=mode)]
        sheet = Image.new('RGB', (960, 720), colors['bg'])
        for i, case in enumerate(cases):
            sheet.paste(case, (240 * (i % 4), 240 * (i // 4)))
        sheet.save(output / f'mode-{mode}-checks.png')
        for value in range(101):
            render(value, 100-value, mode=mode)
    comparison.save(output / 'display-modes.png')
    headings = Image.new('RGB', (960, 960), colors['bg'])
    for row, name in enumerate(('D', 'Dot', 'Irozon Dot', 'WWWWWWWWWWWWWWWWWW')):
        for col, mode in enumerate(('green', 'blue', 'orange', 'classic')):
            headings.paste(render(mode=mode, heading=name), (240*col, 240*row))
    headings.save(output / 'adaptive-headings.png')
    animation = Image.new('RGB', (960, 960), colors['bg'])
    for row, (session, status) in enumerate(((82, ''), (50, ''), (30, ''), (82, 'STALE'))):
        for col, offset in enumerate((0, 4, 7, 0)):
            animation.paste(render(session=session, status=status, heading='Dot', mouth_offset=offset),
                            (240*col, 240*row))
    animation.save(output / 'mouth-animation-states.png')
    for name, session in (('happy', 82), ('neutral', 50), ('sad', 30)):
        frames = [render(status='', session=session, heading='Dot', mouth_offset=mouth_offset_at(t), blink=blink_at(t))
                  for t in range(0, 1001, 40)]
        # Exactly 240x240; 1 s movement followed by the remainder of the 10 s interval.
        frames[0].save(output / f'mouth-{name}.gif', save_all=True, append_images=frames[1:],
                       duration=[40]*25+[9000], loop=0, optimize=False)
    (output / 'mouth-animation.gif').write_bytes((output / 'mouth-happy.gif').read_bytes())
    (output / 'face-blink.gif').write_bytes((output / 'mouth-happy.gif').read_bytes())
    sequence = Image.new('RGB', (1200, 240), colors['bg'])
    for col, t in enumerate((0, 320, 500, 680, 1000)):
        sequence.paste(render(status='', heading='Dot', mouth_offset=mouth_offset_at(t), blink=blink_at(t)),
                       (240*col, 0))
    sequence.save(output / 'face-blink-states.png')
    hidden = Image.new('RGB', (960, 240), colors['bg'])
    for col, mode in enumerate(('green', 'blue', 'orange', 'classic')):
        hidden.paste(render(mode=mode, heading=''), (240*col, 0))
    hidden.save(output / 'heading-hidden.png')
    # Inclusive neutral boundaries; fractional crossings must not be hidden by
    # the whole-number percentage redraw cache. Stale/offline high H stays neutral.
    for value, expected in ((0, -1), (44.99, -1), (45, 0), (50, 0), (55, 0), (55.01, 1), (100, 1)):
        assert mouth_bend(value, '') == (expected, True)
        for state in ('OFFLINE', 'STALE', 'NO DATA', 'WIFI SETUP'):
            assert mouth_bend(value, state) == (0, False)
    assert mouth_bend(None, 'PARTIAL') == (0, False)
    assert mouth_bend(82, 'PARTIAL') == (1, True)  # Unknown W does not change H expression.
    expressions = Image.new('RGB', (960, 480), colors['bg'])
    cases = [(68, 82, 'TEST DATA'), (68, 50, 'TEST DATA'), (68, 30, 'TEST DATA'),
             (68, None, 'PARTIAL'), (68, 45, 'TEST DATA'), (68, 55, 'TEST DATA'),
             (68, 82, 'OFFLINE'), (68, 82, 'STALE')]
    for i, values in enumerate(cases):
        expressions.paste(render(*values), (240 * (i % 4), 240 * (i // 4)))
    expressions.save(output / 'green-expressions.png')
    scratch = Image.new('RGB', (240, 240), colors['bg'])
    for text in [f'{h}h {m:02d}m' for h in range(24) for m in range(60)] + [
                 f'{d}d {h:02d}h' for d in range(1, 8) for h in range(24)]:
        fonts['Font2'].draw(scratch, text, layout['LeftX'], layout['CountdownY'], colors['muted'],
                            box=box(layout['LeftX'], layout['CountdownY'], layout['CountdownWidth'], layout['CountdownHeight']))
    print('PASS: all 0â€“100% glyphs, compact reset labels, gauge/clear bounds and separation.')
    print(output / 'display-modes.png')
