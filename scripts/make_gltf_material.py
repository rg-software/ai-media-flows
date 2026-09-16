#!/usr/bin/env python3
"""U7 - 2D -> 3D bridge: turn 2D-generated maps into a glTF-valid PBR material and
optionally apply it to a mesh.

Why this is more than a file copy: glTF's metallic-roughness workflow is *packed and
conventional*, and getting it wrong produces a material that looks broken in every
engine. The rules this script enforces:

  * metallicRoughness texture is ONE image with  **G = roughness, B = metallic**
    (R unused). Engines read the channels, not separate files.
  * `baseColorTexture` is **sRGB**; normal / metallicRoughness / occlusion are **linear**.
  * `metallicFactor` and `roughnessFactor` must be **1.0** when the packed texture is
    supplied - any other value *multiplies* the texture and silently darkens it.
  * normal maps use the **OpenGL (+Y up)** convention in glTF. Use --flip-normal-green
    to convert a DirectX-convention map.
  * all maps should share one resolution, or the UVs will not line up.

It also reports the numeric channel statistics of the packed texture, because a
plausibility check beats trust: a dielectric (stone, wood) must come out with a LOW
metallic channel. Our earlier QFX map failed exactly this test (mean 0.855 - see
2d/EXPERIMENTS-2D.md E12b/U4), so this script prints the values and warns.

Usage (on the ComfyUI box):
    venv/bin/python scripts/make_gltf_material.py \
        --basecolor input/2d/tex_stone_marigold_albedo.png \
        --roughness input/2d/tex_stone_marigold_roughness.png \
        --metallic  input/2d/tex_stone_marigold_metallic.png \
        --normal    output/2D/U7/tex_stone_normal_00001_.png \
        --size 1024 \
        --outdir  output/2D/U7/stone_material

Writes: basecolor.png, normal.png, metallicRoughness.png, material.json
Add --mesh <glb> --glb-out <glb> to apply the material to a mesh and export.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from PIL import Image


def load_l(path, size):
    im = Image.open(path)
    if im.mode != "L":
        im = im.convert("L")
    return im.resize((size, size), Image.Resampling.LANCZOS)


def load_rgb(path, size):
    im = Image.open(path).convert("RGB")
    return im.resize((size, size), Image.Resampling.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--basecolor", required=True)
    ap.add_argument("--roughness", required=True)
    ap.add_argument("--metallic", required=True)
    ap.add_argument("--normal", required=True)
    ap.add_argument("--occlusion", default=None, help="optional; often unavailable from IID")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--flip-normal-green", action="store_true",
                    help="convert DirectX (Y-down) normal maps to glTF's OpenGL (Y-up)")
    ap.add_argument("--mesh", default=None, help="optional GLB whose material will be replaced")
    ap.add_argument("--glb-out", default=None)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    S = args.size

    base = load_rgb(args.basecolor, S)
    rough = load_l(args.roughness, S)
    metal = load_l(args.metallic, S)
    normal = load_rgb(args.normal, S)

    if args.flip_normal_green:
        a = np.asarray(normal).copy()
        a[..., 1] = 255 - a[..., 1]
        normal = Image.fromarray(a)

    # --- pack metallicRoughness: R unused(=255), G=roughness, B=metallic -------------
    pack = np.zeros((S, S, 3), np.uint8)
    pack[..., 0] = 255
    pack[..., 1] = np.asarray(rough)
    pack[..., 2] = np.asarray(metal)
    mr = Image.fromarray(pack, "RGB")

    base.save(f"{args.outdir}/basecolor.png")
    normal.save(f"{args.outdir}/normal.png")
    mr.save(f"{args.outdir}/metallicRoughness.png")
    if args.occlusion:
        load_l(args.occlusion, S).save(f"{args.outdir}/occlusion.png")

    # --- plausibility report ---------------------------------------------------------
    r, m = np.asarray(rough, np.float32) / 255, np.asarray(metal, np.float32) / 255
    n = np.asarray(normal, np.float32)
    print(f"material maps @ {S}x{S} -> {args.outdir}/")
    print(f"  roughness mean {r.mean():.3f}   metallic mean {m.mean():.3f}   frac(metal>0.5) {(m>0.5).mean():.3f}")
    print(f"  normal mean RGB {n.reshape(-1,3).mean(0).round(1)}  (flat/up-facing ~= [128 128 255])")
    print("  packed metallicRoughness: R=255 (unused)  G=roughness  B=metallic")
    if m.mean() > 0.6:
        print("  !! WARNING: metallic channel is high - fine for actual metal, WRONG for a dielectric.")
        print("     This is the exact failure the QFX generator produced (0.855 on stone).")

    meta = {
        "generator": "scripts/make_gltf_material.py",
        "workflow": "glTF 2.0 metallic-roughness",
        "size": S,
        "maps": {
            "basecolor.png": {"slot": "baseColorTexture", "colorspace": "sRGB"},
            "metallicRoughness.png": {"slot": "metallicRoughnessTexture", "colorspace": "linear",
                                      "channels": {"R": "unused(255)", "G": "roughness", "B": "metallic"}},
            "normal.png": {"slot": "normalTexture", "colorspace": "linear",
                           "convention": "OpenGL (+Y up)", "green_flipped": bool(args.flip_normal_green)},
        },
        "factors": {"metallicFactor": 1.0, "roughnessFactor": 1.0, "baseColorFactor": [1, 1, 1, 1]},
        "stats": {"roughness_mean": round(float(r.mean()), 4), "metallic_mean": round(float(m.mean()), 4),
                  "metallic_frac_gt_0.5": round(float((m > 0.5).mean()), 4),
                  "normal_mean_rgb": [round(float(x), 1) for x in n.reshape(-1, 3).mean(0)]},
        "note": "metallicFactor/roughnessFactor MUST stay 1.0 with a packed texture, or the texture is multiplied.",
    }
    if args.occlusion:
        meta["maps"]["occlusion.png"] = {"slot": "occlusionTexture", "colorspace": "linear", "channels": {"R": "AO"}}
    else:
        meta["note"] += " No occlusion map: Marigold IID does not emit AO directly."
    with open(f"{args.outdir}/material.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"  metadata -> {args.outdir}/material.json")

    # --- optional: apply to a mesh and export a GLB ----------------------------------
    if args.mesh and args.glb_out:
        import trimesh
        from trimesh.visual.material import PBRMaterial

        scene = trimesh.load(args.mesh, force="scene")
        mat = PBRMaterial(
            baseColorTexture=Image.open(f"{args.outdir}/basecolor.png"),
            metallicRoughnessTexture=Image.open(f"{args.outdir}/metallicRoughness.png"),
            normalTexture=Image.open(f"{args.outdir}/normal.png"),
            baseColorFactor=[255, 255, 255, 255],
            metallicFactor=1.0,
            roughnessFactor=1.0,
        )
        for name, geom in scene.geometry.items():
            if getattr(geom.visual, "uv", None) is None:
                print(f"  ! geometry '{name}' has NO UVs - material would be invisible; skipping")
                continue
            geom.visual.material = mat
        scene.export(args.glb_out)
        print(f"  glb -> {args.glb_out}")

        # verify by reloading
        chk = trimesh.load(args.glb_out, force="scene")
        for name, geom in chk.geometry.items():
            m2 = getattr(geom.visual, "material", None)
            uv = getattr(geom.visual, "uv", None)
            print(f"  verify '{name}': UV={'yes' if uv is not None else 'no'} "
                  f"baseColor={'yes' if getattr(m2,'baseColorTexture',None) is not None else 'no'} "
                  f"metalRough={'yes' if getattr(m2,'metallicRoughnessTexture',None) is not None else 'no'} "
                  f"normal={'yes' if getattr(m2,'normalTexture',None) is not None else 'no'} "
                  f"factors={getattr(m2,'metallicFactor',None)}/{getattr(m2,'roughnessFactor',None)}")


if __name__ == "__main__":
    main()
