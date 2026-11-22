"""Glue between the snapshot, the koi pond and the stats panel."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .github_data import Snapshot
from .koi.evolution import Koi, koi_for, next_stage, stage_progress
from .koi.pond import leaves_for
from .palette import Swatch


@dataclass
class KoiMeta:
    stage: str
    stage_index: int
    contributions: int
    window_days: int
    length_px: float
    next_stage: str | None
    next_threshold: int | None
    progress: float
    growth: float
    leaves: list[dict]
    day: str = ""
    stale: bool = False
    inputs_hash: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "KoiMeta":
        d = json.loads(text)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def koi_inputs(contributions: int, languages: list[tuple[str, str, float]],
               window_days: int = 365, min_share: float = 0.03, day: str = "",
               stale: bool = False) -> tuple[Koi, list[Swatch], KoiMeta]:
    koi = koi_for(contributions)
    leaves = leaves_for(languages, min_share=min_share)
    nxt = next_stage(koi.stage)
    meta = KoiMeta(
        stage=koi.stage.name,
        stage_index=koi.stage.index,
        contributions=contributions,
        window_days=window_days,
        length_px=round(koi.length, 1),
        next_stage=nxt.name if nxt else None,
        next_threshold=nxt.threshold if nxt else None,
        progress=round(stage_progress(contributions), 4),
        growth=round(koi.g, 4),
        leaves=[{"name": s.name, "share": round(s.share, 4), "hex": s.hex, "source": s.source}
                for s in leaves],
        day=day,
        stale=stale,
    )
    return koi, leaves, meta


def koi_inputs_hash(meta: KoiMeta, koi_cfg) -> str:
    """Fingerprint of everything that affects the pond's pixels, including the
    renderer's own source, so a code change always forces a re-render."""
    h = hashlib.sha256()
    h.update(json.dumps({"c": meta.contributions, "leaves": meta.leaves, "day": meta.day,
                         "cfg": asdict(koi_cfg)}, sort_keys=True).encode())
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


def write(path: Path, text: str) -> bool:
    """Write only when content changed; returns True if the file changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True
