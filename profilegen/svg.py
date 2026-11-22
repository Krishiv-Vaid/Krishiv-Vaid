"""Small SVG helpers: escaping, embedded font subsets, monospace text runs.

GitHub serves README images through its camo proxy as <img>, so an SVG can't
fetch web fonts. We embed a subset of JetBrains Mono as a base64 WOFF2 data URI
(allowed inside SVG-as-image) and additionally pin every text run with
``textLength`` so column alignment survives even if the font fails to load.
"""

from __future__ import annotations

import base64
import functools
import io
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from fontTools import subset
from fontTools.ttLib import TTFont

from .theme import MONO_ADVANCE

FAMILY = "KVMono"


def esc(text: str) -> str:
    return _xml_escape(text, {'"': "&quot;"})


@functools.lru_cache(maxsize=32)
def _subset_woff2(font_path: str, chars: str) -> str:
    font = TTFont(font_path, recalcTimestamp=False)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []  # no ligatures / contextual alternates
    opts.hinting = False
    opts.desubroutinize = True
    opts.name_IDs = []
    sub = subset.Subsetter(opts)
    sub.populate(text=chars + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def font_face(font_path: Path, chars: str, weight: int = 400) -> str:
    """Return an @font-face rule embedding only ``chars`` from ``font_path``."""
    uniq = "".join(sorted(set(chars)))
    data = _subset_woff2(str(font_path), uniq)
    return (
        f"@font-face{{font-family:'{FAMILY}';font-weight:{weight};"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
    )


FONT_STACK = f"'{FAMILY}','JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"


def mono_width(n_chars: int, size: float) -> float:
    return n_chars * size * MONO_ADVANCE


def text_run(
    x: float,
    y: float,
    spans: list[tuple[str, str]],
    size: float,
    extra: str = "",
) -> str:
    """A single line of monospace text built from (text, css-class) spans.

    ``textLength`` fixes the total advance so alignment never depends on the
    viewer's fallback font.
    """
    n = sum(len(t) for t, _ in spans)
    if n == 0:
        return ""
    inner = "".join(
        f'<tspan class="{cls}">{esc(t)}</tspan>' if cls else esc(t) for t, cls in spans
    )
    length = mono_width(n, size)
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:g}" textLength="{length:.2f}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve"{extra}>{inner}</text>'
    )


def document(width: float, height: float, body: str, style: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title><style>{style}</style>{body}</svg>\n"
    )
