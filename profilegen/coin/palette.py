"""Metal bases and language-derived enamel colours.

Language colours come from GitHub (linguist). Raw linguist colours are loud
(JavaScript is #f1e05a), so each one is pulled into a narrow saturation /
lightness band and blended toward the coin's metal, which makes them read as
tinted enamel rather than stickers. Each colour also gets a 4-step shade ramp
(shadow -> highlight), the same idea Git Tulkun uses for its pixel shading.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

RGB = tuple[float, float, float]

# Albedo (0..1, linear-ish) of each metal. Deliberately desaturated.
METALS: dict[str, RGB] = {
    "copper": (0.70, 0.45, 0.33),
    "bronze": (0.66, 0.52, 0.36),
    "silver": (0.78, 0.79, 0.80),
    "gold": (0.80, 0.66, 0.40),
    "platinum": (0.80, 0.81, 0.82),
}

OTHER_COLOR = "#8b949e"


def hex_to_rgb(h: str) -> RGB:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i: i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(c: RGB) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, v)) * 255):02x}" for v in c)


def mute(color: str | RGB, metal: RGB | None = None, max_sat: float = 0.40,
         light: tuple[float, float] = (0.44, 0.60), metal_mix: float = 0.15) -> RGB:
    """Pull a colour into the README's restrained band, then toward the metal."""
    rgb = hex_to_rgb(color) if isinstance(color, str) else color
    h, l, s = colorsys.rgb_to_hls(*rgb)
    s = min(s, max_sat) * (0.85 if s > 0.6 else 1.0)
    l = min(max(l, light[0]), light[1])
    out = colorsys.hls_to_rgb(h, l, s)
    if metal is not None:
        out = tuple(o * (1 - metal_mix) + m * metal_mix for o, m in zip(out, metal))
    return out  # type: ignore[return-value]


def shade_ramp(c: RGB) -> tuple[RGB, RGB, RGB, RGB]:
    """shadow, mid-dark, mid-light, highlight."""
    scales = (0.38, 0.64, 0.92, 1.16)
    return tuple(  # type: ignore[return-value]
        tuple(min(1.0, v * s + max(0.0, s - 1.0) * 0.25) for v in c) for s in scales
    )


@dataclass(frozen=True)
class Alloy:
    """Languages that tint the coin: name, share, muted colour."""

    name: str
    share: float
    color: RGB

    @property
    def hex(self) -> str:
        return rgb_to_hex(self.color)


def alloy_from_languages(languages: list[tuple[str, str, float]], metal: RGB,
                         min_share: float = 0.03, max_items: int = 4) -> list[Alloy]:
    """languages: (name, linguist_hex, share) sorted by share desc."""
    langs = [lang for lang in languages if lang[2] > 0]
    total = sum(lang[2] for lang in langs) or 1.0
    langs = [(n, c, s / total) for n, c, s in langs]
    main = [lang for lang in langs if lang[2] >= min_share][:max_items]
    rest = 1.0 - sum(lang[2] for lang in main)
    out = [Alloy(n, s, mute(c, metal)) for n, c, s in main]
    if rest > 1e-6 and main:
        out.append(Alloy("other", rest, mute(OTHER_COLOR, metal, max_sat=0.05)))
    if not out:  # no language data: plain metal band
        out.append(Alloy("unknown", 1.0, mute(OTHER_COLOR, metal, max_sat=0.05)))
    return out
