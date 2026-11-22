import pytest

from profilegen.coin.evolution import STAGES, detail_for, growth, next_stage, stage_for, stage_progress


def test_growth_is_monotone_concave_and_bounded():
    vals = [growth(c) for c in range(0, 4000, 25)]
    assert vals[0] == 0.0
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert max(vals) == 1.0
    # concave: early contributions move g more than late ones
    assert growth(100) - growth(0) > growth(2100) - growth(2000)


@pytest.mark.parametrize("count,name", [
    (0, "Copper Fragment"), (99, "Copper Fragment"), (100, "Bronze Medallion"),
    (399, "Bronze Medallion"), (400, "Silver Relic"), (1000, "Gold Medallion"),
    (2199, "Gold Medallion"), (2200, "Masterwork Coin"), (10**6, "Masterwork Coin"),
])
def test_stage_thresholds(count, name):
    assert stage_for(count).name == name


def test_negative_counts_are_clamped():
    assert stage_for(-5).index == 1
    assert growth(-5) == 0.0


def test_at_least_five_distinct_stages():
    assert len({s.name for s in STAGES}) >= 5
    assert [s.threshold for s in STAGES] == sorted(s.threshold for s in STAGES)


def test_progress_runs_zero_to_one_within_a_stage():
    assert stage_progress(100) == 0.0
    assert 0.0 < stage_progress(250) < 1.0
    assert stage_progress(5000) == 1.0
    assert next_stage(STAGES[-1]) is None


def test_detail_complexity_never_decreases_across_stages():
    details = [detail_for(s.threshold) for s in STAGES]
    for a, b in zip(details, details[1:]):
        assert b.beads >= a.beads
        assert b.denticles >= a.denticles
        assert b.guilloche_lines >= a.guilloche_lines
        assert b.polish >= a.polish
        assert b.wear <= a.wear
    assert details[0].fragment and not details[1].fragment
    assert details[-1].lattice and details[-1].stage.rim_metal == "gold"
