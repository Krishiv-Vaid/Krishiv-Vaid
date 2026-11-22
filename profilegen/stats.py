"""Live statistics panel (SVG), drawn in the hero card's visual language.

Every number is labelled with its scope and window. Nothing is estimated:
values come straight from the snapshot written by github_data.collect.
"""

from __future__ import annotations

from datetime import datetime

from .github_data import Snapshot
from .pipeline import KoiMeta
from .svg import FONT_STACK, document, font_face, mono_width, text_run
from .theme import FONT_BOLD, FONT_REGULAR, MONO_ADVANCE, Theme

Spans = list[tuple[str, str]]


def leader(key: str, value: str, cols: int, note: str = "") -> Spans:
    used = 2 + len(key) + 2 + len(value) + (len(note) + 1 if note else 0)
    dots = max(2, cols - used)
    spans: Spans = [("· ", "d"), (key, "k"), (" ", ""), ("." * dots, "d"), (" ", ""), (value, "v")]
    if note:
        spans += [(" ", ""), (note, "n")]
    return spans


def rule(title: str, cols: int) -> Spans:
    return [("─ ", "r"), (title, "s"), (" ", ""), ("─" * max(0, cols - len(title) - 3), "r")]


def _fmt(n: int) -> str:
    return f"{n:,}"


def koi_block(meta: KoiMeta, cols: int) -> list[Spans]:
    rows = [rule("koi", cols)]
    rows.append(leader("age class", f"{meta.stage_index:02d} {meta.stage}", cols))
    rows.append(leader("length", f"{meta.length_px:.0f} px", cols, f"g = {meta.growth:.3f}"))
    rows.append(leader("fed by", f"{_fmt(meta.contributions)} contributions", cols,
                       f"/ {meta.window_days} d"))
    if meta.next_stage:
        remaining = meta.next_threshold - meta.contributions
        rows.append(leader("next", f"{meta.next_stage} @ {_fmt(meta.next_threshold)}", cols))
        rows.append(leader("to go", _fmt(remaining), cols, f"({meta.progress * 100:.0f}%)"))
    else:
        rows.append(leader("next", "fully grown", cols))
    named = [lf["name"] for lf in meta.leaves if lf["name"] not in ("other", "unknown")]
    rows.append(leader("patches", named[0] if named else "plain", cols))
    return rows


def github_block(s: Snapshot, cols: int) -> list[Spans]:
    rows = [rule("github", cols)]
    private = f"incl. {s.private_contributions} private" if s.private_contributions else ""
    rows.append(leader(f"contributions·{s.window_days}d", _fmt(s.contributions_calendar), cols, private))
    rows.append(leader(f"commits·{s.window_days}d", _fmt(s.commits), cols))
    rows.append(leader("pull requests", _fmt(s.pull_requests_total), cols,
                       f"all-time · {s.pull_requests_merged} merged"))
    rows.append(leader("public repos", _fmt(s.public_repos), cols, "owned, non-fork"))
    rows.append(leader("stars", _fmt(s.stars), cols, "on owned repos"))
    rows.append(leader("followers", _fmt(s.followers), cols))
    return rows


def _style(theme: Theme, chars: str) -> str:
    t = theme
    return (
        font_face(FONT_REGULAR, chars, 400) + font_face(FONT_BOLD, chars, 600)
        + f"text{{font-family:{FONT_STACK};}}"
        + f".d{{fill:{t.dim}}}.k{{fill:{t.accent}}}.v{{fill:{t.text}}}.n{{fill:{t.muted}}}"
        + f".r{{fill:{t.faint}}}.s{{fill:{t.muted}}}.f{{fill:{t.dim}}}.h{{fill:{t.text};font-weight:600}}"
        + f".a{{fill:{t.accent};font-weight:600}}.w{{fill:{t.muted}}}"
    )


def _weekly(daily: list[int]) -> list[int]:
    # Calendar weeks run Sunday..Saturday; the first may be partial.
    return [sum(daily[i: i + 7]) for i in range(0, len(daily), 7)]


def render_stats(s: Snapshot, meta: KoiMeta, theme: Theme, width: float = 1000,
                 size: float = 12.6, compact: bool = False) -> str:
    pad = 30 if not compact else 26
    lh = size * 1.75
    cw = size * MONO_ADVANCE
    body: list[str] = []
    all_text: list[str] = []

    def put_rows(rows: list[Spans], x: float, y0: float) -> float:
        y = y0
        for spans in rows:
            if spans:
                body.append(text_run(x, y + lh * 0.72, spans, size))
                all_text.extend(t for t, _ in spans)
            y += lh
        return y

    # Header.
    head: Spans = [("krishiv", "h"), ("@", "d"), ("github", "a"), (" ", ""), ("stats", "w")]
    total_cols = int((width - 2 * pad) // cw)
    y = pad
    when = datetime.fromisoformat(s.generated_at).strftime("%Y-%m-%d")
    status = f"cached {when}" if s.stale else f"updated {when}"
    head_len = sum(len(t) for t, _ in head)
    head += [(" " * max(1, total_cols - head_len - len(status)), ""), (status, "f")]
    y = put_rows([head], pad, y) + lh * 0.35

    if compact:
        cols = total_cols
        y = put_rows(koi_block(meta, cols), pad, y) + lh * 0.5
        y = put_rows(github_block(s, cols), pad, y) + lh * 0.5
    else:
        gap = 3
        cols = (total_cols - gap) // 2
        left = koi_block(meta, cols)
        right = github_block(s, cols)
        yl = put_rows(left, pad, y)
        yr = put_rows(right, pad + (cols + gap) * cw, y)
        y = max(yl, yr) + lh * 0.5

    # Language distribution: the same colours tint the lily pads.
    y = put_rows([rule("languages · lily pads", total_cols)], pad, y)
    bar_w = width - 2 * pad
    bar_h = 7
    x = pad
    alloy = {lf["name"]: lf["hex"] for lf in meta.leaves}
    for lang in s.languages:
        w = bar_w * lang.share
        if w < 0.5:
            continue
        col = alloy.get(lang.name, alloy.get("other", theme.dim))
        body.append(f'<rect x="{x:.2f}" y="{y + 6:.2f}" width="{max(w - 2, 0.5):.2f}" height="{bar_h}" '
                    f'rx="1.5" fill="{col}"/>')
        x += w
    y += bar_h + 14
    legend: Spans = []
    for lang in s.languages[:6]:
        legend += [("■ ", ""), (lang.name, "v"), (f" {lang.share * 100:.1f}%", "n"), ("   ", "")]
    # colour the squares individually
    lx = pad
    for lang in s.languages[:6]:
        col = alloy.get(lang.name, alloy.get("other", theme.dim))
        body.append(f'<rect x="{lx:.2f}" y="{y + lh * 0.30:.2f}" width="{cw * 0.95:.2f}" '
                    f'height="{cw * 0.95:.2f}" rx="1.5" fill="{col}"/>')
        seg = [(lang.name, "v"), (f" {lang.share * 100:.1f}%", "n")]
        body.append(text_run(lx + cw * 1.6, y + lh * 0.72, seg, size))
        all_text.extend(t for t, _ in seg)
        lx += cw * (1.6 + len(lang.name) + len(f" {lang.share * 100:.1f}%") + 3)
    y += lh
    scope = "bytes in owned public non-fork repos, markup excluded · each pad is a share of code"
    y = put_rows([[(scope, "f")]], pad, y)

    # Weekly activity strip over the window.
    weeks = _weekly(s.daily)
    if weeks:
        y += lh * 0.4
        y = put_rows([rule(f"activity · weekly · {s.window_from} → {s.window_to}", total_cols)], pad, y)
        strip_h = 34
        n = len(weeks)
        step = bar_w / n
        peak = max(weeks) or 1
        for i, v in enumerate(weeks):
            hgt = 1.5 if v == 0 else max(3.0, strip_h * (v / peak) ** 0.6)
            col = theme.faint if v == 0 else theme.accent
            op = "" if v == 0 else f' fill-opacity="{0.45 + 0.55 * (v / peak):.2f}"'
            body.append(f'<rect x="{pad + i * step + 0.6:.2f}" y="{y + strip_h - hgt:.2f}" '
                        f'width="{max(step - 1.6, 1):.2f}" height="{hgt:.2f}" rx="1" fill="{col}"{op}/>')
        y += strip_h + 8
        cap = f"peak week {max(weeks)} · active weeks {sum(1 for v in weeks if v)}/{n}"
        y = put_rows([[(cap, "f")]], pad, y)

    height = y + pad - lh * 0.3
    card = (f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1:.1f}" rx="12" '
            f'fill="{theme.card}" stroke="{theme.edge}"/>')
    all_text.extend(t for t, _ in head)
    all_text.append("■→·")
    title = (f"GitHub stats for {s.login}: {s.contributions_calendar} contributions in the last "
             f"{s.window_days} days; koi age class {meta.stage}")
    return document(width, round(height), card + "".join(body), _style(theme, "".join(all_text)), title)
