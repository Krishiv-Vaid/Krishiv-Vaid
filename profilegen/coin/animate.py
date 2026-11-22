"""Turn rendered coin frames into seamless animations.

Primary output is an animated, *transparent* WebP: one file sits cleanly on
both GitHub themes (true alpha edges, a soft shadow that works on either
background) at roughly a third of the size of an equivalent GIF. Theme-matted
GIFs are produced as a fallback for platforms without animated WebP.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

from ..ascii_art import blur
from ..theme import Theme
from .evolution import Detail
from .palette import Alloy, hex_to_rgb
from .render import build_face, render_frame


def tonemap(rgb: np.ndarray) -> np.ndarray:
    # Soft shoulder keeps specular peaks from clipping to flat white.
    return np.clip(1.30 * rgb / (1 + 0.30 * rgb), 0, 1)


def to_rgba(rgb: np.ndarray, alpha: np.ndarray, shadow: float = 0.30) -> np.ndarray:
    """Coin over a soft contact shadow, as straight (non-premultiplied) RGBA."""
    h = alpha.shape[0]
    shift = max(1, int(h * 0.035))
    sh = np.zeros_like(alpha)
    sh[shift:] = alpha[:-shift]
    sh = blur(sh, h * 0.025) * shadow
    a_out = alpha + sh * (1 - alpha)
    col = tonemap(rgb) * alpha[..., None]  # shadow colour is black
    col = np.where(a_out[..., None] > 1e-6, col / np.maximum(a_out[..., None], 1e-6), 0)
    return np.dstack([col, a_out])


def flatten(rgba: Image.Image, theme: Theme) -> Image.Image:
    bg = Image.new("RGBA", rgba.size, tuple(round(c * 255) for c in hex_to_rgb(theme.page)) + (255,))
    return Image.alpha_composite(bg, rgba).convert("RGB")


def yaw_pitch(t: float, yaw_max: float, pitch: float) -> tuple[float, float]:
    """Seamless loop: t in [0, 1). Yaw oscillates; pitch breathes slightly."""
    y = math.radians(yaw_max) * math.sin(2 * math.pi * t)
    p = math.radians(pitch + 2.5 * math.cos(2 * math.pi * t))
    return y, p


def _frame(maps, detail, yaw, pitch, out_px, supersample) -> Image.Image:
    rgb, alpha = render_frame(maps, detail, yaw, pitch, int(out_px * supersample))
    arr = to_rgba(rgb, alpha)
    im = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    return im.resize((out_px, out_px), Image.LANCZOS)


def render_frames(detail: Detail, alloy: list[Alloy], out_px: int, frames: int,
                  yaw_max: float, pitch: float, supersample: float = 1.5,
                  texture: int = 1536) -> list[Image.Image]:
    maps = build_face(detail, alloy, n=texture)
    return [_frame(maps, detail, *yaw_pitch(i / frames, yaw_max, pitch), out_px, supersample)
            for i in range(frames)]


def still(detail: Detail, alloy: list[Alloy], out_px: int, yaw: float = 20,
          pitch: float = 9, texture: int = 1536) -> Image.Image:
    maps = build_face(detail, alloy, n=texture)
    return _frame(maps, detail, math.radians(yaw), math.radians(pitch), out_px, 2.0)


def save_webp(frames: list[Image.Image], path: Path, frame_ms: int, quality: int = 74) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, "WEBP", save_all=True, append_images=frames[1:], duration=frame_ms,
                   loop=0, quality=quality, alpha_quality=90, method=6)


def save_gif(frames: list[Image.Image], path: Path, frame_ms: int, theme: Theme,
             colors: int = 128) -> None:
    """Theme-matted GIF with one global palette, so colours never shimmer."""
    flat = [flatten(f, theme) for f in frames]
    sample = flat[:: max(1, len(flat) // 10)]
    w, h = sample[0].size
    mosaic = Image.new("RGB", (w, h * len(sample)))
    for k, f in enumerate(sample):
        mosaic.paste(f, (0, k * h))
    pal = mosaic.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in flat]
    path.parent.mkdir(parents=True, exist_ok=True)
    q[0].save(path, save_all=True, append_images=q[1:], duration=frame_ms, loop=0,
              optimize=True, disposal=1)
