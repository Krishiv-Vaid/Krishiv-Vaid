"""Glue between the snapshot, the coin and the stats panel."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .coin.evolution import Detail, detail_for, next_stage, stage_progress
from .coin.palette import METALS, Alloy, alloy_from_languages
from .github_data import Snapshot


@dataclass
class CoinMeta:
    stage: str
    stage_index: int
    contributions: int
    window_days: int
    next_stage: str | None
    next_threshold: int | None
    progress: float
    growth: float
    alloy: list[dict]
    stale: bool = False
    inputs_hash: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "CoinMeta":
        d = json.loads(text)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def coin_inputs_hash(meta: "CoinMeta", coin_cfg) -> str:
    """Fingerprint of everything that affects the coin's pixels, including the
    renderer's own source, so a code change always forces a re-render."""
    h = hashlib.sha256()
    h.update(json.dumps({"c": meta.contributions, "alloy": meta.alloy, "cfg": asdict(coin_cfg)},
                        sort_keys=True).encode())
    for src in sorted((Path(__file__).parent / "coin").glob("*.py")):
        h.update(src.read_bytes())
    for dep in ("theme.py", "ascii_art.py"):
        h.update((Path(__file__).parent / dep).read_bytes())
    return h.hexdigest()[:16]


def coin_inputs(contributions: int, languages: list[tuple[str, str, float]],
                window_days: int = 365, min_share: float = 0.03,
                stale: bool = False) -> tuple[Detail, list[Alloy], CoinMeta]:
    detail = detail_for(contributions)
    alloy = alloy_from_languages(languages, METALS[detail.stage.metal], min_share=min_share)
    nxt = next_stage(detail.stage)
    meta = CoinMeta(
        stage=detail.stage.name,
        stage_index=detail.stage.index,
        contributions=contributions,
        window_days=window_days,
        next_stage=nxt.name if nxt else None,
        next_threshold=nxt.threshold if nxt else None,
        progress=round(stage_progress(contributions), 4),
        growth=round(detail.g, 4),
        alloy=[{"name": a.name, "share": round(a.share, 4), "hex": a.hex} for a in alloy],
        stale=stale,
    )
    return detail, alloy, meta


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
