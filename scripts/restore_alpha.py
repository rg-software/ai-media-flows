#!/usr/bin/env python3
"""Restore a rendered sprite's alpha after palette conversion.

`pixel-art-convert.json` returns RGB and drops the source alpha. For a rendered
3D pose/facing, use the original transparent render as `--source`; its alpha is
resized with NEAREST to the converted sprite's dimensions and attached to the
sprite. This keeps the quantised RGB while restoring the silhouette transparency.

Example:
    uv run python scripts/restore_alpha.py --source render.png --sprite palette.png --out sprite.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def restore_alpha(source: Path, sprite: Path, output: Path) -> None:
    with Image.open(source) as src, Image.open(sprite) as spr:
        if "A" not in src.getbands():
            raise SystemExit(f"source has no alpha channel: {source}")
        rgba = spr.convert("RGBA")
        alpha = src.getchannel("A").resize(rgba.size, Image.Resampling.NEAREST)
        rgba.putalpha(alpha)
        output.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(output)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path, help="original RGBA render whose silhouette to restore")
    ap.add_argument("--sprite", required=True, type=Path, help="RGB palette-converted sprite")
    ap.add_argument("--out", required=True, type=Path, help="RGBA sprite output")
    a = ap.parse_args()
    restore_alpha(a.source, a.sprite, a.out)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
