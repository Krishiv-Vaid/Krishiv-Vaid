#!/usr/bin/env python3
"""Collect GitHub metrics into a JSON snapshot.

    GITHUB_TOKEN=... python scripts/collect_github.py --out out/snapshot.json \
        [--cache previous/snapshot.json]

On failure, the cached snapshot (if any) is re-emitted with ``stale: true``
and the script exits 0, so the README keeps showing the last good numbers.
Without a cache it exits 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profilegen import config  # noqa: E402
from profilegen.github_data import GitHubError, collect, http_transport, load_cached, token_from_env  # noqa: E402
from profilegen.pipeline import write  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path)
    args = ap.parse_args()
    cfg = config.load().github
    try:
        snap = collect(cfg, http_transport(token_from_env()))
    except GitHubError as exc:
        print(f"::warning::GitHub collection failed: {exc}", file=sys.stderr)
        snap = load_cached(args.cache) if args.cache else None
        if snap is None:
            print("no cached snapshot to fall back to", file=sys.stderr)
            return 1
        print("using cached snapshot (marked stale)", file=sys.stderr)
    write(args.out, snap.to_json() + "\n")
    print(f"{snap.login}: {snap.contributions} contributions / {snap.window_days} d "
          f"(calendar {snap.contributions_calendar}, excluded {snap.excluded_commits}), "
          f"{snap.public_repos} repos, {snap.stars} stars, stale={snap.stale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
