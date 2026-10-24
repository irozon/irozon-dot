"""Host layout check using the pinned LovyanGFX bitmap fonts; never uses USB.

Requires Pillow (development only). Run after `pio run -e supermini`.
This is a layout preview, not an ESP32 / GC9A01 emulator.
"""
import math
import re
from pathlib import Path
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

def rgb565(hex_value):
    value = int(hex_value, 16)
    return (((value >> 19) & 31) * 255 // 31,
            ((value >> 10) & 63) * 255 // 63, ((value >> 3) & 31) * 255 // 31)


colors = {name: rgb565(value) for name, value in
          re.findall(r'uint16_t (\w+) = rgb\(0x([0-9A-F]+)\)', SOURCE)}
fonts = {name: BitmapFont(name) for name in (
    'FreeSansBold9pt7b', 'FreeSansBold12pt7b', 'FreeSansBold18pt7b',
    'Font2', 'Font0', 'FreeSans9pt7b')}
layout = {name: int(value) for name, value in re.findall(
    r'constexpr int k(\w+) = (\d+);', (ROOT / 'include/ui_layout.h').read_text())}


def draw_text(image, value, x, y, font, color, scale=1.0):
    fonts[font].draw_scaled(image, value, x, y, colors[color] if isinstance(color, str) else color, scale)


def round_bar(draw, x, y, width, height, color):
    if width > 0:
        draw.rounded_rectangle((x, y-height//2, x+width-1, y+height//2),
                               radius=height//2, fill=colors[color])


def render_green(weekly=82, session=90):
    image = Image.new('RGB', (240, 240), colors['classicBackground'])
    draw = ImageDraw.Draw(image)
    draw_text(image, 'Codex', 120, layout['StackHeadingY'], 'FreeSansBold12pt7b', 'white')
    for label, value, row, bar_y, color, track in (
        ('W', weekly, layout['StackWeeklyY'], layout['StackWeeklyBarY'], 'stackWeekly', 'stackWeeklyTrack'),
        ('H', session, layout['StackSessionY'], layout['StackSessionBarY'], 'stackSession', 'stackSessionTrack')):
        draw_text(image, label, 51, row, 'FreeSansBold12pt7b', 'white')
        draw_text(image, f'{value}%', 192, row, 'FreeSansBold18pt7b', color, .8)
        bar_x = layout['StackContentLeft']
        bar_width = layout['StackContentRight'] - bar_x
        round_bar(draw, bar_x, bar_y, bar_width, layout['StackBarHeight'], track)
        round_bar(draw, bar_x, bar_y,
                  round(bar_width * value / 100), layout['StackBarHeight'], color)
    draw.line((42, layout['StackDividerY'], 198, layout['StackDividerY']), fill=colors['classicTrack'])
    return image


def render_classic(weekly=68, session=82):
    image = Image.new('RGB', (240, 240), colors['classicBackground'])
    draw = ImageDraw.Draw(image)
    draw_text(image, 'Codex', 120, layout['ClassicHeadingY'], 'FreeSansBold12pt7b', 'white')
    cx, cy = 120, layout['ClassicGaugeY']
    radius = layout['ClassicGaugeRadius']

    def arc(start, end, color, width=8):
        points = []
        for step in range(round((end - start) * 2) + 1):
            angle = math.radians(start + step / 2)
            points.append((round(cx + math.cos(angle) * radius),
                           round(cy + math.sin(angle) * radius)))
        draw.line(points, fill=colors[color], width=width, joint='curve')
        cap = width // 2
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-cap, y-cap, x+cap, y+cap), fill=colors[color])

    start, sweep = layout['ClassicLeftArcStart'], layout['ClassicArcSweep']
    finish = layout['ClassicRightArcStart'] + sweep
    arc(start, start + sweep, 'classicWeeklyTrack')
    arc(finish - sweep, finish, 'classicSessionTrack')
    if weekly > 0:
        arc(start, start + sweep * min(weekly, 100) / 100, 'classicWeekly')
    if session > 0:
        arc(finish - sweep * min(session, 100) / 100, finish, 'classicSession')
    draw.line((120, layout['ClassicDividerTop'], 120, layout['ClassicDividerBottom']), fill=colors['classicTrack'])
    draw_text(image, f'{weekly}%', layout['ClassicLeftX'], layout['ClassicPercentY'], 'FreeSansBold18pt7b', 'classicWeekly', .85)
    draw_text(image, f'{session}%', layout['ClassicRightX'], layout['ClassicPercentY'], 'FreeSansBold18pt7b', 'classicSession', .85)
    for label, x, countdown in (('W', layout['ClassicLeftX'], '3d 12h'), ('S', layout['ClassicRightX'], '2h 24m')):
        draw_text(image, label, x, layout['ClassicLabelY'], 'FreeSansBold9pt7b', 'white')
        draw_text(image, countdown, x, layout['ClassicResetY'], 'Font2', 'muted')
    return image


def render_companion(expression='happy'):
    image = Image.new('RGB', (240, 240), colors['classicBackground'])
    draw = ImageDraw.Draw(image)
    lime = colors['faceLime']
    for cx in (80, 160):
        top = 82
        draw.rounded_rectangle((cx-21, top, cx+20, top+41), radius=12, outline=lime, width=3)
    if expression == 'sleeping':
        draw.line((64, 103, 96, 103), fill=lime, width=3)
        draw.line((144, 103, 176, 103), fill=lime, width=3)
    else:
        pupil_y = 103 + (-4 if expression == 'curious' else 0)
        shift = -7 if expression == 'curious' else 0
        for cx in (80, 160):
            draw.ellipse((cx+shift-4, pupil_y-4, cx+shift+4, pupil_y+4), fill=lime)
    if expression in ('surprised', 'waking'):
        for cx in (80, 160): draw.line((cx-11, 70, cx+11, 66), fill=lime, width=3)
    x0, x1 = 102, 138
    if expression == 'sad':
        points = [(x, 181 - round(5 * (1-((x-120)/18)**2))) for x in range(x0, x1+1)]
    elif expression in ('sleepy', 'sleeping'):
        points = [(x, 177) for x in range(x0, x1+1)]
    elif expression == 'surprised':
        draw.ellipse((115, 173, 125, 183), outline=lime, width=3)
        return image
    else:
        points = [(x, 177 - round(7 * ((x-120)/18)**2)) for x in range(x0, x1+1)]
    draw.line(points, fill=lime, width=3)
    return image


def render(mode, **values):
    return {'green': render_green, 'classic': render_classic,
            'companion': render_companion}[mode](**values)


if __name__ == '__main__':
    output = ROOT / 'docs'
    output.mkdir(exist_ok=True)
    previews = {'green': render_green(), 'classic': render_classic(),
                'companion': render_companion()}
    for mode, image in previews.items():
        image.save(output / f'mode-{mode}.png')
    print('Rendered: ' + ', '.join(str(output / f'mode-{mode}.png') for mode in previews))
