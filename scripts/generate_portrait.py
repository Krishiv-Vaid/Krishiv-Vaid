#!/usr/bin/env python3
"""Generate the hero portrait assets.

    python scripts/generate_portrait.py                 # assets/portrait-{dark,light}.svg
    python scripts/generate_portrait.py --out out       # daily: refreshes the uptime line
    python scripts/generate_portrait.py --variants      # + docs/img/portrait-variants.png
    python scripts/generate_portrait.py --from-photo me.jpg --crop 185,95,995,1065
                                                        # rebuild source/portrait-cutout.png

The committed cutout (source/portrait-cutout.png) is a greyscale + alpha crop,
so CI and contributors can regenerate without the segmentation model.
``--from-photo`` needs the optional ``rembg`` dependency (requirements-portrait.txt).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from profilegen.ascii_art import AsciiParams, GlyphAtlas, convert, load_cutout, with_overrides  # noqa: E402
from profilegen import config  # noqa: E402
from profilegen.hero import render_hero, render_hero_compact, uptime  # noqa: E402
from profilegen.preview import render_grid_png  # noqa: E402
from profilegen.theme import DARK, FONT_REGULAR, LIGHT, ROOT  # noqa: E402

CUTOUT = ROOT / "source" / "portrait-cutout.png"

# Selected after comparing the variants below (see docs/img/portrait-variants.png).
# Both themes are *positive* images: light mode inks shadows (pencil on paper),
# dark mode inks highlights (light on a screen). An earlier version reused the
# light-mode grid on dark, which is a photographic negative and reads as a
# skull; a positive mapping keeps the face human.
FINAL = AsciiParams(  # light mode
    cols=96,
    tone_levels=6,
    rim_light=True,
    mode="shape",
    shape_weight=1.0,
    level_box=(0.30, 0.30, 0.72, 0.66),  # face: forehead -> chin, cheek to cheek
    lo_pct=3,
    hi_pct=98.5,
    gamma=1.5,
    shadow_detail=0.3,
    smooth=0.8,  # skin reads as shading, not speckle
    edge_weight=0.2,
    local_contrast=0.8,
    local_radius=0.03,
    fade_start=0.58,
    fade_end=0.90,
    fade_to=0.0,
)

FINAL_DARK = with_overrides(
    FINAL,
    ink_is_dark=False,  # bright glyphs = bright skin
    level_box=None,
    lo_pct=2,
    hi_pct=99.5,
    gamma=0.95,
    shadow_detail=0.0,
    smooth=0.6,
    edge_weight=0.15,
    local_contrast=1.5,
    local_radius=0.025,
    floor=0.17,  # dark hair still drawn, faintly, so the silhouette survives
)

VARIANTS: dict[str, dict] = {
    "A  luminance ramp": dict(mode="ramp", level_box=None, lo_pct=1.5, hi_pct=99,
                              gamma=1.0, shadow_detail=0, edge_weight=0.0, smooth=0),
    "B  ramp + Floyd-Steinberg": dict(mode="ramp", dither="fs", level_box=None, lo_pct=1.5,
                                      hi_pct=99, gamma=1.0, shadow_detail=0, edge_weight=0.2, smooth=0),
    "C  hard face levels (v1)": dict(lo_pct=8, hi_pct=92, gamma=1.3, smooth=0, local_contrast=0.5),
    "D  structure + Sobel": dict(edge_weight=0.7, local_contrast=1.5, shadow_detail=0, smooth=0),
    "E  selected": dict(),
}


def make_cutout(photo: Path, crop: tuple[int, int, int, int], width: int = 640) -> None:
    try:
        from rembg import new_session, remove
    except ImportError as exc:  # pragma: no cover - optional path
        raise SystemExit("pip install -r requirements-portrait.txt  (needs rembg)") from exc
    im = Image.open(photo).convert("RGB")
    cut = remove(im, session=new_session("birefnet-portrait")).crop(crop)
    cut = cut.resize((width, round(cut.height * width / cut.width)), Image.LANCZOS)
    Image.merge("LA", (cut.convert("L"), cut.getchannel("A"))).save(CUTOUT, optimize=True)
    print(f"wrote {CUTOUT.relative_to(ROOT)}")


def variants_sheet(out: Path) -> None:
    lum, alpha = load_cutout(CUTOUT)
    atlas = GlyphAtlas(FINAL.charset, FINAL.sub, FINAL.line_height)
    font = ImageFont.truetype(str(FONT_REGULAR), 13)
    tiles = []
    for theme in (LIGHT, DARK):
        row = []
        for name, kw in VARIANTS.items():
            base = FINAL if theme is LIGHT or name.startswith("A") or name.startswith("B") else FINAL
            if theme is DARK and name.startswith("E"):
                base = FINAL_DARK
            elif theme is DARK and name.startswith("C"):
                base, kw = FINAL, dict(kw, ink_is_dark=True)  # the old negative, for reference
            g = convert(lum, alpha, with_overrides(base, cols=64, **kw), atlas)
            im = render_grid_png(g, theme, font_size=8, pad=12)
            canvas = Image.new("RGB", (im.width, im.height + 26), theme.card)
            canvas.paste(im, (0, 26))
            ImageDraw.Draw(canvas).text((12, 8), name, fill=theme.muted, font=font)
            row.append(canvas)
        tiles.append(row)
    W = sum(t.width for t in tiles[0])
    H = sum(r[0].height for r in tiles)
    sheet = Image.new("RGB", (W, H))
    y = 0
    for row in tiles:
        x = 0
        for t in row:
            sheet.paste(t, (x, y))
            x += t.width
        y += row[0].height
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-photo", type=Path)
    ap.add_argument("--crop", default="185,95,995,1065")
    ap.add_argument("--variants", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "assets")
    ap.add_argument("--today", help="date for the uptime line (default: today in Toronto)")
    args = ap.parse_args()
    cfg = config.load()
    today = (date.fromisoformat(args.today) if args.today
             else datetime.now(ZoneInfo("America/Toronto")).date())
    up = uptime(date.fromisoformat(cfg.profile.birthdate), today)

    if args.from_photo:
        make_cutout(args.from_photo, tuple(int(v) for v in args.crop.split(",")))

    lum, alpha = load_cutout(CUTOUT)
    grids = {LIGHT.name: convert(lum, alpha, FINAL).trimmed(),
             DARK.name: convert(lum, alpha, FINAL_DARK).trimmed()}
    grid = grids[LIGHT.name]
    args.out.mkdir(parents=True, exist_ok=True)
    for theme in (DARK, LIGHT):
        grid = grids[theme.name]
        path = args.out / f"portrait-{theme.name}.svg"
        path.write_text(render_hero(grid, theme, up=up), encoding="utf-8")
        print(f"wrote {path}  ({path.stat().st_size / 1024:.0f} KiB)")
        path = args.out / f"portrait-{theme.name}-compact.svg"
        path.write_text(render_hero_compact(grid, theme, up=up), encoding="utf-8")
        print(f"wrote {path}  ({path.stat().st_size / 1024:.0f} KiB)")
    print(f"uptime {up} (as of {today})")
    (ROOT / "source" / "portrait.txt").write_text("\n".join(r.rstrip() for r in grid.chars) + "\n")

    if args.variants:
        variants_sheet(ROOT / "docs" / "img" / "portrait-variants.png")


if __name__ == "__main__":
    main()
