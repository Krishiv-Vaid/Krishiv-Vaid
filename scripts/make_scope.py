"""Oscilloscope strip: a square wave built up from its Fourier series, sweep by sweep.

    square(x) = (4/pi) * sum_{k odd} sin(k x) / k

Each sweep adds harmonics up to N and draws the partial sum left to right.
The previous sweep stays on as dimming "phosphor". The overshoot readout is the
actual max of each partial sum, computed numerically. It converges to the Gibbs
constant (~8.95%) instead of going to zero: adding terms squeezes the ripple
toward the edge but never flattens it.

Output: assets/scope.svg
"""

import numpy as np
from common import CYAN, DIM, FAINT, FG, MAGENTA, MONO, VIOLET, f, svg_doc, write

W, H = 1200, 200
X0, X1 = 40, 1160
YM, AMP = 100, 46
CYCLES = 2.8  # 14 divisions x 0.4 pi rad
NS = [1, 3, 5, 7, 11, 17, 25, 41]
SLOT = 2.3  # s per sweep
DRAW = 1.5  # s of the slot spent drawing


def partial(x, n):
    k = np.arange(1, n + 1, 2)[:, None]
    return 4 / np.pi * np.sum(np.sin(k * x) / k, axis=0)


def build() -> str:
    T = SLOT * len(NS)
    xs = np.linspace(0, 2 * np.pi * CYCLES, 900)
    px = X0 + (X1 - X0) * xs / xs[-1]
    fine = np.linspace(1e-4, np.pi - 1e-4, 200001)

    parts = [f"""<defs><filter id="ph" x="-5%" y="-40%" width="110%" height="180%">
<feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>"""]

    # graticule: 14 x 4 divisions, centre axes with ticks
    g = []
    for i in range(15):
        x = X0 + i * (X1 - X0) / 14
        g.append(f"M{f(x)},{YM - 3 * AMP / 2}V{YM + 3 * AMP / 2}")
    for j in range(-3, 4):
        y = YM + j * AMP / 2
        g.append(f"M{X0},{f(y)}H{X1}")
    parts.append(f'<path d="{"".join(g)}" stroke="{FAINT}" stroke-opacity=".55" stroke-width=".7" fill="none"/>')
    ticks = "".join(f"M{f(X0 + i * (X1 - X0) / 70)},{YM - 3}v6" for i in range(71))
    parts.append(f'<path d="{ticks}" stroke="{FAINT}" stroke-width=".8"/>')

    # ideal square wave, faint dashed
    sq = np.sign(np.sin(xs))
    parts.append(
        f'<polyline points="{" ".join(f"{f(a)},{f(YM - AMP * b)}" for a, b in zip(px, sq))}" fill="none" '
        f'stroke="{MAGENTA}" stroke-opacity=".35" stroke-width="1" stroke-dasharray="3 4"/>'
    )

    readouts = []
    for i, n in enumerate(NS):
        y = partial(xs, n)
        over = (partial(fine, n).max() - 1) / 2 * 100  # as a fraction of the jump (2)
        pts = " ".join(f"{f(a)},{f(YM - AMP * b)}" for a, b in zip(px, y))
        t0, t1, t2 = i * SLOT / T, (i * SLOT + DRAW) / T, ((i + 1) * SLOT) / T
        t3 = min(((i + 1) * SLOT + DRAW) / T, 1)  # persists, dimmed, while the next sweep draws
        color = CYAN if i < len(NS) - 1 else "#7DF3FF"
        ops = f"0;0;1;1;.28;0;0"
        kts = f"0;{f(t0, 4)};{f(t0 + 0.001, 4)};{f(t2, 4)};{f(t2 + 0.001, 4)};{f(t3, 4)};1"
        if i == len(NS) - 1:  # last one fades into the loop restart
            ops, kts = "0;0;1;1;0", f"0;{f(t0, 4)};{f(t0 + 0.001, 4)};{f(t2 - 0.05, 4)};1"
        parts.append(
            f'<polyline points="{pts}" pathLength="1" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linejoin="round" filter="url(#ph)" stroke-dasharray="1 1" stroke-dashoffset="1" opacity="0">'
            f'<animate attributeName="stroke-dashoffset" values="1;1;0;0" keyTimes="0;{f(t0, 4)};{f(t1, 4)};1" '
            f'dur="{f(T, 2)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="{ops}" keyTimes="{kts}" dur="{f(T, 2)}s" repeatCount="indefinite"/>'
            f"</polyline>"
        )
        terms = len(range(1, n + 1, 2))
        readouts.append(
            f'<text opacity="0">N = {n} ({terms} term{"s" if terms > 1 else ""}) · overshoot {over:.2f}%'
            f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{f(t0, 4)};{f(t2, 4)}" calcMode="discrete" '
            f'dur="{f(T, 2)}s" repeatCount="indefinite"/></text>'
        )

    parts.append(
        f'<g font-family="{MONO}" font-size="11" fill="{DIM}">'
        f'<text x="{X0}" y="24">fig. 3 · (4/π) Σ sin(kx)/k, k odd</text>'
        f'<text x="{X1}" y="24" text-anchor="end">gibbs limit 8.95%</text>'
        f'<text x="{X0}" y="{H - 14}" fill="{VIOLET}">CH1</text>'
        f'<text x="{X0 + 38}" y="{H - 14}">0.5 /div · 0.4π rad/div</text></g>'
        f'<g font-family="{MONO}" font-size="12" fill="{FG}" text-anchor="end" transform="translate({X1},{H - 14})">'
        + "".join(readouts) + "</g>"
    )
    return svg_doc(W, H, "\n".join(parts), "Oscilloscope: Fourier series of a square wave, Gibbs overshoot", rx=12)


if __name__ == "__main__":
    write("scope.svg", build())
