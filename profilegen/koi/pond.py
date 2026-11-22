"""Pixel-art koi pond.

Everything is drawn at native resolution (``W x H`` pixels) with hard pixel
edges, then upscaled by an integer factor with nearest-neighbour sampling so
the browser never blurs it. Pixels outside the stone rim are transparent, so a
single GIF sits on both GitHub themes.

Scene
-----
* stone rim (Voronoi stones, mortar, moss) and a vermilion KV seal;
* water in four depth bands with ordered (Bayer) dithering between them, over a
  faint seigaiha wave pattern on the pond floor;
* lily pads tinted by the languages I write, one pad per share of code, some
  carrying lotus flowers;
* the koi: a spine that follows a closed Fourier path by arc length, so the
  body bends naturally through turns, plus a travelling tail-beat wave,
  flapping pectoral fins, translucent fins and a seeded body pattern whose
  patches take my top language's colour;
* ripples, surface glints and the koi's shadow on the floor.

Every animated quantity is periodic over the loop, so the GIF is seamless,
while the path itself is re-seeded each day: the koi never repeats a route
from one day to the next.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..palette import RGB, Swatch, hex_to_rgb, mute, shade_ramp
from .evolution import Koi

W, H = 210, 106
RIM = 8
CORNER = 11

WATER = ["#2f6a72", "#25596440", "#1c4955", "#153a46"]  # shallow -> deep (alpha stripped)
WATER = [c[:7] for c in WATER]
FLOOR = ["#367780", "#2b6470", "#225360", "#1a4350"]  # seigaiha line per band
RIPPLE = "#79aaa9"
GLINT = "#d7ebe3"
STONES = ["#4a5057", "#5b6269", "#6e757c", "#838a90"]
MORTAR = "#2a2f35"
MOSS = ["#5d7a52", "#86a36e"]
WOOD = ["#4a3a2e", "#5c4838", "#6e5843"]
RAIL = ["#7e342c", "#a8483c", "#c96a58"]
BRIDGE_X, BRIDGE_W = W - 62, 16
SEAL = "#b0473b"
IVORY = "#ece5d3"
EYE = "#1d2328"
PETAL = ["#c98993", "#e2b3b8", "#f2d9da"]
POLLEN = "#e6cf86"

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0

GLYPHS = {  # 3x5 pixel font for the seal
    "K": ["1.1", "11.", "1..", "11.", "1.1"],
    "V": ["1.1", "1.1", "1.1", "1.1", ".1."],
}


def _c(h: str | RGB) -> np.ndarray:
    rgb = hex_to_rgb(h) if isinstance(h, str) else h
    return np.array([round(v * 255) for v in rgb], dtype=np.uint8)


def _blend(a, b, t: float) -> np.ndarray:
    a, b = _c(a) if not isinstance(a, np.ndarray) else a, _c(b) if not isinstance(b, np.ndarray) else b
    return np.round(a * (1 - t) + b * t).astype(np.uint8)


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


def _seigaiha(r: float = 7.0) -> np.ndarray:
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


def build_scene(koi: Koi, leaves: list[Swatch], seed: int) -> Scene:
    rng = np.random.default_rng(seed)
    alpha = _rounded_rect(0, CORNER)
    water = _rounded_rect(RIM, CORNER - RIM / 2)
    rgb = np.zeros((H, W, 3), dtype=np.uint8)

    # Rim: Voronoi stones.
    pts = []
    perim = 2 * (W + H)
    for k in range(int(perim / 7)):
        s = (k + rng.uniform(-0.3, 0.3)) * 7
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
    # top-left light on each stone: highlight pixels nearer the stone's top-left
    vec = np.stack([xx - pts[nearest, 0], yy - pts[nearest, 1]], -1)
    lit = (vec[..., 0] + vec[..., 1]) < -1.6
    rim_rgb[lit] = stone[np.minimum(tone[nearest][lit] + 1, 3)]
    rim_rgb[(d2 - d1) < 0.9] = _c(MORTAR)
    moss = (rng.random((H, W)) < 0.05) & ((d2 - d1) < 1.6)
    rim_rgb[moss] = _c(MOSS[0])
    rim_rgb[moss & (rng.random((H, W)) < 0.4)] = _c(MOSS[1])
    rgb[:] = rim_rgb
    # inner lip: a dark line where stone meets water
    lip = _rounded_rect(RIM - 1, CORNER - RIM / 2 + 1) & ~water
    rgb[lip] = _c(MORTAR)

    # Water depth bands with Bayer-dithered transitions.
    inner = water.copy()
    dist = np.zeros((H, W))
    # distance to the water edge (cheap: iterate erosions)
    cur = inner.copy()
    for k in range(1, 40):
        nxt = cur.copy()
        nxt[1:, :] &= cur[:-1, :]
        nxt[:-1, :] &= cur[1:, :]
        nxt[:, 1:] &= cur[:, :-1]
        nxt[:, :-1] &= cur[:, 1:]
        dist[cur & ~nxt] = k
        cur = nxt
        if not cur.any():
            break
    dist[cur] = 40
    bayer = np.tile(BAYER4, (H // 4 + 1, W // 4 + 1))[:H, :W]
    band = np.clip(np.floor(dist / 5.5 + bayer - 0.5), 0, 3).astype(int)
    band[~water] = -1
    floor = _seigaiha()
    wc = np.array([_c(c) for c in WATER])
    fc = np.array([_c(c) for c in FLOOR])
    rgb[water] = wc[band[water]]
    pat = water & floor & (band >= 1)
    rgb[pat] = fc[band[pat]]

    # Pebbles on the pond floor (static, slightly darker than the water band).
    for _ in range(4):
        cx, cy = rng.uniform(RIM + 20, W - RIM - 20), rng.uniform(RIM + 14, H - RIM - 14)
        for _ in range(rng.integers(4, 8)):
            px_, py_ = int(cx + rng.normal(0, 4)), int(cy + rng.normal(0, 2.5))
            for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1))[: rng.integers(2, 5)]:
                X, Y = px_ + ox, py_ + oy
                if water[Y, X]:
                    rgb[Y, X] = np.round(wc[band[Y, X]] * 0.80 + _c(STONES[1]) * 0.20).astype(np.uint8)
            if water[py_, px_]:
                rgb[py_, px_] = np.round(wc[band[py_, px_]] * 0.6 + _c(STONES[3]) * 0.4).astype(np.uint8)

    # Reed tufts growing over the rim in two corners.
    for (bx, by, lean) in ((RIM + 3, H - RIM + 2, 1), (W - RIM - 4, RIM + 6, -1)):
        for k in range(7):
            hgt = rng.integers(6, 13)
            x = bx + k - 3
            for t in range(hgt):
                X = int(round(x + lean * (t / hgt) ** 2 * (k - 3) * 0.8))
                Y = by - t if lean > 0 else by + t - 2
                if 0 <= X < W and 0 <= Y < H and alpha[Y, X]:
                    rgb[Y, X] = _c(MOSS[1] if t > hgt * 0.6 else MOSS[0])

    # Vermilion drum bridge across the pond, seen from above. Static overlay:
    # the koi swims underneath it.
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
                tone = 2 if arch > 0.6 else 1 if arch > 0.25 else 0
                c = WOOD[tone] if (y % 4) else WOOD[max(0, tone - 1)]
            over[y, x] = _c(c)
            omask[y, x] = True
    for y in range(6, H - 4, 13):  # posts with caps
        for x in (x0, x1 - 2):
            for oy in range(3):
                for ox in range(2):
                    over[y + oy, x + ox] = _c(RAIL[0])
            over[y, x] = _c(RAIL[2])
    # its shadow on the water
    sh = water & ~omask
    sh[:, : x1] = False
    sh[:, x1 + 3:] = False
    rgb[sh] = (rgb[sh] * 0.72).astype(np.uint8)

    # Seal on the rim, bottom-right.
    sx, sy = W - CORNER - 13, H - RIM + 0
    rgb[sy: sy + 7, sx: sx + 11] = _c(SEAL)
    for gi, ch in enumerate("KV"):
        for r, row in enumerate(GLYPHS[ch]):
            for c, bit in enumerate(row):
                if bit == "1":
                    rgb[sy + 1 + r, sx + 2 + gi * 4 + c] = _c(IVORY)

    # Lily pads near the rim, one per share of code (largest remainder).
    n_pads = 7
    shares = np.array([s.share for s in leaves])
    raw = shares * n_pads
    counts = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - counts))[: n_pads - counts.sum()]:
        counts[i] += 1
    assigned = [leaves[i] for i, n in enumerate(counts) for _ in range(n)]
    rng.shuffle(assigned)
    pads: list[Pad] = []
    tries = 0
    while len(pads) < len(assigned) and tries < 4000:
        tries += 1
        r = rng.uniform(4.2, 7.2)
        x, y = rng.uniform(RIM + r, W - RIM - r), rng.uniform(RIM + r, H - RIM - r)
        edge = min(x - RIM, W - RIM - x, y - RIM, H - RIM - y)
        if edge > 16 or any(math.hypot(x - p.x, y - p.y) < r + p.r + 3 for p in pads):
            continue
        if x > W - CORNER - 22 and y > H - 20:  # keep the seal clear
            continue
        if BRIDGE_X - r - 3 < x < BRIDGE_X + BRIDGE_W + r + 4:  # and the bridge
            continue
        pads.append(Pad(x, y, r, rng.uniform(0, 2 * math.pi), assigned[len(pads)]))
    for p in pads[: koi.lotus]:
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
    # shadow on the water first
    sh = np.roll(np.roll(inside, 1, 0), 1, 1) & ~inside
    for (yy_, xx_) in zip(*np.nonzero(sh)):
        Y, X = y0 + yy_, x0 + xx_
        if 0 <= Y < H and 0 <= X < W and water_band[Y, X] >= 0:
            img[Y, X] = (img[Y, X] * 0.70).astype(np.uint8)
    idx = np.full(d.shape, 2)
    idx[(dx + dy) < -0.55 * p.r] = 3
    idx[(dx + dy) > 0.55 * p.r] = 1
    idx[(d > p.r - 1.0) & ((dx + dy) > 0)] = 0
    # veins
    vein_ang = np.angle(np.exp(1j * (np.arctan2(dy, dx) - p.notch - math.pi)))
    for a in (-1.2, 0.0, 1.2):
        idx[(np.abs(vein_ang - a) < 0.10) & (d > 1.2) & (d < p.r - 1.2)] = 1
    for (yy_, xx_) in zip(*np.nonzero(inside)):
        Y, X = y0 + yy_, x0 + xx_
        if 0 <= Y < H and 0 <= X < W:
            img[Y, X] = ramp[idx[yy_, xx_]]
    if p.lotus:
        cx, cy = int(round(p.x - p.r * 0.25)), int(round(p.y - p.r * 0.2))
        flower = {(0, -2): 1, (-1, -1): 0, (1, -1): 0, (0, -1): 2, (-2, 0): 1, (2, 0): 1,
                  (-1, 0): 2, (1, 0): 2, (0, 0): -1, (-1, 1): 0, (1, 1): 0, (0, 1): 1}
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


@dataclass
class KoiColors:
    base: list[np.ndarray]
    hi: list[np.ndarray]
    sumi: list[np.ndarray]


def koi_colors(leaves: list[Swatch]) -> KoiColors:
    named = [s for s in leaves if s.name not in ("other", "unknown")]
    primary = named[0].source if named else "#c0533f"
    secondary = named[1].source if len(named) > 1 else "#30343a"
    hi = mute(primary, max_sat=0.58, light=(0.46, 0.58))
    sumi = mute(secondary, max_sat=0.35, light=(0.22, 0.30))
    return KoiColors(_ramp(hex_to_rgb(IVORY)), _ramp(hi), _ramp(sumi))


def _width(u: np.ndarray) -> np.ndarray:
    """Half-width of the body (fraction of length) along the spine, top-down."""
    head = 0.112 * np.sqrt(np.clip(u / 0.11, 0, 1)) ** 0.9
    mid = 0.112 + 0.010 * np.sin(np.clip((u - 0.11) / 0.26, 0, 1) * np.pi)
    taper = 0.112 - (0.112 - 0.030) * np.clip((u - 0.37) / 0.43, 0, 1) ** 1.25
    return np.where(u < 0.11, head, np.where(u < 0.37, mid, taper))


def _pattern(u: np.ndarray, v: np.ndarray, koi: Koi, seed: int) -> np.ndarray:
    """0 = base, 1 = primary patch, 2 = secondary spot. (u along body, v in [-1, 1])."""
    rng = np.random.default_rng(seed + 991)
    out = np.zeros(u.shape, dtype=int)
    # Kohaku-style "steps": head patch, then saddles along the back.
    centres = [0.06, 0.27, 0.45, 0.62][: koi.patches]
    for k, c in enumerate(centres):
        a = 0.045 if k == 0 else rng.uniform(0.06, 0.085)
        b = rng.uniform(0.9, 1.3)
        off = rng.uniform(-0.3, 0.3) if k else 0.0
        edge = 0.18 * np.sin(v * rng.uniform(3, 5) + rng.uniform(0, 6)) * a
        m = ((u - c + edge) / a) ** 2 + ((v - off) / b) ** 2 < 1.0
        out[m] = 1
    if koi.spots:
        for _ in range(6):
            c, off = rng.uniform(0.18, 0.72), rng.choice([-1, 1]) * rng.uniform(0.25, 0.8)
            m = ((u - c) / 0.018) ** 2 + ((v - off) / 0.28) ** 2 < 1.0
            out[m & (out == 0)] = 2
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


def render_koi(koi: Koi, path: Path, tau: float, frames: int, cols: KoiColors,
               water_rgb: np.ndarray, seed: int) -> tuple[dict, set]:
    """Return ({(y, x): rgb} for the fish, set of shadow pixels)."""
    L = koi.length
    # Head position by arc length, with gentle speed variation (periodic).
    eps, m = 0.30, 3
    s_head = path.total * (tau + eps * math.sin(2 * math.pi * m * tau) / (2 * math.pi * m))
    loop_s = frames * 0.08
    beats = max(4, round(1.4 * loop_s))  # tail beats per loop (integer -> seamless)
    flaps = max(3, round(0.8 * loop_s))

    n_u = max(40, int(L * 3))
    u = np.linspace(0, 1, n_u)
    spine = path.at(s_head - u * L * 0.97)
    wave = L * 0.050 * u ** 1.8 * np.sin(2 * np.pi * (beats * tau - u * 1.15))

    def frame_of(sp):
        t = np.gradient(sp, axis=0)
        t = -t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)  # points head-ward
        return t, np.stack([-t[:, 1], t[:, 0]], -1)

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

    # Tail: two lobes with a shallow fork.
    big = koi.fin_scale * (1.45 if koi.butterfly else 1.0)
    half = L * 0.105 * big
    jt = n_u - 1
    pl, pr = left[-1], right[-1]
    tip_l = spine[jt] + nrm[jt] * half + tang[jt] * (-L * 0.03 * (big - 1))
    tip_r = spine[jt] - nrm[jt] * half + tang[jt] * (-L * 0.03 * (big - 1))
    mid_l = spine[at(0.90)] + nrm[at(0.90)] * half * 0.62
    mid_r = spine[at(0.90)] - nrm[at(0.90)] * half * 0.62
    notch = spine[at(0.93)]
    tail_poly = np.array([pl, mid_l, tip_l, notch, tip_r, mid_r, pr])

    # Pectoral fins: rounded fans, flapping.
    fins = [tail_poly]
    rays: list[tuple[np.ndarray, np.ndarray]] = []
    flap = math.radians(16) * math.sin(2 * math.pi * flaps * tau)

    def fan(uu: float, length: float, angle: float, spread: float, side: int) -> None:
        j = at(uu)
        origin = spine[j] + nrm[j] * side * widths[j] * 0.75
        back = -tang[j]
        centre = _rot(back, -side * angle)
        arc = [origin + _rot(centre, a) * length * (0.92 + 0.08 * math.cos(a * 3))
               for a in np.linspace(-spread, spread, 9)]
        fins.append(np.vstack([origin[None, :], arc]))
        for a in np.linspace(-spread * 0.6, spread * 0.6, 3):
            rays.append((origin, origin + _rot(centre, a) * length * 0.85))

    pect = L * 0.13 * koi.fin_scale * (1.7 if koi.butterfly else 1.0)
    for side in (-1, 1):
        fan(0.22, pect, math.radians(52) + flap * side, math.radians(24), side)
        if koi.stage.index >= 2:
            fan(0.47, pect * 0.55, math.radians(40) - flap * side * 0.5, math.radians(18), side)

    body = _poly_mask([body_poly])
    fin = _poly_mask(fins) & ~body
    every = body | fin

    fish: dict = {}
    shadow = {(y + 3, x + 2) for y, x in zip(*np.nonzero(every)) if y + 3 < H and x + 2 < W}

    # Fins: ivory over the water, translucent, with darker rays.
    fy, fx = np.nonzero(fin)
    for y, x in zip(fy, fx):
        fish[(y, x)] = _blend(cols.base[2], water_rgb[y, x], 0.50)
    ray_px = set()
    for a, b in rays + [(spine[body_end], spine[jt] + nrm[jt] * k * half * 0.8) for k in (-0.6, 0.0, 0.6)]:
        for t in np.linspace(0, 1, int(np.hypot(*(b - a)) * 2) + 2):
            p = a + (b - a) * t
            ray_px.add((int(round(p[1])), int(round(p[0]))))
    for (y, x) in ray_px:
        if (y, x) in fish and fin[y, x]:
            fish[(y, x)] = _blend(cols.base[1], water_rgb[y, x], 0.55)

    # Body: per-pixel (u, v) from the nearest spine sample.
    by, bx = np.nonzero(body)
    if len(by):
        P = np.stack([bx + 0.5, by + 0.5], -1)
        sp = spine[: body_end + 1]
        d = np.linalg.norm(P[:, None, :] - sp[None, :, :], axis=-1)
        j = d.argmin(1)
        uu = u[j]
        vv = ((P - sp[j]) * nrm[j]).sum(1) / np.maximum(widths[j], 0.5)
        vv = np.clip(vv, -1, 1)
        pat = _pattern(uu, vv, koi, seed)
        av = np.abs(vv)
        shade = np.full(len(uu), 2)
        shade[av > 0.62] = 1
        shade[(av < 0.25) & (uu > 0.10) & (uu < 0.68)] = 3
        shade[av > 0.88] = 0
        ramps = [cols.base, cols.hi, cols.sumi]
        colors = np.array([ramps[p][s] for p, s in zip(pat, shade)], dtype=np.uint8)
        if koi.ginrin:
            scale = ((np.floor(uu * L / 2.0) + np.floor((vv + 1) * 2.5)) % 3 == 0)
            phase = (np.floor(uu * 41) * 0.137 + np.floor(vv * 3) * 0.29 + tau * 4) % 1.0
            colors[scale & (phase < 0.07) & (av < 0.8)] = _c("#fbfbf6")
        for y, x, col in zip(by, bx, colors):
            fish[(y, x)] = col

    # Eyes.
    if L >= 18:
        je = at(0.07)
        for side in (-1, 1):
            p = spine[je] + nrm[je] * side * widths[je] * 0.70
            x, y = int(round(p[0] - 0.5)), int(round(p[1] - 0.5))
            if 0 <= x < W and 0 <= y < H:
                fish[(y, x)] = _c(EYE)
    return fish, shadow


@dataclass
class Ripple:
    x: float
    y: float
    t0: float  # start, fraction of loop
    life: float  # fraction of loop


def make_ripples(seed: int, scene: Scene, n: int = 7) -> list[Ripple]:
    rng = np.random.default_rng(seed + 17)
    ys, xs = np.nonzero(scene.band >= 1)
    out = []
    for _ in range(n):
        i = rng.integers(len(xs))
        out.append(Ripple(float(xs[i]), float(ys[i]), rng.random(), rng.uniform(0.12, 0.18)))
    return out


def render_frame(scene: Scene, koi: Koi, path: Path, cols: KoiColors, ripples: list[Ripple],
                 tau: float, frames: int, seed: int) -> np.ndarray:
    img = scene.rgb.copy()
    water = scene.water

    # Ripples on the surface (drawn under the pads and the fish).
    for rp in ripples:
        age = (tau - rp.t0) % 1.0
        if age > rp.life:
            continue
        a = age / rp.life
        rad = 1.0 + 10.0 * a
        y0, y1 = int(rp.y - rad - 2), int(rp.y + rad + 3)
        x0, x1 = int(rp.x - rad - 2), int(rp.x + rad + 3)
        yy, xx = np.mgrid[max(0, y0):min(H, y1), max(0, x0):min(W, x1)]
        d = np.hypot(xx + 0.5 - rp.x, (yy + 0.5 - rp.y) * 1.35)
        ring = np.abs(d - rad) < 0.55
        keep = ((xx * 7 + yy * 13) % 4) >= int(a * 4)  # thins out as it spreads
        m = ring & keep & water[yy, xx]
        img[yy[m], xx[m]] = _c(RIPPLE)

    fish, shadow = render_koi(koi, path, tau, frames, cols, img, seed)
    for (y, x) in shadow:
        if water[y, x]:
            img[y, x] = (img[y, x] * 0.66).astype(np.uint8)
    for (y, x), col in fish.items():
        if water[y, x]:
            img[y, x] = col

    for p in scene.pads:
        _draw_pad(img, p, scene.band)

    # Sakura petals drifting on the surface: each crosses the pond an integer
    # number of times per loop, so the drift is seamless.
    prng = np.random.default_rng(seed + 23)
    span_x = W - 2 * RIM
    for k in range(4):
        y0 = prng.uniform(RIM + 6, H - RIM - 6)
        x0 = prng.uniform(0, span_x)
        x = RIM + (x0 + tau * span_x * (1 + (k % 2))) % span_x
        y = y0 + 2.5 * math.sin(2 * math.pi * (2 * tau + k / 4))
        X, Y = int(x), int(y)
        for (ox, oy), col in (((0, 0), PETAL[1]), ((1, 0), PETAL[2]), ((0, 1), PETAL[0])):
            if 0 <= Y + oy < H and 0 <= X + ox < W and water[Y + oy, X + ox]:
                img[Y + oy, X + ox] = _c(col)

    # Surface glints (periodic twinkle).
    rng = np.random.default_rng(seed + 5)
    ys, xs = np.nonzero(scene.band >= 2)
    for k in range(9):
        i = rng.integers(len(xs))
        ph = (tau * 2 + k / 9) % 1.0
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
