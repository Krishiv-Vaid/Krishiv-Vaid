#!/usr/bin/env python3
"""Render README.md the way GitHub does, for visual QA in both themes.

    python scripts/build_preview.py [--out preview] [--screenshots]

* README is converted by GitHub's own Markdown API (same sanitiser as the
  profile page), using `gh api markdown`.
* Dynamic images are pointed at ./out (run the dynamic pipeline first) so the
  preview works before the output branch exists.
* GitHub's <themed-picture> is emulated by rewriting the colour-scheme media
  queries, producing dark/light x desktop/mobile pages.
* --screenshots captures PNGs with headless Chrome when it is installed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/Krishiv-Vaid/Krishiv-Vaid/output/"
CSS = "https://cdn.jsdelivr.net/npm/github-markdown-css@5.8.1/github-markdown-{}.css"
CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "preview")
    ap.add_argument("--screenshots", action="store_true")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    html = subprocess.run(
        ["gh", "api", "markdown", "-f", "mode=gfm", "-f", "context=Krishiv-Vaid/Krishiv-Vaid",
         "-F", f"text=@{ROOT / 'README.md'}"],
        check=True, capture_output=True, text=True).stdout
    html = html.replace(RAW, (ROOT / "out").as_uri() + "/")
    html = re.sub(r'(src|srcset|href)="(?!https?:|mailto:|#|file:)([^"]+)"',
                  lambda m: f'{m.group(1)}="{(ROOT / m.group(2)).as_uri()}"', html)
    html = html.replace("<details>", "<details open>")

    for theme, bg in (("dark", "#0d1117"), ("light", "#ffffff")):
        css = out / f"github-{theme}.css"
        if not css.exists():
            urllib.request.urlretrieve(CSS.format(theme), css)
        if theme == "dark":
            body = html.replace("(prefers-color-scheme: dark) and ", "")
            body = body.replace('media="(prefers-color-scheme: dark)"', 'media="all"')
        else:
            body = re.sub(r'<source media="\(prefers-color-scheme: dark\)[^>]*>', "", html)
        for mode, width, pad in (("desktop", 1012, 32), ("mobile", 390, 16)):
            page = out / f"{theme}-{mode}.html"
            page.write_text(
                f'<!doctype html><html><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width">'
                f'<link rel="stylesheet" href="{css.name}"><style>body{{background:{bg};margin:0}}'
                f'.markdown-body{{box-sizing:border-box;width:{width}px;max-width:{width}px;margin:0;padding:{pad}px}}'
                f'</style></head><body><article class="markdown-body">{body}</article></body></html>')
            print(f"wrote {page}")
            if args.screenshots:
                chrome = next((c for c in CHROME if c and Path(c).exists()), None)
                if not chrome:
                    print("chrome not found; skipping screenshots", file=sys.stderr)
                    continue
                subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                f"--window-size={width},7000", "--force-device-scale-factor=1",
                                f"--screenshot={page.with_suffix('.png')}", page.as_uri()],
                               check=False, capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
