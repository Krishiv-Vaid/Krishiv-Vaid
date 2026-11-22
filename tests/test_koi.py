import numpy as np
import pytest
from PIL import Image

from profilegen.koi.animate import day_seed, render, save_gif
from profilegen.koi.evolution import Unit, school
from profilegen.koi.pond import BRIDGE_W, BRIDGE_X, H, RIM, W, build_scene, leaves_for, make_path, make_swimmers, render_koi
from profilegen.pipeline import synthetic_units

LANGS = [("Python", "#3572A5", 0.6), ("JavaScript", "#f1e05a", 0.4)]


@pytest.fixture(scope="module")
def small():
    fish = school(synthetic_units(130, LANGS), "octo")
    return render(fish, leaves_for(LANGS), 12, "octo", "2026-11-22")


def test_frames_shape_and_transparent_corners(small):
    frames, alpha = small
    assert len(frames) == 12 and frames[0].shape == (H, W, 3)
    assert not alpha[0, 0] and not alpha[-1, -1] and alpha[H // 2, W // 2]


def test_animation_actually_moves(small):
    frames, _ = small
    assert np.abs(frames[0].astype(int) - frames[6].astype(int)).sum() > 0


def test_loop_is_seamless():
    fish, leaves = school(synthetic_units(250, LANGS), "octo"), leaves_for(LANGS)
    a, _ = render(fish, leaves, 8, "octo", "d")
    b, _ = render(fish, leaves, 16, "octo", "d")
    assert np.array_equal(a[0], b[0])  # tau = 0 is identical regardless of frame count


def test_path_is_closed_and_inside_the_pond():
    p = make_path(day_seed("octo", "2026-11-22"), margin=10)
    assert np.allclose(p.at(np.array([0.0])), p.at(np.array([p.total])))
    assert p.pts[:, 0].min() >= RIM + 10 - 1e-6 and p.pts[:, 0].max() <= W - RIM - 10 + 1e-6
    assert p.pts[:, 1].min() >= RIM + 10 - 1e-6 and p.pts[:, 1].max() <= H - RIM - 10 + 1e-6


def test_routes_change_daily_and_each_koi_has_its_own():
    fish = school(synthetic_units(250, LANGS), "octo")
    d1 = make_swimmers(fish, "octo", "2026-11-22")
    d2 = make_swimmers(fish, "octo", "2026-11-23")
    assert not np.allclose(d1[0].path.pts, d2[0].path.pts)
    assert not np.allclose(d1[0].path.pts, d1[1].path.pts)


def test_more_contributions_more_fish_on_screen():
    leaves = leaves_for(LANGS)
    scene = build_scene(0, leaves, 3)
    areas = []
    for n in (5, 60, 100, 350):
        sw = make_swimmers(school(synthetic_units(n, LANGS), "octo"), "octo", "d")
        areas.append(sum(len(render_koi(s, 0.3, 40, scene.rgb)[0]) for s in sw))
    assert areas == sorted(areas) and areas[-1] > 3 * areas[0]


def test_patches_use_language_colours():
    py = school([Unit("Python", "#3572A5")] * 40, "o")[0]
    js = school([Unit("JavaScript", "#f1e05a")] * 40, "o")[0]
    assert py.patches[0].color != js.patches[0].color


def test_one_pad_per_share_and_a_lotus_per_adult():
    scene = build_scene(2, leaves_for([("Python", "#3572A5", 0.75), ("JavaScript", "#f1e05a", 0.25)]), 9)
    names = [p.swatch.name for p in scene.pads]
    assert names.count("Python") == 6 and names.count("JavaScript") == 2
    assert sum(p.lotus for p in scene.pads) == 2
    for p in scene.pads:
        assert not (BRIDGE_X - p.r < p.x < BRIDGE_X + BRIDGE_W + p.r)


def test_gif_uses_exact_palette_with_transparency(tmp_path, small):
    frames, alpha = small
    path = tmp_path / "pond.gif"
    n = save_gif(frames, alpha, path, 80, 2)
    assert 20 < n <= 255
    im = Image.open(path)
    assert im.size == (W * 2, H * 2)
    assert im.info.get("transparency") == 0
    assert im.getpixel((0, 0)) == 0
    assert tuple(im.convert("RGB").getpixel((W, H))) == tuple(frames[0][H // 2, W // 2])
