#!/usr/bin/env python3
"""Render the koi pond.

    python scripts/generate_koi.py --snapshot out/snapshot.json --out out/
    python scripts/generate_koi.py --contributions 1500 \
        --languages "C++:#f34b7d:0.5,Python:#3572A5:0.5" --out /tmp/pond
    python scripts/generate_koi.py --stages docs/img/koi-stages.png

Outputs (in --out): koi.webp (animated, lossless, transparent), koi.gif
(fallback), koi.png (still) and koi.json (metadata for the stats panel).
The koi's route is seeded by the date, so it swims somewhere new each day.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from profilegen import config  # noqa: E402
from profilegen.github_data import Snapshot  # noqa: E402
from profilegen.koi.animate import render, save_gif, still  # noqa: E402
from profilegen.koi.evolution import STAGES  # noqa: E402
from profilegen.koi.pond import H, W  # noqa: E402
from profilegen.pipeline import KoiMeta, koi_inputs, koi_inputs_hash, parse_languages, snapshot_languages, write  # noqa: E402
from profilegen.theme import DARK, FONT_REGULAR, LIGHT  # noqa: E402

DEMO_LANGS = "Python:#3572A5:0.5,JavaScript:#f1e05a:0.5"
FILES = ["koi.webp", "koi.gif", "koi.png"]


def save_webp(frames, alpha, path: Path, frame_ms: int, scale: int) -> None:
    a = (alpha * 255).astype(np.uint8)
    ims = [Image.fromarray(np.dstack([f, a]), "RGBA").resize((W * scale, H * scale), Image.NEAREST)
           for f in frames]
    path.parent.mkdir(parents=True, exist_ok=True)
    ims[0].save(path, "WEBP", save_all=True, append_images=ims[1:], duration=frame_ms, loop=0,
                lossless=True, method=4)


def _most_visible(frames, leaves) -> int:
    """Frame where the most ivory body pixels are on screen (not under the bridge)."""
    from profilegen.koi.pond import koi_colors

    ivory = np.array(koi_colors(leaves).base)
    counts = [int((f[..., None, :] == ivory[None, None]).all(-1).any(-1).sum()) for f in frames]
    return int(np.argmax(counts))


def stages_sheet(out: Path, languages, login: str) -> None:
    """One sheet per theme: every age class at its threshold size."""
    font = ImageFont.truetype(str(FONT_REGULAR), 14)
    scale = 2
    tiles = []
    for s in STAGES:
        count = s.threshold + (s.threshold // 4 if s.index < 5 else 600)
        koi, leaves, _ = koi_inputs(count, languages)
        frames, alpha = render(koi, leaves, 36, login, "preview")
        tiles.append((s, koi, still(frames, alpha, scale, _most_visible(frames, leaves))))
    tw, th = tiles[0][2].size
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    for theme in (DARK, LIGHT):
        sheet = Image.new("RGBA", (cols * (tw + 16), rows * (th + 46)), theme.page)
        d = ImageDraw.Draw(sheet)
        for i, (s, koi, im) in enumerate(tiles):
            x, y = (i % cols) * (tw + 16), (i // cols) * (th + 46)
            sheet.alpha_composite(im, (x, y))
            d.text((x + 4, y + th + 8), f"{s.index:02d}  {s.name}", fill=theme.text, font=font)
            d.text((x + 4, y + th + 26), f"{s.threshold:,}+ contributions · {koi.length:.0f} px",
                   fill=theme.muted, font=font)
        path = out.with_name(f"{out.stem}-{theme.name}{out.suffix}")
        path.parent.mkdir(parents=True, exist_ok=True)
        sheet.convert("RGB").save(path, optimize=True)
        print(f"wrote {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", type=Path)
    ap.add_argument("--contributions", type=int)
    ap.add_argument("--languages", default=None, help='e.g. "Python:#3572A5:0.6,C++:#f34b7d:0.4"')
    ap.add_argument("--day", default=None, help="route seed (default: today, UTC)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--stages", type=Path, help="write preview sheets of every age class")
    ap.add_argument("--frames", type=int)
    ap.add_argument("--reuse", type=Path, help="directory of a previous run; copy its pond if inputs match")
    args = ap.parse_args()
    cfg = config.load()
    login = cfg.github.login

    if args.stages:
        stages_sheet(args.stages, parse_languages(args.languages or DEMO_LANGS), login)
        if not args.out:
            return 0

    stale = False
    day = args.day
    if args.snapshot:
        snap = Snapshot.from_json(args.snapshot.read_text())
        contributions, languages, window, stale = (
            snap.contributions, snapshot_languages(snap), snap.window_days, snap.stale)
        day = day or snap.window_to
    elif args.contributions is not None:
        contributions, window = args.contributions, cfg.github.window_days
        languages = parse_languages(args.languages or DEMO_LANGS)
    else:
        ap.error("need --snapshot or --contributions")
    if not args.out:
        ap.error("need --out")
    day = day or date.today().isoformat()

    koi, leaves, meta = koi_inputs(contributions, languages, window,
                                   cfg.github.min_language_share, day, stale)
    k = cfg.koi
    meta.inputs_hash = koi_inputs_hash(meta, k)
    if args.reuse and (args.reuse / "koi.json").exists():
        try:
            prev = KoiMeta.from_json((args.reuse / "koi.json").read_text())
        except (ValueError, TypeError):
            prev = None
        if prev and prev.inputs_hash == meta.inputs_hash and all((args.reuse / f).exists() for f in FILES):
            args.out.mkdir(parents=True, exist_ok=True)
            for f in FILES:
                if (args.reuse / f).resolve() != (args.out / f).resolve():
                    shutil.copy2(args.reuse / f, args.out / f)
            write(args.out / "koi.json", meta.to_json() + "\n")
            print(f"{meta.stage}: inputs unchanged ({meta.inputs_hash}), reused previous render")
            return 0

    t0 = time.time()
    frames, alpha = render(koi, leaves, args.frames or k.frames, login, day)
    save_webp(frames, alpha, args.out / "koi.webp", k.frame_ms, k.scale)
    colours = save_gif(frames, alpha, args.out / "koi.gif", k.frame_ms, k.gif_scale)
    still(frames, alpha, k.scale).save(args.out / "koi.png", optimize=True)
    write(args.out / "koi.json", meta.to_json() + "\n")
    sizes = ", ".join(f"{f} {(args.out / f).stat().st_size / 1e6:.2f} MB" for f in FILES)
    print(f"{meta.stage} koi, {meta.length_px} px ({contributions} contributions, route {day}), "
          f"{colours} colours, {time.time() - t0:.1f}s: {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
