"""Hero banner: butterflies flying closed bezier loops around an outlined name.

Each butterfly is drawn top-down with its body on the local +x axis, so
animateMotion rotate="auto" points the head along the flight tangent. A wing
beat is a scaleY on the wing group: seen from above, a raised wing shrinks
toward the body. Smaller butterflies are dimmer and blurrier, so they read as
farther away.

Flight paths are closed Lissajous-like curves (x ~ sin t, y ~ sin 2t plus
wobble harmonics), sampled and smoothed into cubic beziers. A closed path with
repeatCount="indefinite" loops with no seam.

Outputs: assets/butterflies.svg, assets/butterfly-small.svg (footer)
"""

import numpy as np
from common import BG, CYAN, DIM, FAINT, FG, MAGENTA, MONO, VIOLET, closed_catmull_rom, f, svg_doc, text_outline, write

W, H = 1200, 300
rng = np.random.default_rng(7)

# --- one butterfly, local coords: body along x, head at +x, wings toward -y (mirrored for +y)
FOREWING = "M2,0C3,-9 9,-25 22,-30C31,-33 36,-27 33,-19C30,-11 17,-3 2,0Z"
HINDWING = "M4,-1C2,-10 -6,-23 -16,-24C-25,-24 -27,-15 -22,-9C-17,-3 -6,0 4,-1Z"
VEINS = "M3,-1Q12,-14 23,-27M3,-1Q18,-9 31,-19M2,-1Q-6,-12 -15,-21M2,-1Q-10,-6 -21,-11"
SPOTS = '<circle cx="27" cy="-24" r="1.6" fill="#fff" opacity=".55"/><circle cx="-18" cy="-17" r="1.2" fill="#fff" opacity=".4"/>'


def defs() -> str:
    return f"""<defs>
  <radialGradient id="wing" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="32">
    <stop offset=".08" stop-color="{CYAN}"/><stop offset=".55" stop-color="{VIOLET}"/><stop offset="1" stop-color="{MAGENTA}"/>
  </radialGradient>
  <radialGradient id="halo" cx=".5" cy=".5" r=".5">
    <stop offset="0" stop-color="{VIOLET}" stop-opacity=".22"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="name" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{FG}"/><stop offset=".5" stop-color="#E6E9FF"/><stop offset="1" stop-color="{FG}"/>
  </linearGradient>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="far" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="0.9"/></filter>
  <g id="wings">
    <path d="{HINDWING}" fill="url(#wing)" stroke="#fff" stroke-opacity=".3" stroke-width=".5"/>
    <path d="{FOREWING}" fill="url(#wing)" fill-opacity=".92" stroke="#fff" stroke-opacity=".4" stroke-width=".5"/>
    <path d="{VEINS}" stroke="{BG}" stroke-opacity=".45" stroke-width=".6" fill="none"/>
    {SPOTS}
  </g>
  <g id="body">
    <ellipse cx="1" cy="0" rx="10" ry="1.7" fill="{FG}"/>
    <path d="M10,-.6Q15,-2 17,-6M10,.6Q15,2 17,6" stroke="{FG}" stroke-width=".7" fill="none" stroke-linecap="round"/>
  </g>
</defs>"""


def butterfly(flap: float, phase: float) -> str:
    """A butterfly whose wing pairs scale toward the body with period `flap` seconds."""
    beat = (f'<animateTransform attributeName="transform" type="scale" values="1 1;1 .18;1 1" '
            f'keyTimes="0;.45;1" calcMode="spline" keySplines=".4 0 .6 1;.4 0 .6 1" '
            f'dur="{f(flap, 3)}s" begin="-{f(phase, 3)}s" repeatCount="indefinite"/>')
    return (f'<g>{beat}<use href="#wings"/></g>'
            f'<g transform="scale(1,-1)"><g>{beat}<use href="#wings"/></g></g>'
            f'<use href="#body"/>')


def flight_path(cx, cy, ax, ay, seed) -> str:
    r = np.random.default_rng(seed)
    t = np.linspace(0, 2 * np.pi, 28, endpoint=False)
    p1, p2, p3 = r.uniform(0, 2 * np.pi, 3)
    k = r.choice([3, 4, 5])
    x = cx + ax * np.sin(t + p1) + 0.12 * ax * np.sin(k * t + p2)
    y = cy + ay * np.sin(2 * t + p3) + 0.18 * ay * np.cos((k + 1) * t + p1)
    if r.random() < 0.5:
        x = 2 * cx - x  # some fly the loop the other way round
    return closed_catmull_rom(np.column_stack([x, y]))


# (center x, center y, x amplitude, y amplitude, scale, period s)
FLOCK = [
    (600, 150, 640, 110, 1.55, 30),
    (330, 120, 300, 80, 1.05, 21),
    (880, 170, 320, 90, 1.20, 24),
    (600, 90, 560, 60, 0.70, 34),
    (220, 200, 200, 70, 0.60, 17),
    (1000, 95, 220, 60, 0.65, 19),
    (620, 225, 480, 55, 0.85, 27),
]


def banner() -> str:
    parts = [defs()]

    # dust field: faint, a few twinkle
    dust = []
    for i in range(70):
        x, y = rng.uniform(10, W - 10), rng.uniform(10, H - 10)
        r = rng.uniform(0.4, 1.2)
        op = rng.uniform(0.08, 0.35)
        tw = ""
        if i % 6 == 0:
            tw = (f'<animate attributeName="opacity" values="{f(op, 2)};.8;{f(op, 2)}" '
                  f'dur="{f(rng.uniform(3, 7))}s" begin="-{f(rng.uniform(0, 7))}s" repeatCount="indefinite"/>')
        dust.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="{FG}" opacity="{f(op, 2)}">{tw}</circle>')
    parts.append(f'<g>{"".join(dust)}</g>')

    # glow behind the name
    parts.append(f'<ellipse cx="600" cy="150" rx="430" ry="120" fill="url(#halo)"/>')

    # lab-notebook annotations
    parts.append(
        f'<g font-family="{MONO}" font-size="11" fill="{DIM}" letter-spacing=".5">'
        f'<text x="28" y="34">fig. 1 · lepidoptera, in flight</text>'
        f'<text x="1172" y="34" text-anchor="end">43.47°N 80.54°W</text>'
        f'<text x="28" y="276">n = {len(FLOCK)} · paths: closed béziers</text>'
        f'<text x="1172" y="276" text-anchor="end">waterloo, on</text></g>'
        f'<path d="M20,20h14M20,20v14M1180,20h-14M1180,20v14M20,280h14M20,280v-14M1180,280h-14M1180,280v-14" '
        f'stroke="{FAINT}" stroke-width="1.2" fill="none"/>'
    )

    # butterflies behind the name are the far, small ones; near ones fly in front
    far = [b for b in FLOCK if b[4] < 0.9]
    near = [b for b in FLOCK if b[4] >= 0.9]

    def flock_svg(group, idx0):
        out = []
        for i, (cx, cy, ax, ay, sc, dur) in enumerate(group):
            n = idx0 + i
            d = flight_path(cx, cy, ax, ay, seed=100 + n)
            begin = rng.uniform(0, dur)
            flap = rng.uniform(0.26, 0.40) / (0.8 + 0.2 * sc)
            depth = 'filter="url(#far)" opacity=".55"' if sc < 0.9 else 'filter="url(#glow)"'
            # particle trail: same path, slightly behind in time, fading
            for k in range(1, 6):
                lag = k * 0.22
                out.append(
                    f'<circle r="{f(1.5 - 0.2 * k)}" fill="{CYAN if k % 2 else MAGENTA}" opacity="{f(0.55 - 0.09 * k, 2)}">'
                    f'<animateMotion path="{d}" dur="{dur}s" begin="-{f((begin - lag) % dur, 2)}s" repeatCount="indefinite"/></circle>'
                )
            out.append(
                f'<g {depth}><animateMotion path="{d}" dur="{dur}s" begin="-{f(begin, 2)}s" rotate="auto" '
                f'repeatCount="indefinite"/><g transform="scale({sc})">{butterfly(flap, rng.uniform(0, flap))}</g></g>'
            )
        return "".join(out)

    parts.append(flock_svg(far, 0))

    # name, converted to outlines
    d, w, cap = text_outline("KRISHIV VAID", size=84, weight=700, tracking=6)
    x0, base = (W - w) / 2, 150 + cap / 2
    parts.append(f'<path transform="translate({f(x0)},{f(base)})" d="{d}" fill="url(#name)"/>')
    parts.append(
        f'<text x="600" y="{f(base + 34)}" text-anchor="middle" font-family="{MONO}" font-size="14" '
        f'fill="{DIM}" letter-spacing="4">PHYSICS · SILICON · INTELLIGENCE</text>'
    )

    parts.append(flock_svg(near, len(far)))
    return svg_doc(W, H, "\n".join(parts), "Krishiv Vaid — animated butterflies banner", rx=16)


def small() -> str:
    """Footer: one butterfly drifting on a small loop."""
    d = flight_path(60, 40, 26, 10, seed=3)
    # transparent background, so the near-white body would vanish in light mode: use violet
    body = (defs().replace(f'<ellipse cx="1" cy="0" rx="10" ry="1.7" fill="{FG}"/>',
                           f'<ellipse cx="1" cy="0" rx="10" ry="1.7" fill="{VIOLET}"/>')
            .replace(f'stroke="{FG}" stroke-width=".7"', f'stroke="{VIOLET}" stroke-width=".7"') + f'<g filter="url(#glow)"><animateMotion path="{d}" dur="9s" rotate="auto" '
            f'repeatCount="indefinite"/><g transform="scale(.75)">{butterfly(0.34, 0)}</g></g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80" width="120" height="80" '
            f'role="img" aria-label="a butterfly"><title>a butterfly</title>{body}</svg>\n')


if __name__ == "__main__":
    write("butterflies.svg", banner())
    write("butterfly-small.svg", small())
