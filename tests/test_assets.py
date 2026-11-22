"""Every committed SVG is well-formed, self-contained and referenced correctly."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from profilegen.github_data import Language, Snapshot
from profilegen.pipeline import koi_inputs
from profilegen.stats import render_stats
from profilegen.theme import DARK, LIGHT

ROOT = Path(__file__).resolve().parent.parent
SVGS = sorted((ROOT / "assets").rglob("*.svg"))


def test_assets_exist():
    assert len(SVGS) >= 30


@pytest.mark.parametrize("path", SVGS, ids=lambda p: str(p.relative_to(ROOT)))
def test_svg_is_well_formed_and_self_contained(path):
    text = path.read_text()
    root = ET.fromstring(text)
    assert root.tag.endswith("svg")
    assert root.find("{http://www.w3.org/2000/svg}title") is not None  # accessible name
    assert "@font-face" in text and "data:font/woff2;base64," in text
    # GitHub serves SVGs through camo as <img>: no scripts, no external fetches.
    assert "<script" not in text
    assert not re.search(r'(?:href|src)="https?://', text)
    assert path.stat().st_size < 400_000


def test_both_themes_exist_for_every_asset():
    names = {p.name for p in SVGS}
    for p in SVGS:
        if "-dark" in p.name:
            assert p.name.replace("-dark", "-light") in names


def test_readme_local_images_and_links_exist():
    readme = (ROOT / "README.md").read_text()
    refs = re.findall(r'(?:src|srcset|href)="([^"]+)"', readme)
    refs += re.findall(r"\]\(([^)]+)\)", readme)
    local = [r for r in refs if not r.startswith(("http", "mailto:", "#"))]
    assert local, "expected local references"
    for ref in local:
        assert (ROOT / ref).exists(), f"README references missing file: {ref}"


def test_readme_dynamic_assets_point_at_output_branch():
    readme = (ROOT / "README.md").read_text()
    dyn = re.findall(r"https://raw\.githubusercontent\.com/[^\"]+", readme)
    assert dyn and all("/Krishiv-Vaid/Krishiv-Vaid/output/" in u for u in dyn)
    assert any(u.endswith("koi.webp") for u in dyn)


def test_readme_has_no_phone_number():
    readme = (ROOT / "README.md").read_text()
    assert not re.search(r"\(?\d{3}\)?[ -]\d{3}-\d{4}", readme)


def _snapshot(stale=False):
    return Snapshot(login="octo", generated_at="2026-11-22T06:00:00+00:00", window_days=365,
                    window_from="2025-11-22", window_to="2026-11-22", contributions_calendar=812,
                    contributions=790, excluded_commits=22, private_contributions=40, commits=600,
                    pull_requests_window=30, issues_window=4, reviews_window=9, public_repos=14,
                    stars=57, followers=33, pull_requests_total=48, pull_requests_merged=41,
                    languages=[Language("C++", "#f34b7d", 700, 0.7), Language("Python", "#3572A5", 300, 0.3)],
                    language_scope="test", daily=[i % 5 for i in range(371)], stale=stale)


@pytest.mark.parametrize("theme", [DARK, LIGHT])
@pytest.mark.parametrize("compact", [False, True])
def test_stats_panel_labels_scope_and_values(theme, compact):
    snap = _snapshot()
    _, _, meta = koi_inputs(snap.contributions, [(l.name, l.color, l.share) for l in snap.languages])
    svg = render_stats(snap, meta, theme, width=560 if compact else 1000, compact=compact)
    ET.fromstring(svg)
    for needle in ("812", "incl. 40 private", "365d", "all-time", "owned, non-fork", "57",
                   "Nisai", "C++", "2025-11-22"):
        assert needle in svg, needle
    assert "cached" not in svg


def test_stats_panel_flags_stale_data():
    snap = _snapshot(stale=True)
    _, _, meta = koi_inputs(snap.contributions, [])
    assert "cached 2026-11-22" in render_stats(snap, meta, DARK)
