"""Procedural coin renderer (numpy only).

Two stages:

``build_face``   bakes the obverse into texture maps in face coordinates
                 (u, v in [-1, 1], radius 1): a relief height field, metal
                 albedo, enamel colour + mask, and a wear/cavity map. Every
                 engraving is generated from ``Detail``: rim and bevel, bead
                 ring, denticles, a raised legend ring, guilloche rosettes, a
                 star lattice, the enamel language band and the KV monogram.

``render_frame`` ray-casts an orthographic camera against a thick disc rotated
                 by (yaw, pitch). Face hits are bump-mapped from the height
                 field; edge hits get a cylindrical normal with optional
                 reeding and a rolled bevel. Lighting is a small studio rig:
                 key + fill, Blinn-Phong specular whose sharpness follows the
                 stage's polish, and an environment term (soft box over a dark
                 floor) that gives metal its characteristic reflections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..ascii_art import blur as gblur
from ..theme import FONT_BOLD, FONT_MEDIUM
from .evolution import Detail
from .palette import METALS, Alloy

HALF_THICKNESS = 0.072  # in units of radius
EXTENT = 1.16  # half-width of the view in radii

# Radial layout of the obverse (fractions of radius).
R_RIM_IN = 0.885
R_DENT = (0.858, 0.884)
R_BEADS = 0.833
R_TEXT = (0.742, 0.808)
R_INLAY_IN = 0.700
R_FIELD = (0.335, 0.690)
R_CARTOUCHE = 0.305


@dataclass
class FaceMaps:
    n: int
    height: np.ndarray
    gx: np.ndarray  # dh/du
    gy: np.ndarray  # dh/dv (v up)
    metal: np.ndarray  # (n, n, 3)
    enamel: np.ndarray  # (n, n, 3)
    enamel_mask: np.ndarray
    wear: np.ndarray
    radius_lut: np.ndarray  # R(phi) sampled over [0, 2pi)


# --------------------------------------------------------------------------
# helpers


def _smooth(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _band(x: np.ndarray, a: float, b: float, soft: float) -> np.ndarray:
    return _smooth(a - soft, a + soft, x) * (1 - _smooth(b - soft, b + soft, x))


def _value_noise(n: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    grid = rng.random((cells + 1, cells + 1))
    im = Image.fromarray((grid * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)
    return np.asarray(im, dtype=np.float64) / 255.0


def _fbm(n: int, rng: np.random.Generator, octaves: int = 5, base: int = 6) -> np.ndarray:
    out = np.zeros((n, n))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        out += amp * _value_noise(n, base * 2**o, rng)
        total += amp
        amp *= 0.5
    return out / total


def _mask_from_draw(n: int, draw_fn, blur: float = 0.0) -> np.ndarray:
    im = Image.new("L", (n, n), 0)
    draw_fn(ImageDraw.Draw(im), n)
    if blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, dtype=np.float64) / 255.0


def _to_px(n: int, u: float, v: float) -> tuple[float, float]:
    return ((u + 1) / 2 * (n - 1), (1 - v) / 2 * (n - 1))


def radius_lut(detail: Detail, seed: int, samples: int = 2048) -> np.ndarray:
    """Outline radius as a function of angle. Round except for the fragment."""
    phi = np.linspace(0, 2 * np.pi, samples, endpoint=False)
    if not detail.fragment:
        return np.ones(samples)
    rng = np.random.default_rng(seed)
    # One large break (lower right) with a jagged fracture, plus small chips.
    centre = math.radians(-38)
    d = np.angle(np.exp(1j * (phi - centre)))
    chunk = 0.17 * np.exp(-((d / 0.62) ** 6))
    jag = np.interp(phi, np.linspace(0, 2 * np.pi, 97), rng.random(97)) - 0.5
    jag = jag * 0.035 * (chunk > 0.01)
    chips = np.zeros(samples)
    for c in rng.uniform(0, 2 * np.pi, 5):
        dd = np.angle(np.exp(1j * (phi - c)))
        chips += rng.uniform(0.008, 0.02) * np.exp(-((dd / rng.uniform(0.04, 0.09)) ** 2))
    return 1.0 - chunk - np.abs(jag) - chips


def _lut_lookup(lut: np.ndarray, phi: np.ndarray) -> np.ndarray:
    k = len(lut)
    x = (phi % (2 * np.pi)) / (2 * np.pi) * k
    i0 = np.floor(x).astype(int) % k
    f = x - np.floor(x)
    return lut[i0] * (1 - f) + lut[(i0 + 1) % k] * f


def _lut_slope(lut: np.ndarray, phi: np.ndarray) -> np.ndarray:
    k = len(lut)
    d = (np.roll(lut, -1) - np.roll(lut, 1)) / (2 * (2 * np.pi / k))
    return _lut_lookup(d, phi)


# --------------------------------------------------------------------------
# face construction


def _legend_strip(text: str, w: int, h: int) -> np.ndarray:
    """Text rendered on a horizontal strip, stretched to exactly fill ``w``."""
    font = ImageFont.truetype(str(FONT_MEDIUM), int(h * 0.78))
    tw = int(font.getlength(text)) + 4
    im = Image.new("L", (tw, h), 0)
    ImageDraw.Draw(im).text((2, h * 0.52), text, fill=255, font=font, anchor="lm")
    im = im.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    return np.asarray(im, dtype=np.float64) / 255.0


def build_face(detail: Detail, alloy: list[Alloy], n: int = 1024, seed: int = 7,
               legend: str = "KRISHIV VAID · UNIVERSITY OF WATERLOO · GITHUB.COM/KRISHIV-VAID · ") -> FaceMaps:
    rng = np.random.default_rng(seed)
    ax = np.linspace(-1, 1, n)
    u, v = np.meshgrid(ax, -ax)  # row 0 is v = +1
    r = np.hypot(u, v)
    phi = np.arctan2(v, u)
    px = 2.0 / (n - 1)  # one texel in face units

    h = np.zeros((n, n))

    # Field: very slight dish so light rolls across it.
    h += -0.010 * (1 - np.clip(r / R_RIM_IN, 0, 1) ** 2)

    # Rim: raised flat with an inner wall and an outer bevel.
    rim = _smooth(R_RIM_IN, R_RIM_IN + 0.02, r) * 0.055
    rim -= _smooth(0.972, 1.0, r) * 0.030
    h += rim

    # Concentric engraved rings just inside the rim.
    for k in range(detail.rim_rings):
        rr = R_RIM_IN - 0.012 - 0.014 * k
        h -= 0.006 * np.exp(-(((r - rr) / (1.6 * px)) ** 2))

    if detail.denticles:
        teeth = (0.5 + 0.5 * np.cos(detail.denticles * phi)) ** 3
        h += 0.016 * teeth * _band(r, *R_DENT, 1.5 * px)

    if detail.beads:
        step = 2 * np.pi / detail.beads
        pb = np.round(phi / step) * step
        dist = np.hypot(r - R_BEADS, R_BEADS * (phi - pb))
        h += 0.022 * np.clip(1 - (dist / 0.0105) ** 2, 0, 1) ** 0.6

    if detail.text_ring:
        W, H = 4096, 96
        strip = _legend_strip(legend, W, H)
        xs = (((np.pi / 2 - phi) % (2 * np.pi)) / (2 * np.pi) * (W - 1)).astype(int)
        ys = ((R_TEXT[1] - r) / (R_TEXT[1] - R_TEXT[0]) * (H - 1))
        inside = (ys >= 0) & (ys <= H - 1)
        glyphs = np.zeros_like(r)
        glyphs[inside] = strip[ys[inside].astype(int), xs[inside]]
        h += 0.014 * glyphs

    # Enamel band carrying the language alloy, recessed below the field.
    inlay_out = R_INLAY_IN + detail.inlay_width
    inlay = _band(r, R_INLAY_IN, inlay_out, 0.9 * px)
    h -= 0.008 * inlay
    h += 0.010 * (np.exp(-(((r - R_INLAY_IN + 0.006) / (1.4 * px)) ** 2))
                  + np.exp(-(((r - inlay_out - 0.006) / (1.4 * px)) ** 2)))
    enamel = np.zeros((n, n, 3))
    theta = ((np.pi / 2 - phi) % (2 * np.pi)) / (2 * np.pi)  # clockwise from top
    gap = 0.0035
    start = 0.0
    seg_mask = np.zeros_like(r)
    for a in alloy:
        end = start + a.share
        m = _band(theta, start + gap, end - gap, 0.0008) if a.share > 2 * gap else 0 * theta
        enamel += m[..., None] * np.array(a.color)
        seg_mask += m
        start = end
    enamel_mask = inlay * np.clip(seg_mask, 0, 1)

    if detail.guilloche_lines:
        band = _band(r, R_FIELD[0] + 0.01, R_FIELD[1] - 0.01, 0.012)
        acc = np.zeros_like(r)
        mid = (R_FIELD[0] + R_FIELD[1]) / 2
        amp = (R_FIELD[1] - R_FIELD[0]) * 0.36
        lines = detail.guilloche_lines
        for i in range(lines):
            ph = 2 * np.pi * i / lines
            ri = mid + amp * np.sin(6 * phi + ph)
            acc += np.exp(-(((r - ri) / (2.0 * px)) ** 2))
        h -= 0.0065 * np.clip(acc, 0, 1.2) * band

    if detail.lattice:
        pts = []
        spikes = 12
        for k in range(spikes * 2):
            a = math.pi / 2 + k * math.pi / spikes
            rr = 0.47 if k % 2 == 0 else R_CARTOUCHE + 0.035
            pts.append(_to_px(n, rr * math.cos(a), rr * math.sin(a)))
        star = _mask_from_draw(n, lambda d, nn: d.line(pts + [pts[0]], fill=255,
                                                         width=max(2, nn // 420), joint="curve"), 0.8)
        h += 0.010 * star
        rays = (0.5 + 0.5 * np.cos(72 * phi)) ** 6 * _band(r, 0.50, R_FIELD[1] - 0.02, 0.01)
        if not detail.guilloche_lines:
            h -= 0.003 * rays

    # Cartouche ring + KV monogram.
    h += 0.016 * np.exp(-(((r - R_CARTOUCHE) / (2.2 * px)) ** 2))
    h += 0.007 * np.exp(-(((r - R_CARTOUCHE + 0.018) / (1.2 * px)) ** 2))

    def draw_kv(d: ImageDraw.ImageDraw, nn: int) -> None:
        font = ImageFont.truetype(str(FONT_BOLD), int(nn * 0.17))
        cx, cy = _to_px(nn, 0, -0.005)
        d.text((cx, cy), "KV", fill=255, font=font, anchor="mm")

    kv = _mask_from_draw(n, draw_kv, blur=n / 700)
    kv_soft = _mask_from_draw(n, draw_kv, blur=n / 180)
    h += 0.030 * kv + 0.006 * kv_soft

    # Wear: soften relief, pit the surface, darken recesses.
    noise = _fbm(n, rng)
    if detail.wear > 0:
        soft = gblur(h, 1 + 3 * detail.wear)
        h = h * (1 - 0.6 * detail.wear) + soft * 0.6 * detail.wear
        h += (noise - 0.5) * 0.006 * detail.wear
        enamel_mask = enamel_mask * (noise > 0.25 + 0.4 * detail.wear)
    hb = gblur(h, 6)
    cavity = np.clip((hb - h) * 40, 0, 1)
    wear = np.clip(cavity * (0.35 + 0.65 * detail.wear) + (noise - 0.5) * 0.5 * detail.wear, 0, 1)

    # Metal albedo (bimetallic for the masterwork).
    base = np.array(METALS[detail.stage.metal])
    metal = np.broadcast_to(base, (n, n, 3)).copy()
    if detail.stage.rim_metal:
        ring = _smooth(R_INLAY_IN - 0.004, R_INLAY_IN + 0.004, r)
        metal = metal * (1 - ring[..., None]) + np.array(METALS[detail.stage.rim_metal]) * ring[..., None]
    # Fine brushed grain (direction follows the angle: lathe-turned blank).
    grain = np.sin(r * 900 + noise * 6) * 0.025 * (1 - detail.wear)
    metal = metal * (1 + grain[..., None])

    gy_rows, gx = np.gradient(h, px)
    gy = -gy_rows  # rows run downward, v runs up
    return FaceMaps(n, h, gx, gy, metal, enamel, enamel_mask, wear, radius_lut(detail, seed))


# --------------------------------------------------------------------------
# frame rendering


def _rot(yaw: float, pitch: float) -> np.ndarray:
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return ry @ rx  # coin -> camera


def _sample(img: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    n = img.shape[0]
    x = np.clip((u + 1) / 2 * (n - 1), 0, n - 1.001)
    y = np.clip((1 - v) / 2 * (n - 1), 0, n - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    if img.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def _norm(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


KEY = _norm(np.array([-0.52, 0.62, 0.59]))
FILL = _norm(np.array([0.75, -0.15, 0.64]))
VIEW = np.array([0.0, 0.0, 1.0])


def _environment(rv: np.ndarray) -> np.ndarray:
    """Studio environment seen in reflection: soft box top-left, dark floor."""
    x, y = rv[..., 0], rv[..., 1]
    sky = 0.07 + 0.50 * _smooth(-0.35, 0.95, y)
    box = 1.35 * np.exp(-(((y - 0.30) / 0.26) ** 2)) * np.exp(-(((x + 0.28) / 0.50) ** 2))
    strip = 0.55 * np.exp(-(((x - 0.70) / 0.09) ** 2)) * _smooth(-0.6, 0.4, y)
    floor = _smooth(-0.15, -0.65, y) * 0.06
    return sky + box + strip - floor


def render_frame(maps: FaceMaps, detail: Detail, yaw: float, pitch: float,
                 px: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (rgb, alpha) arrays of shape (px, px[, 3]) with values in [0, 1]."""
    M = _rot(yaw, pitch)
    Mi = M.T
    ax = np.linspace(-EXTENT, EXTENT, px)
    X, Y = np.meshgrid(ax, -ax)
    o = X[..., None] * Mi[:, 0] + Y[..., None] * Mi[:, 1] + 10.0 * Mi[:, 2]
    d = -Mi[:, 2]
    hgt = HALF_THICKNESS

    # Front face (z = +h).
    t_face = np.full(X.shape, np.inf)
    if d[2] < -1e-6:
        t = (hgt - o[..., 2]) / d[2]
        q = o + t[..., None] * d
        rq = np.hypot(q[..., 0], q[..., 1])
        ok = rq <= _lut_lookup(maps.radius_lut, np.arctan2(q[..., 1], q[..., 0]))
        t_face = np.where(ok, t, np.inf)

    # Edge: cylinder whose radius follows the outline, solved by fixed point.
    a = d[0] ** 2 + d[1] ** 2
    R = np.ones(X.shape)
    t_side = np.full(X.shape, np.inf)
    if a > 1e-9:
        for _ in range(4):
            b = 2 * (o[..., 0] * d[0] + o[..., 1] * d[1])
            c = o[..., 0] ** 2 + o[..., 1] ** 2 - R**2
            disc = b * b - 4 * a * c
            t = (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a)
            p = o + t[..., None] * d
            R = _lut_lookup(maps.radius_lut, np.arctan2(p[..., 1], p[..., 0]))
        ok = (disc >= 0) & (np.abs(p[..., 2]) <= hgt)
        t_side = np.where(ok, t, np.inf)

    face = np.isfinite(t_face) & (t_face <= t_side)
    side = np.isfinite(t_side) & ~face
    alpha = (face | side).astype(np.float64)

    rgb = np.zeros(X.shape + (3,))
    polish = detail.polish
    shin = 18 + 220 * polish

    def shade_metal(n_cam: np.ndarray, albedo: np.ndarray, darken: np.ndarray | float) -> np.ndarray:
        ndl = np.clip((n_cam * KEY).sum(-1), 0, 1)
        ndf = np.clip((n_cam * FILL).sum(-1), 0, 1)
        hv = _norm(KEY + VIEW)
        spec = np.clip((n_cam * hv).sum(-1), 0, 1) ** shin
        broad = np.clip((n_cam * hv).sum(-1), 0, 1) ** 9
        rv = 2 * n_cam[..., 2:3] * n_cam - VIEW
        env = _environment(rv)
        c = albedo * (0.04 + 0.18 * ndl[..., None] + 0.05 * ndf[..., None] + 0.95 * env[..., None])
        tint = albedo * 0.65 + 0.35
        c = c + tint * (spec * (0.7 + 0.8 * polish) + broad * 0.14)[..., None]
        return c * (1 - 0.55 * np.asarray(darken))[..., None] if np.ndim(darken) else c * (1 - 0.55 * darken)

    if face.any():
        t = np.where(face, t_face, 0)
        q = o + t[..., None] * d
        fu, fv = q[face, 0], q[face, 1]
        gx = _sample(maps.gx, fu, fv)
        gy = _sample(maps.gy, fu, fv)
        bump = 0.75
        # Slight macro convexity: a perfectly flat face under an orthographic
        # camera reflects a single environment value and looks like plastic.
        convex = 0.20
        n_c = _norm(np.stack([-gx * bump + fu * convex, -gy * bump + fv * convex,
                              np.ones_like(gx)], -1))
        n_cam = n_c @ M.T
        albedo = _sample(maps.metal, fu, fv)
        wear = _sample(maps.wear, fu, fv)
        col = shade_metal(n_cam, albedo, wear)
        em = _sample(maps.enamel_mask, fu, fv)[..., None]
        if em.max() > 0:
            ecol = _sample(maps.enamel, fu, fv)
            ndl = np.clip((n_cam * KEY).sum(-1), 0, 1)[..., None]
            hv = _norm(KEY + VIEW)
            gloss = np.clip((n_cam * hv).sum(-1), 0, 1)[..., None] ** 260
            e = ecol * (0.30 + 0.62 * ndl) + 0.40 * gloss
            col = col * (1 - em) + e * em
        rgb[face] = col

    if side.any():
        t = np.where(side, t_side, 0)
        p = o + t[..., None] * d
        ph = np.arctan2(p[side, 1], p[side, 0])
        z = p[side, 2]
        Rv = _lut_lookup(maps.radius_lut, ph)
        dR = _lut_slope(maps.radius_lut, ph) / np.maximum(Rv, 1e-6)
        radial = np.stack([np.cos(ph) + dR * np.sin(ph), np.sin(ph) - dR * np.cos(ph), np.zeros_like(ph)], -1)
        tangent = np.stack([-np.sin(ph), np.cos(ph), np.zeros_like(ph)], -1)
        n_c = _norm(radial)
        if detail.reeded_edge:
            n_c = _norm(n_c + tangent * (0.32 * np.sin(detail.reeded_edge * ph))[..., None])
        roll = _smooth(hgt * 0.55, hgt, np.abs(z)) * np.sign(z)
        n_c = _norm(n_c + np.stack([0 * z, 0 * z, roll * 1.1], -1))
        n_cam = n_c @ M.T
        albedo = np.broadcast_to(np.array(METALS[detail.stage.rim_metal or detail.stage.metal]), n_c.shape) * 0.92
        fract = 0.0
        if detail.fragment:
            # Fracture surface: darker and rougher than the minted edge.
            fract = np.clip((1 - Rv) * 6, 0, 1)
        rgb[side] = shade_metal(n_cam, albedo, 0.25 + 0.5 * fract if np.ndim(fract) else 0.25)

    return np.clip(rgb, 0, 1.4), alpha
