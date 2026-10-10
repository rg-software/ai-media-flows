"""Letterbox a portrait image into a 16:9 canvas, so a landscape video flow does not crop it.

Usage:  uv run python scripts/letterbox_16x9.py <in.png> [--out <out.png>] [--ratio 16:9] [--bg "#727274"]

Why this exists (E19/E18, 2026-10-10): Wan camera/motion flows take the start image straight
into a fixed canvas, so a **portrait** still in an 832x480 frame is cropped - measured, our
own `char_heroine.png` lost her head entirely. Padding to the target aspect first keeps the
whole subject. The pad colour matches the grey studio backdrop our reference assets sit on, so
the letterbox reads as background rather than as an edit.

Not a resize: the image is scaled to *fit* and centred, never cropped or stretched.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image


def parse_ratio(text: str) -> float:
    a, _, b = text.partition(":")
    return float(a) / float(b)


def letterbox(src: Path, dst: Path, ratio: float, bg: str, width: int | None = None) -> tuple[int, int]:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    target_w = width or w
    target_h = int(round(target_w / ratio))
    scale = min(target_w / w, target_h / h)
    new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(im.resize((new_w, new_h), Image.LANCZOS), ((target_w - new_w) // 2, (target_h - new_h) // 2))
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)
    return canvas.size


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", help="the portrait image to pad")
    ap.add_argument("--out", help="output path (default: <name>_16x9.png beside the input)")
    ap.add_argument("--ratio", default="16:9", help="target aspect (default 16:9)")
    ap.add_argument("--bg", default="#727274", help="pad colour (default matches our studio-grey backdrop)")
    ap.add_argument("--width", type=int, help="target width in px (default: the source's width)")
    a = ap.parse_args()
    src = Path(a.image)
    if not src.is_file():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    dst = Path(a.out) if a.out else src.with_name(src.stem + "_16x9.png")
    size = letterbox(src, dst, parse_ratio(a.ratio), a.bg, a.width)
    print(f"{src} ({Image.open(src).size}) -> {dst} {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
