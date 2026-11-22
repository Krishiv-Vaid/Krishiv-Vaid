import colorsys

import pytest

from profilegen.coin.palette import METALS, alloy_from_languages, hex_to_rgb, mute, rgb_to_hex, shade_ramp

LINGUIST = {"Python": "#3572A5", "JavaScript": "#f1e05a", "C++": "#f34b7d", "Rust": "#dea584",
            "TypeScript": "#3178c6", "Go": "#00ADD8", "Java": "#b07219"}


def test_hex_roundtrip():
    for h in LINGUIST.values():
        assert rgb_to_hex(hex_to_rgb(h)).lower() == h.lower()
    assert hex_to_rgb("#fff") == (1.0, 1.0, 1.0)


@pytest.mark.parametrize("name,color", sorted(LINGUIST.items()))
def test_muted_colours_stay_in_the_restrained_band(name, color):
    for metal in METALS.values():
        r, g, b = mute(color, metal)
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        assert s <= 0.42, f"{name} too saturated: {s:.2f}"
        assert 0.38 <= l <= 0.66, f"{name} lightness out of band: {l:.2f}"


def test_shade_ramp_is_ordered():
    ramp = shade_ramp((0.5, 0.4, 0.3))
    lum = [sum(c) for c in ramp]
    assert lum == sorted(lum)


def test_alloy_shares_normalise_and_fold_small_languages():
    langs = [("Python", LINGUIST["Python"], 0.70), ("C++", LINGUIST["C++"], 0.28),
             ("Go", LINGUIST["Go"], 0.02)]
    alloy = alloy_from_languages(langs, METALS["gold"], min_share=0.03)
    assert [a.name for a in alloy] == ["Python", "C++", "other"]
    assert abs(sum(a.share for a in alloy) - 1.0) < 1e-9


def test_alloy_caps_at_four_named_languages():
    langs = [(n, c, 1.0 / len(LINGUIST)) for n, c in LINGUIST.items()]
    alloy = alloy_from_languages(langs, METALS["silver"])
    assert len([a for a in alloy if a.name != "other"]) == 4
    assert alloy[-1].name == "other"


def test_alloy_without_language_data_is_plain():
    alloy = alloy_from_languages([], METALS["copper"])
    assert len(alloy) == 1 and alloy[0].share == 1.0
