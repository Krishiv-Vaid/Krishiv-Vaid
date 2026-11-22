"""Raster previews of character grids (used for QA and variant selection)."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .ascii_art import AsciiGrid
from .theme import FONT_REGULAR, MONO_ADVANCE, Theme


def render_grid_png(grid: AsciiGrid, theme: Theme, font_size: int = 14,
                    line_height: float = 2.0, pad: int = 16) -> Image.Image:
    font = ImageFont.truetype(str(FONT_REGULAR), font_size)
    cw = font_size * MONO_ADVANCE
    ch = cw * line_height
    W = int(grid.cols * cw + 2 * pad)
    H = int(grid.rows * ch + 2 * pad)
    im = Image.new("RGB", (W, H), theme.card)
    d = ImageDraw.Draw(im)
    ascent, descent = font.getmetrics()
    for r, row in enumerate(grid.chars):
        base = pad + r * ch + (ch - (ascent + descent)) / 2 + ascent
        for c, glyph in enumerate(row):
            if glyph == " ":
                continue
            color = theme.ink[int(grid.tones[r, c])]
            d.text((pad + c * cw, base), glyph, fill=color, font=font, anchor="ls")
    return im
