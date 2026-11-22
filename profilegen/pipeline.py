"""Glue between the snapshot, the koi pond and the stats panel."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .github_data import Snapshot
from .koi.evolution import PER_KOI, KoiSpec, Unit, school, summary
from .koi.pond import leaves_for
from .palette import Swatch, koi_pigment, rgb_to_hex


@dataclass
class KoiMeta:
    contributions: int  # all-time, the pond's food
    koi: int  # swimming now
    adults: int
    current_index: int
    current_fed: int
    current_stage: str
    current_length_px: float
    next_koi_at: int
    colours: list[dict] = field(default_factory=list)  # [{name, hex, count}]
    leaves: list[dict] = field(default_factory=list)
    day: str = ""
    stale: bool = False
    inputs_hash: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "KoiMeta":
        d = json.loads(text)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def units_from_history(history_langs: list[list], history: list[int]) -> list[Unit]:
    out = []
    for i in history:
        if 0 <= i < len(history_langs):
            name, color = history_langs[i]
            out.append(Unit(name, color))
        else:
            out.append(Unit(None, None))
    return out


def koi_inputs(units: list[Unit], languages: list[tuple[str, str, float]], login: str = "",
               min_share: float = 0.03, day: str = "",
               stale: bool = False) -> tuple[list[KoiSpec], list[Swatch], KoiMeta]:
    fish = school(units, login)
    leaves = leaves_for(languages, min_share=min_share)
    info = summary(units)
    current = fish[-1]
    counts = Counter((u.language, u.color) for u in units)
    colours = [
        {"name": name or "private / no code", "hex": rgb_to_hex(koi_pigment(color)) if color else "#6b7078",
         "count": n}
        for (name, color), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0] or "~"))
    ]
    meta = KoiMeta(
        contributions=info["contributions"],
        koi=len(fish),
        adults=info["adults"],
        current_index=info["current_index"],
        current_fed=info["current_fed"],
        current_stage=current.stage,
        current_length_px=round(current.length, 1),
        next_koi_at=info["next_koi_at"],
        colours=colours,
        leaves=[{"name": s.name, "share": round(s.share, 4), "hex": s.hex, "source": s.source}
                for s in leaves],
        day=day,
        stale=stale,
    )
    return fish, leaves, meta


def koi_inputs_hash(meta: KoiMeta, units: list[Unit], koi_cfg) -> str:
    """Fingerprint of everything that affects the pond's pixels, including the
    renderer's own source, so a code change always forces a re-render."""
    h = hashlib.sha256()
    h.update(json.dumps({"units": [[u.language, u.color] for u in units], "leaves": meta.leaves,
                         "day": meta.day, "cfg": asdict(koi_cfg)}, sort_keys=True).encode())
    for src in sorted((Path(__file__).parent / "koi").glob("*.py")):
        h.update(src.read_bytes())
    h.update((Path(__file__).parent / "palette.py").read_bytes())
    return h.hexdigest()[:16]


def snapshot_languages(snap: Snapshot) -> list[tuple[str, str, float]]:
    return [(lang.name, lang.color, lang.share) for lang in snap.languages]


def parse_languages(spec: str) -> list[tuple[str, str, float]]:
    """"Python:#3572A5:0.6,C++:#f34b7d:0.4" -> [(name, hex, share), ...]"""
    out = []
    for part in filter(None, (p.strip() for p in spec.split(","))):
        name, color, share = part.rsplit(":", 2)
        out.append((name, color, float(share)))
    return sorted(out, key=lambda t: -t[2])


def synthetic_units(n: int, languages: list[tuple[str, str, float]], run: int = 10) -> list[Unit]:
    """Deterministic history for previews/tests.

    Real commits arrive in bursts per repository, so languages are interleaved
    by share in runs of ``run`` contributions rather than one at a time.
    """
    if not languages:
        return [Unit(None, None)] * n
    out: list[Unit] = []
    acc = [0.0] * len(languages)
    while len(out) < n:
        for i, (_, _, share) in enumerate(languages):
            acc[i] += share
        i = max(range(len(languages)), key=lambda k: acc[k])
        acc[i] -= sum(lang[2] for lang in languages)
        out.extend([Unit(languages[i][0], languages[i][1])] * run)
    return out[:n]


def write(path: Path, text: str) -> bool:
    """Write only when content changed; returns True if the file changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


__all__ = ["PER_KOI", "KoiMeta", "koi_inputs", "koi_inputs_hash", "units_from_history",
           "synthetic_units", "snapshot_languages", "parse_languages", "write"]
