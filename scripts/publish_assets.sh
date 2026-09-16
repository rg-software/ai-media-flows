#!/usr/bin/env bash
# Publish accepted assets from the ComfyUI input dir into the versioned repo copy,
# then verify byte-for-byte that they match.
#
# Why this exists: promotion (ComfyUI staging dir -> repo assets/) is a separate step
# from generation, and skipping it silently leaves *stale* assets in the repo. That
# happened in E1d: `input/2d/` got the new RealVisXL assets but `assets/2d/` kept the
# old ones, so the repo char_knight was still the two-view E1b image.
#
# LOCATION DECIDES, NOT FILE TYPE (AGENTS.md -> "Asset policy"): this promotes whatever
# sits in the scenario's staging dir, whatever the extension -- .png for 2d,
# .glb/.gltf/.fbx/.obj/.stl/.ply for 3d. Subdirectories are published recursively with
# their relative path preserved, so a material folder can travel with its maps as one
# unit (input/3d/stone_material/* -> assets/3d/stone_material/*).
#
# Usage (on the ComfyUI box, from anywhere):
#   scripts/publish_assets.sh                    # scenario 2d, everything
#   scripts/publish_assets.sh 2d                 # same
#   scripts/publish_assets.sh 3d                 # meshes in input/3d
#   scripts/publish_assets.sh all                # every scenario
#   scripts/publish_assets.sh 2d char_knight     # only these ids
#   scripts/publish_assets.sh 3d stone_statue stone_material   # file or subdir ids
#
# Staging layout (under the ComfyUI input dir):
#   $COMFY/input/2d/  ->  repo assets/2d/   (images)
#   $COMFY/input/3d/  ->  repo assets/3d/   (meshes)
#
# Env overrides: COMFY=... REPO=...
set -euo pipefail

COMFY="${COMFY:-$HOME/Projects-Git/ComfyUI}"
REPO="${REPO:-$HOME/Projects-Git/ai-gamedev-tasks}"

# scenario -> extensions published from that staging dir
exts_for() {
  case "$1" in
    2d) echo "png jpg jpeg webp" ;;
    3d) echo "glb gltf fbx obj stl ply" ;;
    *)  echo "" ;;
  esac
}

rc=0
total=0

publish_file() {   # $1 scenario, $2 relative path inside the staging dir
  local scen="$1" rel="$2"
  local src="$COMFY/input/$scen/$rel" dst="$REPO/assets/$scen/$rel"
  if [ ! -f "$src" ]; then echo "  MISSING $src" >&2; rc=1; return; fi
  mkdir -p "$(dirname "$dst")"
  cp -f "$src" "$dst"
  local a b
  a=$(md5sum "$src"  | cut -d' ' -f1)
  b=$(md5sum "$dst"  | cut -d' ' -f1)
  if [ "$a" = "$b" ]; then echo "  ok   $rel"; else echo "  FAIL $rel" >&2; rc=1; fi
  total=$((total+1))
}

publish_scenario() {
  local scen="$1"; shift
  local ids=("$@")
  local src="$COMFY/input/$scen"
  [ -d "$src" ] || { echo "no such staging dir: $src (skipping $scen)" >&2; return; }
  echo "== $scen: $src -> $REPO/assets/$scen"

  local exts; exts=$(exts_for "$scen") || true
  [ -n "$exts" ] || { echo "  unknown scenario '$scen'" >&2; rc=1; return; }
  local prune=()
  for e in $exts; do prune+=( ! -iname "*.$e" ); done

  if [ "${#ids[@]}" -gt 0 ]; then
    for id in "${ids[@]}"; do
      if [ -d "$src/$id" ]; then
        while IFS= read -r f; do publish_file "$scen" "${f#"$src"/}"; done \
          < <(find "$src/$id" -type f | sort)
      else
        local found=0
        for e in $exts; do
          if [ -f "$src/$id.$e" ]; then publish_file "$scen" "$id.$e"; found=1; fi
        done
        [ "$found" -eq 1 ] || { echo "  MISSING $id (.$exts)" >&2; rc=1; }
      fi
    done
  else
    while IFS= read -r f; do publish_file "$scen" "${f#"$src"/}"; done \
      < <(find "$src" -type f "${prune[@]}" | sort)
  fi
}

if [ "$#" -gt 0 ] && { [ "$1" = "2d" ] || [ "$1" = "3d" ] || [ "$1" = "all" ]; }; then
  scen="$1"; shift
else
  scen="2d"
fi

case "$scen" in
  2d|3d) publish_scenario "$scen" "$@" ;;
  all)   publish_scenario 2d; publish_scenario 3d ;;
esac

if [ "$rc" -eq 0 ]; then echo "published $total asset(s)"; fi
exit $rc
