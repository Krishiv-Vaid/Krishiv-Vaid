"""Koi pond frames -> WebP / GIF.

Pixel art has a small, exact palette, so the GIF fallback is encoded with that
exact palette (no quantisation, no dithering noise) and one transparent index
for the area outside the rim. Frames are upscaled by an integer factor with
nearest-neighbour sampling, so every native pixel stays a crisp square.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np
from PIL import Image

from .evolution import KoiSpec
from .pond import H, W, build_scene, make_ripples, make_swimmers, render_frame


def day_seed(login: str, day: str) -> int:
    """New routes every day, stable within a day (so reruns don't churn)."""
    return zlib.crc32(f"{login}:{day}".encode())


def scene_seed(login: str) -> int:
    """The pond's layout belongs to the account and never changes."""
    return zlib.crc32(f"{login}:pond".encode())


def render(school: list[KoiSpec], leaves, frames: int, login: str,
           day: str) -> tuple[list[np.ndarray], np.ndarray]:
    sseed = scene_seed(login)
    adults = sum(k.adult for k in school)
    scene = build_scene(adults, leaves, sseed)
    swimmers = make_swimmers(school, login, day)
    ripples = make_ripples(day_seed(login, day), scene)
    out = [render_frame(scene, swimmers, ripples, i / frames, frames, sseed) for i in range(frames)]
    return out, scene.alpha


def save_gif(frames: list[np.ndarray], alpha: np.ndarray, path: Path, frame_ms: int, scale: int) -> int:
    """Encode with an exact shared palette; returns the number of colours used."""
    stack = np.stack(frames)
    packed = (stack[..., 0].astype(np.uint32) << 16) | (stack[..., 1].astype(np.uint32) << 8) | stack[..., 2]
    packed[:, ~alpha] = 0xFFFFFFFF
    colours, inverse = np.unique(packed, return_inverse=True)
    inverse = inverse.reshape(packed.shape)
    opaque = colours[colours != 0xFFFFFFFF]
    if len(opaque) > 255:
        # Rare (many languages): fall back to Pillow's quantiser on the frames.
        return _save_gif_quantised(frames, alpha, path, frame_ms, scale)
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
        idx = lut[inverse[f]].repeat(scale, 0).repeat(scale, 1)
        im = Image.fromarray(idx, "P")
        im.putpalette(pal)
        images.append(im)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:], duration=frame_ms, loop=0,
                   transparency=0, disposal=1, optimize=False)
    return len(opaque)


def _save_gif_quantised(frames, alpha, path: Path, frame_ms: int, scale: int) -> int:
    rgb = [Image.fromarray(f).resize((W * scale, H * scale), Image.NEAREST) for f in frames]
    pal = rgb[0].quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in rgb]
    path.parent.mkdir(parents=True, exist_ok=True)
    q[0].save(path, save_all=True, append_images=q[1:], duration=frame_ms, loop=0, disposal=1)
    return 255


def save_webp(frames, alpha, path: Path, frame_ms: int, scale: int) -> None:
    a = (alpha * 255).astype(np.uint8)
    ims = [Image.fromarray(np.dstack([f, a]), "RGBA").resize((W * scale, H * scale), Image.NEAREST)
           for f in frames]
    path.parent.mkdir(parents=True, exist_ok=True)
    ims[0].save(path, "WEBP", save_all=True, append_images=ims[1:], duration=frame_ms, loop=0,
                lossless=True, method=4)


def still(frames: list[np.ndarray], alpha: np.ndarray, scale: int, index: int = 0) -> Image.Image:
    rgba = np.dstack([frames[index], (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA").resize((W * scale, H * scale), Image.NEAREST)
