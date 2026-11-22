"""Static SVGs: section rules, project cards and the toolkit grid.

Each asset has a wide (desktop) and a compact (phone) layout; the README picks
one with <picture> media queries. Visuals are generated from real data:

* double pendulum: an actual RK4 integration (energy drift is measured and
  printed on the card);
* TinyTorch: the strided-storage layout its tensors use (design, no numbers);
* Centsible: the exact paycheque breakdown from the app's own screenshot.
"""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass, field

import numpy as np

from .svg import FONT_STACK, document, esc, font_face, text_run
from .theme import FONT_BOLD, FONT_REGULAR, MONO_ADVANCE, Theme

Spans = list[tuple[str, str]]


def _style(theme: Theme, chars: str, extra: str = "") -> str:
    t = theme
    return (
        font_face(FONT_REGULAR, chars, 400) + font_face(FONT_BOLD, chars, 600)
        + f"text{{font-family:{FONT_STACK};}}"
        + f".x{{fill:{t.text}}}.b{{fill:{t.text};font-weight:600}}.m{{fill:{t.muted}}}"
        + f".d{{fill:{t.dim}}}.a{{fill:{t.accent}}}.ab{{fill:{t.accent};font-weight:600}}"
        + f".f{{fill:{t.faint}}}.sv{{fill:{t.silver}}}"
        + extra
    )


class Canvas:
    """Accumulates SVG elements and the characters used (for font subsetting)."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.chars: list[str] = []

    def text(self, x: float, y: float, spans: Spans, size: float, anchor: str = "start") -> None:
        n = sum(len(t) for t, _ in spans)
        if anchor == "end":
            x -= n * size * MONO_ADVANCE
        elif anchor == "middle":
            x -= n * size * MONO_ADVANCE / 2
        self.parts.append(text_run(x, y, spans, size))
        self.chars.extend(t for t, _ in spans)

    def raw(self, s: str) -> None:
        self.parts.append(s)

    def svg(self, width: float, height: float, theme: Theme, title: str, extra_css: str = "") -> str:
        return document(width, round(height), "".join(self.parts),
                        _style(theme, "".join(self.chars) + "0123456789", extra_css), title)


def card_rect(width: float, height: float, theme: Theme) -> str:
    return (f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1:.1f}" rx="12" '
            f'fill="{theme.card}" stroke="{theme.edge}"/>')


# --------------------------------------------------------------------------
# section rules


def section_rule(index: int, title: str, theme: Theme, width: float = 1000,
                 note: str = "") -> str:
    c = Canvas()
    size = 13
    y = 24
    c.text(0, y, [(f"{index:02d}", "d"), ("  ", ""), (title, "b")], size)
    x0 = (len(title) + 5) * size * MONO_ADVANCE
    x1 = width - (len(note) + 2) * size * MONO_ADVANCE if note else width
    c.raw(f'<line x1="{x0:.1f}" y1="{y - 4.5}" x2="{x1:.1f}" y2="{y - 4.5}" stroke="{theme.rule}" stroke-width="1"/>')
    if note:
        c.text(width, y, [(note, "d")], size, anchor="end")
    return c.svg(width, 36, theme, f"{index:02d} {title}")


# --------------------------------------------------------------------------
# visuals


def double_pendulum_path(t_max: float = 12.0, dt: float = 1e-3, th1: float = 150.0,
                         th2: float = 150.0) -> tuple[np.ndarray, np.ndarray, float]:
    """Integrate the frictionless double pendulum with fixed-step RK4.

    Returns (bob-1 positions, bob-2 positions, max relative energy drift).
    m1 = m2 = 1 kg, L1 = L2 = 1 m, g = 9.81 m/s^2, released from rest.
    """
    g, m1, m2, l1, l2 = 9.81, 1.0, 1.0, 1.0, 1.0

    def f(s: np.ndarray) -> np.ndarray:
        a, b, wa, wb = s
        d = a - b
        den = 2 * m1 + m2 - m2 * math.cos(2 * d)
        aa = (-g * (2 * m1 + m2) * math.sin(a) - m2 * g * math.sin(a - 2 * b)
              - 2 * math.sin(d) * m2 * (wb * wb * l2 + wa * wa * l1 * math.cos(d))) / (l1 * den)
        ab = (2 * math.sin(d) * (wa * wa * l1 * (m1 + m2) + g * (m1 + m2) * math.cos(a)
              + wb * wb * l2 * m2 * math.cos(d))) / (l2 * den)
        return np.array([wa, wb, aa, ab])

    def energy(s: np.ndarray) -> float:
        a, b, wa, wb = s
        T = 0.5 * (m1 + m2) * l1**2 * wa**2 + 0.5 * m2 * l2**2 * wb**2 + m2 * l1 * l2 * wa * wb * math.cos(a - b)
        V = -(m1 + m2) * g * l1 * math.cos(a) - m2 * g * l2 * math.cos(b)
        return T + V

    s = np.array([math.radians(th1), math.radians(th2), 0.0, 0.0])
    e0 = energy(s)
    steps = int(round(t_max / dt))
    keep = max(1, int(round(0.008 / dt)))
    p1, p2, drift = [], [], 0.0
    for i in range(steps + 1):
        if i % keep == 0:
            a, b = s[0], s[1]
            x1, y1 = l1 * math.sin(a), -l1 * math.cos(a)
            p1.append((x1, y1))
            p2.append((x1 + l2 * math.sin(b), y1 - l2 * math.cos(b)))
            drift = max(drift, abs(energy(s) - e0) / abs(e0))
        k1 = f(s)
        k2 = f(s + 0.5 * dt * k1)
        k3 = f(s + 0.5 * dt * k2)
        k4 = f(s + dt * k3)
        s = s + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return np.array(p1), np.array(p2), drift


_PENDULUM_CACHE: dict = {}


def visual_pendulum(c: Canvas, x: float, y: float, w: float, h: float, theme: Theme) -> None:
    if "data" not in _PENDULUM_CACHE:
        _PENDULUM_CACHE["data"] = double_pendulum_path()
    p1, p2, drift = _PENDULUM_CACHE["data"]
    scale = min(w, h - 40) / 4.5
    cx, cy = x + w / 2, y + (h - 24) / 2

    def P(pt) -> tuple[float, float]:
        return cx + pt[0] * scale, cy - pt[1] * scale

    # Long exposure: older segments fainter.
    chunks = 48
    n = len(p2)
    for k in range(chunks):
        a, b = k * n // chunks, min(n, (k + 1) * n // chunks + 1)
        pts = " ".join(f"{P(q)[0]:.1f},{P(q)[1]:.1f}" for q in p2[a:b])
        op = 0.06 + 0.84 * (k / (chunks - 1)) ** 1.6
        c.raw(f'<polyline points="{pts}" fill="none" stroke="{theme.text}" stroke-opacity="{op:.3f}" '
              f'stroke-width="1" stroke-linejoin="round" stroke-linecap="round"/>')
    pv, b1, b2 = (cx, cy), P(p1[-1]), P(p2[-1])
    c.raw(f'<polyline points="{pv[0]:.1f},{pv[1]:.1f} {b1[0]:.1f},{b1[1]:.1f} {b2[0]:.1f},{b2[1]:.1f}" '
          f'fill="none" stroke="{theme.silver}" stroke-width="1.6" stroke-linecap="round"/>')
    c.raw(f'<circle cx="{pv[0]:.1f}" cy="{pv[1]:.1f}" r="2.4" fill="{theme.dim}"/>')
    for bx, by in (b1, b2):
        c.raw(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="4.6" fill="{theme.text}"/>')
    c.text(x + 14, y + h - 14, [("RK4 · 1 ms · 12 s · 150°/150° · |ΔE/E| ≤ ", "d"),
                                (f"{drift:.1e}", "m")], 10.5)


def visual_tensor(c: Canvas, x: float, y: float, w: float, h: float, theme: Theme) -> None:
    hi = 6  # element highlighted across storage and both views
    cell = 24
    size = 10.5
    sx = x + (w - 12 * cell) / 2
    sy = y + 44
    c.text(sx, sy - 12, [("storage", "m"), ("  float32[12], contiguous", "d")], size)

    def box(bx, by, val, on):
        stroke = theme.accent if on else theme.rule
        fill = theme.accent if on else "none"
        op = ' fill-opacity="0.16"' if on else ""
        c.raw(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{cell - 3}" height="{cell - 3}" rx="3" '
              f'fill="{fill}"{op} stroke="{stroke}"/>')
        c.text(bx + (cell - 3) / 2, by + cell / 2 + 2.5, [(str(val), "ab" if on else "x")], size, "middle")

    for i in range(12):
        box(sx + i * cell, sy, i, i == hi)
    gy = sy + 76
    ax = x + w * 0.10
    c.text(ax, gy - 14, [("a", "b"), ("  (3,4) stride (4,1)", "d")], size)
    for r in range(3):
        for q in range(4):
            v = r * 4 + q
            box(ax + q * cell, gy + r * cell, v, v == hi)
    bx = x + w * 0.58
    c.text(bx, gy - 14, [("a.T", "b"), ("  (4,3) stride (1,4)", "d")], size)
    for r in range(4):
        for q in range(3):
            v = q * 4 + r
            box(bx + q * cell, gy + r * cell, v, v == hi)
    c.text(x + 14, y + h - 14, [("transpose = new strides, same buffer: zero copies", "d")], size)


def visual_receipt(c: Canvas, x: float, y: float, w: float, h: float, theme: Theme) -> None:
    size = 11.2
    lh = size * 1.85
    cols = 33
    lines: list[Spans] = [
        [("monthly paycheque", "b"), (" · ontario 2026", "d")],
        [("$16.90/h × 12 h × 50 wk ÷ 12", "m")],
        [],
    ]

    def row(k: str, v: str, cls: str = "x") -> Spans:
        dots = cols - len(k) - len(v) - 2
        return [(k, "m"), (" " + "." * dots + " ", "d"), (v, cls)]

    lines += [row("gross pay", "$845.00"), row("EI 1.63%", "-13.77"),
              row("CPP (starts at 18)", "0.00"), row("income tax (est.)", "0.00"),
              [("─" * cols, "f")], row("take-home", "$831.23", "b")]
    total_w = cols * size * MONO_ADVANCE
    x0 = x + (w - total_w) / 2
    y0 = y + (h - 24 - len(lines) * lh) / 2 + lh * 0.8
    for i, spans in enumerate(lines):
        if spans:
            c.text(x0, y0 + i * lh, spans, size)
    c.text(x + 14, y + h - 14, [("example from the app: age 16, student minimum wage", "d")], 10.5)


# --------------------------------------------------------------------------
# project cards


@dataclass
class Metric:
    value: str
    label: str


@dataclass
class Project:
    slug: str
    name: str
    tag: str
    description: str
    metrics: list[Metric] = field(default_factory=list)
    roadmap: list[tuple[str, str]] = field(default_factory=list)  # (status, item)
    detail: str = ""
    tech: str = ""
    visual: str = ""


PROJECTS = [
    Project(
        slug="double-pendulum",
        name="Double Pendulum Simulator",
        tag="live demo",
        description=("A chaos laboratory for the double pendulum: Lagrangian equations of motion, "
                     "verified integrators, Lyapunov exponents and Poincaré sections, and a full "
                     "Python dashboard that runs in the browser through Pyodide."),
        metrics=[Metric("7.8M", "pendulum-steps/s"), Metric("640k", "steps/s, 1 trajectory"),
                 Metric("3.6×", "multiprocess speedup"), Metric("150", "tests in CI")],
        detail="RK4 · RK45 · DOP853 · energy error 1.9×10⁻⁷ · ensembles of up to 2,000",
        tech="python · numpy · scipy · matplotlib · pyodide · pytest",
        visual="pendulum",
    ),
    Project(
        slug="tinytorch",
        name="TinyTorch",
        tag="in progress",
        description=("A deep learning framework written from scratch in C++20, built to understand "
                     "the systems side of ML: memory layout, autodiff and numerical kernels."),
        roadmap=[("building", "strided tensors, broadcasting, zero-copy views"),
                 ("building", "reverse-mode autodiff"),
                 ("developing", "NN layers, SGD/Adam, finite-difference grad checks"),
                 ("designing", "arena allocator, AVX2/FMA blocked matmul vs OpenBLAS")],
        tech="c++20 · python · avx2 · cmake",
        visual="tensor",
    ),
    Project(
        slug="centsible",
        name="Centsible",
        tag="hackathon winner",
        description=("A savings planner for teens in Ontario: take-home pay with real EI, CPP and "
                     "tax rules, a spending budget, and month-by-month projections of when each "
                     "goal is reached."),
        metrics=[Metric("183", "occupations, 11 categories"), Metric("10 yr", "goal projection"),
                 Metric("120k", "PBKDF2-SHA256 iterations"), Metric("0", "servers: data stays local")],
        detail="React 19 · Vite · hand-written SVG charts · unit-tested money math",
        tech="react · vite · javascript · vitest · netlify",
        visual="receipt",
    ),
]

VISUALS = {"pendulum": visual_pendulum, "tensor": visual_tensor, "receipt": visual_receipt}


def _tag(c: Canvas, x_right: float, y: float, text: str, theme: Theme, size: float = 11) -> None:
    w = (len(text) + 2) * size * MONO_ADVANCE
    c.raw(f'<rect x="{x_right - w:.1f}" y="{y - size - 3:.1f}" width="{w:.1f}" height="{size + 9:.1f}" '
          f'rx="{(size + 9) / 2:.1f}" fill="none" stroke="{theme.rule}"/>')
    c.text(x_right - w / 2, y + 0.5, [(text, "m")], size, "middle")


def _project_text(c: Canvas, p: Project, x: float, y: float, w: float, theme: Theme,
                  body: float, title: float, small: float = 10.8, metric_cols: int = 4) -> float:
    c.text(x, y, [(p.name, "b")], title)
    _tag(c, x + w, y - 3, p.tag, theme)
    y += title * 1.2 + 6
    cols = int(w // (body * MONO_ADVANCE))
    for line in textwrap.wrap(p.description, cols):
        c.text(x, y, [(line, "m")], body)
        y += body * 1.6
    y += 16
    if p.metrics:
        mw = w / metric_cols
        big = title * 1.25
        label_cols = max(8, int((mw - 10) // (small * MONO_ADVANCE)))
        for r0 in range(0, len(p.metrics), metric_cols):
            row = p.metrics[r0: r0 + metric_cols]
            max_lines = 1
            for i, m in enumerate(row):
                mx = x + i * mw
                c.text(mx, y + big * 0.8, [(m.value, "b")], big)
                parts = textwrap.wrap(m.label, label_cols)
                max_lines = max(max_lines, len(parts))
                for j, part in enumerate(parts):
                    c.text(mx, y + big * 0.8 + small * 1.7 + j * small * 1.35, [(part, "d")], small)
            y += big + small * 1.7 + small * 1.35 * max_lines + 18
    if p.roadmap:
        prefix = 2 + 11
        width_cols = int(w // (body * MONO_ADVANCE))
        for status, item in p.roadmap:
            lines = textwrap.wrap(item, max(12, width_cols - prefix))
            for k, line in enumerate(lines):
                head = [("◦ ", "d"), (f"{status:<11}", "a")] if k == 0 else [(" " * prefix, "")]
                c.text(x, y, head + [(line, "x")], body)
                y += body * 1.75
        y += 6
    if p.detail:
        for line in textwrap.wrap(p.detail, int(w // (small * MONO_ADVANCE))):
            c.text(x, y, [(line, "d")], small)
            y += small * 1.6
        y += 8
    c.raw(f'<line x1="{x:.1f}" y1="{y - 6:.1f}" x2="{x + w:.1f}" y2="{y - 6:.1f}" stroke="{theme.faint}"/>')
    c.text(x, y + 12, [(p.tech, "sv")], small + 0.2)
    return y + 12


def project_card(p: Project, theme: Theme, width: float = 1000) -> str:
    c = Canvas()
    pad = 30
    vis_w = 360
    height = 300
    c.raw("")  # placeholder for the card rect (height known up front)
    c.raw(f'<line x1="{vis_w}" y1="1" x2="{vis_w}" y2="{height - 1}" stroke="{theme.edge}"/>')
    VISUALS[p.visual](c, 0, 0, vis_w, height, theme)
    tx = vis_w + pad
    end = _project_text(c, p, tx, pad + 22, width - tx - pad, theme, body=12.4, title=19)
    height = max(height, end + pad)
    c.parts[0] = card_rect(width, height, theme)
    return c.svg(width, height, theme, f"{p.name}: {p.description}")


def project_card_compact(p: Project, theme: Theme, width: float = 560) -> str:
    c = Canvas()
    pad = 24
    vis_h = 300
    c.raw("")
    VISUALS[p.visual](c, (width - 380) / 2, 0, 380, vis_h, theme)
    c.raw(f'<line x1="1" y1="{vis_h}" x2="{width - 1}" y2="{vis_h}" stroke="{theme.edge}"/>')
    end = _project_text(c, p, pad, vis_h + pad + 18, width - 2 * pad, theme, body=14.5, title=20,
                        small=13.0, metric_cols=2)
    height = end + pad
    c.parts[0] = card_rect(width, height, theme)
    return c.svg(width, height, theme, f"{p.name}: {p.description}")


# --------------------------------------------------------------------------
# toolkit

TOOLKIT: list[tuple[str, list[str]]] = [
    ("languages", ["Python", "C++", "TypeScript", "JavaScript", "Java", "SQL", "Ruby", "LaTeX"]),
    ("ml · numerical", ["PyTorch", "NumPy", "SciPy", "Matplotlib", "Pillow", "Pyodide"]),
    ("systems · backend", ["C++20", "CMake", "Node.js", "Supabase Edge Functions", "Stripe", "OAuth"]),
    ("frontend", ["React", "Next.js", "Gatsby", "Tailwind CSS", "Capacitor", "Storybook"]),
    ("data", ["PostgreSQL", "Row-Level Security", "SQLite / Turso", "Supabase"]),
    ("tooling · deploy", ["Git", "GitHub Actions", "pytest", "Vitest", "Playwright", "ruff", "ESLint",
                          "Lighthouse CI", "Vercel", "Netlify", "Cloudflare Pages"]),
]


def toolkit(theme: Theme, width: float = 1000, compact: bool = False) -> str:
    c = Canvas()
    pad = 30 if not compact else 24
    size = 12.6 if not compact else 15
    ncol = 1 if compact else 2
    gap = 40
    col_w = (width - 2 * pad - gap * (ncol - 1)) / ncol
    cols = int(col_w // (size * MONO_ADVANCE))
    lh = size * 1.7
    c.raw("")
    y_col = [pad + 6.0] * ncol
    for i, (label, items) in enumerate(TOOLKIT):
        k = i % ncol if not compact else 0
        x = pad + k * (col_w + gap)
        y = y_col[k]
        c.text(x, y + size, [(label, "a")], size)
        c.raw(f'<line x1="{x + (len(label) + 1) * size * MONO_ADVANCE:.1f}" y1="{y + size * 0.62:.1f}" '
              f'x2="{x + col_w:.1f}" y2="{y + size * 0.62:.1f}" stroke="{theme.faint}"/>')
        y += lh
        line: Spans = []
        used = 0
        for j, item in enumerate(items):
            sep = " · " if j < len(items) - 1 else ""
            if used + len(item) + len(sep) > cols and line:
                c.text(x, y + size, line, size)
                y += lh
                line, used = [], 0
            line += [(item, "x"), (sep, "d")]
            used += len(item) + len(sep)
        if line:
            c.text(x, y + size, line, size)
            y += lh
        y_col[k] = y + lh * 0.55
    height = max(y_col) + pad - lh * 0.55
    c.parts[0] = card_rect(width, height, theme)
    title = "Toolkit: " + "; ".join(f"{label}: {', '.join(items)}" for label, items in TOOLKIT)
    return c.svg(width, height, theme, title)
