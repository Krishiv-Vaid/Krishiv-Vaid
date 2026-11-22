#!/usr/bin/env python3
"""Render the statistics panel from a snapshot + coin metadata.

    python scripts/generate_stats.py --snapshot out/snapshot.json --coin out/coin.json --out out/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profilegen.github_data import Snapshot  # noqa: E402
from profilegen.pipeline import CoinMeta, write  # noqa: E402
from profilegen.stats import render_stats  # noqa: E402
from profilegen.theme import THEMES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--coin", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    snap = Snapshot.from_json(args.snapshot.read_text())
    meta = CoinMeta.from_json(args.coin.read_text())
    for theme in THEMES:
        for compact, suffix, width in ((False, "", 1000), (True, "-compact", 560)):
            path = args.out / f"stats-{theme.name}{suffix}.svg"
            changed = write(path, render_stats(snap, meta, theme, width=width, compact=compact,
                                               size=12.6 if not compact else 15))
            print(f"{'wrote' if changed else 'unchanged'} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
