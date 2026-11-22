"""Koi pond frames -> GIF.

Pixel art has a small, exact palette, so frames are encoded with that exact
palette (no quantisation, no dithering noise) and one transparent index for
the area outside the rim. Frames are upscaled by an integer factor with
nearest-neighbour sampling, so every native pixel stays a crisp square.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np
from PIL import Image

from .evolution import Koi
from .pond import H, W, build_scene, koi_colors, make_path, make_ripples, render_frame


def path_seed(login: str, day: str) -> int:
    """New route every day, stable within a day (so reruns don't churn)."""
    return zlib.crc32(f"{login}:{day}".encode())


def pattern_seed(login: str) -> int:
    """The fish's markings belong to the account and never change."""
    return zlib.crc32(f"{login}:koi".encode())


def render(koi: Koi, leaves, frames: int, login: str, day: str) -> tuple[list[np.ndarray], np.ndarray]:
    pseed = pattern_seed(login)
    scene = build_scene(koi, leaves, pseed)
    stiff = 1.0 + 1.6 * max(0.0, (koi.length - 30) / 48)
    path = make_path(path_seed(login, day), margin=koi.length * 0.30 + 5, stiffness=stiff)
    cols = koi_colors(leaves)
    ripples = make_ripples(path_seed(login, day), scene)
    out = [render_frame(scene, koi, path, cols, ripples, i / frames, frames, pseed) for i in range(frames)]
    return out, scene.alpha


def save_gif(frames: list[np.ndarray], alpha: np.ndarray, path: Path, frame_ms: int, scale: int) -> int:
    """Encode with an exact shared palette; returns the number of colours used."""
    stack = np.stack(frames)  # (F, H, W, 3)
    packed = (stack[..., 0].astype(np.uint32) << 16) | (stack[..., 1].astype(np.uint32) << 8) | stack[..., 2]
    packed[:, ~alpha] = 0xFFFFFFFF
    colours, inverse = np.unique(packed, return_inverse=True)
    inverse = inverse.reshape(packed.shape)
    opaque = colours[colours != 0xFFFFFFFF]
    if len(opaque) > 255:
        raise ValueError(f"pond uses {len(opaque)} colours; GIF allows 255 + transparency")
    # index 0 = transparent; opaque colours follow
    lut = np.zeros(len(colours), dtype=np.uint8)
    pal = [0, 0, 0]
    k = 1
    for i, c in enumerate(colours):
        if c == 0xFFFFFFFF:
            lut[i] = 0
        else:
            lut[i] = k
            pal += [(int(c) >> 16) & 255, (int(c) >> 8) & 255, int(c) & 255]
            k += 1
    pal += [0] * (768 - len(pal))
    images = []
    for f in range(len(frames)):
        idx = lut[inverse[f]]
        idx = idx.repeat(scale, 0).repeat(scale, 1)
        im = Image.fromarray(idx, "P")
        im.putpalette(pal)
        im.info["transparency"] = 0
        images.append(im)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:], duration=frame_ms, loop=0,
                   transparency=0, disposal=1, optimize=False)
    return len(opaque)


def still(frames: list[np.ndarray], alpha: np.ndarray, scale: int, index: int = 0) -> Image.Image:
    rgba = np.dstack([frames[index], (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA").resize((W * scale, H * scale), Image.NEAREST)
