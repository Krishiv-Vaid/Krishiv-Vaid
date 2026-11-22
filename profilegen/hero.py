"""Hero card: character portrait (left) + fastfetch-style panel (right)."""

from __future__ import annotations

from dataclasses import dataclass

from .ascii_art import AsciiGrid
from .svg import FONT_STACK, document, font_face, mono_width, text_run
from .theme import FONT_BOLD, FONT_REGULAR, MONO_ADVANCE, Theme

# --------------------------------------------------------------------------
# Panel content. Every value here is taken from the resume / portfolio; keep
# it that way (see docs/MAINTENANCE.md).

HOST = ("krishiv", "waterloo")

SECTIONS: list[tuple[str | None, list[tuple[str, str]]]] = [
    (None, [
        ("user", "Krishiv Vaid"),
        ("institution", "University of Waterloo"),
        ("program", "B.Math · Statistics & CS"),
        ("focus", "Systems · ML Infra · Mathematics"),
        ("interests", "Distributed Systems, SciComp, AI"),
    ]),
    ("experience", [
        ("usamo-guide", "Software Engineer"),
        ("wat-rocketry", "Software Engineer"),
        ("orangutany", "Machine Learning Engineer"),
    ]),
    ("research", [
        ("mit-csail", "AI for Science & Mathematics"),
        ("uoft.math", "Harmonic Analysis"),
    ]),
    ("languages", [
        ("primary", "Python, C++, TypeScript"),
        ("also", "JavaScript, SQL, Java, LaTeX"),
    ]),
    ("contact", [
        ("portfolio", "krishvaid.me"),
        ("email", "kvaid@uwaterloo.ca"),
        ("github", "Krishiv-Vaid"),
    ]),
    ("misc", [
        ("chess", "Chess.com top 0.01% · 2562 peak"),
    ]),
]


@dataclass(frozen=True)
class HeroLayout:
    width: float = 1000
    pad: float = 30
    gap: float = 36
    portrait_size: float = 8.6  # px per portrait glyph
    panel_size: float = 12.4
    panel_line: float = 1.78  # line height in ems
    panel_cols: int = 0  # computed from available width when 0


def _panel_lines(cols: int) -> list[list[tuple[str, str]]]:
    """Build the right-hand panel as rows of (text, class) spans, ``cols`` wide."""
    rows: list[list[tuple[str, str]]] = []
    user, host = HOST
    head = f"{user}@{host} "
    rows.append([
        (user, "hb"), ("@", "hm"), (host, "ha"), (" ", ""),
        ("─" * (cols - len(head)), "hr"),
    ])
    for title, items in SECTIONS:
        if title is not None:
            rows.append([])
            label = f"─ {title} "
            rows.append([("─ ", "hr"), (title, "hs"), (" ", ""),
                         ("─" * (cols - len(label)), "hr")])
        for key, value in items:
            used = 2 + len(key) + 1 + 1 + len(value)
            dots = max(3, cols - used)
            rows.append([
                ("· ", "hd"), (key, "hk"), (" ", ""),
                ("." * dots, "hd"), (" ", ""), (value, "hv"),
            ])
    return rows


def _style(theme: Theme, chars: str) -> str:
    t = theme
    tone_css = "".join(f".t{i}{{fill:{c}}}" for i, c in enumerate(t.ink)) + f".rl{{fill:{t.accent}}}"
    return (
        font_face(FONT_REGULAR, chars, 400)
        + font_face(FONT_BOLD, chars, 600)
        + f"text{{font-family:{FONT_STACK};}}"
        + tone_css
        + f".hb{{fill:{t.text};font-weight:600}}.hm{{fill:{t.dim}}}.ha{{fill:{t.accent};font-weight:600}}"
        + f".hr{{fill:{t.faint}}}.hs{{fill:{t.muted}}}.hd{{fill:{t.dim}}}"
        + f".hk{{fill:{t.accent}}}.hv{{fill:{t.text}}}.cap{{fill:{t.dim}}}"
    )


def _portrait_rows(grid: AsciiGrid, x0: float, y0: float, ps: float,
                   line_height: float) -> list[str]:
    """One <text> per row; runs of equal tone become tspans."""
    cw = ps * MONO_ADVANCE
    ch = cw * line_height
    out = []
    for r, row in enumerate(grid.chars):
        if not row.strip():
            continue
        lead = len(row) - len(row.lstrip(" "))
        body = row.strip(" ")
        spans: list[tuple[str, str]] = []
        for c, glyph in enumerate(body, start=lead):
            if glyph == " ":
                cls = ""
            elif grid.rim is not None and grid.rim[r, c]:
                cls = "rl"
            else:
                cls = f"t{int(grid.tones[r, c])}"
            if spans and spans[-1][1] == cls:
                spans[-1] = (spans[-1][0] + glyph, cls)
            else:
                spans.append((glyph, cls))
        # Baseline: centre the x-height in the cell.
        y = y0 + r * ch + ch * 0.5 + ps * 0.36
        out.append(text_run(x0 + lead * cw, y, spans, ps))
    return out


def _panel(lines, x0: float, y0: float, size: float, lh: float, theme: Theme,
           palette_strip: bool) -> list[str]:
    out = []
    for i, spans in enumerate(lines):
        if spans:
            out.append(text_run(x0, y0 + i * lh + lh * 0.72, spans, size))
    if palette_strip:
        # fastfetch-style colour blocks, in the README's own palette.
        sw = mono_width(3, size)
        y = y0 + len(lines) * lh + lh * 0.6
        tones = [theme.faint, theme.dim, theme.muted, theme.silver, theme.accent, theme.text]
        for k, col in enumerate(tones):
            out.append(f'<rect x="{x0 + 2 * size * MONO_ADVANCE + k * (sw + 4):.2f}" '
                       f'y="{y:.2f}" width="{sw:.2f}" height="{lh * 0.55:.2f}" rx="1.5" fill="{col}"/>')
    return out


def _card(width: float, height: float, theme: Theme) -> str:
    return (f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" '
            f'fill="{theme.card}" stroke="{theme.edge}"/>')


TITLE = "Krishiv Vaid: character portrait and profile summary"


def render_hero(grid: AsciiGrid, theme: Theme, layout: HeroLayout = HeroLayout(),
                line_height: float = 2.0, palette_strip: bool = True) -> str:
    """Wide layout: portrait left, panel right."""
    L = layout
    ps = L.portrait_size
    portrait_w = grid.cols * ps * MONO_ADVANCE
    portrait_h = grid.rows * ps * MONO_ADVANCE * line_height

    panel_x = L.pad + portrait_w + L.gap
    avail = L.width - panel_x - L.pad
    cols = L.panel_cols or int(avail // (L.panel_size * MONO_ADVANCE))
    lines = _panel_lines(cols)
    lh = L.panel_size * L.panel_line
    panel_h = len(lines) * lh + (lh * 1.6 if palette_strip else 0)

    inner_h = max(portrait_h, panel_h)
    height = inner_h + 2 * L.pad
    py0 = L.pad + (inner_h - portrait_h) / 2  # vertically centre both columns
    ty0 = L.pad + (inner_h - panel_h) / 2

    body = [_card(L.width, height, theme), f'<g font-size="{ps}">']
    body += _portrait_rows(grid, L.pad, py0, ps, line_height)
    body += ["</g>", f'<g font-size="{L.panel_size}">']
    body += _panel(lines, panel_x, ty0, L.panel_size, lh, theme, palette_strip)
    body.append("</g>")
    chars = "".join(grid.chars) + "".join(t for row in lines for t, _ in row)
    return document(L.width, height, "".join(body), _style(theme, chars), TITLE)


def render_hero_compact(grid: AsciiGrid, theme: Theme, width: float = 560,
                        pad: float = 26, panel_size: float = 15.0,
                        line_height: float = 2.0) -> str:
    """Narrow layout for phones: portrait stacked above a larger-type panel."""
    ps = (width - 2 * pad) / (grid.cols * MONO_ADVANCE)
    portrait_h = grid.rows * ps * MONO_ADVANCE * line_height
    cols = int((width - 2 * pad) // (panel_size * MONO_ADVANCE))
    lines = _panel_lines(cols)
    lh = panel_size * 1.7
    panel_y = pad + portrait_h + 18
    height = panel_y + len(lines) * lh + pad
    body = [_card(width, height, theme), f'<g font-size="{ps:.3f}">']
    body += _portrait_rows(grid, pad, pad, ps, line_height)
    body += ["</g>", f'<g font-size="{panel_size}">']
    body += _panel(lines, pad, panel_y, panel_size, lh, theme, palette_strip=False)
    body.append("</g>")
    chars = "".join(grid.chars) + "".join(t for row in lines for t, _ in row)
    return document(width, round(height), "".join(body), _style(theme, chars), TITLE)
