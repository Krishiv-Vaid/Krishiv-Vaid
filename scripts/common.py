"""Shared bits for the SVG generators: palette, file output, font outlines, curves.

The palette is the "neon" theme from double-pendulum (chaos_lab), so the
profile and the project look like they came out of the same lab.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT = ROOT / ".fonts" / "SpaceGrotesk.ttf"  # OFL; fetched by build_all.sh, not committed

BG = "#070910"
PANEL_EDGE = "#1A2030"
FG = "#F4F7FF"
DIM = "#5B6478"
FAINT = "#2A3348"
CYAN = "#00E5FF"
VIOLET = "#8F5BFF"
MAGENTA = "#FF3CAC"

MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"


def lerp_color(stops: list[str], t: float) -> str:
    """Piecewise-linear interpolation through hex colors, t in [0, 1]."""
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    a = [int(stops[i][k:k + 2], 16) for k in (1, 3, 5)]
    b = [int(stops[i + 1][k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * f):02X}" for x, y in zip(a, b))


def svg_doc(w: int, h: int, body: str, title: str, rx: int = 14) -> str:
    """Wrap body in an <svg> with its own dark rounded background (works in light mode too)."""
    title = escape(title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{title}">\n<title>{title}</title>\n'
        f'<rect width="{w}" height="{h}" rx="{rx}" fill="{BG}"/>\n'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{rx}" fill="none" '
        f'stroke="{PANEL_EDGE}"/>\n{body}\n</svg>\n'
    )


def write(name: str, content: str) -> None:
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / name
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.1f} KB)")


def f(x: float, nd: int = 1) -> str:
    """Compact number formatting: trims trailing zeros to keep files small."""
    s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def closed_catmull_rom(pts: np.ndarray, nd: int = 1) -> str:
    """Smooth closed path through pts (N, 2) as cubic beziers (Catmull-Rom, tension 0.5)."""
    n = len(pts)
    d = [f"M{f(pts[0][0], nd)},{f(pts[0][1], nd)}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) / 6
        c2 = p2 - (p3 - p1) / 6
        d.append(f"C{f(c1[0], nd)},{f(c1[1], nd)} {f(c2[0], nd)},{f(c2[1], nd)} "
                 f"{f(p2[0], nd)},{f(p2[1], nd)}")
    return "".join(d) + "Z"


def text_outline(text: str, size: float, weight: int = 700, tracking: float = 0.0):
    """Convert text to SVG path data using Space Grotesk at the given weight.

    Returns (path_d, width, cap_height) in px, with the baseline at y=0, so the
    banner looks identical on every OS instead of depending on installed fonts.
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = instancer.instantiateVariableFont(TTFont(FONT), {"wght": weight})
    upm = font["head"].unitsPerEm
    s = size / upm
    cmap, glyphs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    pen = SVGPathPen(glyphs, ntos=lambda v: f(v, 2))
    x = 0.0
    for ch in text:
        g = cmap[ord(ch)]
        glyphs[g].draw(TransformPen(pen, (s, 0, 0, -s, x, 0)))
        x += hmtx[g][0] * s + tracking
    cap = font["OS/2"].sCapHeight * s
    return pen.getCommands(), x - tracking, cap
