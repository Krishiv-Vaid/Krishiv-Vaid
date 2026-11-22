import pytest

from profilegen.koi.evolution import LEN_MAX, LEN_MIN, STAGES, growth, koi_for, length_for, next_stage, stage_for, stage_progress


def test_growth_is_monotone_concave_and_bounded():
    vals = [growth(c) for c in range(0, 4000, 25)]
    assert vals[0] == 0.0
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert max(vals) == 1.0
    assert growth(100) - growth(0) > growth(2100) - growth(2000)


def test_every_contribution_makes_the_koi_bigger():
    lengths = [length_for(c) for c in range(0, 2800)]
    assert all(b > a for a, b in zip(lengths, lengths[1:]))
    assert lengths[0] == LEN_MIN
    assert length_for(10**6) == LEN_MAX


@pytest.mark.parametrize("count,name", [
    (0, "Fry"), (99, "Fry"), (100, "Tosai"), (399, "Tosai"), (400, "Nisai"),
    (1000, "Sansai"), (2199, "Sansai"), (2200, "Jumbo"), (10**6, "Jumbo"),
])
def test_age_classes(count, name):
    assert stage_for(count).name == name


def test_negative_counts_are_clamped():
    assert stage_for(-5).index == 1 and growth(-5) == 0.0


def test_progress_and_final_stage():
    assert stage_progress(100) == 0.0
    assert 0.0 < stage_progress(250) < 1.0
    assert stage_progress(5000) == 1.0
    assert next_stage(STAGES[-1]) is None


def test_ornament_never_decreases():
    ks = [koi_for(s.threshold) for s in STAGES]
    for a, b in zip(ks, ks[1:]):
        assert b.patches >= a.patches
        assert b.fin_scale >= a.fin_scale
        assert b.lotus >= a.lotus
        assert b.length > a.length
    assert not ks[0].spots and ks[2].spots
    assert ks[-1].butterfly and ks[-1].ginrin
