"""Contribution history -> a pond of koi.

Contributions are laid out in chronological order and fed to the pond in
blocks of ``PER_KOI`` (100):

* contributions 1-100 raise the first koi, 101-200 the second, and so on;
* a koi grows from fry to adult over its block. Every ``PER_PATCH`` (10)
  contributions add a body patch, coloured by the language those contributions
  were written in, and each single contribution enlarges the patch in progress.
  So every commit makes the current koi a little bigger and more colourful;
* at 100 the koi is fully grown: its markings are frozen, its fins lengthen and
  a lotus blooms. Then a new fry hatches.

Sizes stay in proportion: adults are all roughly the same length (with a
little individual variation), and fry start at about a quarter of that.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

from ..palette import RGB, koi_pigment

PER_KOI = 100
PER_PATCH = 10
MAX_KOI = 14  # the pond holds this many; older adults leave when it is full

LEN_FRY = 13.0  # native pixels for a just-hatched koi
LEN_ADULT = 50.0  # native pixels at 100 contributions

SUMI = (0.17, 0.18, 0.20)  # black markings: private or language-less work


@dataclass(frozen=True)
class Unit:
    """One contribution's language (None = private / no detected language)."""

    language: str | None
    color: str | None


@dataclass(frozen=True)
class Patch:
    color: RGB
    fill: float  # 0..1, grows with each contribution in its block of 10
    language: str | None


@dataclass(frozen=True)
class KoiSpec:
    index: int  # 0 = first koi ever
    fed: int  # contributions in its block, 0..100
    length: float
    patches: tuple[Patch, ...]
    adult: bool
    fin_scale: float
    ginrin: bool
    seed: int

    @property
    def stage(self) -> str:
        if self.adult:
            return "Adult"
        if self.fed < 25:
            return "Fry"
        if self.fed < 60:
            return "Tosai"
        return "Nisai"


def growth(fed: int) -> float:
    """0..1 growth inside a block: fast at first, easing toward adulthood."""
    return min(1.0, max(0, fed) / PER_KOI) ** 0.7


def _majority(units: list[Unit]) -> Unit:
    counts: dict[tuple, int] = {}
    for u in units:
        counts[(u.language, u.color)] = counts.get((u.language, u.color), 0) + 1
    (lang, color), _ = max(counts.items(), key=lambda kv: (kv[1], kv[0][0] or ""))
    return Unit(lang, color)


def koi_from_block(index: int, block: list[Unit], login: str = "") -> KoiSpec:
    fed = min(PER_KOI, len(block))
    seed = zlib.crc32(f"{login}:koi:{index}".encode())
    adult = fed >= PER_KOI
    # individual variation so a school of adults isn't identical
    jitter = ((seed % 1000) / 1000 - 0.5) * 0.12
    length = (LEN_FRY + (LEN_ADULT - LEN_FRY) * growth(fed)) * (1 + jitter)
    patches = []
    for j in range(math.ceil(fed / PER_PATCH)):
        chunk = block[j * PER_PATCH: (j + 1) * PER_PATCH]
        unit = _majority(chunk)
        color = koi_pigment(unit.color) if unit.color else SUMI
        patches.append(Patch(color, min(1.0, len(chunk) / PER_PATCH), unit.language))
    return KoiSpec(
        index=index,
        fed=fed,
        length=length,
        patches=tuple(patches),
        adult=adult,
        fin_scale=1.25 if adult else 0.95 + 0.2 * growth(fed),
        ginrin=adult,
        seed=seed,
    )


def school(units: list[Unit], login: str = "") -> list[KoiSpec]:
    """All koi raised by ``units`` (oldest first), capped at MAX_KOI."""
    if not units:
        return [koi_from_block(0, [], login)]
    blocks = [units[i: i + PER_KOI] for i in range(0, len(units), PER_KOI)]
    if len(blocks[-1]) == PER_KOI:
        blocks.append([])  # the next fry has just hatched
    koi = [koi_from_block(i, b, login) for i, b in enumerate(blocks)]
    return koi[-MAX_KOI:]


def summary(units: list[Unit]) -> dict:
    total = len(units)
    adults = total // PER_KOI
    fed = total % PER_KOI
    return {
        "contributions": total,
        "adults": adults,
        "koi": min(MAX_KOI, adults + 1),
        "current_index": adults,
        "current_fed": fed,
        "next_koi_at": (adults + 1) * PER_KOI,
    }
