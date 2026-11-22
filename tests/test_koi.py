import numpy as np
import pytest
from PIL import Image

from profilegen.koi.animate import path_seed, render, save_gif
from profilegen.koi.evolution import koi_for
from profilegen.koi.pond import BRIDGE_W, BRIDGE_X, H, RIM, W, build_scene, leaves_for, make_path, render_koi, koi_colors

LANGS = [("Python", "#3572A5", 0.6), ("JavaScript", "#f1e05a", 0.4)]


@pytest.fixture(scope="module")
def small():
    return render(koi_for(80), leaves_for(LANGS), 12, "octo", "2026-11-22")


def test_frames_shape_and_transparent_corners(small):
    frames, alpha = small
    assert len(frames) == 12 and frames[0].shape == (H, W, 3)
    assert not alpha[0, 0] and not alpha[-1, -1] and alpha[H // 2, W // 2]


def test_animation_actually_moves(small):
    frames, _ = small
    assert np.abs(frames[0].astype(int) - frames[6].astype(int)).sum() > 0


def test_loop_is_seamless():
    """Frame N would equal frame 0: render 2 frames of a 1-frame-period check."""
    koi, leaves = koi_for(500), leaves_for(LANGS)
    a, _ = render(koi, leaves, 8, "octo", "d")
    b, _ = render(koi, leaves, 16, "octo", "d")
    assert np.array_equal(a[0], b[0])  # tau = 0 is identical regardless of frame count


def test_path_is_closed_and_inside_the_pond():
    p = make_path(path_seed("octo", "2026-11-22"), margin=10)
    assert np.allclose(p.at(np.array([0.0])), p.at(np.array([p.total])))
    assert p.pts[:, 0].min() >= RIM + 10 - 1e-6 and p.pts[:, 0].max() <= W - RIM - 10 + 1e-6
    assert p.pts[:, 1].min() >= RIM + 10 - 1e-6 and p.pts[:, 1].max() <= H - RIM - 10 + 1e-6


def test_route_changes_daily_but_markings_do_not():
    p1 = make_path(path_seed("octo", "2026-11-22"), margin=10)
    p2 = make_path(path_seed("octo", "2026-11-23"), margin=10)
    assert not np.allclose(p1.pts, p2.pts)
    s1 = build_scene(koi_for(80), leaves_for(LANGS), 1)
    s2 = build_scene(koi_for(80), leaves_for(LANGS), 1)
    assert np.array_equal(s1.rgb, s2.rgb)


def test_bigger_contributions_draw_a_bigger_fish():
    leaves = leaves_for(LANGS)
    scene = build_scene(koi_for(0), leaves, 3)
    path = make_path(5, margin=30)
    areas = []
    for c in (0, 300, 1500, 4000):
        fish, _ = render_koi(koi_for(c), path, 0.3, 40, koi_colors(leaves), scene.rgb, 3)
        areas.append(len(fish))
    assert areas == sorted(areas) and areas[-1] > 4 * areas[0]


def test_one_pad_per_share_of_code():
    scene = build_scene(koi_for(80), leaves_for([("Python", "#3572A5", 0.72), ("JavaScript", "#f1e05a", 0.28)]), 9)
    names = [p.swatch.name for p in scene.pads]
    assert names.count("Python") == 5 and names.count("JavaScript") == 2
    for p in scene.pads:
        assert not (BRIDGE_X - p.r < p.x < BRIDGE_X + BRIDGE_W + p.r)


def test_lotus_count_follows_age_class():
    assert sum(p.lotus for p in build_scene(koi_for(0), leaves_for(LANGS), 2).pads) == 0
    assert sum(p.lotus for p in build_scene(koi_for(3000), leaves_for(LANGS), 2).pads) == 4


def test_gif_uses_exact_palette_with_transparency(tmp_path, small):
    frames, alpha = small
    path = tmp_path / "pond.gif"
    n = save_gif(frames, alpha, path, 80, 2)
    assert 20 < n <= 255
    im = Image.open(path)
    assert im.size == (W * 2, H * 2)
    assert im.info.get("transparency") == 0
    assert im.getpixel((0, 0)) == 0  # corner is transparent
    im.seek(0)
    rgb = im.convert("RGB").getpixel((W, H))
    assert tuple(rgb) == tuple(frames[0][H // 2, W // 2])  # pixel-exact
