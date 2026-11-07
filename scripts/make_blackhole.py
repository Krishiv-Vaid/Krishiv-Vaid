"""A Schwarzschild black hole with a thin accretion disk, rendered in 0s and 1s.

This is a real ray trace (geometric units G = c = M = 1, so r_s = 2), not an
approximation of the look:

* Every character cell fires 3x3 rays backward from a distant observer at
  inclination INC. A ray with image-plane offset (alpha, beta) has impact
  parameter b and stays in one plane. Its orbit u(phi) = 1/r obeys
        u'' + u = 3 u^2,      u(0) = 0,  u'(0) = 1/b,
  integrated with RK4 in phi.
* u > 1/2 means the ray crossed the horizon (shadow). u < 0 means it escaped.
  Rays with b near sqrt(27) ~ 5.196 wind around the hole before deciding; they
  are the photon ring.
* Each time the ray's plane cuts the equator we check r against the disk
  [R_IN, R_OUT]. The first hit wins (the disk is opaque). Hits after half an
  orbit or more are the lensed far side of the disk, bent over the top and
  under the bottom.
* Disk emission is the thin-disk profile F(r) ~ r^-3 (1 - sqrt(6/r)), which
  vanishes at the ISCO (r = 6). Each patch orbits at the Keplerian
  Omega = r^-3/2. The photon's redshift is
        1 + z = (1 - 3/r)^-1/2 * (1 - Omega * L_z),   L_z = -alpha sin(INC),
  gravitational plus Doppler. Observed intensity ~ g^4 F with g = 1/(1+z), so
  the side coming toward us is brighter (beaming) and bluer: color encodes g.

Animation (CSS inside the SVG):
* Rotation: each disk cell's brightness is modulated by cos(m (phi_disk - Omega t)),
  with Omega taken from that cell's own radius. Inner rings turn faster, so
  features shear the way a Keplerian disk does.
* Flicker: digits near the inner edge and photon ring swap between 0 and 1.

Output: assets/blackhole.svg
"""

import numpy as np
from common import BG, CYAN, DIM, FAINT, FG, MAGENTA, MONO, VIOLET, f, lerp_color, svg_doc, write

INC = np.radians(80.0)
R_IN, R_OUT = 6.0, 17.0
COLS, ROWS = 92, 30
CW, CH = 6.0, 11.0  # px per cell (monospace 10px: 0.6em advance)
FONT = 10
SCALE = 0.072  # geometric units per px, the same on both axes
SS = 3  # supersampling per axis
PAD_X, PAD_Y = 24, 30
W, H = int(COLS * CW + 2 * PAD_X), int(ROWS * CH + PAD_Y + 52)
rng = np.random.default_rng(1)


def trace():
    # image-plane sample points, cell-major so we can average per cell
    ix = (np.arange(COLS * SS) + 0.5) / SS - COLS / 2
    iy = (np.arange(ROWS * SS) + 0.5) / SS - ROWS / 2
    alpha = ix[None, :] * CW * SCALE
    beta = -iy[:, None] * CH * SCALE
    alpha, beta = np.broadcast_arrays(alpha, beta)
    a, bt = alpha.ravel(), beta.ravel()
    b = np.hypot(a, bt) + 1e-9

    o = np.array([0.0, -np.sin(INC), np.cos(INC)])  # toward observer
    d = np.stack([a / b, bt * np.cos(INC) / b, bt * np.sin(INC) / b], 1)  # in-plane offset dir

    n = a.size
    u, du = np.zeros(n), 1.0 / b
    alive = np.ones(n, bool)
    captured = np.zeros(n, bool)
    hit_r = np.full(n, np.nan)
    hit_phid = np.zeros(n)
    hit_order = np.full(n, -1)
    crossings = np.zeros(n, int)
    esc_dir = np.zeros((n, 3))

    def zc(phi):
        return np.cos(phi) * o[2] + np.sin(phi) * d[:, 2]

    h, phi = 0.004, 0.0
    z_prev = zc(phi)
    while phi < 4 * np.pi and alive.any():
        def acc(uu):
            return 3 * uu * uu - uu
        k1u, k1v = du, acc(u)
        k2u, k2v = du + h / 2 * k1v, acc(u + h / 2 * k1u)
        k3u, k3v = du + h / 2 * k2v, acc(u + h / 2 * k2u)
        k4u, k4v = du + h * k3v, acc(u + h * k3u)
        un = u + h / 6 * (k1u + 2 * k2u + 2 * k3u + k4u)
        dun = du + h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        phin = phi + h
        z_new = zc(phin)

        cross = alive & (np.sign(z_new) != np.sign(z_prev)) & (z_prev != 0)
        if cross.any():
            w = z_prev[cross] / (z_prev[cross] - z_new[cross])
            uc = u[cross] + w * (un[cross] - u[cross])
            pc = phi + w * h
            rc = 1 / np.maximum(uc, 1e-9)
            idx = np.flatnonzero(cross)
            ok = (rc >= R_IN) & (rc <= R_OUT) & np.isnan(hit_r[idx]) & (uc > 0)
            j = idx[ok]
            hit_r[j] = rc[ok]
            rhat = np.cos(pc[ok])[:, None] * o + np.sin(pc[ok])[:, None] * d[j]
            hit_phid[j] = np.arctan2(rhat[:, 1], rhat[:, 0])
            hit_order[j] = crossings[j]
            crossings[idx] += 1

        u, du, phi, z_prev = np.where(alive, un, u), np.where(alive, dun, du), phin, z_new
        cap = alive & (u >= 0.5)
        esc = alive & (u <= 0)
        captured |= cap
        if esc.any():
            j = np.flatnonzero(esc)
            esc_dir[j] = np.cos(phi) * o + np.sin(phi) * d[j]
        alive &= ~(cap | esc)
        # a ray that already hit the opaque disk is done
        alive &= np.isnan(hit_r)

    orbiting = alive  # still winding at 4*pi: right on the photon sphere
    return dict(alpha=a, b=b, hit_r=hit_r, hit_phid=hit_phid, hit_order=hit_order,
                captured=captured, orbiting=orbiting, esc_dir=esc_dir)


def shade(tr):
    r, a = tr["hit_r"], tr["alpha"]
    hit = ~np.isnan(r)
    rr = np.where(hit, r, R_IN)
    F = rr**-3 * (1 - np.sqrt(R_IN / rr))
    omega = rr**-1.5
    one_z = (1 - 3 / rr) ** -0.5 * (1 + omega * a * np.sin(INC))  # L_z = -alpha sin i
    g = 1 / one_z
    I = np.where(hit, g**4 * F, 0.0)

    # background: celestial grid seen through the lens
    e = tr["esc_dir"]
    lat = np.degrees(np.arcsin(np.clip(e[:, 2], -1, 1)))
    lon = np.degrees(np.arctan2(e[:, 1], e[:, 0]))
    on_grid = (np.abs((lat + 7.5) % 15 - 7.5) < 1.4) | (np.abs((lon + 7.5) % 15 - 7.5) < 1.4)
    escaped = ~hit & ~tr["captured"] & ~tr["orbiting"]
    bg = np.where(escaped, np.where(on_grid, 1.0, 0.0), 0.0)

    def cells(x):
        return x.reshape(ROWS, SS, COLS, SS).mean(axis=(1, 3))

    def cells_w(x, wgt):
        num = (x * wgt).reshape(ROWS, SS, COLS, SS).sum(axis=(1, 3))
        den = wgt.reshape(ROWS, SS, COLS, SS).sum(axis=(1, 3))
        return np.where(den > 0, num / np.maximum(den, 1e-12), np.nan)

    Ic = cells(I)
    hitc = cells(hit.astype(float))
    gc = cells_w(g, hit * I + 1e-30 * hit)
    rc = cells_w(np.where(hit, r, 0), hit.astype(float))
    phidc = np.angle(cells_w(np.exp(1j * tr["hit_phid"]), hit.astype(float)).astype(complex))
    orderc = cells_w(tr["hit_order"].astype(float), hit.astype(float))
    ringc = cells(tr["orbiting"].astype(float))
    capc = cells(tr["captured"].astype(float))
    bgc = cells(bg)
    return dict(I=Ic, hit=hitc, g=gc, r=rc, phid=phidc, order=orderc, ring=ringc, cap=capc, bg=bgc)


def render(c) -> str:
    I = c["I"] / np.percentile(c["I"][c["I"] > 0], 98)
    lum = np.clip(I, 0, 1) ** 0.36
    # photon ring: rays still orbiting, plus higher-order disk images
    lum = np.maximum(lum, np.clip(c["ring"] * 3, 0, 1) * 0.9)
    lum = np.where(c["order"] >= 0.5, np.clip(lum * 1.6 + 0.25, 0, 1), lum)
    gmin, gmax = np.nanpercentile(c["g"], [2, 98])

    styles, rules = {}, []

    def cls(color, key):
        if key not in styles:
            styles[key] = f"c{len(styles)}"
            rules.append(f".{styles[key]}{{fill:{color}}}")
        return styles[key]

    # rotation classes: radial bin x phase bin
    m, NPH = 2, 12
    rbins = np.geomspace(R_IN, R_OUT, 8)
    P0 = 7.0  # s, period at the ISCO; P ~ r^1.5
    for k in range(len(rbins) - 1):
        rmid = np.sqrt(rbins[k] * rbins[k + 1])
        Pm = P0 * (rmid / R_IN) ** 1.5 / m
        for p in range(NPH):
            rules.append(f".k{k}_{p}{{animation:spin {f(Pm, 2)}s linear {f(-Pm * (1 - p / NPH), 2)}s infinite}}")

    rows_svg, flick = [], []
    flick_candidates = []
    for y in range(ROWS):
        runs, cur = [], None
        for x in range(COLS):
            L = lum[y, x]
            disk = c["hit"][y, x] > 0.15 and L > 0.035
            ring = c["ring"][y, x] > 0.05
            if disk or ring:
                g = c["g"][y, x] if not np.isnan(c["g"][y, x]) else (gmin + gmax) / 2
                tg = np.clip((g - gmin) / (gmax - gmin + 1e-9), 0, 1)
                hue = lerp_color([MAGENTA, VIOLET, CYAN, "#E8FCFF"], tg)
                lq = round(min(max(L, 0.26), 1.0) * 10) / 10
                color = lerp_color([BG, hue], lq)
                ccls = cls(color, (hue, lq))
                if disk and not np.isnan(c["r"][y, x]):
                    rk = int(np.clip(np.searchsorted(rbins, c["r"][y, x]) - 1, 0, len(rbins) - 2))
                    ph = (m * c["phid"][y, x] / (2 * np.pi)) % 1
                    acls = f" k{rk}_{int(ph * NPH) % NPH}"
                    near = c["r"][y, x] < 7.5 or c["order"][y, x] >= 0.5
                else:
                    acls, near = "", True
                key = ccls + acls
                if near and L > 0.25:
                    flick_candidates.append((x, y, key))
            elif c["cap"][y, x] < 0.05 and c["hit"][y, x] == 0 and rng.random() < 0.13:
                key = cls(lerp_color([BG, FAINT], 0.55), ("bg", 0))
            else:
                key = None
            ch = "01"[rng.integers(2)] if key else None
            if key != cur:
                runs.append([key, [], ""])
                cur = key
            if key:
                runs[-1][1].append(PAD_X + x * CW)
                runs[-1][2] += ch
        spans = "".join(
            f'<tspan class="{k}" x="{" ".join(f(v) for v in xs)}">{s}</tspan>' for k, xs, s in runs if k
        )
        rows_svg.append(f'<text y="{f(PAD_Y + (y + 0.8) * CH)}">{spans}</text>')

    # flicker: overlay a 0 and a 1 that swap; the base glyph underneath is hidden by a dark block
    pick = rng.choice(len(flick_candidates), size=min(170, len(flick_candidates)), replace=False)
    for i in pick:
        x, y, key = flick_candidates[i]
        px, py = PAD_X + x * CW, PAD_Y + (y + 0.8) * CH
        fc = f"f{rng.integers(5)}"
        flick.append(
            f'<rect x="{f(px)}" y="{f(py - CH * 0.78)}" width="{f(CW)}" height="{f(CH)}" fill="{BG}"/>'
            f'<text class="{key}" y="{f(py)}"><tspan x="{f(px)}" class="{fc}">0</tspan>'
            f'<tspan x="{f(px)}" class="{fc} b">1</tspan></text>'
        )
    flick_rules = "".join(
        f".f{k}{{animation:flk {f(0.6 + 0.37 * k, 2)}s steps(1) {f(-0.21 * k, 2)}s infinite}}" for k in range(5)
    )
    css = (
        "@keyframes spin{0%{opacity:1}50%{opacity:.42}100%{opacity:1}}"
        "@keyframes flk{0%{opacity:1}50%{opacity:0}}"
        ".b{animation-direction:reverse!important}"
        + "".join(rules) + flick_rules
    )

    shadow_r = np.sqrt(27) / SCALE  # px
    cx, cy = PAD_X + COLS * CW / 2, PAD_Y + ROWS * CH / 2
    body = (
        f"<style>{css}</style>"
        f'<g font-family="{MONO}" font-size="{FONT}">{"".join(rows_svg)}{"".join(flick)}</g>'
        f'<g font-family="{MONO}" font-size="11" fill="{DIM}">'
        f'<text x="{PAD_X}" y="20">fig. 2 · schwarzschild, i = {round(np.degrees(INC))}°</text>'
        f'<text x="{W - PAD_X}" y="20" text-anchor="end">← approaching · receding →</text>'
        f'<text x="{W / 2}" y="{H - 30}" text-anchor="middle" fill="{FG}" font-size="12">'
        f"u″ + u = 3Mu² · disk {f(R_IN)}–{f(R_OUT)} M · I ∝ g⁴F(r)</text>"
        f'<text x="{W / 2}" y="{H - 13}" text-anchor="middle">'
        f"shadow b = √27 M · color = redshift g · {COLS * ROWS * SS * SS:,} rays</text></g>"
    )
    return svg_doc(W, H, body, "Black hole ray-traced in binary: shadow, lensed accretion disk, photon ring")


if __name__ == "__main__":
    tr = trace()
    c = shade(tr)
    write("blackhole.svg", render(c))
