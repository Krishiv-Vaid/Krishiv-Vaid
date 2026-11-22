import numpy as np

from profilegen.ascii_art import CHARSET, AsciiParams, GlyphAtlas, convert, grid_shape, ink_map


def disc(n=240, w=200):
    ax = np.linspace(-1, 1, w)
    ay = np.linspace(-1.2, 1.2, n)
    x, y = np.meshgrid(ax, ay)
    alpha = (x**2 + (y / 1.2) ** 2 <= 0.8).astype(float)
    lum = 0.3 + 0.5 * (x > 0)  # left half darker
    return lum, alpha


def test_rows_preserve_aspect_for_cell_geometry():
    p = AsciiParams(cols=80, line_height=2.0)
    # A square image must produce half as many rows as columns with 1:2 cells.
    assert grid_shape(400, 400, p) == (80, 40)
    assert grid_shape(400, 800, p) == (80, 80)


def test_atlas_density_is_measured_from_the_font():
    p = AsciiParams()
    atlas = GlyphAtlas(CHARSET, p.sub, p.line_height)
    assert atlas.density[atlas.chars.index(" ")] == 0.0
    assert atlas.density[atlas.chars.index("@")] > atlas.density[atlas.chars.index(".")]
    assert atlas.bitmaps.shape[1:] == (p.sub[1], p.sub[0])


def test_background_stays_blank_and_subject_is_drawn():
    lum, alpha = disc()
    g = convert(lum, alpha, AsciiParams(cols=40, fade_start=1.0))
    assert g.chars[0].strip() == ""  # corner of the frame, outside the subject
    middle = g.chars[g.rows // 2]
    assert middle.strip() != ""
    assert all(len(r) == g.cols for r in g.chars)


def test_light_mode_inks_shadows():
    lum, alpha = disc()
    p = AsciiParams(cols=40, ink_is_dark=True, edge_weight=0, fade_start=1.0, local_contrast=0)
    ink = ink_map(lum, alpha, p)
    h, w = ink.shape
    left, right = ink[h // 3: 2 * h // 3, w // 4], ink[h // 3: 2 * h // 3, 3 * w // 4]
    assert left.mean() > right.mean()  # darker side gets more ink


def test_conversion_is_deterministic_and_trimmed():
    lum, alpha = disc()
    p = AsciiParams(cols=32)
    a, b = convert(lum, alpha, p), convert(lum, alpha, p)
    assert a.chars == b.chars
    t = a.trimmed()
    assert t.chars[0].strip() and t.chars[-1].strip()
    assert t.tones.shape == (t.rows, t.cols)
