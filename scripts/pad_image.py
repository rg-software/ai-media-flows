#!/usr/bin/env python3
"""Make a padded canvas + mask for a *controlled* outpaint fill (E18).

`InpaintCropImproved`'s own `extend_for_outpainting` fills the new area by **edge-clamp** - it
repeats the border row/column outward - and then `KSampler` usually replaces the whole thing, so the
extension is pure invention and a clipped object (half a tree) simply stops at the boundary.

This script instead produces the two inputs the deliberate route needs:

    <stem>_padded.png   the source, extended by `--left/--right/--up/--down` **pixels**, filled with
                        `--mode` (mirror / reflect / edge) - a fill the extension can *continue from*
    <stem>_mask.png     white (255) over the new area only, black over the original

which you then load as an image + mask into the `outpaint-continue` flow (mask the new area, inpaint
at moderate denoise, stitch). A mirrored canopy is a plausible continuation, so the model refines
rather than invents; an edge smear gives it nothing to continue.

Usage:
    uv run python scripts/pad_image.py assets/2d/env_cottage.png --left 512 --right 512 \
        --mode mirror --out-dir output/from-box/pads
    # then, on the box:
    uv run python scripts/comfy_io.py upload output/from-box/pads/env_cottage_padded.png \
        output/from-box/pads/env_cottage_mask.png --subfolder _outpaint

No third-party deps beyond numpy/PIL (already in the repo env).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MODES = {
    "mirror": "symmetric",   # reflect including the edge pixel (no seam at the fold)
    "reflect": "reflect",    # reflect without repeating the edge pixel
    "edge": "edge",          # repeat the border pixel (what the node itself does)
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Pad an image + build the outpaint mask (E18).")
    ap.add_argument("image")
    ap.add_argument("--out-dir", default="output/from-box/pads")
    ap.add_argument("--left", type=int, default=0)
    ap.add_argument("--right", type=int, default=0)
    ap.add_argument("--up", type=int, default=0)
    ap.add_argument("--down", type=int, default=0)
    ap.add_argument("--mode", choices=sorted(MODES), default="mirror")
    a = ap.parse_args()

    src = Path(a.image)
    if not src.is_file():
        raise SystemExit(f"no such image: {src}")
    im = np.asarray(Image.open(src).convert("RGB"))
    h, w = im.shape[:2]
    pad = ((a.up, a.down), (a.left, a.right), (0, 0))
    filled = np.pad(im, pad, mode=MODES[a.mode])  # type: ignore[call-overload]  # str mode is valid

    mask = np.zeros(filled.shape[:2], np.uint8)
    mask[: a.up, :] = 255
    mask[a.up + h:, :] = 255
    mask[:, : a.left] = 255
    mask[:, a.left + w:] = 255

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    padded = out / f"{src.stem}_padded_{a.mode}.png"
    maskp = out / f"{src.stem}_mask.png"
    Image.fromarray(filled).save(padded)
    Image.fromarray(mask, "L").save(maskp)
    print(f"  source  : {src} {w}x{h}")
    print(f"  padded  : {padded} {filled.shape[1]}x{filled.shape[0]}  (mode={a.mode}, "
          f"l{a.left} r{a.right} u{a.up} d{a.down})")
    print(f"  mask    : {maskp}   (white = the {int((mask > 0).mean() * 100)}% to be generated)")
    print(f"  seams   : x={a.left} and x={a.left + w}, y={a.up} and y={a.up + h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
