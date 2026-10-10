#!/usr/bin/env python3
"""Pack a generated clip into an engine-ready VFX flipbook: one sheet plus a manifest.

WHY THIS EXISTS

`scripts/atlas.py` packs frames into a sheet but has no notion of *time*, and that is the whole
job here. A VFX flipbook is a sheet whose cells are meant to be played in order at a known rate,
so two decisions have to be made that atlas cannot make for you:

  * **which frames** - a generated clip is mostly dead time around the event (an explosion spends
    its first and last second barely moving), so `--frames N` samples *uniformly* and `--window
    A B` (fractions of the clip) picks the part worth sampling. Sampling the whole clip of a
    one-shot event gives you a sheet where six cells look identical.
  * **how they play** - a generated clip does not loop. `--loop pingpong` (out and back, dropping
    the duplicated end frames) is the only ordering that is seamless for *any* source; `--loop cycle`
    is honest about wrapping and only right when the source really is cyclic; `--loop none` is a
    one-shot, which is what most impacts actually want.

    A flipbook's playback rate is a **delivery** decision, not the clip's: `--fps` defaults to 12
    and is recorded in the manifest independently of the source's own rate.

THE COMPOSITING QUESTION (the one that decides the verdict)

An effect has to composite over a game background, and there are two different answers:

  * **additive blending** - fire, sparks, energy and magic glow on *black* need no alpha at all.
    The black is the background; the engine adds the sprite. This is the cheapest and often the
    correct answer, so `--key none` is a legitimate deliverable, not a cop-out.
  * **alpha blending** - smoke, dust and anything soft or dark *must* have real transparency, which
    means keying the background out: `--key luma` for a black backdrop, `--key chroma` for any flat
    colour. Keying is a measurement, not a given - a soft effect keys badly, and the tell is a
    dark halo, so look at the sheet on a mid-grey background (`--preview-bg`) before believing it.

  For effects, the video model is **not** a motion source to retarget - it *is* the renderer. There
  is no skeleton, no skin and no retargeting step, which is what makes this route cheap next to the
  character routes (`animation/README.md`).

USAGE

    # a clip (webp/gif via PIL, webm/mp4 via OpenCV) -> an 8-frame 128 px ping-pong sheet
    uv run python scripts/flipbook.py output/2D/e20/fire_c00_00002_.webp --frames 8 --cell 128 --out assets/2d/vfx/fire

    # keep only the event, key the black backdrop to alpha, and preview on grey
    uv run python scripts/flipbook.py clip.webm --frames 8 --window 0.05 0.55 --key luma --preview-bg "#808080" --out fire

Outputs `<out>.png` and `<out>_manifest.json` (frame indices, cells, fps, loop, alpha mode, blend hint).
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
PIL_ANIMATED = {".webp", ".gif"}


# --------------------------------------------------------------------------- reading

def read_frames(path: Path) -> tuple[list[Image.Image], float | None, str]:
    """-> (frames as RGB, source fps if known, how it was read). Animated GIF/WebP via PIL,
    everything else (webm/mp4/avi/mov) via OpenCV, or a still/sequence on disk."""
    if path.is_dir() or any(ch in str(path) for ch in "*?["):
        pattern = str(path) if path.is_dir() else str(path)
        files = sorted(glob.glob(pattern)) if not path.is_dir() else sorted(
            p for p in Path(path).iterdir() if p.suffix.lower() in IMAGE_EXT)
        if not files:
            raise SystemExit(f"no frames matched {path}")
        return [Image.open(f).convert("RGB") for f in files], None, f"{len(files)} files"

    ext = path.suffix.lower()
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    if ext in PIL_ANIMATED:
        im = Image.open(path)
        frames = [f.convert("RGB").copy() for f in ImageSequence.Iterator(im)]
        fps = None
        if ext == ".gif" and im.info.get("duration"):
            fps = round(1000.0 / im.info["duration"], 3)
        if not frames:
            raise SystemExit(f"{path} has no frames")
        return frames, fps, f"PIL {ext}"

    try:
        import cv2
    except ImportError:
        raise SystemExit(f"{ext} needs OpenCV (it is in pyproject) or convert the clip to an animated webp first")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"OpenCV could not open {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or None
    frames = []
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        frames.append(Image.fromarray(bgr[:, :, ::-1]))
    cap.release()
    if not frames:
        raise SystemExit(f"{path} decoded to 0 frames")
    return frames, (round(fps, 3) if fps else None), f"OpenCV {ext}"


# --------------------------------------------------------------------------- sampling

def sample_indices(total: int, n: int, window: tuple[float, float]) -> list[int]:
    """n indices spread evenly across the window, always including its first and last frame."""
    if total == 0:
        raise SystemExit("no frames to sample")
    n = max(1, min(n, total))
    a, b = window
    if not (0.0 <= a < b <= 1.0):
        raise SystemExit(f"--window must satisfy 0 <= START < END <= 1, got {window}")
    lo = int(round(a * (total - 1)))
    hi = int(round(b * (total - 1)))
    if hi <= lo:
        lo, hi = 0, total - 1
    if n == 1:
        return [(lo + hi) // 2]
    span = hi - lo
    return [lo + round(i * span / (n - 1)) for i in range(n)]


def order_frames(frames: list[Image.Image], loop: str) -> list[Image.Image]:
    if loop == "pingpong":
        # out and back, dropping the duplicated endpoints - seamless for any source
        return frames + frames[-2:0:-1]
    return frames


# --------------------------------------------------------------------------- alpha

def parse_hex(text: str) -> tuple[int, int, int]:
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise SystemExit(f"--key-color must be #rrggbb, got {text}")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def key_alpha(im: Image.Image, mode: str, color: tuple[int, int, int],
              threshold: float, softness: float) -> Image.Image:
    """Background -> alpha. luma: black (or any dark) backdrop; chroma: any flat colour.
    A linear ramp between threshold and threshold+softness, so the edge is not a hard stencil."""
    rgb = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    if mode == "luma":
        dist = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        ref = (color[0] * 0.2126 + color[1] * 0.7152 + color[2] * 0.0722) / 255.0
        d = np.abs(dist - ref)
    else:
        ref = np.array(color, dtype=np.float32) / 255.0
        d = np.sqrt(((rgb - ref) ** 2).sum(axis=2)) / math.sqrt(3.0)
    span = max(softness, 1e-6)
    alpha = np.clip((d - threshold) / span, 0.0, 1.0)
    out = im.convert("RGBA")
    out.putalpha(Image.fromarray((alpha * 255).astype(np.uint8), mode="L"))
    return out


def blend_hint(mode: str) -> str:
    return "additive" if mode == "none" else "alpha"


# --------------------------------------------------------------------------- main

def build_sheet(cells: list[Image.Image], columns: int, pad: int, bg: tuple[int, int, int],
                border: int) -> Image.Image:
    cw, ch = cells[0].size
    rows = math.ceil(len(cells) / columns)
    width = columns * cw + (columns + 1) * pad + max(0, columns - 1) * border
    height = rows * ch + (rows + 1) * pad + max(0, rows - 1) * border
    sheet = Image.new("RGBA", (width, height), bg + (0,))
    for i, cell in enumerate(cells):
        cx, cy = i % columns, i // columns
        x = pad + cx * (cw + pad + border)
        y = pad + cy * (ch + pad + border)
        sheet.alpha_composite(cell.convert("RGBA"), (x, y))
    return sheet


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="clip (webp/gif/webm/mp4), a still, a frame directory, or a glob")
    ap.add_argument("--out", required=True, help="output stem; writes <out>.png + <out>_manifest.json")
    ap.add_argument("--frames", type=int, default=8, help="source frames to sample (default 8)")
    ap.add_argument("--window", type=float, nargs=2, metavar=("START", "END"),
                    default=(0.0, 1.0), help="fraction of the clip to sample from (default the whole clip)")
    ap.add_argument("--fps", type=float, default=12.0, help="playback rate for the manifest (default 12)")
    ap.add_argument("--cell", help="cell size WxH (default: the source frame size)")
    ap.add_argument("--columns", type=int, help="grid columns (default: ceil(sqrt(cells)))")
    ap.add_argument("--loop", choices=("none", "pingpong", "cycle"), default="pingpong",
                    help="playback order (default pingpong: the only seamless one for any source)")
    ap.add_argument("--key", choices=("none", "luma", "chroma"), default="none",
                    help="background -> alpha (default none: additive blending needs no alpha)")
    ap.add_argument("--key-color", default="#000000", help="backdrop colour to key (default black)")
    ap.add_argument("--threshold", type=float, default=0.12, help="key threshold 0-1 (default 0.12)")
    ap.add_argument("--softness", type=float, default=0.10, help="key edge width 0-1 (default 0.10)")
    ap.add_argument("--pad", type=int, default=0, help="padding between cells, px (default 0)")
    ap.add_argument("--border", type=int, default=0, help="cell border width, px (default 0)")
    ap.add_argument("--bg", default="#00000000", help="sheet background (default transparent)")
    ap.add_argument("--preview-bg", help="also write <out>_preview.png composited on this colour "
                                         "(the honest test for a keyed matte)")
    a = ap.parse_args()

    src = Path(a.source)
    frames, src_fps, how = read_frames(src)
    idx = sample_indices(len(frames), a.frames, (a.window[0], a.window[1]))
    picked = [frames[i] for i in idx]
    picked = order_frames(picked, a.loop)
    if not picked:
        raise SystemExit("nothing sampled")

    if a.cell:
        sw, sh = picked[0].size
        w, sep, h = a.cell.lower().partition("x")
        # ONE dimension keeps the source aspect - squashing a landscape frame into a square cell
        # distorts the effect, which is the same trap as letterboxing a portrait into 16:9
        # (scripts/letterbox_16x9.py). Both dimensions given means the caller asked for it.
        if sep:
            size = (int(w), int(h))
        else:
            size = (int(w), max(1, round(int(w) * sh / sw)))
        picked = [f.resize(size, Image.LANCZOS) for f in picked]
    cw, ch = picked[0].size

    color = parse_hex(a.key_color) if a.key != "none" else (0, 0, 0)
    if a.key == "none":
        cells = [f.convert("RGBA") for f in picked]
    else:
        cells = [key_alpha(f, a.key, color, a.threshold, a.softness) for f in picked]

    columns = a.columns or max(1, math.ceil(math.sqrt(len(cells))))
    bg = parse_hex(a.bg) if a.bg.lower() not in ("#00000000", "transparent") else (0, 0, 0)
    sheet = build_sheet(cells, columns, a.pad, bg, a.border)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet_path = out.with_suffix(".png")
    sheet.save(sheet_path)

    manifest = {
        # name the clip, not the scratch path it was run from - a manifest that records
        # "output\\fetched\\..." dies with the machine that produced it
        "source": src.name,
        "source_frames": len(frames),
        "source_fps": src_fps,
        "read_via": how,
        "window": list(a.window),
        "sampled_indices": idx,
        "sampled_frames": len(idx),
        "loop": a.loop,
        "cells": len(cells),
        "cell_order": "row-major, left-to-right, top-to-bottom",
        "fps": a.fps,
        "duration_s": round(len(cells) / a.fps, 3),
        "cell_size": [cw, ch],
        "grid": [columns, math.ceil(len(cells) / columns)],
        "alpha": a.key != "none",
        "key": {"mode": a.key, "color": a.key_color, "threshold": a.threshold, "softness": a.softness}
        if a.key != "none" else None,
        "blend_hint": blend_hint(a.key),
        "sheet": sheet_path.name,
    }
    mpath = out.with_name(out.name + "_manifest.json")
    io.open(mpath, "w", encoding="utf-8", newline="\n").write(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")

    if a.preview_bg:
        pbg = parse_hex(a.preview_bg)
        flat = Image.new("RGBA", sheet.size, pbg + (255,))
        flat.alpha_composite(sheet)
        prev = out.with_name(out.name + "_preview.png")
        flat.convert("RGB").save(prev)
        manifest["preview"] = prev.name
        io.open(mpath, "w", encoding="utf-8", newline="\n").write(
            json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
        print(f"preview -> {prev}")

    print(f"{src} ({len(frames)} frames via {how}"
          + (f", {src_fps} fps" if src_fps else "") + ")")
    print(f"  sampled {idx} -> {len(cells)} cells ({a.loop}, {a.fps} fps, "
          f"{cw}x{ch}, grid {columns}x{math.ceil(len(cells) / columns)}, {blend_hint(a.key)})")
    print(f"  sheet -> {sheet_path}\n  manifest -> {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())