"""Photograph -> monospaced character portrait.

Pipeline
--------
1. ``load_cutout``   subject cutout (luminance + alpha), cropped.
2. ``ink_map``       local-contrast boost, percentile levels, gamma, Sobel
                     edge emphasis, silhouette floor, lower-body fade. Output is
                     an "ink" field in [0, 1]: how much glyph coverage we want.
                     Light mode inks shadows (pencil on paper); dark mode inks
                     highlights (phosphor on a screen).
3. ``GlyphAtlas``    renders every candidate glyph with the real font at the
                     real cell geometry, so density is measured, not guessed.
4. ``convert``       per cell, either nearest-density ramp lookup (optionally
                     error-diffused) or structural matching, where each cell's
                     sub-pixel patch is compared with every glyph bitmap and the
                     best tone + shape match wins. Structural matching is what
                     keeps eyebrows, eyelids and the smile line legible.

Cell aspect is handled explicitly: a cell is ``advance`` wide and
``line_height`` tall, and the image is resampled to exactly that grid, so the
face is never stretched.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .theme import FONT_REGULAR, MONO_ADVANCE

# Curated glyph set: line-like punctuation carries structure (brows, jaw, hair
# edges); a few round letters fill mid-tones. Dense capitals are limited so the
# portrait reads as drawing, not letter soup.
CHARSET = " .,'-_:;~^\"=+*<>!?/\\|()[]{}1iltfjrxcvunoszaeLJCYXZUOQ0#%&8B$@MW"

# Tone-only ramp used where a cell has no internal structure.
RAMP = " .,:-~=+*coxzO0Q8&%#B@"


@dataclass(frozen=True)
class AsciiParams:
    cols: int = 64
    line_height: float = 2.0  # cell height in units of advance (h / w)
    ink_is_dark: bool = True  # light mode: True; dark mode: False
    local_contrast: float = 0.9  # unsharp-mask amount at portrait scale
    local_radius: float = 0.06  # as a fraction of width
    gamma: float = 1.0
    lo_pct: float = 1.5
    hi_pct: float = 99.0
    # Region (fractions of width/height) whose histogram sets the levels. Using
    # the face rather than the whole subject stops black hair and a black shirt
    # from compressing skin tones, which is where eyes/brows/smile live.
    level_box: tuple[float, float, float, float] | None = None
    shadow_detail: float = 0.0  # 0..1 blend of whole-subject levels
    smooth: float = 0.0  # pre-blur (analysis px): skin reads as shading, not speckle
    edge_weight: float = 0.35
    floor: float = 0.0  # minimum ink inside the subject (keeps silhouette)
    fade_start: float = 0.70  # fraction of height where the torso fades
    fade_to: float = 0.25
    fade_end: float = 1.0  # fraction of height where the fade reaches fade_to
    mode: str = "shape"  # "ramp" | "shape"
    dither: str = "none"  # "none" | "fs" | "atkinson" (ramp mode)
    shape_weight: float = 0.6  # 0 = pure tone, 1 = pure structure
    tone_levels: int = 4
    rim_light: bool = False  # mark silhouette cells facing the key light (top-left)
    charset: str = CHARSET
    sub: tuple[int, int] = (6, 12)  # analysis pixels per cell (w, h)


@dataclass
class AsciiGrid:
    chars: list[str]  # one string per row
    tones: np.ndarray  # (rows, cols) int in [0, tone_levels)
    ink: np.ndarray = field(repr=False)  # (rows, cols) mean ink per cell
    rim: np.ndarray | None = field(default=None, repr=False)  # rim-lit cells

    def trimmed(self) -> "AsciiGrid":
        """Drop blank rows at the top and bottom."""
        keep = [i for i, r in enumerate(self.chars) if r.strip()]
        if not keep:
            return self
        a, b = keep[0], keep[-1] + 1
        rim = self.rim[a:b] if self.rim is not None else None
        return AsciiGrid(self.chars[a:b], self.tones[a:b], self.ink[a:b], rim)

    @property
    def rows(self) -> int:
        return len(self.chars)

    @property
    def cols(self) -> int:
        return len(self.chars[0]) if self.chars else 0


# --------------------------------------------------------------------------
# image utilities (numpy only, so CI needs nothing heavier than Pillow)


def _gauss_kernel(sigma: float) -> np.ndarray:
    r = max(1, int(round(3 * sigma)))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-(x**2) / (2 * sigma**2))
    return k / k.sum()


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return a
    k = _gauss_kernel(sigma)
    r = len(k) // 2
    p = np.pad(a, ((0, 0), (r, r)), mode="edge")
    a = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    p = np.pad(a, ((r, r), (0, 0)), mode="edge")
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)


def sobel(a: np.ndarray) -> np.ndarray:
    p = np.pad(a, 1, mode="edge")
    gx = (
        (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:])
        - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    )
    gy = (
        (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:])
        - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    )
    return np.hypot(gx, gy)


# --------------------------------------------------------------------------
# stage 1: cutout


def load_cutout(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load an RGBA / LA cutout. Returns (luminance, alpha) as float arrays."""
    im = Image.open(path)
    if im.mode not in ("RGBA", "LA"):
        im = im.convert("RGBA")
    alpha = np.asarray(im.getchannel("A"), dtype=np.float64) / 255.0
    lum = np.asarray(im.convert("L"), dtype=np.float64) / 255.0
    return lum, alpha


def grid_shape(img_w: int, img_h: int, p: AsciiParams) -> tuple[int, int]:
    """Rows that keep the image's true aspect given the cell aspect."""
    rows = round(p.cols * img_h / (img_w * p.line_height))
    return p.cols, max(1, rows)


def _resample(a: np.ndarray, w: int, h: int) -> np.ndarray:
    im = Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8))
    return np.asarray(im.resize((w, h), Image.LANCZOS), dtype=np.float64) / 255.0


# --------------------------------------------------------------------------
# stage 2: ink field


def ink_map(lum: np.ndarray, alpha: np.ndarray, p: AsciiParams) -> np.ndarray:
    cols, rows = grid_shape(lum.shape[1], lum.shape[0], p)
    sw, sh = p.sub
    W, H = cols * sw, rows * sh
    L = _resample(lum, W, H)
    A = _resample(alpha, W, H)
    inside = A > 0.5

    if p.smooth > 0:
        L = blur(L, p.smooth)
    # Local contrast: lift mid-frequency detail (brows, eyelids, smile).
    base = blur(L, p.local_radius * W)
    L = L + p.local_contrast * (L - base)

    # Percentile levels measured on the subject only.
    region = inside.copy()
    if p.level_box is not None:
        x0, y0, x1, y1 = p.level_box
        box = np.zeros_like(region)
        box[int(y0 * H): int(y1 * H), int(x0 * W): int(x1 * W)] = True
        region &= box
    vals = L[region] if region.any() else L.ravel()
    lo, hi = np.percentile(vals, [p.lo_pct, p.hi_pct])
    Lf = np.clip((L - lo) / max(hi - lo, 1e-6), 0.0, 1.0) ** p.gamma
    if p.shadow_detail > 0:
        # Face-based levels clip hair to solid black; blend in whole-subject
        # levels so strands and highlights survive as texture.
        gv = L[inside] if inside.any() else L.ravel()
        glo, ghi = np.percentile(gv, [1, 99])
        Lg = np.clip((L - glo) / max(ghi - glo, 1e-6), 0.0, 1.0)
        Lf = (1 - p.shadow_detail) * Lf + p.shadow_detail * Lg
    L = Lf

    ink = 1.0 - L if p.ink_is_dark else L

    if p.edge_weight > 0:
        e = sobel(blur(L, 0.8))
        e = e * (A > 0.15)  # silhouette edge handled by alpha, not Sobel
        ref = np.percentile(e[inside], 98) if inside.any() else e.max()
        e = np.clip(e / max(ref, 1e-6), 0.0, 1.0)
        ink = np.clip(ink + p.edge_weight * e, 0.0, 1.0)

    ink = np.maximum(ink, p.floor) * A

    if p.fade_start < 1.0:
        y = np.linspace(0.0, 1.0, H)[:, None]
        t = np.clip((y - p.fade_start) / max(p.fade_end - p.fade_start, 1e-6), 0.0, 1.0)
        t = t * t * (3 - 2 * t)  # smoothstep
        ink = ink * (1.0 - (1.0 - p.fade_to) * t)
    return ink


# --------------------------------------------------------------------------
# stage 3: glyph atlas


class GlyphAtlas:
    """Coverage bitmaps for each glyph at analysis resolution."""

    def __init__(self, charset: str, sub: tuple[int, int], line_height: float,
                 font_path: Path = FONT_REGULAR, oversample: int = 8):
        sw, sh = sub
        size = 64  # render big, then area-average down
        font = ImageFont.truetype(str(font_path), size)
        adv = size * MONO_ADVANCE
        cell_w, cell_h = adv, adv * line_height
        W, H = int(round(cell_w)), int(round(cell_h))
        ascent, descent = font.getmetrics()
        # Centre the font's em box vertically in the cell (as the SVG does).
        baseline = (H - (ascent + descent)) / 2 + ascent
        bitmaps = []
        for ch in charset:
            im = Image.new("L", (W, H), 0)
            ImageDraw.Draw(im).text((0, baseline), ch, fill=255, font=font, anchor="ls")
            bm = im.resize((sw, sh), Image.BOX)
            bitmaps.append(np.asarray(bm, dtype=np.float64) / 255.0)
        self.chars = charset
        self.bitmaps = np.stack(bitmaps)  # (n, sh, sw)
        self.density = self.bitmaps.mean(axis=(1, 2))
        self.order = np.argsort(self.density)

    def ramp(self, levels: int = 18) -> str:
        """Evenly spaced density ramp, space first."""
        d = self.density
        targets = np.linspace(0.0, d.max(), levels)
        out = []
        for t in targets:
            i = int(np.argmin(np.abs(d - t)))
            if self.chars[i] not in out:
                out.append(self.chars[i])
        return "".join(out)


# --------------------------------------------------------------------------
# stage 4: conversion


def _cells(ink: np.ndarray, sub: tuple[int, int]) -> np.ndarray:
    sw, sh = sub
    H, W = ink.shape
    rows, cols = H // sh, W // sw
    return ink[: rows * sh, : cols * sw].reshape(rows, sh, cols, sw).transpose(0, 2, 1, 3)


def _diffuse(tone: np.ndarray, levels: np.ndarray, kind: str) -> np.ndarray:
    """Error diffusion of a tone grid onto a discrete set of levels."""
    t = tone.copy()
    rows, cols = t.shape
    idx = np.zeros_like(t, dtype=int)
    if kind == "fs":
        taps = [(0, 1, 7 / 16), (1, -1, 3 / 16), (1, 0, 5 / 16), (1, 1, 1 / 16)]
    else:  # atkinson: lighter, keeps highlights clean
        taps = [(0, 1, 1 / 8), (0, 2, 1 / 8), (1, -1, 1 / 8), (1, 0, 1 / 8),
                (1, 1, 1 / 8), (2, 0, 1 / 8)]
    for y in range(rows):
        for x in range(cols):
            i = int(np.argmin(np.abs(levels - t[y, x])))
            idx[y, x] = i
            err = t[y, x] - levels[i]
            for dy, dx, w in taps:
                yy, xx = y + dy, x + dx
                if 0 <= yy < rows and 0 <= xx < cols:
                    t[yy, xx] += err * w
    return idx


def convert(lum: np.ndarray, alpha: np.ndarray, p: AsciiParams,
            atlas: GlyphAtlas | None = None) -> AsciiGrid:
    atlas = atlas or GlyphAtlas(p.charset, p.sub, p.line_height)
    ink = ink_map(lum, alpha, p)
    cells = _cells(ink, p.sub)  # (rows, cols, sh, sw)
    rows, cols = cells.shape[:2]
    mean_ink = cells.mean(axis=(2, 3))
    dmax = atlas.density.max()

    if p.mode == "ramp":
        ramp = "".join(c for c in RAMP if c in atlas.chars)
        ramp_idx = [atlas.chars.index(c) for c in ramp]
        levels = atlas.density[ramp_idx] / dmax
        if p.dither in ("fs", "atkinson"):
            sel = _diffuse(mean_ink, levels, p.dither)
        else:
            sel = np.abs(mean_ink[..., None] - levels[None, None, :]).argmin(axis=-1)
        chars = ["".join(ramp[i] for i in row) for row in sel]
    else:
        # Hybrid structural match.
        #  * tone term: cell mean vs glyph density (both in glyph units)
        #  * shape term: mean-removed patch vs mean-removed glyph, weighted by
        #    how much structure the cell actually has. Flat cells fall back to
        #    the calm tone ramp; cells crossing an edge pick the glyph whose
        #    strokes line up with it.
        P = cells.reshape(rows * cols, -1) * dmax
        Gb = np.stack([blur(b, 0.6) for b in atlas.bitmaps])
        G = Gb.reshape(len(atlas.chars), -1)
        D = P.shape[1]
        Pm, Gm = P.mean(1, keepdims=True), G.mean(1, keepdims=True)
        Ps, Gs = P - Pm, G - Gm
        # ||Ps - Gs||^2 = |Ps|^2 + |Gs|^2 - 2 Ps.Gs  (vectorised over all pairs)
        shape = ((Ps**2).sum(1)[:, None] + (Gs**2).sum(1)[None, :] - 2 * Ps @ Gs.T) / D
        tone = (Pm - Gm.T) ** 2
        structure = np.sqrt((Ps**2).mean(1, keepdims=True)) / max(dmax, 1e-6)
        w = p.shape_weight * np.clip(structure / 0.12, 0.0, 1.0)  # (N, 1)
        in_ramp = np.array([c in RAMP for c in atlas.chars], dtype=float)[None, :]
        off_ramp_penalty = (1.0 - w) * (1.0 - in_ramp) * 1e3
        cost = w * shape + 3.0 * tone + off_ramp_penalty
        sel = cost.argmin(1).reshape(rows, cols)
        # Empty cells must stay empty: no glyph for (near) zero ink.
        sel[mean_ink < 0.03] = atlas.chars.index(" ")
        chars = ["".join(atlas.chars[i] for i in row) for row in sel]

    q = np.clip(mean_ink / max(np.percentile(mean_ink[mean_ink > 0.02], 97)
                               if (mean_ink > 0.02).any() else 1.0, 1e-6), 0, 0.9999)
    tones = (q * p.tone_levels).astype(int)
    rim = None
    if p.rim_light:
        # Cell-level alpha; a subject cell whose left / upper-left / upper
        # neighbour is background sits on the lit edge of the silhouette.
        cols_, rows_ = grid_shape(lum.shape[1], lum.shape[0], p)
        A = _resample(alpha, cols_ * p.sub[0], rows_ * p.sub[1])
        ca = _cells(A, p.sub).mean(axis=(2, 3))
        bg = np.pad(ca < 0.35, 1, constant_values=True)
        lit = bg[1:-1, :-2] | bg[:-2, :-2] | bg[:-2, 1:-1]
        nonblank = np.array([[ch != " " for ch in row] for row in chars])
        rim = (ca > 0.5) & lit & nonblank
    return AsciiGrid(chars=chars, tones=tones, ink=mean_ink, rim=rim)


def with_overrides(p: AsciiParams, **kw) -> AsciiParams:
    return replace(p, **kw)
