#!/usr/bin/env python3
"""Render the evolving coin.

    python scripts/generate_coin.py --snapshot out/snapshot.json --out out/
    python scripts/generate_coin.py --contributions 1500 \
        --languages "C++:#f34b7d:0.5,Python:#3572A5:0.5" --out /tmp/coin
    python scripts/generate_coin.py --stages docs/img/coin-stages.png

Outputs (in --out): coin.webp (animated, transparent), coin-dark.gif and
coin-light.gif (matted fallbacks), coin.png (still) and coin.json (stage
metadata consumed by the stats panel).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from profilegen import config  # noqa: E402
from profilegen.coin.animate import flatten, render_frames, save_gif, save_webp, still  # noqa: E402
from profilegen.coin.evolution import STAGES  # noqa: E402
from profilegen.github_data import Snapshot  # noqa: E402
from profilegen.pipeline import coin_inputs, parse_languages, snapshot_languages, write  # noqa: E402
from profilegen.theme import DARK, FONT_REGULAR, LIGHT  # noqa: E402

DEMO_LANGS = "Python:#3572A5:0.56,JavaScript:#f1e05a:0.44"


def stages_sheet(out: Path, languages, px: int = 300) -> None:
    font = ImageFont.truetype(str(FONT_REGULAR), 15)
    rows = []
    for theme in (DARK, LIGHT):
        tiles = []
        for s in STAGES:
            count = max(s.threshold, 1) + (s.threshold // 4 if s.index < 5 else 600)
            detail, alloy, meta = coin_inputs(count, languages)
            im = flatten(still(detail, alloy, px, texture=1024), theme)
            tile = Image.new("RGB", (px, px + 46), theme.page)
            tile.paste(im, (0, 0))
            d = ImageDraw.Draw(tile)
            d.text((px / 2, px + 12), f"{s.index:02d}  {s.name}", fill=theme.text, font=font, anchor="mm")
            d.text((px / 2, px + 32), f"{s.threshold}+ contributions", fill=theme.muted, font=font, anchor="mm")
            tiles.append(tile)
        row = Image.new("RGB", (px * len(tiles), tiles[0].height), theme.page)
        for i, t in enumerate(tiles):
            row.paste(t, (i * px, 0))
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * r.height))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path)
    ap.add_argument("--contributions", type=int)
    ap.add_argument("--languages", default=None, help='e.g. "Python:#3572A5:0.6,C++:#f34b7d:0.4"')
    ap.add_argument("--out", type=Path)
    ap.add_argument("--stages", type=Path, help="write a preview sheet of every stage")
    ap.add_argument("--frames", type=int)
    args = ap.parse_args()
    cfg = config.load()

    if args.stages:
        stages_sheet(args.stages, parse_languages(args.languages or DEMO_LANGS))
        if not args.out:
            return 0

    stale = False
    if args.snapshot:
        snap = Snapshot.from_json(args.snapshot.read_text())
        contributions, languages, window, stale = (
            snap.contributions, snapshot_languages(snap), snap.window_days, snap.stale)
    elif args.contributions is not None:
        contributions, window = args.contributions, cfg.github.window_days
        languages = parse_languages(args.languages or DEMO_LANGS)
    else:
        ap.error("need --snapshot or --contributions")
    if not args.out:
        ap.error("need --out")

    detail, alloy, meta = coin_inputs(contributions, languages, window,
                                      cfg.github.min_language_share, stale)
    c = cfg.coin
    frames = args.frames or c.frames
    t0 = time.time()
    hi = render_frames(detail, alloy, c.size * 2, frames, c.yaw, c.pitch)
    save_webp(hi, args.out / "coin.webp", c.frame_ms)
    # GIF fallback: 1.25x density and fewer colours keep it a few MB.
    lo = [f.resize((int(c.size * 1.25),) * 2, Image.LANCZOS) for f in hi]
    for theme in (DARK, LIGHT):
        save_gif(lo, args.out / f"coin-{theme.name}.gif", c.frame_ms, theme)
    still(detail, alloy, c.size * 2).save(args.out / "coin.png", optimize=True)
    write(args.out / "coin.json", meta.to_json() + "\n")
    sizes = ", ".join(f"{p.name} {p.stat().st_size / 1e6:.2f} MB"
                      for p in sorted(args.out.glob("coin*")) if p.suffix in (".webp", ".gif"))
    print(f"{meta.stage} ({contributions} contributions, g={meta.growth}) in {time.time() - t0:.1f}s: {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
