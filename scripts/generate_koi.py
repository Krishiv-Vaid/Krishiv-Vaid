#!/usr/bin/env python3
"""Render the koi pond.

    python scripts/generate_koi.py --snapshot out/snapshot.json --out out/
    python scripts/generate_koi.py --contributions 350 \
        --languages "C++:#f34b7d:0.5,Python:#3572A5:0.5" --out /tmp/pond
    python scripts/generate_koi.py --stages docs/img/koi-stages.png

Every 100 contributions raise one koi; each block of 10 adds a patch in the
language those contributions were written in. Outputs (in --out): koi.webp
(animated, lossless, transparent), koi.gif (fallback), koi.png (still) and
koi.json (metadata for the stats panel). Routes are seeded by the date, so
the school swims somewhere new each day.
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
from profilegen.koi.animate import render, save_gif, save_webp, still  # noqa: E402
from profilegen.koi.pond import IVORY, _c  # noqa: E402
from profilegen.palette import hex_to_rgb, shade_ramp  # noqa: E402
from profilegen.pipeline import (  # noqa: E402
    KoiMeta, koi_inputs, koi_inputs_hash, parse_languages, snapshot_languages, synthetic_units,
    units_from_history, write,
)
from profilegen.theme import DARK, FONT_REGULAR, LIGHT  # noqa: E402

DEMO_LANGS = "Python:#3572A5:0.34,C++:#f34b7d:0.22,JavaScript:#f1e05a:0.16,TypeScript:#3178c6:0.12,Java:#b07219:0.10,HTML:#e34c26:0.06"
FILES = ["koi.webp", "koi.gif", "koi.png"]
PREVIEW_COUNTS = [(20, "a fry hatches"), (60, "patches fill in"), (100, "first adult · second fry"),
                  (250, "two adults · a growing koi"), (600, "a school of six"), (1300, "pond of thirteen")]


def _most_visible(frames) -> int:
    """Frame where the most ivory body pixels are on screen (not under the bridge)."""
    ivory = np.array([_c(c) for c in shade_ramp(hex_to_rgb(IVORY))])
    counts = [int((f[..., None, :] == ivory[None, None]).all(-1).any(-1).sum()) for f in frames]
    return int(np.argmax(counts))


def stages_sheet(out: Path, languages, login: str) -> None:
    """One sheet per theme showing how the pond fills as contributions grow."""
    font = ImageFont.truetype(str(FONT_REGULAR), 14)
    scale = 2
    tiles = []
    for count, note in PREVIEW_COUNTS:
        fish, leaves, _ = koi_inputs(synthetic_units(count, languages), languages, login)
        frames, alpha = render(fish, leaves, 30, login, "preview")
        tiles.append((count, note, still(frames, alpha, scale, _most_visible(frames))))
    tw, th = tiles[0][2].size
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    for theme in (DARK, LIGHT):
        sheet = Image.new("RGBA", (cols * (tw + 16) - 16, rows * (th + 46)), theme.page)
        d = ImageDraw.Draw(sheet)
        for i, (count, note, im) in enumerate(tiles):
            x, y = (i % cols) * (tw + 16), (i // cols) * (th + 46)
            sheet.alpha_composite(im, (x, y))
            d.text((x + 4, y + th + 8), f"{count:,} contributions", fill=theme.text, font=font)
            d.text((x + 4, y + th + 26), note, fill=theme.muted, font=font)
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
    ap.add_argument("--stages", type=Path, help="write preview sheets of a growing pond")
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
        units = units_from_history(snap.history_langs, snap.history)
        languages, stale = snapshot_languages(snap), snap.stale
        day = day or snap.window_to
    elif args.contributions is not None:
        languages = parse_languages(args.languages or DEMO_LANGS)
        units = synthetic_units(args.contributions, languages)
    else:
        ap.error("need --snapshot or --contributions")
    if not args.out:
        ap.error("need --out")
    day = day or date.today().isoformat()

    fish, leaves, meta = koi_inputs(units, languages, login, cfg.github.min_language_share, day, stale)
    k = cfg.koi
    meta.inputs_hash = koi_inputs_hash(meta, units, k)
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
            print(f"pond unchanged ({meta.inputs_hash}), reused previous render")
            return 0

    t0 = time.time()
    frames, alpha = render(fish, leaves, args.frames or k.frames, login, day)
    save_webp(frames, alpha, args.out / "koi.webp", k.frame_ms, k.scale)
    colours = save_gif(frames, alpha, args.out / "koi.gif", k.frame_ms, k.gif_scale)
    still(frames, alpha, k.scale).save(args.out / "koi.png", optimize=True)
    write(args.out / "koi.json", meta.to_json() + "\n")
    sizes = ", ".join(f"{f} {(args.out / f).stat().st_size / 1e6:.2f} MB" for f in FILES)
    print(f"{meta.koi} koi ({meta.adults} adult; current {meta.current_stage} {meta.current_fed}/100, "
          f"{meta.current_length_px} px) from {meta.contributions} contributions, route {day}, "
          f"{colours} colours, {time.time() - t0:.1f}s: {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
