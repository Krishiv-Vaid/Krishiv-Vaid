"""Pixel-art koi pond.

Everything is drawn at native resolution (``W x H`` pixels) with hard pixel
edges, then upscaled by an integer factor with nearest-neighbour sampling so
the browser never blurs it. Pixels outside the stone rim are transparent, so a
single image sits on both GitHub themes.

Scene
-----
* stone rim (Voronoi stones, mortar, moss), reeds in two corners;
* water in four depth bands with ordered (Bayer) dithering between them, over a
  faint seigaiha wave pattern and scattered pebbles on the pond floor;
* lily pads tinted by the languages I write, one pad per share of code; a lotus
  blooms for every fully grown koi;
* a vermilion drum bridge the koi swim under;
* the school: each koi's spine follows its own closed Fourier path by arc
  length, so bodies bend naturally through turns, with a travelling tail-beat
  wave, flapping fins, translucent fin rays and a body pattern whose patches
  are coloured by the languages of the contributions that raised it;
* ripples, drifting sakura petals, surface glints and shadows on the floor.

Every animated quantity is periodic over the loop, so the animation is
seamless, while the routes are re-seeded each day.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field

import numpy as np

from ..palette import RGB, Swatch, hex_to_rgb, shade_ramp
from .evolution import KoiSpec

W, H = 280, 140
RIM = 10
CORNER = 14

WATER = ["#2f6a72", "#255964", "#1c4955", "#153a46"]  # shallow -> deep
FLOOR = ["#367780", "#2b6470", "#225360", "#1a4350"]  # seigaiha line per band
RIPPLE = "#79aaa9"
GLINT = "#d7ebe3"
STONES = ["#4a5057", "#5b6269", "#6e757c", "#838a90"]
MORTAR = "#2a2f35"
MOSS = ["#5d7a52", "#86a36e"]
WOOD = ["#4a3a2e", "#5c4838", "#6e5843"]
RAIL = ["#7e342c", "#a8483c", "#c96a58"]
BRIDGE_W = 20
BRIDGE_X = W - 82
IVORY = "#ede6d4"
EYE = "#1d2328"
PETAL = ["#c98993", "#e2b3b8", "#f2d9da"]
POLLEN = "#e6cf86"

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def _c(h: str | RGB | np.ndarray) -> np.ndarray:
    if isinstance(h, np.ndarray):
        return h
    rgb = hex_to_rgb(h) if isinstance(h, str) else h
    return np.array([round(v * 255) for v in rgb], dtype=np.uint8)


def _blend(a, b, t: float) -> np.ndarray:
    return np.round(_c(a) * (1 - t) + _c(b) * t).astype(np.uint8)


def _ramp(rgb: RGB) -> list[np.ndarray]:
    return [_c(c) for c in shade_ramp(rgb)]


@dataclass
class Pad:
    x: float
    y: float
    r: float
    notch: float
    swatch: Swatch
    lotus: bool = False


@dataclass
class Scene:
    rgb: np.ndarray  # (H, W, 3) uint8, static background
    alpha: np.ndarray  # (H, W) bool
    band: np.ndarray  # (H, W) int depth band, -1 outside water
    water: np.ndarray  # (H, W) bool
    pads: list[Pad] = field(default_factory=list)
    over_rgb: np.ndarray | None = None  # overlay drawn above the koi (bridge)
    over_mask: np.ndarray | None = None


# --------------------------------------------------------------------------
# static background


def _rounded_rect(inset: float, radius: float) -> np.ndarray:
    y, x = np.mgrid[0:H, 0:W] + 0.5
    x0, y0, x1, y1 = inset, inset, W - inset, H - inset
    cx = np.clip(x, x0 + radius, x1 - radius)
    cy = np.clip(y, y0 + radius, y1 - radius)
    return np.hypot(x - cx, y - cy) <= radius


def _seigaiha(r: float = 9.0) -> np.ndarray:
    """Overlapping concentric-arc wave pattern (painter's algorithm, row by row)."""
    y, x = np.mgrid[0:H, 0:W].astype(float)
    line = np.zeros((H, W), dtype=bool)
    row_step = r / 2
    for row in range(int(H / row_step) + 3):
        cy = row * row_step
        off = r if row % 2 else 0.0
        cx = np.round((x - off) / (2 * r)) * 2 * r + off
        d = np.hypot(x - cx, y - cy)
        inside = d < r
        line[inside] = (np.floor(d[inside]) % 3 == 1)
    return line


def build_scene(lotus: int, leaves: list[Swatch], seed: int) -> Scene:
    rng = np.random.default_rng(seed)
    alpha = _rounded_rect(0, CORNER)
    water = _rounded_rect(RIM, CORNER - RIM / 2)
    rgb = np.zeros((H, W, 3), dtype=np.uint8)

    # Rim: Voronoi stones.
    step = 9.0
    pts = []
    perim = 2 * (W + H)
    for k in range(int(perim / step)):
        s = (k + rng.uniform(-0.3, 0.3)) * step
        if s < W:
            px, py = s, rng.uniform(0, RIM)
        elif s < W + H:
            px, py = W - rng.uniform(0, RIM), s - W
        elif s < 2 * W + H:
            px, py = 2 * W + H - s, H - rng.uniform(0, RIM)
        else:
            px, py = rng.uniform(0, RIM), perim - s
        pts.append((px, py))
    pts = np.array(pts)
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    d = np.hypot(xx[..., None] - pts[:, 0], yy[..., None] - pts[:, 1])
    order = np.argsort(d, axis=-1)
    nearest = order[..., 0]
    d1 = np.take_along_axis(d, order[..., :1], -1)[..., 0]
    d2 = np.take_along_axis(d, order[..., 1:2], -1)[..., 0]
    tone = rng.integers(0, 3, len(pts))
    stone = np.array([_c(s) for s in STONES])
    rim_rgb = stone[tone[nearest]]
    vec = np.stack([xx - pts[nearest, 0], yy - pts[nearest, 1]], -1)
    lit = (vec[..., 0] + vec[..., 1]) < -2.0  # top-left light on each stone
    rim_rgb[lit] = stone[np.minimum(tone[nearest][lit] + 1, 3)]
    dark = (vec[..., 0] + vec[..., 1]) > 3.0
    rim_rgb[dark] = stone[np.maximum(tone[nearest][dark] - 1, 0)]
    rim_rgb[(d2 - d1) < 1.0] = _c(MORTAR)
    moss = (rng.random((H, W)) < 0.05) & ((d2 - d1) < 1.8)
    rim_rgb[moss] = _c(MOSS[0])
    rim_rgb[moss & (rng.random((H, W)) < 0.4)] = _c(MOSS[1])
    rgb[:] = rim_rgb
    lip = _rounded_rect(RIM - 1, CORNER - RIM / 2 + 1) & ~water
    rgb[lip] = _c(MORTAR)

    # Water depth bands with Bayer-dithered transitions.
    dist = np.zeros((H, W))
    cur = water.copy()
    for k in range(1, 60):
        nxt = cur.copy()
        nxt[1:, :] &= cur[:-1, :]
        nxt[:-1, :] &= cur[1:, :]
        nxt[:, 1:] &= cur[:, :-1]
        nxt[:, :-1] &= cur[:, 1:]
        dist[cur & ~nxt] = k
        cur = nxt
        if not cur.any():
            break
    dist[cur] = 60
    bayer = np.tile(BAYER4, (H // 4 + 1, W // 4 + 1))[:H, :W]
    band = np.clip(np.floor(dist / 7.0 + bayer - 0.5), 0, 3).astype(int)
    band[~water] = -1
    floor = _seigaiha()
    wc = np.array([_c(c) for c in WATER])
    fc = np.array([_c(c) for c in FLOOR])
    rgb[water] = wc[band[water]]
    pat = water & floor & (band >= 1)
    rgb[pat] = fc[band[pat]]

    # Pebbles on the pond floor.
    for _ in range(5):
        cx, cy = rng.uniform(RIM + 26, W - RIM - 26), rng.uniform(RIM + 18, H - RIM - 18)
        for _ in range(rng.integers(5, 10)):
            px_, py_ = int(cx + rng.normal(0, 5)), int(cy + rng.normal(0, 3.2))
            for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (2, 1))[: rng.integers(2, 7)]:
                X, Y = px_ + ox, py_ + oy
                if 0 <= X < W and 0 <= Y < H and water[Y, X]:
                    rgb[Y, X] = np.round(wc[band[Y, X]] * 0.80 + _c(STONES[1]) * 0.20).astype(np.uint8)
            if water[py_, px_]:
                rgb[py_, px_] = np.round(wc[band[py_, px_]] * 0.6 + _c(STONES[3]) * 0.4).astype(np.uint8)

    # Reed tufts growing over the rim in two corners.
    for (bx, by, lean) in ((RIM + 4, H - RIM + 3, 1), (W - RIM - 5, RIM + 8, -1)):
        for k in range(9):
            hgt = rng.integers(8, 17)
            x = bx + k - 4
            for t in range(hgt):
                X = int(round(x + lean * (t / hgt) ** 2 * (k - 4) * 0.9))
                Y = by - t if lean > 0 else by + t - 3
                if 0 <= X < W and 0 <= Y < H and alpha[Y, X]:
                    rgb[Y, X] = _c(MOSS[1] if t > hgt * 0.6 else MOSS[0])

    # Vermilion drum bridge across the pond, seen from above (overlay above koi).
    over = np.zeros((H, W, 3), dtype=np.uint8)
    omask = np.zeros((H, W), dtype=bool)
    x0, x1 = BRIDGE_X, BRIDGE_X + BRIDGE_W
    for y in range(1, H - 1):
        arch = 1 - abs(y - H / 2) / (H / 2)  # higher in the middle -> lighter
        for x in range(x0, x1):
            if not alpha[y, x]:
                continue
            if x in (x0, x0 + 1, x1 - 2, x1 - 1):
                c = RAIL[1] if x in (x0, x1 - 1) else RAIL[0]
            else:
                tone_ = 2 if arch > 0.6 else 1 if arch > 0.25 else 0
                c = WOOD[tone_] if (y % 4) else WOOD[max(0, tone_ - 1)]
                if x in (x0 + 2, x1 - 3) and y % 4:
                    c = WOOD[max(0, tone_ - 1)]  # plank ends in shadow
            over[y, x] = _c(c)
            omask[y, x] = True
    for y in range(7, H - 5, 17):  # posts with caps
        for x in (x0, x1 - 2):
            for oy in range(3):
                for ox in range(2):
                    over[y + oy, x + ox] = _c(RAIL[0])
            over[y, x] = _c(RAIL[2])
    sh = water & ~omask
    sh[:, : x1] = False
    sh[:, x1 + 4:] = False
    rgb[sh] = (rgb[sh] * 0.72).astype(np.uint8)

    # Lily pads near the rim, one per share of code (largest remainder).
    n_pads = 8
    shares = np.array([s.share for s in leaves])
    raw = shares * n_pads
    counts = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - counts))[: n_pads - counts.sum()]:
        counts[i] += 1
    assigned = [leaves[i] for i, n in enumerate(counts) for _ in range(n)]
    rng.shuffle(assigned)
    pads: list[Pad] = []
    tries = 0
    while len(pads) < len(assigned) and tries < 6000:
        tries += 1
        r = rng.uniform(5.5, 9.5)
        x, y = rng.uniform(RIM + r, W - RIM - r), rng.uniform(RIM + r, H - RIM - r)
        edge = min(x - RIM, W - RIM - x, y - RIM, H - RIM - y)
        if edge > 21 or any(math.hypot(x - p.x, y - p.y) < r + p.r + 4 for p in pads):
            continue
        if BRIDGE_X - r - 4 < x < BRIDGE_X + BRIDGE_W + r + 5:
            continue
        pads.append(Pad(x, y, r, rng.uniform(0, 2 * math.pi), assigned[len(pads)]))
    for p in pads[: max(0, lotus)]:
        p.lotus = True
    return Scene(rgb, alpha, band, water, pads, over, omask)


# --------------------------------------------------------------------------
# dynamic elements


def _draw_pad(img: np.ndarray, p: Pad, water_band: np.ndarray) -> None:
    ramp = _ramp(p.swatch.color)
    y0, y1 = int(p.y - p.r - 2), int(p.y + p.r + 3)
    x0, x1 = int(p.x - p.r - 2), int(p.x + p.r + 3)
    yy, xx = np.mgrid[y0:y1, x0:x1] + 0.5
    dx, dy = xx - p.x, yy - p.y
    d = np.hypot(dx, dy)
    ang = np.angle(np.exp(1j * (np.arctan2(dy, dx) - p.notch)))
    inside = (d <= p.r) & ~((np.abs(ang) < 0.20) & (d > p.r * 0.15))
    sh = np.roll(np.roll(inside, 1, 0), 1, 1) & ~inside
    for (yy_, xx_) in zip(*np.nonzero(sh)):
        Y, X = y0 + yy_, x0 + xx_
        if 0 <= Y < H and 0 <= X < W and water_band[Y, X] >= 0:
            img[Y, X] = (img[Y, X] * 0.70).astype(np.uint8)
    idx = np.full(d.shape, 2)
    idx[(dx + dy) < -0.55 * p.r] = 3
    idx[(dx + dy) > 0.55 * p.r] = 1
    idx[(d > p.r - 1.0) & ((dx + dy) > 0)] = 0
    vein_ang = np.angle(np.exp(1j * (np.arctan2(dy, dx) - p.notch - math.pi)))
    for a in (-1.6, -0.8, 0.0, 0.8, 1.6):
        idx[(np.abs(vein_ang - a) < 0.08) & (d > 1.5) & (d < p.r - 1.4)] = 1
    for (yy_, xx_) in zip(*np.nonzero(inside)):
        Y, X = y0 + yy_, x0 + xx_
        if 0 <= Y < H and 0 <= X < W:
            img[Y, X] = ramp[idx[yy_, xx_]]
    if p.lotus:
        cx, cy = int(round(p.x - p.r * 0.2)), int(round(p.y - p.r * 0.15))
        flower = {(0, -3): 0, (-1, -2): 1, (0, -2): 2, (1, -2): 1,
                  (-3, 0): 0, (-2, -1): 1, (-2, 0): 2, (-2, 1): 1,
                  (3, 0): 0, (2, -1): 1, (2, 0): 2, (2, 1): 1,
                  (-1, 2): 1, (0, 2): 2, (1, 2): 1, (0, 3): 0,
                  (-1, -1): 2, (1, -1): 2, (-1, 1): 2, (1, 1): 2,
                  (-1, 0): 2, (1, 0): 2, (0, -1): 2, (0, 1): 2, (0, 0): -1}
        for (ox, oy), k in flower.items():
            Y, X = cy + oy, cx + ox
            if 0 <= Y < H and 0 <= X < W:
                img[Y, X] = _c(POLLEN) if k < 0 else _c(PETAL[k])


@dataclass
class Path:
    pts: np.ndarray  # (N, 2) closed polyline
    cum: np.ndarray  # cumulative arc length, len N+1
    total: float

    def at(self, s: np.ndarray) -> np.ndarray:
        s = np.mod(s, self.total)
        i = np.searchsorted(self.cum, s, side="right") - 1
        i = np.clip(i, 0, len(self.pts) - 1)
        seg = self.cum[i + 1] - self.cum[i]
        f = (s - self.cum[i]) / np.maximum(seg, 1e-9)
        a, b = self.pts[i], self.pts[(i + 1) % len(self.pts)]
        return a + (b - a) * f[..., None]


def make_path(seed: int, margin: float, harmonics: int = 5, n: int = 3000,
              stiffness: float = 1.0) -> Path:
    """Closed wandering curve: a random Fourier series fitted inside the pond.

    ``stiffness`` > 1 damps the higher harmonics so a long fish swims wider
    curves instead of folding on itself.
    """
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, n, endpoint=False)
    x = np.zeros(n)
    y = np.zeros(n)
    for k in range(1, harmonics + 1):
        amp = rng.uniform(0.5, 1.0) / k ** (0.8 * stiffness)
        x += amp * np.cos(2 * np.pi * k * t + rng.uniform(0, 2 * np.pi))
        y += amp * rng.uniform(0.7, 1.0) * np.sin(2 * np.pi * k * t + rng.uniform(0, 2 * np.pi))
    if rng.random() < 0.5:
        x = -x
    pts = np.stack([x, y], -1)
    lo, hi = pts.min(0), pts.max(0)
    box = np.array([W - 2 * (RIM + margin), H - 2 * (RIM + margin)])
    pts = (pts - lo) / np.maximum(hi - lo, 1e-9) * box + (RIM + margin)
    seg = np.hypot(*np.diff(np.vstack([pts, pts[:1]]), axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    return Path(pts, cum, float(cum[-1]))


def _width(u: np.ndarray) -> np.ndarray:
    """Half-width of the body (fraction of length) along the spine, top-down."""
    head = 0.112 * np.sqrt(np.clip(u / 0.11, 0, 1)) ** 0.9
    mid = 0.112 + 0.010 * np.sin(np.clip((u - 0.11) / 0.26, 0, 1) * np.pi)
    taper = 0.112 - (0.112 - 0.030) * np.clip((u - 0.37) / 0.43, 0, 1) ** 1.25
    return np.where(u < 0.11, head, np.where(u < 0.37, mid, taper))


def _pattern(u: np.ndarray, v: np.ndarray, koi: KoiSpec) -> np.ndarray:
    """Index of the patch covering each body pixel (-1 = bare ivory).

    Patches are irregular blotches scattered along the back (seeded per fish),
    each one growing with the contributions in its block of ten. Later patches
    overlap earlier ones, like the layered markings of a real koi.
    """
    rng = np.random.default_rng(koi.seed + 991)
    out = np.full(u.shape, -1, dtype=int)
    slots = rng.permutation(10)  # spread blocks over the body, not head-to-tail
    for j, patch in enumerate(koi.patches):
        c = 0.06 + 0.64 * (slots[j % 10] / 9.0) + rng.uniform(-0.03, 0.03)
        a = rng.uniform(0.045, 0.085) * (0.35 + 0.65 * patch.fill)
        b = rng.uniform(0.45, 0.85) * (0.45 + 0.55 * patch.fill)
        off = rng.uniform(-0.55, 0.55)
        f1, f2 = rng.uniform(5, 9), rng.uniform(0, 6)
        wob = 0.25 * np.sin(v * f1 + f2) + 0.18 * np.sin(u * 60 * a + f2)
        r2 = ((u - c) / a) ** 2 + ((v - off) / b) ** 2
        out[r2 < 1.0 + wob] = j
    return out


def _poly_mask(polys: list[np.ndarray]) -> np.ndarray:
    from PIL import Image as _Image, ImageDraw as _Draw

    im = _Image.new("L", (W, H), 0)
    d = _Draw.Draw(im)
    for poly in polys:
        if len(poly) >= 3:
            d.polygon([(float(x), float(y)) for x, y in poly], fill=255)
    return np.asarray(im) > 0


def _rot(v: np.ndarray, a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


@dataclass
class Swimmer:
    koi: KoiSpec
    path: Path
    laps: int  # integer -> seamless
    phase: float  # start offset along the path, fraction of its length


def render_koi(sw: Swimmer, tau: float, frames: int,
               water_rgb: np.ndarray) -> tuple[dict, set]:
    """Return ({(y, x): rgb} for one fish, set of its shadow pixels)."""
    koi, path = sw.koi, sw.path
    L = koi.length
    eps, m = 0.30, 3
    t = sw.laps * tau
    s_head = path.total * (sw.phase + t + eps * math.sin(2 * math.pi * m * tau) / (2 * math.pi * m))
    loop_s = frames * 0.08
    beats = max(4, round(1.4 * loop_s * (1.3 if L < 24 else 1.0)))
    flaps = max(3, round(0.8 * loop_s))

    n_u = max(48, int(L * 3))
    u = np.linspace(0, 1, n_u)
    spine = path.at(s_head - u * L * 0.97)
    wave = L * 0.050 * u ** 1.8 * np.sin(2 * np.pi * (beats * tau - u * 1.15) + koi.seed % 7)

    def frame_of(sp):
        tg = np.gradient(sp, axis=0)
        tg = -tg / np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-9)  # head-ward
        return tg, np.stack([-tg[:, 1], tg[:, 0]], -1)

    tang, nrm = frame_of(spine)
    spine = spine + nrm * wave[:, None]
    tang, nrm = frame_of(spine)
    widths = _width(u) * L

    def at(uu: float) -> int:
        return int(round(uu * (n_u - 1)))

    body_end = at(0.80)
    left = spine[: body_end + 1] + nrm[: body_end + 1] * widths[: body_end + 1, None]
    right = spine[: body_end + 1] - nrm[: body_end + 1] * widths[: body_end + 1, None]
    body_poly = np.vstack([left, right[::-1]])

    # Tail: two lobes with a shallow fork; adults carry longer, flowing lobes.
    big = koi.fin_scale
    half = L * 0.105 * big
    jt = n_u - 1
    pl, pr = left[-1], right[-1]
    reach = -L * 0.04 * (big - 1)
    tip_l = spine[jt] + nrm[jt] * half + tang[jt] * reach
    tip_r = spine[jt] - nrm[jt] * half + tang[jt] * reach
    mid_l = spine[at(0.90)] + nrm[at(0.90)] * half * 0.62
    mid_r = spine[at(0.90)] - nrm[at(0.90)] * half * 0.62
    notch = spine[at(0.93)]
    fins = [np.array([pl, mid_l, tip_l, notch, tip_r, mid_r, pr])]
    rays: list[tuple[np.ndarray, np.ndarray]] = []
    flap = math.radians(16) * math.sin(2 * math.pi * flaps * tau + koi.seed % 5)

    def fan(uu: float, length: float, angle: float, spread: float, side: int) -> None:
        j = at(uu)
        origin = spine[j] + nrm[j] * side * widths[j] * 0.75
        centre = _rot(-tang[j], -side * angle)
        arc = [origin + _rot(centre, a) * length * (0.92 + 0.08 * math.cos(a * 3))
               for a in np.linspace(-spread, spread, 11)]
        fins.append(np.vstack([origin[None, :], arc]))
        for a in np.linspace(-spread * 0.65, spread * 0.65, 4 if koi.adult else 3):
            rays.append((origin, origin + _rot(centre, a) * length * 0.88))

    pect = L * 0.13 * koi.fin_scale
    for side in (-1, 1):
        fan(0.22, pect, math.radians(52) + flap * side, math.radians(24), side)
        if koi.fed >= 25:
            fan(0.47, pect * 0.55, math.radians(40) - flap * side * 0.5, math.radians(18), side)

    body = _poly_mask([body_poly])
    fin = _poly_mask(fins) & ~body
    every = body | fin
    fish: dict = {}
    off = 2 if L < 30 else 3
    shadow = {(y + off, x + off - 1) for y, x in zip(*np.nonzero(every))
              if y + off < H and 0 <= x + off - 1 < W}

    base = _ramp(hex_to_rgb(IVORY))
    fy, fx = np.nonzero(fin)
    for y, x in zip(fy, fx):
        fish[(y, x)] = _blend(base[2], water_rgb[y, x], 0.48)
    ray_px = set()
    tail_rays = (-0.7, -0.35, 0.0, 0.35, 0.7) if koi.adult else (-0.6, 0.0, 0.6)
    for a, b in rays + [(spine[body_end], spine[jt] + nrm[jt] * k * half * 0.85) for k in tail_rays]:
        for tt in np.linspace(0, 1, int(np.hypot(*(b - a)) * 2) + 2):
            p = a + (b - a) * tt
            ray_px.add((int(round(p[1])), int(round(p[0]))))
    for (y, x) in ray_px:
        if (y, x) in fish and fin[y, x]:
            fish[(y, x)] = _blend(base[1], water_rgb[y, x], 0.52)

    # Body: per-pixel (u, v) from the nearest spine sample.
    by, bx = np.nonzero(body)
    if len(by):
        P = np.stack([bx + 0.5, by + 0.5], -1)
        sp = spine[: body_end + 1]
        d = np.linalg.norm(P[:, None, :] - sp[None, :, :], axis=-1)
        j = d.argmin(1)
        uu = u[j]
        vv = np.clip(((P - sp[j]) * nrm[j]).sum(1) / np.maximum(widths[j], 0.5), -1, 1)
        pat = _pattern(uu, vv, koi)
        av = np.abs(vv)
        shade = np.full(len(uu), 2)
        shade[av > 0.62] = 1
        shade[(av < 0.25) & (uu > 0.10) & (uu < 0.68)] = 3
        shade[av > 0.88] = 0
        if koi.adult:
            # scale lattice: every other diamond a shade darker on the flanks
            lattice = ((np.floor(uu * L / 2.2) + np.floor((vv + 1) * L * 0.06)) % 2 == 0)
            shade[lattice & (av > 0.35) & (av < 0.88) & (shade == 2)] = 1
        ramps = [_ramp(p.color) for p in koi.patches]
        colors = np.array([(ramps[p] if p >= 0 else base)[s] for p, s in zip(pat, shade)], dtype=np.uint8)
        if koi.ginrin:
            sc = ((np.floor(uu * L / 2.0) + np.floor((vv + 1) * 2.5)) % 3 == 0)
            phase = (np.floor(uu * 41) * 0.137 + np.floor(vv * 3) * 0.29 + tau * 4) % 1.0
            colors[sc & (phase < 0.06) & (av < 0.8)] = _c("#fbfbf6")
        for y, x, col in zip(by, bx, colors):
            fish[(y, x)] = col
        # dorsal fin ridge along the spine (visible on bigger fish)
        if L >= 26:
            for k in range(at(0.30), at(0.62)):
                x, y = int(round(spine[k, 0] - 0.5)), int(round(spine[k, 1] - 0.5))
                if (y, x) in fish:
                    fish[(y, x)] = _blend(fish[(y, x)], base[3], 0.45)

    if L >= 16:
        je = at(0.07)
        for side in (-1, 1):
            p = spine[je] + nrm[je] * side * widths[je] * 0.70
            x, y = int(round(p[0] - 0.5)), int(round(p[1] - 0.5))
            if 0 <= x < W and 0 <= y < H:
                fish[(y, x)] = _c(EYE)
    return fish, shadow


def make_swimmers(school: list[KoiSpec], login: str, day: str) -> list[Swimmer]:
    out = []
    for k in school:
        seed = zlib.crc32(f"{login}:{day}:{k.index}".encode())
        stiff = 1.0 + 1.6 * max(0.0, (k.length - 22) / 30)
        path = make_path(seed, margin=k.length * 0.30 + 6, stiffness=stiff)
        laps = 2 if (not k.adult and k.length < 24) else 1
        out.append(Swimmer(k, path, laps, (seed % 997) / 997))
    return out


@dataclass
class Ripple:
    x: float
    y: float
    t0: float  # start, fraction of loop
    life: float  # fraction of loop


def make_ripples(seed: int, scene: Scene, n: int = 8) -> list[Ripple]:
    rng = np.random.default_rng(seed + 17)
    ys, xs = np.nonzero(scene.band >= 1)
    out = []
    for _ in range(n):
        i = rng.integers(len(xs))
        out.append(Ripple(float(xs[i]), float(ys[i]), rng.random(), rng.uniform(0.12, 0.18)))
    return out


def render_frame(scene: Scene, swimmers: list[Swimmer], ripples: list[Ripple],
                 tau: float, frames: int, seed: int) -> np.ndarray:
    img = scene.rgb.copy()
    water = scene.water

    for rp in ripples:
        age = (tau - rp.t0) % 1.0
        if age > rp.life:
            continue
        a = age / rp.life
        rad = 1.0 + 13.0 * a
        y0, y1 = int(rp.y - rad - 2), int(rp.y + rad + 3)
        x0, x1 = int(rp.x - rad - 2), int(rp.x + rad + 3)
        yy, xx = np.mgrid[max(0, y0):min(H, y1), max(0, x0):min(W, x1)]
        d = np.hypot(xx + 0.5 - rp.x, (yy + 0.5 - rp.y) * 1.35)
        ring = np.abs(d - rad) < 0.55
        keep = ((xx * 7 + yy * 13) % 4) >= int(a * 4)
        m = ring & keep & water[yy, xx]
        img[yy[m], xx[m]] = _c(RIPPLE)

    # Shadows for the whole school first, then fish: big ones below small ones.
    rendered = [render_koi(sw, tau, frames, img) for sw in swimmers]
    for _, shadow in rendered:
        for (y, x) in shadow:
            if water[y, x]:
                img[y, x] = (img[y, x] * 0.68).astype(np.uint8)
    order = sorted(range(len(swimmers)), key=lambda i: -swimmers[i].koi.length)
    for i in order:
        for (y, x), col in rendered[i][0].items():
            if water[y, x]:
                img[y, x] = col

    for p in scene.pads:
        _draw_pad(img, p, scene.band)

    prng = np.random.default_rng(seed + 23)
    span_x = W - 2 * RIM
    for k in range(5):
        y0 = prng.uniform(RIM + 8, H - RIM - 8)
        x0 = prng.uniform(0, span_x)
        x = RIM + (x0 + tau * span_x * (1 + (k % 2))) % span_x
        y = y0 + 3.0 * math.sin(2 * math.pi * (2 * tau + k / 5))
        X, Y = int(x), int(y)
        for (ox, oy), col in (((0, 0), PETAL[1]), ((1, 0), PETAL[2]), ((0, 1), PETAL[0]), ((1, 1), PETAL[1])):
            if 0 <= Y + oy < H and 0 <= X + ox < W and water[Y + oy, X + ox]:
                img[Y + oy, X + ox] = _c(col)

    rng = np.random.default_rng(seed + 5)
    ys, xs = np.nonzero(scene.band >= 2)
    for k in range(12):
        i = rng.integers(len(xs))
        ph = (tau * 2 + k / 12) % 1.0
        if ph < 0.05 and water[ys[i], xs[i]]:
            img[ys[i], xs[i]] = _c(GLINT)
            if ph < 0.025 and xs[i] + 1 < W:
                img[ys[i], xs[i] + 1] = _c(GLINT)
    if scene.over_mask is not None:  # bridge last: everything passes under it
        img[scene.over_mask] = scene.over_rgb[scene.over_mask]
    return img


def leaves_for(languages: list[tuple[str, str, float]], min_share: float = 0.03) -> list[Swatch]:
    from ..palette import swatches

    # Leaves keep a hint of green so pads still read as pads.
    return swatches(languages, tint=(0.42, 0.62, 0.36), min_share=min_share,
                    max_sat=0.46, light=(0.50, 0.60), tint_mix=0.32)
