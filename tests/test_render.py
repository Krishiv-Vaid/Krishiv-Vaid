import math

import numpy as np
import pytest

from profilegen.coin.animate import to_rgba, yaw_pitch
from profilegen.coin.evolution import STAGES, detail_for
from profilegen.coin.palette import METALS, alloy_from_languages
from profilegen.coin.render import build_face, render_frame
from profilegen.static_assets import double_pendulum_path

LANGS = [("Python", "#3572A5", 0.6), ("C++", "#f34b7d", 0.4)]


@pytest.fixture(scope="module")
def faces():
    out = {}
    for s in STAGES:
        d = detail_for(s.threshold + 1)
        out[s.index] = (d, build_face(d, alloy_from_languages(LANGS, METALS[d.stage.metal]), n=256))
    return out


def test_every_stage_renders_a_coin(faces):
    for idx, (d, maps) in faces.items():
        rgb, alpha = render_frame(maps, d, math.radians(15), math.radians(9), 96)
        cover = alpha.mean()
        assert 0.35 < cover < 0.75, (d.stage.name, cover)
        assert np.isfinite(rgb).all()
        assert rgb[alpha > 0].mean() > 0.05  # lit, not black


def test_fragment_is_missing_a_piece(faces):
    d1, m1 = faces[1]
    d2, m2 = faces[2]
    a1 = render_frame(m1, d1, 0.0, 0.0, 96)[1].mean()
    a2 = render_frame(m2, d2, 0.0, 0.0, 96)[1].mean()
    assert a1 < a2 * 0.97
    assert m1.radius_lut.min() < 0.9 and np.allclose(m2.radius_lut, 1.0)


def test_enamel_band_follows_language_shares(faces):
    d, maps = faces[3]
    assert maps.enamel_mask.max() > 0.9
    assert maps.enamel_mask.mean() < 0.1  # a band, not the whole face


def test_animation_loop_is_seamless():
    assert yaw_pitch(0.0, 34, 9) == pytest.approx(yaw_pitch(1.0, 34, 9))


def test_rgba_has_shadow_outside_the_coin():
    alpha = np.zeros((40, 40))
    alpha[10:25, 10:30] = 1
    rgba = to_rgba(np.ones((40, 40, 3)) * 0.5, alpha)
    assert rgba.shape == (40, 40, 4)
    assert rgba[28, 20, 3] > 0  # shadow below the coin
    assert rgba[2, 2, 3] == pytest.approx(0, abs=1e-6)


def test_pendulum_visual_is_physically_accurate():
    p1, p2, drift = double_pendulum_path(t_max=4.0)
    assert drift < 1e-6  # RK4 at 1 ms conserves energy to this tolerance
    assert np.allclose(np.hypot(*p1.T), 1.0)  # rod 1 length
    assert np.allclose(np.hypot(*(p2 - p1).T), 1.0)  # rod 2 length
