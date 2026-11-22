"""Language-derived colours.

Language colours come from GitHub (linguist). Raw linguist colours are loud
(JavaScript is #f1e05a), so each one is pulled into a narrow saturation /
lightness band before use. Each colour also gets a shade ramp
(shadow -> highlight) for pixel-art shading, the same idea Git Tulkun uses.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

RGB = tuple[float, float, float]

OTHER_COLOR = "#8b949e"


def hex_to_rgb(h: str) -> RGB:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i: i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(c: RGB) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, v)) * 255):02x}" for v in c)


def mute(color: str | RGB, tint: RGB | None = None, max_sat: float = 0.40,
         light: tuple[float, float] = (0.44, 0.60), tint_mix: float = 0.15) -> RGB:
    """Pull a colour into a restrained band, optionally toward a tint colour."""
    rgb = hex_to_rgb(color) if isinstance(color, str) else color
    h, l, s = colorsys.rgb_to_hls(*rgb)
    s = min(s, max_sat) * (0.85 if s > 0.6 else 1.0)
    l = min(max(l, light[0]), light[1])
    out = colorsys.hls_to_rgb(h, l, s)
    if tint is not None:
        out = tuple(o * (1 - tint_mix) + m * tint_mix for o, m in zip(out, tint))
    return out  # type: ignore[return-value]


def koi_pigment(color: str | RGB) -> RGB:
    """A koi-scale pigment from a linguist colour: vivid but not neon.

    Every language keeps its own hue (so each one reads as a distinct colour
    on the fish); saturation is lifted into a koi-like band and lightness is
    kept mid-range so patches stand out against the ivory body and the water.
    Near-greys (no real hue) become a metallic platinum.
    """
    rgb = hex_to_rgb(color) if isinstance(color, str) else color
    h, l, s = colorsys.rgb_to_hls(*rgb)
    if s < 0.12:
        return (0.70, 0.72, 0.74)
    s = min(0.82, max(0.58, s))
    l = min(0.56, max(0.40, l))
    return colorsys.hls_to_rgb(h, l, s)  # type: ignore[return-value]


def shade_ramp(c: RGB) -> tuple[RGB, RGB, RGB, RGB]:
    """shadow, mid-dark, mid-light, highlight."""
    scales = (0.52, 0.74, 1.0, 1.18)
    return tuple(  # type: ignore[return-value]
        tuple(min(1.0, v * s + max(0.0, s - 1.0) * 0.30) for v in c) for s in scales
    )


@dataclass(frozen=True)
class Swatch:
    """A language with its share and display colour."""

    name: str
    share: float
    color: RGB
    source: str = ""  # original linguist colour

    @property
    def hex(self) -> str:
        return rgb_to_hex(self.color)


def swatches(languages: list[tuple[str, str, float]], tint: RGB | None = None,
             min_share: float = 0.03, max_items: int = 4, **mute_kw) -> list[Swatch]:
    """languages: (name, linguist_hex, share). Small languages fold into "other"."""
    langs = sorted((lang for lang in languages if lang[2] > 0), key=lambda t: -t[2])
    total = sum(lang[2] for lang in langs) or 1.0
    langs = [(n, c, s / total) for n, c, s in langs]
    main = [lang for lang in langs if lang[2] >= min_share][:max_items]
    rest = 1.0 - sum(lang[2] for lang in main)
    out = [Swatch(n, s, mute(c, tint, **mute_kw), c) for n, c, s in main]
    if rest > 1e-6 and main:
        out.append(Swatch("other", rest, mute(OTHER_COLOR, tint, max_sat=0.05), OTHER_COLOR))
    if not out:  # no language data
        out.append(Swatch("unknown", 1.0, mute(OTHER_COLOR, tint, max_sat=0.05), OTHER_COLOR))
    return out
