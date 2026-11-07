"""Interests and tech-stack rows as small SVGs instead of a wall of shields.io badges.

Edit INTERESTS / STACK and rerun. Text is laid out at a 0.6em monospace
advance with generous padding, so chips still fit with slightly narrower fonts.

Outputs: assets/interests.svg, assets/stack.svg
"""

from html import escape

from common import CYAN, DIM, FAINT, FG, MAGENTA, MONO, VIOLET, f, svg_doc, write

# label, glyph (hand-drawn, in a 20x20 box)
INTERESTS = [
    ("hardware", "M5,5h10v10h-10zM8,2v3M12,2v3M8,15v3M12,15v3M2,8h3M2,12h3M15,8h3M15,12h3M8,8h4v4h-4z"),
    ("deep tech", "M10,2L17,6V14L10,18L3,14V6ZM10,2V10M3,6L10,10L17,6M10,10V18"),
    ("physics", "M1,10C3.5,2 6,2 8.5,10S13.5,18 16,10S19,6 19,6"),
    ("AI", "M4,4m-1.6,0a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0-3.2,0M4,16m-1.6,0a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0-3.2,0"
           "M16,10m-1.6,0a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0-3.2,0M10,7m-1.6,0a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0-3.2,0"
           "M10,13m-1.6,0a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0-3.2,0M5.5,4.6L8.5,6.4M5.5,15.4L8.5,13.6M5.5,4.8L8.6,12"
           "M5.5,15.2L8.6,8M11.5,7.6L14.5,9.4M11.5,12.4L14.5,10.6"),
]

STACK = [
    ("lang", ["python", "c++17", "racket"]),
    ("sci", ["numpy", "scipy", "matplotlib", "pytorch"]),
    ("build", ["cmake", "pytest", "git"]),
]

ACCENTS = [CYAN, VIOLET, MAGENTA, CYAN]


def interests() -> str:
    W, H, n = 880, 76, len(INTERESTS)
    gap, pad = 16, 20
    cw = (W - 2 * pad - (n - 1) * gap) / n
    out = []
    for i, (label, glyph) in enumerate(INTERESTS):
        x = pad + i * (cw + gap)
        c = ACCENTS[i]
        out.append(
            f'<rect x="{f(x)}" y="16" width="{f(cw)}" height="44" rx="8" fill="{c}" fill-opacity=".06" '
            f'stroke="{c}" stroke-opacity=".45"/>'
            f'<path transform="translate({f(x + 18)},28)" d="{glyph}" fill="none" stroke="{c}" stroke-width="1.4" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<text x="{f(x + 50)}" y="43" font-family="{MONO}" font-size="16" fill="{FG}">{escape(label)}</text>'
        )
    return svg_doc(W, H, "\n".join(out), "Interests: " + ", ".join(l for l, _ in INTERESTS), rx=12)


def stack() -> str:
    W, row_h, top = 880, 44, 18
    H = top * 2 + row_h * len(STACK) - 8
    size, adv = 15, 15 * 0.6
    out = []
    for r, (group, items) in enumerate(STACK):
        y = top + r * row_h
        out.append(f'<text x="28" y="{y + 23}" font-family="{MONO}" font-size="13" fill="{DIM}">{group}</text>')
        x = 110
        for j, item in enumerate(items):
            w = len(item) * adv + 30
            c = ACCENTS[(r + j) % 3]
            out.append(
                f'<rect x="{f(x)}" y="{y + 4}" width="{f(w)}" height="28" rx="6" fill="none" stroke="{FAINT}"/>'
                f'<circle cx="{f(x + 12)}" cy="{y + 18}" r="2.6" fill="{c}"/>'
                f'<text x="{f(x + 22)}" y="{y + 23}" font-family="{MONO}" font-size="{size}" fill="{FG}">{escape(item)}</text>'
            )
            x += w + 10
    return svg_doc(W, H, "\n".join(out), "Stack: " + "; ".join(f"{g}: {', '.join(i)}" for g, i in STACK), rx=12)


if __name__ == "__main__":
    write("interests.svg", interests())
    write("stack.svg", stack())
