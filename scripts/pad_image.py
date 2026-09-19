#!/usr/bin/env python3
"""Make a padded canvas + mask for a *controlled* outpaint fill (E18).

**Outpainting is invention** (`outpaint.json` does that, and should). This script exists for the
other, deliberately manual technique: when you want the frame *extended* rather than *invented*,
mirror (or reflect/clamp) the canvas yourself and then inpaint the seam - "mirror manually, then
inpaint", not a separate flow.

`InpaintCropImproved`'s own `extend_for_outpainting` fills the new area by **edge-clamp** - it
repeats the border row/column outward - and then `KSampler` usually replaces the whole thing, so a
clipped object (half a tree) simply stops at the boundary. Padding first instead gives the sampler a
fill that carries structure, and gives the mask knobs something to act on.

Produces:

    <stem>_padded_<mode>.png   the source, extended by `--left/--right/--up/--down` **pixels**, filled
                               with `--mode` (mirror / reflect / edge)
    <stem>_mask.png            white (255) over the new area only, optionally `--mask-feather`ed
                               (blurred) because `ImageCompositeMasked` does not feather

Then run the ordinary inpaint flow with those two files and a **reduced denoise** (~0.6-0.75) so it
refines the fill instead of replacing it. **Use `--mirror-band 128` for this** (E18b): mirroring only a
band at the seam keeps the boundary continuous *and* leaves the sampler free to invent the rest - no
echo of a building, which whole-padding mirror and the node's edge smear both produce. The band is an
*option*; with `--mirror-band 0` (the default) the whole padding is mirrored.

    uv run python scripts/pad_image.py input/2d/env_cottage.png --left 512 --right 512 \\
        --mode mirror --mask-feather 24 --out-dir <ComfyUI>/input/_outpaint

E18 measured the fills on a cottage: mirror beats the node's edge smear on the seam (step ratio
0.83-0.85 vs 0.97) and carries walls/ground/foliage across, but **a mirrored building survives** -
mirror suits self-similar content (trees, sky, ground, water), not a building-dominated frame.

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
    ap.add_argument("--mirror-band", type=int, default=0,
                    help="with --mode mirror: mirror only this many px at the seam and edge-clamp the "
                         "rest, so the boundary gets real structure to continue while the far region "
                         "carries nothing duplicated (0 = mirror the whole padding)")
    ap.add_argument("--mask-feather", type=int, default=0,
                    help="blur the mask edge by N px - the inpaint step needs a soft boundary, "
                         "because ImageCompositeMasked does not feather")
    a = ap.parse_args()

    src = Path(a.image)
    if not src.is_file():
        raise SystemExit(f"no such image: {src}")
    im = np.asarray(Image.open(src).convert("RGB"))
    h, w = im.shape[:2]

    def pad_side(arr, amount, axis, pre):
        """symmetric for the first `band` px (structure at the seam), edge-clamp beyond it."""
        if amount <= 0:
            return arr
        band = min(a.mirror_band, amount) if a.mode == "mirror" and a.mirror_band > 0 else amount
        pads = [(0, 0)] * 3
        pads[axis] = (band, 0) if pre else (0, band)
        arr = np.pad(arr, pads, mode="symmetric")
        rest = amount - band
        if rest > 0:
            pads = [(0, 0)] * 3
            pads[axis] = (rest, 0) if pre else (0, rest)
            arr = np.pad(arr, pads, mode="edge")
        return arr

    if a.mode == "mirror" and a.mirror_band > 0:
        filled = im
        filled = pad_side(filled, a.up, 0, True)
        filled = pad_side(filled, a.down, 0, False)
        filled = pad_side(filled, a.left, 1, True)
        filled = pad_side(filled, a.right, 1, False)
    else:
        filled = np.pad(im, ((a.up, a.down), (a.left, a.right), (0, 0)), mode=MODES[a.mode])  # type: ignore[call-overload]

    mask = np.zeros(filled.shape[:2], np.uint8)
    mask[: a.up, :] = 255
    mask[a.up + h:, :] = 255
    mask[:, : a.left] = 255
    mask[:, a.left + w:] = 255
    mask_im = Image.fromarray(mask, "L")
    if a.mask_feather > 0:
        from PIL import ImageFilter
        mask_im = mask_im.filter(ImageFilter.GaussianBlur(a.mask_feather))

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{a.mode}" + (f"_band{a.mirror_band}" if a.mode == "mirror" and a.mirror_band else "")
    padded = out / f"{src.stem}_padded{suffix}.png"
    maskp = out / f"{src.stem}_mask.png"
    Image.fromarray(filled).save(padded)
    mask_im.save(maskp)
    print(f"  source  : {src} {w}x{h}")
    print(f"  padded  : {padded} {filled.shape[1]}x{filled.shape[0]}  (mode={a.mode}, "
          f"l{a.left} r{a.right} u{a.up} d{a.down})")
    print(f"  mask    : {maskp}   (white = the {int((mask > 0).mean() * 100)}% to be generated"
          + (f", feathered {a.mask_feather} px" if a.mask_feather else "") + ")")
    print(f"  seams   : x={a.left} and x={a.left + w}, y={a.up} and y={a.up + h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
