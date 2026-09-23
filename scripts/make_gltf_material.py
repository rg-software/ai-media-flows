#!/usr/bin/env python3
"""Pack 2D-generated PBR maps for a target: glTF (engines) or Unity (shader slots).

This is TWO tasks behind one command, because they share the same inputs but produce different
maps. Pick the task with `--for`, and the outputs follow:

  --for gltf   (default)  the interchange format: Unity, Godot, Blender's glTF importer, three.js
      writes  basecolor.png  normal.png  metallicRoughness.png  [occlusion.png]  material.json
      layout  metallicRoughness: R unused(255), **G = roughness, B = metallic**
              occlusion: AO in **R** (grayscale is fine)
      plus    --mesh <glb> --glb-out <glb> applies it to a mesh (the GLB then carries a standard
              glTF material, so an engine's glTF importer needs nothing else)

  --for unity  Unity Built-in / URP, for assigning PNGs by hand in an Inspector
      writes  basecolor.png  normal.png  metallicSmoothness.png  [occlusion.png]  material.json
      layout  metallicSmoothness: **R = metallic, A = smoothness (= 1 - roughness)**
              occlusion: AO in **G** (the channel _OcclusionMap samples)
      note    Unity samples SMOOTHNESS where glTF packs ROUGHNESS, so a glTF roughness map used
              as _MetallicGlossMap inverts the surface: on our stone (roughness 0.629) an import
              would read 0.371 - smoother where it is roughest. Hence the conversion here.
              (HDRP differs again: it wants ONE Mask Map, R=metallic G=occlusion B=detail
              A=smoothness - not implemented; the numbers above are what you'd pack.)

Both tasks resample every map to one common size, so this is **not a copy**: default size is
`--basecolor`'s own (same-size inputs come back unchanged); `--size` forces one and reports what it
resampled, flagging an upscale (which adds no detail, only file size). PNG output is a fresh encode.

`material.json` is a MANIFEST - slot names, colourspaces, factors, per-channel statistics - for a
human or a future importer script. No engine reads it. The importable things are the PNGs and the GLB.

It also reports the numeric channel statistics of the packed map, because a plausibility check beats
trust: a dielectric (stone, wood) must come out with a LOW metallic channel. Our earlier QFX map
failed exactly this test (mean 0.855 - see 2d/EXPERIMENTS-2D.md E12b/U4), so this script warns.

Usage (anywhere - no ComfyUI needed; deps are numpy + Pillow, and trimesh only for --mesh, all in the
repo's uv env). The maps come from the box's ComfyUI output - fetch them first (see HOWTO S14):

    # glTF for an engine (and put it on a mesh)
    uv run python scripts/make_gltf_material.py --for gltf \
        --basecolor basecolor.png --roughness roughness.png --metallic metallic.png \
        --normal normal.png --occlusion ao.png \
        --outdir out/gltf --mesh model.glb --glb-out out/model_textured.glb

    # Unity, to assign by hand
    uv run python scripts/make_gltf_material.py --for unity \
        --basecolor basecolor.png --roughness roughness.png --metallic metallic.png \
        --normal normal.png --occlusion ao.png --outdir out/unity
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from PIL import Image

TASKS = ("gltf", "unity")


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


def pack_metallic_roughness(rough, metal, S):
    """glTF: one image, R unused, G = roughness, B = metallic."""
    pack = np.zeros((S, S, 3), np.uint8)
    pack[..., 0] = 255
    pack[..., 1] = np.asarray(rough)
    pack[..., 2] = np.asarray(metal)
    return Image.fromarray(pack, "RGB")


def pack_metallic_smoothness(rough, metal, S):
    """Unity Built-in/URP: one image, R = metallic, A = smoothness = 1 - roughness."""
    rough_f = np.asarray(rough, np.float32) / 255.0
    metal_f = np.asarray(metal, np.float32) / 255.0
    rgba = np.zeros((S, S, 4), np.uint8)
    rgba[..., 0] = np.round(metal_f * 255)                  # R = metallic
    rgba[..., 1] = 0                                        # G unused
    rgba[..., 2] = 0                                        # B unused
    rgba[..., 3] = np.round(np.clip(1.0 - rough_f, 0, 1) * 255)   # A = smoothness
    return Image.fromarray(rgba, "RGBA")


def occlusion_for(mode, ao, S):
    """Where AO goes depends on the consumer: glTF reads occlusion from R, Unity's _OcclusionMap
    samples G."""
    if mode == "gltf":
        return ao                                  # grayscale satisfies glTF (R = the value)
    a = np.zeros((S, S, 3), np.uint8)
    a[..., 0] = 255                                # R unused by Unity
    a[..., 1] = np.asarray(ao)                     # G = occlusion
    a[..., 2] = 255                                # B unused
    return Image.fromarray(a, "RGB")


def main():
    ap = argparse.ArgumentParser(
        description="Pack 2D-generated PBR maps for glTF (engines) or Unity (shader slots).",
        epilog="The two tasks share inputs but write different maps - see the module docstring.")
    ap.add_argument("--for", dest="mode", choices=TASKS, default=None,
                    help="which target to pack for: gltf (interchange; default) or unity "
                         "(Built-in/URP shader slots, for assigning by hand)")
    ap.add_argument("--unity", action="store_true",
                    help="alias for --for unity (kept so earlier commands still work)")
    ap.add_argument("--basecolor", required=True)
    ap.add_argument("--roughness", required=True, help="required by BOTH tasks (Unity's smoothness is 1-roughness)")
    ap.add_argument("--metallic", required=True, help="required by BOTH tasks (goes in the packed map)")
    ap.add_argument("--normal", required=True)
    ap.add_argument("--occlusion", default=None, help="optional AO; used by both tasks (in R for glTF, G for Unity)")
    ap.add_argument("--size", type=int, default=None,
                    help="force every map to this square size; default = --basecolor's own size "
                         "(so same-size inputs are not resampled). Upscaling adds no detail.")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--flip-normal-green", action="store_true",
                    help="convert DirectX (Y-down) normal maps to glTF's OpenGL (Y-up)")
    ap.add_argument("--mesh", default=None,
                    help="gltf task only: GLB whose material will be replaced")
    ap.add_argument("--glb-out", default=None, help="gltf task only: where to write the textured GLB")
    args = ap.parse_args()

    if args.unity:
        if args.mode is not None:
            raise SystemExit("--unity is an alias for --for unity; pass one or the other, not both")
        args.mode = "unity"
    elif args.mode is None:
        args.mode = "gltf"
    if args.mode == "unity" and (args.mesh or args.glb_out):
        raise SystemExit("--mesh/--glb-out write a GLB, whose material is glTF-convention. "
                         "Use --for gltf for the mesh, or drop the mesh and use --for unity for the PNGs.")

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

    # --- the one map that differs per task ---------------------------------------------
    if args.mode == "gltf":
        packed = pack_metallic_roughness(rough, metal, S)
        packed_name = "metallicRoughness.png"
        packed_layout = "R=255 (unused)  G=roughness  B=metallic"
    else:
        packed = pack_metallic_smoothness(rough, metal, S)
        packed_name = "metallicSmoothness.png"
        packed_layout = "R=metallic  A=smoothness (1-roughness)  [G,B unused]"

    base.save(f"{args.outdir}/basecolor.png")
    normal.save(f"{args.outdir}/normal.png")
    packed.save(f"{args.outdir}/{packed_name}")

    if args.occlusion:
        occlusion_for(args.mode, load_l(args.occlusion, S), S).save(f"{args.outdir}/occlusion.png")

    # --- plausibility report ---------------------------------------------------------
    r, m = np.asarray(rough, np.float32) / 255, np.asarray(metal, np.float32) / 255
    n = np.asarray(normal, np.float32)
    print(f"task: {args.mode}   material maps @ {S}x{S} -> {args.outdir}/")
    print(f"  roughness mean {r.mean():.3f}   metallic mean {m.mean():.3f}   frac(metal>0.5) {(m>0.5).mean():.3f}")
    print(f"  normal mean RGB {n.reshape(-1,3).mean(0).round(1)}  (flat/up-facing ~= [128 128 255])")
    print(f"  wrote {packed_name}: {packed_layout}")
    if args.mode == "unity":
        print(f"  Unity smoothness mean {(1 - r).mean():.3f} (R=metallic, A=smoothness; keep alpha on import)")
        print("  import the data maps as LINEAR (sRGB off) or the values shift")
    if args.occlusion:
        print(f"  occlusion.png: AO in {'R (glTF occlusionTexture)' if args.mode == 'gltf' else 'G (_OcclusionMap)'}")
    if m.mean() > 0.6:
        print("  !! WARNING: metallic channel is high - fine for actual metal, WRONG for a dielectric.")
        print("     This is the exact failure the QFX generator produced (0.855 on stone).")

    # --- manifest (for humans / a future importer; no engine reads it) -----------------
    meta = {
        "generator": "scripts/make_gltf_material.py",
        "target": args.mode,
        "size": S,
        "maps": {
            "basecolor.png": {"slot": "baseColorTexture / Base Map", "colorspace": "sRGB"},
            "normal.png": {"slot": "normalTexture / Normal Map", "colorspace": "linear",
                           "convention": "OpenGL (+Y up)", "green_flipped": bool(args.flip_normal_green)},
            packed_name: {
                "slot": "metallicRoughnessTexture" if args.mode == "gltf" else "_MetallicGlossMap",
                "colorspace": "linear",
                "channels": ({"R": "unused(255)", "G": "roughness", "B": "metallic"} if args.mode == "gltf"
                             else {"R": "metallic", "G": "unused", "B": "unused",
                                   "A": "smoothness (1 - roughness)"}),
            },
        },
        "stats": {"roughness_mean": round(float(r.mean()), 4), "metallic_mean": round(float(m.mean()), 4),
                  "metallic_frac_gt_0.5": round(float((m > 0.5).mean()), 4),
                  "normal_mean_rgb": [round(float(x), 1) for x in n.reshape(-1, 3).mean(0)]},
        "note": "This file is a manifest, not an engine asset - no engine reads it.",
    }
    if args.mode == "gltf":
        meta["workflow"] = "glTF 2.0 metallic-roughness"
        meta["factors"] = {"metallicFactor": 1.0, "roughnessFactor": 1.0, "baseColorFactor": [1, 1, 1, 1]}
        meta["note"] += (" metallicFactor/roughnessFactor MUST stay 1.0 with a packed texture, "
                         "or the texture is multiplied.")
    else:
        meta["workflow"] = "Unity Built-in/URP metallic-smoothness (hand-assigned)"
        meta["note"] += (" Unity samples smoothness, not roughness; alpha must be kept on import. "
                         "HDRP wants one Mask Map (R=metallic G=occlusion B=detail A=smoothness) - "
                         "not emitted.")
    if args.occlusion:
        meta["maps"]["occlusion.png"] = {
            "slot": "occlusionTexture" if args.mode == "gltf" else "_OcclusionMap",
            "colorspace": "linear",
            "channels": {"R": "AO"} if args.mode == "gltf" else {"G": "AO"},
        }
    else:
        meta["note"] += " No occlusion map: Marigold IID does not emit AO directly."
    with open(f"{args.outdir}/material.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"  metadata -> {args.outdir}/material.json")

    # --- gltf only: apply to a mesh and export -----------------------------------------
    if args.mesh and args.glb_out:
        import trimesh
        from trimesh.visual.material import PBRMaterial

        scene = trimesh.load(args.mesh, force="scene")
        mat = PBRMaterial(
            baseColorTexture=Image.open(f"{args.outdir}/basecolor.png"),
            metallicRoughnessTexture=Image.open(f"{args.outdir}/{packed_name}"),
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
