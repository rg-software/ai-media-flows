#!/usr/bin/env python3
"""Pack a Unity metallic-smoothness map from separate roughness and metallic maps.

Unity's Built-in/URP shaders read ONE packed map in `_MetallicGlossMap`:

    R = metallic, A = smoothness (= 1 - roughness)

glTF and most other engines pack the opposite way (roughness in G), which is why a roughness map dropped
straight into that slot inverts the surface: on our stone (roughness 0.629) a naive import would read 0.371
- smoother where it is roughest. This tool is the whole conversion, and it is the only map our ComfyUI PBR
flow does not already produce.

Everything else your material needs, you already have:
  * basecolor and normal come out of the flow correct as they are - no processing, no re-encode
  * an occlusion map can stay **grayscale**: `_OcclusionMap` samples G, and a grayscale image has R=G=B,
    so the value is already in the right channel

**Import settings are yours to set** (this tool does not emit `.meta` files), and getting them wrong is the
usual reason a correct map looks wrong:
  * data maps (normal, metallicSmoothness, occlusion) must import as **linear** (sRGB OFF) or the values shift
  * the normal map needs **Texture Type = Normal map**, not plain Texture
  * this map needs its **alpha KEPT**, and a compression that preserves alpha (DXT1/BC1 has none - the
    smoothness channel would collapse to a constant, i.e. uniformly glossy)
  * on the material, keep **Metallic at 1** when a metallic map is assigned, or the map is multiplied away

Usage:
    uv run python scripts/pack_pbr_material.py --roughness roughness.png --metallic metallic.png \
        --out metallicSmoothness.png
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Pack Unity's metallic-smoothness map (R=metallic, A=1-roughness) from two maps.")
    ap.add_argument("--roughness", required=True, help="roughness map (ANY engine's smoothness is 1 - this)")
    ap.add_argument("--metallic", required=True)
    ap.add_argument("--out", required=True, help="output PNG, e.g. metallicSmoothness.png")
    ap.add_argument("--size", type=int, default=None,
                    help="force this square size; by default the two inputs must already match "
                         "(they do when both come from the same ComfyUI run)")
    args = ap.parse_args()

    with Image.open(args.roughness) as im:
        r_size = im.size
    with Image.open(args.metallic) as im:
        m_size = im.size

    if r_size != m_size:
        if args.size is None:
            raise SystemExit(f"size mismatch: roughness {r_size[0]}x{r_size[1]} but metallic "
                             f"{m_size[0]}x{m_size[1]}. Both maps come from the same run so they should "
                             f"match - pass --size to force a size if you really mean it.")
        S = args.size
        note = f"  resampling both to {S}x{S} (--size)"
    else:
        S = args.size or r_size[0]
        note = None
    if S != r_size[0] or S != m_size[0]:
        note = f"  resampling inputs to {S}x{S}"
    if note:
        print(note)

    rough = Image.open(args.roughness).convert("L").resize((S, S), Image.Resampling.LANCZOS)
    metal = Image.open(args.metallic).convert("L").resize((S, S), Image.Resampling.LANCZOS)

    rough_f = np.asarray(rough, np.float32) / 255.0
    metal_f = np.asarray(metal, np.float32) / 255.0

    rgba = np.zeros((S, S, 4), np.uint8)
    rgba[..., 0] = np.round(metal_f * 255)                        # R = metallic
    rgba[..., 1] = 0                                             # G unused by Unity
    rgba[..., 2] = 0                                             # B unused by Unity
    rgba[..., 3] = np.round(np.clip(1.0 - rough_f, 0, 1) * 255)   # A = smoothness
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(args.out)

    print(f"packed @ {S}x{S} -> {args.out}")
    print(f"  R = metallic   mean {metal_f.mean():.3f}")
    print(f"  A = smoothness mean {1 - rough_f.mean():.3f}   (= 1 - roughness {rough_f.mean():.3f})")
    print("  G, B unused by Unity (written as 0)")
    if metal_f.mean() > 0.6:
        print("  !! WARNING: metallic is high - right for actual metal, WRONG for a dielectric")
        print("     (stone, wood, cloth). This is the failure the old QFX route produced: 0.855 on stone.")
    print("  rem: import as LINEAR (sRGB off), KEEP the alpha, and set the material's Metallic to 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
