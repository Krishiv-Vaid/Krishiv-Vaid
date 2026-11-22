from profilegen.koi.evolution import (
    LEN_ADULT, LEN_FRY, MAX_KOI, PER_KOI, PER_PATCH, SUMI, Unit, growth, koi_from_block, school, summary,
)

PY = Unit("Python", "#3572A5")
CPP = Unit("C++", "#f34b7d")
PRIV = Unit(None, None)


def test_growth_is_monotone_and_saturates_at_100():
    g = [growth(n) for n in range(0, 101)]
    assert g[0] == 0.0 and g[-1] == 1.0
    assert all(b > a for a, b in zip(g, g[1:]))
    assert growth(250) == 1.0


def test_every_contribution_grows_the_current_koi():
    lengths = [koi_from_block(0, [PY] * n, "octo").length for n in range(0, 101)]
    assert all(b > a for a, b in zip(lengths, lengths[1:]))
    assert abs(lengths[0] / (1 + 0) - LEN_FRY) < LEN_FRY * 0.07
    assert lengths[-1] > LEN_ADULT * 0.9


def test_every_ten_contributions_add_a_patch_coloured_by_language():
    block = [PY] * 10 + [CPP] * 10 + [PY] * 5
    k = koi_from_block(0, block, "octo")
    assert [p.language for p in k.patches] == ["Python", "C++", "Python"]
    assert [p.fill for p in k.patches] == [1.0, 1.0, 0.5]
    assert k.patches[0].color != k.patches[1].color


def test_private_work_paints_black_markings():
    k = koi_from_block(0, [PRIV] * PER_PATCH, "octo")
    assert k.patches[0].color == SUMI and k.patches[0].language is None


def test_new_koi_every_hundred_and_adults_are_frozen():
    units = [PY] * 100 + [CPP] * 35
    fish = school(units, "octo")
    assert len(fish) == 2
    first, second = fish
    assert first.adult and first.fed == PER_KOI and len(first.patches) == 10
    assert all(p.language == "Python" for p in first.patches)
    assert not second.adult and second.fed == 35
    assert [p.language for p in second.patches] == ["C++"] * 4
    # adding more contributions never changes a grown koi
    assert school(units + [PY] * 50, "octo")[0] == first


def test_a_fry_hatches_exactly_at_each_hundred():
    fish = school([PY] * 200, "octo")
    assert [k.fed for k in fish] == [100, 100, 0]


def test_adults_are_similar_in_size():
    fish = school([PY] * 600, "octo")
    adults = [k.length for k in fish if k.adult]
    assert max(adults) / min(adults) < 1.15


def test_pond_is_capped_and_summary_counts():
    fish = school([PY] * (PER_KOI * (MAX_KOI + 5) + 7), "octo")
    assert len(fish) == MAX_KOI and fish[-1].fed == 7
    s = summary([PY] * 237)
    assert s == {"contributions": 237, "adults": 2, "koi": 3, "current_index": 2,
                 "current_fed": 37, "next_koi_at": 300}


def test_empty_history_still_has_a_fry():
    fish = school([], "octo")
    assert len(fish) == 1 and fish[0].fed == 0
