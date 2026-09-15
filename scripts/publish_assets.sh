#!/usr/bin/env bash
# Publish accepted 2D assets from the ComfyUI input dir into the versioned repo copy,
# then verify byte-for-byte that they match.
#
# Why this exists: promotion (ComfyUI `input/2d/` -> repo `assets/2d/`) is a separate
# step from generation, and skipping it silently leaves *stale* assets in the repo.
# That happened in E1d: `input/2d/` got the new RealVisXL assets but `assets/2d/`
# kept the old ones, so the repo char_knight was still the two-view E1b image.
#
# Usage (on the ComfyUI box, from the repo root or anywhere):
#   scripts/publish_assets.sh                  # publish all of input/2d
#   scripts/publish_assets.sh char_knight ...  # publish specific ids
#
# Env overrides: COMFY=... REPO=...
set -euo pipefail

COMFY="${COMFY:-$HOME/Projects-Git/ComfyUI}"
REPO="${REPO:-$HOME/Projects-Git/ai-gamedev-tasks}"
SRC="$COMFY/input/2d"
DST="$REPO/assets/2d"

[ -d "$SRC" ] || { echo "no such dir: $SRC" >&2; exit 1; }
mkdir -p "$DST"

if [ "$#" -gt 0 ]; then
  ids=("$@")
else
  mapfile -t ids < <(cd "$SRC" && printf '%s\n' *.png | sed 's/\.png$//')
fi

rc=0
for id in "${ids[@]}"; do
  src="$SRC/$id.png"
  if [ ! -f "$src" ]; then echo "  MISSING $src" >&2; rc=1; continue; fi
  cp -f "$src" "$DST/$id.png"
  a=$(md5sum "$src" | cut -d' ' -f1)
  b=$(md5sum "$DST/$id.png" | cut -d' ' -f1)
  if [ "$a" = "$b" ]; then echo "  ok   $id"; else echo "  FAIL $id" >&2; rc=1; fi
done

if [ "$rc" -eq 0 ]; then echo "published ${#ids[@]} asset(s) -> $DST"; fi
exit $rc
