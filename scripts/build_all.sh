#!/usr/bin/env bash
# Regenerate every SVG in assets/.  Usage: ./scripts/build_all.sh
# make_pendulum.py imports chaos_lab from ~/double-pendulum (override with DOUBLE_PENDULUM_PATH).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r scripts/requirements.txt; }

# Space Grotesk (SIL OFL) is only used to turn the banner name into outlines; not committed.
if [ ! -f .fonts/SpaceGrotesk.ttf ]; then
  mkdir -p .fonts
  curl -sfL -o .fonts/SpaceGrotesk.ttf \
    "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
fi

cd scripts
for s in make_banner make_typing make_blackhole make_pendulum make_scope make_chips; do
  ../.venv/bin/python "$s.py"
done
