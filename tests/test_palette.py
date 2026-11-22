import colorsys

import pytest

from profilegen.koi.pond import koi_colors, leaves_for
from profilegen.palette import hex_to_rgb, mute, rgb_to_hex, shade_ramp, swatches

LINGUIST = {"Python": "#3572A5", "JavaScript": "#f1e05a", "C++": "#f34b7d", "Rust": "#dea584",
            "TypeScript": "#3178c6", "Go": "#00ADD8", "Java": "#b07219"}


def test_hex_roundtrip():
    for h in LINGUIST.values():
        assert rgb_to_hex(hex_to_rgb(h)).lower() == h.lower()
    assert hex_to_rgb("#fff") == (1.0, 1.0, 1.0)


@pytest.mark.parametrize("name,color", sorted(LINGUIST.items()))
def test_muted_colours_stay_in_band(name, color):
    r, g, b = mute(color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    assert s <= 0.42 and 0.40 <= l <= 0.62


def test_shade_ramp_is_ordered():
    lum = [sum(c) for c in shade_ramp((0.5, 0.4, 0.3))]
    assert lum == sorted(lum)


def test_swatches_normalise_and_fold_small_languages():
    langs = [("Python", LINGUIST["Python"], 0.70), ("C++", LINGUIST["C++"], 0.28), ("Go", LINGUIST["Go"], 0.02)]
    sw = swatches(langs, min_share=0.03)
    assert [s.name for s in sw] == ["Python", "C++", "other"]
    assert abs(sum(s.share for s in sw) - 1.0) < 1e-9
    assert sw[0].source == LINGUIST["Python"]


def test_swatches_cap_and_empty():
    sw = swatches([(n, c, 1 / 7) for n, c in LINGUIST.items()])
    assert len([s for s in sw if s.name != "other"]) == 4
    assert swatches([])[0].name == "unknown"


def test_language_changes_leaf_and_koi_colours():
    py = leaves_for([("Python", LINGUIST["Python"], 1.0)])
    js = leaves_for([("JavaScript", LINGUIST["JavaScript"], 1.0)])
    assert py[0].hex != js[0].hex
    assert (koi_colors(py).hi[2] != koi_colors(js).hi[2]).any()
