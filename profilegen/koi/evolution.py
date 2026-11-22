"""Contribution count -> koi age class, length and ornament.

Growth follows a concave power curve, ``g = min(1, (c / C_MAX) ** 0.45)``
(the curve Git Tulkun uses for its creature): early contributions grow the
fish quickly, later ones refine it. Length is continuous in ``g``, so every
single contribution makes the koi a little bigger; the age classes (named
after how koi keepers grade fish by age) unlock ornament.
"""

from __future__ import annotations

from dataclasses import dataclass

C_MAX = 2800
EXPONENT = 0.45

LEN_MIN = 16  # native pixels at 0 contributions
LEN_MAX = 74  # native pixels at C_MAX and beyond


@dataclass(frozen=True)
class Stage:
    index: int
    name: str
    threshold: int
    note: str


STAGES: tuple[Stage, ...] = (
    Stage(1, "Fry", 0, "plain body, single patch"),
    Stage(2, "Tosai", 100, "second patch, longer fins"),
    Stage(3, "Nisai", 400, "secondary-language spots, a lotus blooms"),
    Stage(4, "Sansai", 1000, "butterfly fins, gin-rin scales sparkle"),
    Stage(5, "Jumbo", 2200, "full pattern, flowing fins, three lotus"),
)


def growth(contributions: int) -> float:
    return min(1.0, (max(0, contributions) / C_MAX) ** EXPONENT)


def stage_for(contributions: int) -> Stage:
    current = STAGES[0]
    for s in STAGES:
        if contributions >= s.threshold:
            current = s
    return current


def next_stage(stage: Stage) -> Stage | None:
    return STAGES[stage.index] if stage.index < len(STAGES) else None


def stage_progress(contributions: int) -> float:
    s = stage_for(contributions)
    n = next_stage(s)
    if n is None:
        return 1.0
    return (contributions - s.threshold) / (n.threshold - s.threshold)


def length_for(contributions: int) -> float:
    return LEN_MIN + (LEN_MAX - LEN_MIN) * growth(contributions)


@dataclass(frozen=True)
class Koi:
    """Every renderer knob, derived from the contribution count."""

    stage: Stage
    g: float
    length: float  # native pixels, head to tail tip
    patches: int  # primary-colour patches along the back
    spots: bool  # secondary-language (sumi-style) spots
    fin_scale: float  # pectoral + tail fin size
    butterfly: bool  # long trailing fins
    ginrin: bool  # sparkling scales
    lotus: int  # flowers on the pads
    speed: float  # laps of the path per loop


def koi_for(contributions: int) -> Koi:
    s = stage_for(contributions)
    g = growth(contributions)
    i = s.index
    return Koi(
        stage=s,
        g=g,
        length=length_for(contributions),
        patches=min(4, i),
        spots=i >= 3,
        fin_scale=0.9 + 0.12 * (i - 1) + 0.1 * stage_progress(contributions),
        butterfly=i >= 4,
        ginrin=i >= 4,
        lotus=max(0, i - 2) + (1 if i == 5 else 0),
        speed=1.0,
    )
