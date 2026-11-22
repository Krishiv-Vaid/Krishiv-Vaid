"""Contribution count -> coin stage and detail parameters.

Growth follows a concave power curve, ``g = min(1, (c / C_MAX) ** 0.45)``
(the same shape Git Tulkun uses for its creature): early contributions move
the design quickly, later ones refine it. Stage thresholds are placed along
that curve, and the continuous ``g`` drives detail *within* a stage, so the
coin changes a little with every contribution rather than only at stage
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass

C_MAX = 2800
EXPONENT = 0.45


@dataclass(frozen=True)
class Stage:
    index: int  # 1-based
    name: str
    threshold: int  # minimum contributions
    metal: str  # key into palette.METALS
    rim_metal: str | None = None  # bimetallic ring, masterwork only


STAGES: tuple[Stage, ...] = (
    Stage(1, "Copper Fragment", 0, "copper"),
    Stage(2, "Bronze Medallion", 100, "bronze"),
    Stage(3, "Silver Relic", 400, "silver"),
    Stage(4, "Gold Medallion", 1000, "gold"),
    Stage(5, "Masterwork Coin", 2200, "platinum", rim_metal="gold"),
)


def growth(contributions: int) -> float:
    c = max(0, contributions)
    return min(1.0, (c / C_MAX) ** EXPONENT)


def stage_for(contributions: int) -> Stage:
    current = STAGES[0]
    for s in STAGES:
        if contributions >= s.threshold:
            current = s
    return current


def next_stage(stage: Stage) -> Stage | None:
    return STAGES[stage.index] if stage.index < len(STAGES) else None


def stage_progress(contributions: int) -> float:
    """0..1 progress from the current stage threshold to the next."""
    s = stage_for(contributions)
    n = next_stage(s)
    if n is None:
        return 1.0
    return (contributions - s.threshold) / (n.threshold - s.threshold)


@dataclass(frozen=True)
class Detail:
    """Design parameters derived from stage + growth. All renderer knobs live here."""

    stage: Stage
    g: float
    fragment: bool  # broken edge, worn surface
    wear: float  # 0 pristine .. 1 heavily worn
    polish: float  # specular sharpness, 0..1
    beads: int  # bead ring count (0 = none)
    denticles: int  # radial teeth inside the rim (0 = none)
    text_ring: bool
    guilloche_lines: int  # 0 = none
    lattice: bool  # star/sunburst geometry around the monogram
    reeded_edge: int  # edge grooves (0 = plain)
    inlay_width: float  # language enamel band width (fraction of radius)
    rim_rings: int  # concentric engraved rings near the rim


def detail_for(contributions: int) -> Detail:
    s = stage_for(contributions)
    g = growth(contributions)
    p = stage_progress(contributions)
    i = s.index
    return Detail(
        stage=s,
        g=g,
        fragment=i == 1,
        wear=max(0.0, 0.85 - 0.22 * (i - 1) - 0.15 * p),
        polish=min(1.0, 0.25 + 0.17 * (i - 1) + 0.08 * p),
        beads=0 if i < 2 else int(48 + 24 * (i - 2) + 24 * p),
        denticles=0 if i < 3 else int(96 + 48 * (i - 3)),
        text_ring=i >= 3,
        guilloche_lines=0 if i < 4 else int(10 + 6 * (i - 4) + 6 * p),
        lattice=i >= 5 or (i == 4 and p > 0.5),
        reeded_edge=0 if i < 2 else int(90 + 60 * (i - 2)),
        inlay_width=0.030 + 0.005 * (i - 1),
        rim_rings=min(3, i - 1),
    )
