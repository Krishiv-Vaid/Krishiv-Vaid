#!/usr/bin/env python3
"""Generate the static SVGs: section rules, project cards and the toolkit.

    python scripts/generate_static.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profilegen.pipeline import write  # noqa: E402
from profilegen.static_assets import PROJECTS, project_card, project_card_compact, section_rule, toolkit  # noqa: E402
from profilegen.theme import ROOT, THEMES  # noqa: E402

SECTIONS = [
    (1, "about", ""),
    (2, "experience", ""),
    (3, "projects", ""),
    (4, "toolkit", ""),
    (5, "telemetry", "regenerated daily"),
    (6, "beyond the terminal", ""),
    (7, "contact", ""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "assets")
    out = ap.parse_args().out
    n = 0
    for theme in THEMES:
        for idx, title, note in SECTIONS:
            slug = title.split()[0]
            n += write(out / "sections" / f"{idx:02d}-{slug}-{theme.name}.svg",
                       section_rule(idx, title, theme, note=note))
            n += write(out / "sections" / f"{idx:02d}-{slug}-{theme.name}-compact.svg",
                       section_rule(idx, title, theme, width=380))
        for p in PROJECTS:
            n += write(out / "projects" / f"{p.slug}-{theme.name}.svg", project_card(p, theme))
            n += write(out / "projects" / f"{p.slug}-{theme.name}-compact.svg", project_card_compact(p, theme))
        n += write(out / f"toolkit-{theme.name}.svg", toolkit(theme))
        n += write(out / f"toolkit-{theme.name}-compact.svg", toolkit(theme, width=560, compact=True))
    print(f"static assets: {n} file(s) changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
