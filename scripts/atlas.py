#!/usr/bin/env python3
"""Pack bitmaps into a sheet, or slice a sheet back into tiles - locally, with no ComfyUI.

Why this is a script and not a workflow: packing and slicing are pure pixel-grid arithmetic on files you
already have on disk. ComfyUI's `ImageGrid` / `ImageBatchMulti` / `SplitImageToTileList` do the same work
*inside* a graph, which only helps if the sprites are already in the graph - and the batch node hides its
extra inputs from `/object_info` (it invents `image_3`, `image_4`... from a widget), so a headless tool
cannot even see them. As a script the job is local, deterministic, and the round trip can be **checked**
instead of eyeballed.

    pack    images... -> one sheet      (row-major: left-to-right, top-to-bottom)
    slice   sheet -> tiles              (--verify merges them back and compares, byte-for-byte)

    # four sprites into a 2x2 sheet of 64 px cells
    uv run python scripts/atlas.py pack --out sheet.png --columns 2 --cell 64x64 \\
        assets/2d/potion_1.png assets/2d/potion_2.png assets/2d/potion_3.png assets/2d/potion_4.png

    # and back again, proving the cut is exact
    uv run python scripts/atlas.py slice sheet.png --outdir tiles --tile 64x64 --verify

`--padding` is the gap *between* cells (no outer margin). Verified against the E6 sheet: packing the four
64 px potions with `--columns 2 --cell 64x64` reproduces `assets/2d/potion_atlas.png` pixel-identical, and
`slice --verify` on that sheet reports identical.

No third-party deps beyond numpy/PIL (already in the repo env).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image


def _load(path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _parse_size(text: str) -> tuple[int, int]:
    for sep in ("x", ",", "X"):
        if sep in text:
            w, h = text.split(sep, 1)
            return int(w), int(h)
    n = int(text)
    return n, n


def cmd_pack(a) -> int:
    if len(a.images) < 1:
        raise SystemExit("pack: give at least one image")
    images = [_load(p) for p in a.images]
    cell = _parse_size(a.cell) if a.cell else (max(i.width for i in images),
                                              max(i.height for i in images))
    cols = a.columns or min(len(images), 2)
    rows = (len(images) + cols - 1) // cols
    pad = a.padding
    W = cols * cell[0] + (cols - 1) * pad
    H = rows * cell[1] + (rows - 1) * pad
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        if im.size != cell:
            print(f"  note: {os.path.basename(a.images[i])} is {im.width}x{im.height}, "
                  f"resizing to the {cell[0]}x{cell[1]} cell")
            im = im.resize(cell, Image.Resampling.LANCZOS)
        x = c * (cell[0] + pad) + (cell[0] - im.width) // 2
        y = r * (cell[1] + pad) + (cell[1] - im.height) // 2
        sheet.paste(im, (x, y))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f"packed {len(images)} image(s) -> {a.out}")
    print(f"  grid   : {cols} column(s) x {rows} row(s), cell {cell[0]}x{cell[1]}, padding {pad}")
    print(f"  sheet  : {W}x{H}   order: row-major (left-to-right, top-to-bottom)")
    return 0


def cmd_slice(a) -> int:
    src = _load(a.sheet)
    tile = _parse_size(a.tile)
    step_x = tile[0] - a.overlap
    step_y = tile[1] - a.overlap
    if step_x < 1 or step_y < 1:
        raise SystemExit(f"slice: overlap {a.overlap} must be smaller than the tile {tile[0]}x{tile[1]}")
    cols = (src.width + step_x - 1) // step_x
    rows = (src.height + step_y - 1) // step_y
    os.makedirs(a.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.sheet))[0]
    written = []
    for r in range(rows):
        for c in range(cols):
            box = (c * step_x, r * step_y, min(c * step_x + tile[0], src.width),
                   min(r * step_y + tile[1], src.height))
            piece = src.crop(box)
            path = os.path.join(a.outdir, f"{stem}_r{r}_c{c}.png")
            piece.save(path)
            written.append((r, c, piece, box))
    print(f"sliced {a.sheet} -> {a.outdir}/")
    print(f"  grid  : {cols} column(s) x {rows} row(s), tile {tile[0]}x{tile[1]}, overlap {a.overlap}")
    print(f"  wrote : {len(written)} tile(s)  (names {stem}_r<row>_c<col>.png)")

    if a.verify:
        # exact inverse: each pixel belongs to the FIRST tile covering it, so paste each tile's
        # non-overlapping region only
        merged = Image.new("RGBA", src.size, (0, 0, 0, 0))
        for r, c, piece, _box in written:
            w = min(step_x if c < cols - 1 else tile[0], src.width - c * step_x)
            h = min(step_y if r < rows - 1 else tile[1], src.height - r * step_y)
            merged.paste(piece.crop((0, 0, w, h)), (c * step_x, r * step_y))
        a1 = np.asarray(src)
        a2 = np.asarray(merged)
        same = a1.shape == a2.shape and np.array_equal(a1, a2)
        diff = int(np.abs(a1.astype(int) - a2.astype(int)).max()) if a1.shape == a2.shape else -1
        print(f"  verify: merged == source -> {same}" + ("" if same else f"  (max channel diff {diff})"))
        return 0 if same else 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack bitmaps into a sheet, or slice a sheet into tiles.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack", help="images -> one sheet (row-major)")
    p.add_argument("images", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--columns", type=int, default=0, help="default: 2 (or fewer if fewer images)")
    p.add_argument("--cell", default=None, help="cell size, e.g. 64x64 (default: largest input)")
    p.add_argument("--padding", type=int, default=0, help="gap between cells, no outer margin")
    p.set_defaults(fn=cmd_pack)

    s = sub.add_parser("slice", help="sheet -> tiles")
    s.add_argument("sheet")
    s.add_argument("--outdir", required=True)
    s.add_argument("--tile", required=True, help="tile size, e.g. 64x64")
    s.add_argument("--overlap", type=int, default=0)
    s.add_argument("--verify", action="store_true", help="merge the tiles back and compare with the source")
    s.set_defaults(fn=cmd_slice)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
