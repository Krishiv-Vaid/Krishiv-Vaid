"""Typing line under the banner: a terminal prompt that types, holds, deletes, repeats.

Each character is its own <text> at an explicit x, with a discrete opacity
animation over one shared cycle. That keeps it exact even if a viewer's
monospace font has a different advance width (Consolas is 0.55em, Menlo 0.60em):
glyphs never drift away from the cursor. The cursor's x is keyed to the same
timeline.

Edit PHRASES and rerun.  Output: assets/typing.svg
"""

from html import escape

from common import CYAN, DIM, FG, MAGENTA, MONO, f, svg_doc, write

PHRASES = [
    "Applied Physics @ UWaterloo",
    "Building at the edge of hardware & AI",
    "Simulating chaos for fun",
    "Writing an autograd engine from scratch",
    "Porting it to C++17, one stride at a time",
]
TYPE, DELETE, HOLD, GAP = 0.065, 0.028, 1.9, 0.35  # seconds

W, H = 1200, 64
SIZE = 22
CW = SIZE * 0.6  # advance we lay glyphs out on
PROMPT = "krishiv@uwaterloo:~$"
X0 = 34 + (len(PROMPT) + 1) * CW
Y = 40


def build() -> str:
    # timeline: list of (time, n_visible_chars) per phrase
    t = 0.0
    chars, cursor = [], [(0.0, X0)]
    for p in PHRASES:
        n = len(p)
        on = [t + (i + 1) * TYPE for i in range(n)]
        full = t + n * TYPE + HOLD
        off = [full + (n - i) * DELETE for i in range(n)]  # last char deleted first
        for i, ch in enumerate(p):
            chars.append((ch, X0 + i * CW, on[i], off[i]))
        for i in range(n):
            cursor.append((on[i], X0 + (i + 1) * CW))
        for i in range(n):
            cursor.append((full + (i + 1) * DELETE, X0 + (n - 1 - i) * CW))
        t = full + n * DELETE + GAP
    T = t

    out = [f'<g font-family="{MONO}" font-size="{SIZE}">']
    out.append(f'<text x="34" y="{Y}" fill="{DIM}">{PROMPT.replace("$", "")}<tspan fill="{MAGENTA}">$</tspan></text>')
    for ch, x, a, b in chars:
        if ch == " ":
            continue
        out.append(
            f'<text x="{f(x)}" y="{Y}" fill="{FG}" opacity="0">{escape(ch)}'
            f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{f(a / T, 5)};{f(b / T, 5)}" '
            f'calcMode="discrete" dur="{f(T, 3)}s" repeatCount="indefinite"/></text>'
        )
    out.append("</g>")

    ts = [c[0] / T for c in cursor]
    xs = [c[1] for c in cursor]
    out.append(
        f'<rect y="{Y - SIZE * 0.8:.0f}" width="{f(CW * 0.9)}" height="{SIZE + 2}" x="{f(X0)}" fill="{CYAN}">'
        f'<animate attributeName="x" values="{";".join(f(x) for x in xs)}" keyTimes="{";".join(f(k, 5) for k in ts)}" '
        f'calcMode="discrete" dur="{f(T, 3)}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.05s" repeatCount="indefinite"/></rect>'
    )
    return svg_doc(W, H, "\n".join(out), "typing: " + " / ".join(PHRASES), rx=12)


if __name__ == "__main__":
    write("typing.svg", build())
