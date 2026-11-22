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
    rows = [rule("koi pond", cols)]
    rows.append(leader("swimming", f"{meta.koi} koi", cols, f"{meta.adults} adult"))
    rows.append(leader("growing", f"#{meta.current_index + 1} {meta.current_stage}", cols,
                       f"{meta.current_fed}/100 fed"))
    rows.append(leader("length", f"{meta.current_length_px:.0f} px", cols))
    remaining = meta.next_koi_at - meta.contributions
    rows.append(leader("next koi", f"at {_fmt(meta.next_koi_at)}", cols, f"({remaining} to go)"))
    rows.append(leader("fed by", f"{_fmt(meta.contributions)} contributions", cols, "all-time"))
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


def _swatch_row(body: list[str], all_text: list[str], items: list[tuple[str, str, str]],
                x0: float, y: float, size: float, lh: float, max_x: float) -> float:
    """Coloured squares with labels, wrapping at max_x. Returns the next y."""
    cw = size * MONO_ADVANCE
    x = x0
    for name, value, col in items:
        need = cw * (1.6 + len(name) + 1 + len(value) + 3)
        if x + need > max_x and x > x0:
            x, y = x0, y + lh
        body.append(f'<rect x="{x:.2f}" y="{y + lh * 0.30:.2f}" width="{cw * 0.95:.2f}" '
                    f'height="{cw * 0.95:.2f}" rx="1.5" fill="{col}"/>')
        seg = [(name, "v"), (f" {value}", "n")]
        body.append(text_run(x + cw * 1.6, y + lh * 0.72, seg, size))
        all_text.extend(t for t, _ in seg)
        x += need
    return y + lh


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

    # Koi colours: what each language has painted on the school.
    y = put_rows([rule("koi colours · contributions by language", total_cols)], pad, y)
    items = [(c["name"], str(c["count"]), c["hex"]) for c in meta.colours]
    y = _swatch_row(body, all_text, items, pad, y, size, lh, width - pad)
    y = put_rows([[("every 10 contributions paint one patch in the language they were written in", "f")]],
                 pad, y) + lh * 0.4

    # Language distribution: the same colours tint the lily pads.
    y = put_rows([rule("languages · lily pads", total_cols)], pad, y)
    bar_w = width - 2 * pad
    bar_h = 7
    x = pad
    pads = {lf["name"]: lf["hex"] for lf in meta.leaves}
    for lang in s.languages:
        w = bar_w * lang.share
        if w < 0.5:
            continue
        col = pads.get(lang.name, pads.get("other", theme.dim))
        body.append(f'<rect x="{x:.2f}" y="{y + 6:.2f}" width="{max(w - 2, 0.5):.2f}" height="{bar_h}" '
                    f'rx="1.5" fill="{col}"/>')
        x += w
    y += bar_h + 14
    items = [(lang.name, f"{lang.share * 100:.1f}%", pads.get(lang.name, pads.get("other", theme.dim)))
             for lang in s.languages[:6]]
    y = _swatch_row(body, all_text, items, pad, y, size, lh, width - pad)
    scope = "bytes in owned public non-fork repos, markup excluded · each pad is a share of code"
    y = put_rows([[(scope, "f")]], pad, y)

    # Activity: the year by week, then the past seven days by day, flush right.
    weeks = _weekly(s.daily)
    if weeks:
        y += lh * 0.4
        y = put_rows([rule(f"activity · {s.window_from} → {s.window_to}", total_cols)], pad, y)
        strip_h = 34
        days7 = s.daily[-7:]
        day_w = (bar_w * (0.30 if compact else 0.17))
        gap = 18
        year_w = bar_w - day_w - gap
        n = len(weeks)
        step = year_w / n
        peak = max(weeks) or 1
        for i, v in enumerate(weeks):
            hgt = 1.5 if v == 0 else max(3.0, strip_h * (v / peak) ** 0.6)
            col = theme.faint if v == 0 else theme.accent
            op = "" if v == 0 else f' fill-opacity="{0.45 + 0.55 * (v / peak):.2f}"'
            body.append(f'<rect x="{pad + i * step + 0.6:.2f}" y="{y + strip_h - hgt:.2f}" '
                        f'width="{max(step - 1.6, 1):.2f}" height="{hgt:.2f}" rx="1" fill="{col}"{op}/>')
        dx0 = pad + year_w + gap
        body.append(f'<line x1="{dx0 - gap / 2:.1f}" y1="{y:.1f}" x2="{dx0 - gap / 2:.1f}" '
                    f'y2="{y + strip_h:.1f}" stroke="{theme.rule}"/>')
        dstep = day_w / 7
        dpeak = max(max(days7), 1)
        for i, v in enumerate(days7):
            hgt = 1.5 if v == 0 else max(3.0, strip_h * (v / dpeak) ** 0.6)
            col = theme.faint if v == 0 else theme.text
            body.append(f'<rect x="{dx0 + i * dstep + 1:.2f}" y="{y + strip_h - hgt:.2f}" '
                        f'width="{max(dstep - 3, 1):.2f}" height="{hgt:.2f}" rx="1" fill="{col}"/>')
        y += strip_h + 8
        cap_l = f"weekly · peak {max(weeks)} · active weeks {sum(1 for v in weeks if v)}/{n}"
        cap_r = f"past 7 days · {sum(days7)}"
        body.append(text_run(pad, y + lh * 0.72, [(cap_l, "f")], size))
        body.append(text_run(width - pad - mono_width(len(cap_r), size), y + lh * 0.72, [(cap_r, "f")], size))
        all_text.extend([cap_l, cap_r])
        y += lh

    height = y + pad - lh * 0.3
    card = (f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1:.1f}" rx="12" '
            f'fill="{theme.card}" stroke="{theme.edge}"/>')
    all_text.extend(t for t, _ in head)
    all_text.append("■→·")
    title = (f"GitHub stats for {s.login}: {s.contributions_calendar} contributions in the last "
             f"{s.window_days} days; {meta.koi} koi fed by {meta.contributions} contributions")
    return document(width, round(height), card + "".join(body), _style(theme, "".join(all_text)), title)
