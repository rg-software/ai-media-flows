#!/usr/bin/env python3
"""E10 - scene composition: place cutouts on a background plate, then hand off to
ComfyUI for the harmonization pass (see 2d/workflows/compose-harmonize.json).

Placement is scripted rather than done with ComfyUI composites because it is the
step where pixel-exact control matters (scale, feet-on-ground, depth ordering,
overlap) and because it is then trivially diffable/replayable.

Run on the ComfyUI box, from ~/Projects-Git/ComfyUI:
    venv/bin/python ~/Projects-Git/ai-gamedev-tasks/scripts/compose_scene.py

Then submit 2d/workflows/compose-harmonize.json against the two _base/_mask
pairs it drops in input/2d/_work/.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

COMFY = os.path.expanduser("~/Projects-Git/ComfyUI")
REPO = os.path.expanduser("~/Projects-Git/ai-gamedev-tasks")
os.chdir(COMFY)
os.makedirs("input/2d/_work", exist_ok=True)
os.makedirs("output/2D/E10", exist_ok=True)

BACKGROUND = "input/2d/env_cottage_wide.png"

# (name, source RGBA, feet_x, feet_y, target height px)
#   feet_x/feet_y are in background-plate pixels; target height sets the scale -
#   this IS the composition decision: ~200 px reads as "in the world" (next to a
#   ~650 px cottage), ~620 px reads as a character portrait.
VARIANTS = {
    "perspective": [
        ("knight", "output/2D/E10/knight_cut_*.png", 1010, 800, 200),
        ("chest", f"{REPO}/assets/2d/prop_chest_cutout.png", 380, 1010, 120),
    ],
    "hero": [
        ("knight", "output/2D/E10/knight_cut_*.png", 1150, 1000, 620),
        ("chest", f"{REPO}/assets/2d/prop_chest_cutout.png", 380, 1010, 120),
    ],
}
MASK_DILATE = 16  # give the harmonizer margin around the subject footprint


def cutout(path_glob):
    path = sorted(glob.glob(path_glob))[-1]
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 8)
    if not len(xs):
        sys.exit(f"no opaque pixels in {path}")
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def place(bg, items):
    canvas, mask = bg.copy(), Image.new("L", bg.size, 0)
    for name, src, feet_x, feet_y, target_h in items:
        w = max(1, round(src.width * target_h / src.height))
        s = src.resize((w, target_h), Image.LANCZOS)
        x, y = feet_x - w // 2, feet_y - target_h
        canvas.paste(s, (x, y), s)
        m = Image.new("L", bg.size, 0)
        m.paste(s.split()[3], (x, y))
        mask = Image.fromarray(np.maximum(np.asarray(mask), np.asarray(m)))
        print(f"    {name}: {src.size} -> {s.size} at ({x},{y})")
    return canvas, mask


bg = Image.open(BACKGROUND).convert("RGB")
print(f"background {BACKGROUND} {bg.size}")
for name, items in VARIANTS.items():
    base, mask = place(bg, [(n, cutout(g), fx, fy, h) for n, g, fx, fy, h in items])
    dilated = mask.filter(ImageFilter.MaxFilter(2 * MASK_DILATE + 1))
    base.save(f"input/2d/_work/E10_{name}_base.png")
    dilated.save(f"input/2d/_work/E10_{name}_mask.png")
    print(f"  {name}: footprint {(np.asarray(mask) > 128).sum()} px, "
          f"dilated {(np.asarray(dilated) > 128).sum()} px")
print("now submit 2d/workflows/compose-harmonize.json")
