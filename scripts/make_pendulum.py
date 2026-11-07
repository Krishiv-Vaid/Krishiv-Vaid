"""Double pendulum card, baked from a real run of chaos_lab's fixed-step RK4.

Pipeline:
  1. Integrate (theta1, theta2, omega1, omega2) with RK4 at dt = 1 ms for 30 s,
     the same defaults as double_pendulum.py (theta1=120 deg, theta2=-10 deg).
  2. Measure the relative energy drift over the run; the caption uses that number.
  3. Downsample a window to FPS and write the angles as rotate() keyframes:
     rod 1 turns by -theta1 about the pivot, and rod 2 is nested inside it,
     turning by -(theta2 - theta1). SVG rotation is clockwise with y down,
     hence the minus signs.
  4. The lower bob's trail is one short segment per frame. Each appears at its
     timestamp and fades cyan -> violet -> gone.
  5. The moving parts fade out at the end of the window and back in at the
     start, which hides the loop seam.

Needs the double-pendulum repo (default ~/double-pendulum, or set
DOUBLE_PENDULUM_PATH). Output: assets/double-pendulum.svg
"""

import os
import sys
from pathlib import Path

import numpy as np
from common import BG, CYAN, DIM, FAINT, FG, MAGENTA, MONO, VIOLET, f, svg_doc, write

SIM = Path(os.environ.get("DOUBLE_PENDULUM_PATH", Path.home() / "double-pendulum"))
sys.path.insert(0, str(SIM))
from chaos_lab.core import physics  # noqa: E402
from chaos_lab.core.config import Initial, Numerics, Physical, SimConfig  # noqa: E402
from chaos_lab.core.simulation import simulate  # noqa: E402

DT, T_MAX = 1e-3, 30.0
WINDOW = (3.0, 17.0)  # seconds of the run shown in the loop
FPS = 30
FADE_TRAIL = 1.6  # s a trail segment stays visible
W, H = 480, 540
CX, CY, L = 240, 236, 104  # pivot (px) and rod length (px per metre)


def run():
    p = Physical(1.0, 1.0, 1.0, 1.0, 9.81)
    init = Initial(120.0, -10.0, 0.0, 0.0)
    cfg = SimConfig(p, init, Numerics(method="rk4", dt=DT, t_max=T_MAX, output_dt=DT))
    res = simulate(cfg)
    assert res.success, res.message
    E = physics.total_energy(res.y, p)
    drift = float(np.max(np.abs((E - E[0]) / abs(E[0]))))
    return res.t, res.y, drift


def build() -> str:
    t, Y, drift = run()
    assert drift < 1e-6, f"energy drift {drift:.2e} — caption would be a lie"
    stride = round(1 / (FPS * DT))
    i0, i1 = int(WINDOW[0] / DT), int(WINDOW[1] / DT)
    th1, th2 = Y[i0:i1 + 1:stride, 0], Y[i0:i1 + 1:stride, 1]
    n = len(th1)
    dur = (n - 1) / FPS

    kt = ";".join(f(i / (n - 1), 4) for i in range(n))
    rot1 = ";".join(f(-np.degrees(a)) for a in th1)
    rot2 = ";".join(f(-np.degrees(b - a)) for a, b in zip(th1, th2))

    # lower-bob path in px (y down)
    x2 = CX + L * (np.sin(th1) + np.sin(th2))
    y2 = CY + L * (np.cos(th1) + np.cos(th2))

    fade_in, fade_out = 0.5 / dur, 0.9 / dur
    vis = (f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;{f(fade_in, 4)};{f(1 - fade_out, 4)};1" '
           f'dur="{f(dur, 3)}s" repeatCount="indefinite"/>')

    parts = [f"""<defs>
  <filter id="g" x="-200%" y="-200%" width="500%" height="500%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
    <path d="M26,0H0V26" fill="none" stroke="{FAINT}" stroke-opacity=".35" stroke-width=".6"/>
  </pattern>
</defs>
<rect x="16" y="16" width="{W - 32}" height="{W - 32}" rx="8" fill="url(#grid)"/>
<circle cx="{CX}" cy="{CY}" r="{2 * L}" fill="none" stroke="{FAINT}" stroke-dasharray="2 5"/>"""]

    # ghost of the whole window: the shape chaos traces out
    ghost = " ".join(f"{f(a)},{f(b)}" for a, b in zip(x2, y2))
    parts.append(f'<polyline points="{ghost}" fill="none" stroke="{VIOLET}" stroke-opacity=".10" stroke-width="1"/>')

    # fading trail
    seg = []
    hold = FADE_TRAIL / dur
    for i in range(1, n):
        a = (i - 1) / (n - 1)
        k1, k2 = a + 0.25 * hold, a + hold
        if k2 >= 1:
            k1, k2 = min(k1, 0.9995), 0.9999
        seg.append(
            f'<line x1="{f(x2[i - 1])}" y1="{f(y2[i - 1])}" x2="{f(x2[i])}" y2="{f(y2[i])}" opacity="0" stroke="{CYAN}">'
            f'<animate attributeName="opacity" values="0;0;.95;.5;0;0" '
            f'keyTimes="0;{f(max(a - 1e-4, 0), 4)};{f(a, 4)};{f(k1, 4)};{f(k2, 4)};1" dur="{f(dur, 3)}s" repeatCount="indefinite"/>'
            f'<animate attributeName="stroke" values="{CYAN};{CYAN};{VIOLET};{VIOLET}" '
            f'keyTimes="0;{f(a, 4)};{f(k1, 4)};1" dur="{f(dur, 3)}s" repeatCount="indefinite"/></line>'
        )
    parts.append(f'<g stroke-width="1.8" stroke-linecap="round">{"".join(seg)}</g>')

    # rods + bobs
    parts.append(
        f'<g>{vis}<g transform="translate({CX},{CY})">'
        f'<g><animateTransform attributeName="transform" type="rotate" values="{rot1}" keyTimes="{kt}" '
        f'dur="{f(dur, 3)}s" repeatCount="indefinite"/>'
        f'<line x2="0" y2="{L}" stroke="{FG}" stroke-opacity=".85" stroke-width="1.6"/>'
        f'<g transform="translate(0,{L})"><g><animateTransform attributeName="transform" type="rotate" '
        f'values="{rot2}" keyTimes="{kt}" dur="{f(dur, 3)}s" repeatCount="indefinite"/>'
        f'<line x2="0" y2="{L}" stroke="{FG}" stroke-opacity=".85" stroke-width="1.6"/>'
        f'<circle cy="{L}" r="6.5" fill="{CYAN}" filter="url(#g)"/><circle cy="{L}" r="3" fill="#fff"/></g>'
        f'<circle r="6.5" fill="{MAGENTA}" filter="url(#g)"/><circle r="3" fill="#fff"/></g></g>'
        f'</g></g>'
    )
    # pivot
    parts.append(f'<circle cx="{CX}" cy="{CY}" r="4" fill="{BG}" stroke="{FG}" stroke-width="1.5"/>')

    # caption + labels
    exp = int(np.floor(np.log10(drift)))
    mant = drift / 10**exp
    sup = str(exp).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    parts.append(
        f'<g font-family="{MONO}" fill="{DIM}" font-size="11">'
        f'<text x="28" y="40">θ₁(0) = 120° · θ₂(0) = −10°</text>'
        f'<text x="{W - 28}" y="40" text-anchor="end">t ∈ [{f(WINDOW[0])}, {f(WINDOW[1])}] s</text>'
        f'</g>'
        f'<line x1="16" y1="{W - 4}" x2="{W - 16}" y2="{W - 4}" stroke="{PANEL}"/>'
        f'<text x="{W / 2}" y="{W + 26}" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{FG}">'
        f'RK4 · dt = 1 ms · |ΔE/E₀| &lt; 10⁻⁶</text>'
        f'<text x="{W / 2}" y="{W + 46}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{DIM}">'
        f'measured: max |ΔE/E₀| = {mant:.1f}×10{sup} over {f(T_MAX)} s</text>'
    )
    print(f"energy drift {drift:.3e}, {n} frames, loop {dur:.2f} s")
    return svg_doc(W, H, "\n".join(parts), "Double pendulum, RK4 trajectory from chaos_lab", rx=14)


PANEL = FAINT

if __name__ == "__main__":
    write("double-pendulum.svg", build())
