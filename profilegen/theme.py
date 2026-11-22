"""Design tokens shared by every generated asset.

One palette per GitHub colour scheme. All assets read from here so the hero,
coin panel, stats panel and section rules stay visually identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "fonts"
FONT_REGULAR = FONT_DIR / "JetBrainsMonoNL-Regular.ttf"
FONT_MEDIUM = FONT_DIR / "JetBrainsMonoNL-Medium.ttf"
FONT_BOLD = FONT_DIR / "JetBrainsMonoNL-SemiBold.ttf"
FONT_LIGHT = FONT_DIR / "JetBrainsMonoNL-Light.ttf"

# JetBrains Mono advance width is 600/1000 em for every glyph.
MONO_ADVANCE = 0.6


@dataclass(frozen=True)
class Theme:
    name: str
    page: str  # GitHub page background the asset sits on
    card: str  # raised panel
    edge: str  # 1px panel border
    rule: str  # separators
    text: str  # primary (ivory / graphite)
    muted: str  # secondary labels
    dim: str  # tertiary, dotted leaders
    faint: str  # hairlines, inactive cells
    accent: str  # muted steel blue: keys
    silver: str  # metallic secondary
    # Four ink tones for the portrait, faintest -> strongest.
    ink: tuple[str, str, str, str] = field(default=("#000",) * 4)

    @property
    def dark(self) -> bool:
        return self.name == "dark"


DARK = Theme(
    name="dark",
    page="#0d1117",
    card="#10151c",
    edge="#252c35",
    rule="#2a313b",
    text="#e6e2d8",
    muted="#8d949d",
    dim="#5a626c",
    faint="#2f3640",
    accent="#9fb3c7",
    silver="#c3c8cd",
    ink=("#454c56", "#737b86", "#aab1b9", "#ebe7de"),
)

LIGHT = Theme(
    name="light",
    page="#ffffff",
    card="#fafaf7",
    edge="#e3e1da",
    rule="#dcdad3",
    text="#1c2026",
    muted="#5f666f",
    dim="#9a9fa6",
    faint="#e6e4de",
    accent="#41607d",
    silver="#5b6269",
    ink=("#bdbab2", "#8a8e95", "#4c525a", "#1c2026"),
)

THEMES = (DARK, LIGHT)
