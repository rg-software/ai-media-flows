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

NOTE: this is not a copy operation. Every map is **resampled to one common size** (the
docstring rule above - mismatched sizes make UVs disagree), and PNG output is a fresh
encode. By default the size is taken from `--basecolor`, so same-size inputs are written
back at their own size; pass `--size` to force one, and the report says what was resampled
and whether that upscaled (which adds no detail, only file size).

Usage (anywhere - this needs no ComfyUI; deps are numpy + Pillow, and trimesh only for --mesh,
all in the repo's uv env):
    uv run python scripts/make_gltf_material.py \
        --basecolor tex_stone_albedo.png \
        --roughness tex_stone_roughness.png \
        --metallic  tex_stone_metallic.png \
        --normal    tex_stone_normal.png \
        --occlusion tex_stone_ao.png \
        --outdir  out/stone_material \
        --unity

Writes (glTF 2.0, read by Unity, Godot, Blender's glTF importer, three.js):
    basecolor.png, normal.png, metallicRoughness.png, occlusion.png (if given)
    material.json  - a MANIFEST for a human or a future importer script: slot names,
                     colourspaces, factors, per-channel statistics. It is NOT an engine
                     asset and no engine reads it. The importable things are the PNGs and
                     the exported GLB.
Add --unity to ALSO write the maps Unity's own shaders want when you assign textures by
    hand in an Inspector (this does not change the GLB):
    metallicSmoothness.png (R=metallic, A=smoothness = 1 - roughness), roughness.png,
    occlusion.png (AO in G, which is the channel Unity's _OcclusionMap samples)
Add --mesh <glb> --glb-out <glb> to apply the material to a mesh and export (needs UVs).
    The GLB carries a standard glTF material, so an engine's glTF importer reads it with
    nothing extra - including occlusionTexture when --occlusion is supplied.
The maps themselves come from the box's ComfyUI output - fetch them first (see HOWTO S14).
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from PIL import Image


def probe_size(path):
    """Native size of an input map, so we resample only when it is actually needed."""
    with Image.open(path) as im:
        return im.size


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
    ap.add_argument("--occlusion", default=None, help="optional AO map (glTF occlusionTexture, AO in R)")
    ap.add_argument("--size", type=int, default=None,
                    help="force every map to this square size; default = --basecolor's own size "
                         "(so same-size inputs are not resampled). Upscaling adds no detail.")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--flip-normal-green", action="store_true",
                    help="convert DirectX (Y-down) normal maps to glTF's OpenGL (Y-up)")
    ap.add_argument("--unity", action="store_true",
                    help="also emit Unity's packed metallic-smoothness map (R=metallic, A=1-roughness); "
                         "the glTF metallicRoughness map is still written, so one run feeds both")
    ap.add_argument("--mesh", default=None, help="optional GLB whose material will be replaced")
    ap.add_argument("--glb-out", default=None)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # --- size: default to the basecolor's own, resample only when a map differs or --size is given ------
    inputs = [("basecolor", args.basecolor), ("roughness", args.roughness),
              ("metallic", args.metallic), ("normal", args.normal)]
    if args.occlusion:
        inputs.append(("occlusion", args.occlusion))
    native = {name: probe_size(path) for name, path in inputs}

    if args.size:
        S = args.size
        if native["basecolor"] != (S, S):
            up = S > native["basecolor"][0]
            print(f"  --size {S}: resampling {native['basecolor'][0]}x{native['basecolor'][1]} -> {S}x{S}"
                  f"{'  (UPSCALE - adds no detail, only file size)' if up else ''}")
    else:
        w, h = native["basecolor"]
        if w != h:
            raise SystemExit(f"--basecolor is {w}x{h}, not square; pass --size to pick a square target")
        S = w
    for name, size in native.items():
        if size != (S, S):
            print(f"  {name}: {size[0]}x{size[1]} -> {S}x{S} (resampled to match the other maps)")

    base = load_rgb(args.basecolor, S)
    rough = load_l(args.roughness, S)
    metal = load_l(args.metallic, S)
    normal = load_rgb(args.normal, S)

    if args.flip_normal_green:
        a = np.asarray(normal).copy()
        a[..., 1] = 255 - a[..., 1]
        normal = Image.fromarray(a)

    if args.unity:
        # Unity's metallic-smoothness maps put SMOOTHNESS in alpha, and smoothness = 1 - roughness.
        # Shipping our roughness straight into a smoothness slot inverts the surface response: on our
        # stone (roughness mean 0.629) an import would read as 0.371 - smoother where it is roughest.
        # Layout Unity's Standard/URP shaders sample with _MetallicGlossMap: R = metallic, A = smoothness.
        rough_f = np.asarray(rough, np.float32) / 255.0
        smooth = np.clip(1.0 - rough_f, 0.0, 1.0)
        metal_f = np.asarray(metal, np.float32) / 255.0
        rgba = np.zeros((S, S, 4), np.uint8)
        rgba[..., 0] = np.round(metal_f * 255)          # R = metallic
        rgba[..., 1] = 0                                # G = unused by Unity
        rgba[..., 2] = 0                                # B = unused by Unity
        rgba[..., 3] = np.round(smooth * 255)           # A = smoothness (1 - roughness)
        ms = Image.fromarray(rgba, "RGBA")
        ms.save(f"{args.outdir}/metallicSmoothness.png")
        # also emit the inverse map, so a shader that wants roughness in G can use it
        rough_out = Image.fromarray(np.round(rough_f * 255).astype(np.uint8), "L")
        rough_out.save(f"{args.outdir}/roughness.png")

    # --- pack metallicRoughness: R unused(=255), G=roughness, B=metallic -------------
    # (glTF 2.0 convention; still emitted in --unity mode so both engines can be fed from one run)
    pack = np.zeros((S, S, 3), np.uint8)
    pack[..., 0] = 255
    pack[..., 1] = np.asarray(rough)
    pack[..., 2] = np.asarray(metal)
    mr = Image.fromarray(pack, "RGB")

    base.save(f"{args.outdir}/basecolor.png")
    normal.save(f"{args.outdir}/normal.png")
    mr.save(f"{args.outdir}/metallicRoughness.png")

    # --- occlusion: one write, placed for the consumer ---------------------------------
    # glTF reads occlusion from the R channel of occlusionTexture; Unity's _OcclusionMap samples G.
    # A grayscale map satisfies glTF (R = the value); the Unity variant needs it in G explicitly.
    if args.occlusion:
        ao = load_l(args.occlusion, S)
        if args.unity:
            a = np.zeros((S, S, 3), np.uint8)
            a[..., 0] = 255                     # R unused by Unity
            a[..., 1] = np.asarray(ao)          # G = occlusion (what _OcclusionMap samples)
            a[..., 2] = 255                     # B unused
            Image.fromarray(a, "RGB").save(f"{args.outdir}/occlusion.png")
        else:
            ao.save(f"{args.outdir}/occlusion.png")

    # --- plausibility report ---------------------------------------------------------
    r, m = np.asarray(rough, np.float32) / 255, np.asarray(metal, np.float32) / 255
    n = np.asarray(normal, np.float32)
    print(f"material maps @ {S}x{S} -> {args.outdir}/")
    print(f"  roughness mean {r.mean():.3f}   metallic mean {m.mean():.3f}   frac(metal>0.5) {(m>0.5).mean():.3f}")
    print(f"  normal mean RGB {n.reshape(-1,3).mean(0).round(1)}  (flat/up-facing ~= [128 128 255])")
    print("  packed metallicRoughness: R=255 (unused)  G=roughness  B=metallic")
    if args.unity:
        print(f"  Unity metallicSmoothness: R=metallic  A=smoothness (1-roughness, mean {1-r.mean():.3f})")
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
    if args.unity:
        meta["unity"] = {
            "maps": {
                "metallicSmoothness.png": {"slot": "_MetallicGlossMap", "colorspace": "linear",
                                           "channels": {"R": "metallic", "G": "unused", "B": "unused",
                                                        "A": "smoothness (1 - roughness)"}},
                "roughness.png": {"note": "roughness in the green channel for a shader that wants it"},
            },
            "note": "Unity samples smoothness, not roughness: using a glTF roughness map as _MetallicGlossMap "
                    "inverts the surface response. Alpha must be imported (no alpha cropping).",
        }
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
            occlusionTexture=(Image.open(f"{args.outdir}/occlusion.png").convert("L")
                              if args.occlusion else None),
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
                  f"occlusion={'yes' if getattr(m2,'occlusionTexture',None) is not None else 'no'} "
                  f"factors={getattr(m2,'metallicFactor',None)}/{getattr(m2,'roughnessFactor',None)}")


if __name__ == "__main__":
    main()
