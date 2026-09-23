#!/usr/bin/env python3
"""Pack a glTF metallic-roughness map, and optionally apply the whole material to a mesh.

For glTF (Unity, Godot, Blender's glTF importer, three.js). glTF reads one packed map:

    R = unused, G = roughness, B = metallic

and that map is required by the format, not a convenience: glTF 2.0 has NO separate roughness or metallic
texture - `pbrMetallicRoughness.metallicRoughnessTexture` is a single image, with metallic sampled from B
and roughness from G. The only alternative is the scalar `metallicFactor`/`roughnessFactor`, which is
uniform and gives up per-pixel variation. Note that when the packed map IS supplied, those two factors must
stay **1.0** - any other value multiplies the texture and silently darkens the material (the GLB written
here sets them 1.0). (Occlusion is separate: glTF has its own `occlusionTexture` slot,
read from R, which is why a grayscale AO is already correct here.)

What you get:
  * with `--mesh`/`--glb-out`: the packed map PLUS a **self-contained GLB** - the textures are embedded, so
    one file carries mesh + material and an engine imports it already wired. `--out` is optional here.
  * without a mesh: just the packed map, for assembling the material yourself in Blender / Godot / a viewer,
    or adding it to a GLB built elsewhere.

Two tasks, two tools: this one is the glTF/GLB route. For Unity's shader slots (assigned by hand) use
`scripts/pack_pbr_material.py`, which packs R=metallic / A=smoothness instead - Unity samples smoothness
where glTF samples roughness, so the two are not interchangeable.

Import settings are yours to set (no `.meta` is emitted): data maps as **linear** (sRGB off), the normal map
as **Texture Type = Normal map**. Importing a GLB usually handles this for you, since the material carries
its own definition - which is why the GLB route is the more robust one for Unity.

Usage (anywhere - no ComfyUI needed; deps numpy + Pillow, trimesh only for --mesh, all in the repo's uv env):
    uv run python scripts/make_gltf_material.py \
        --basecolor basecolor.png --normal normal.png \
        --roughness roughness.png --metallic metallic.png --occlusion ao.png \
        --out out/metallicRoughness.png \
        --mesh model.glb --glb-out out/model_textured.glb
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image


def probe_size(path):
    with Image.open(path) as im:
        return im.size


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Pack a glTF metallic-roughness map (G=roughness, B=metallic) and optionally "
                    "apply the material to a GLB.")
    ap.add_argument("--basecolor", required=True, help="used as-is; attached to the GLB if --mesh is given")
    ap.add_argument("--normal", required=True, help="used as-is (OpenGL +Y up, which is what glTF wants)")
    ap.add_argument("--roughness", required=True)
    ap.add_argument("--metallic", required=True)
    ap.add_argument("--occlusion", default=None, help="optional; glTF reads occlusion from R, so a "
                                                      "grayscale map is already correct")
    ap.add_argument("--out", default=None,
                    help="output PNG for the packed map. Optional when --glb-out is given (defaults to "
                         "metallicRoughness.png next to the GLB); required when there is no mesh, since "
                         "the map is then the only output")
    ap.add_argument("--size", type=int, default=None,
                    help="force this square size; by default all inputs must already match (they do when "
                         "they come from the same ComfyUI run)")
    ap.add_argument("--flip-normal-green", action="store_true",
                    help="convert a DirectX (Y-down) normal map to glTF's OpenGL (Y-up) - only used when "
                         "attaching to a GLB")
    ap.add_argument("--mesh", default=None, help="optional GLB whose material will be replaced")
    ap.add_argument("--glb-out", default=None, help="where to write the textured GLB (needs --mesh)")
    args = ap.parse_args()

    if args.out is None:
        if not args.glb_out:
            raise SystemExit("--out is required when there is no --mesh/--glb-out: the packed map would be "
                             "the only output. Pass --out metallicRoughness.png, or add a mesh.")
        args.out = os.path.join(os.path.dirname(os.path.abspath(args.glb_out)), "metallicRoughness.png")

    inputs = [("basecolor", args.basecolor), ("normal", args.normal),
              ("roughness", args.roughness), ("metallic", args.metallic)]
    if args.occlusion:
        inputs.append(("occlusion", args.occlusion))
    sizes = {name: probe_size(path) for name, path in inputs}

    distinct = set(sizes.values())
    if len(distinct) > 1 and args.size is None:
        detail = ", ".join(f"{n} {s[0]}x{s[1]}" for n, s in sizes.items())
        raise SystemExit(f"input sizes differ ({detail}). They come from the same run, so they should "
                         f"match - check you are passing the maps from ONE run, or pass --size to force one.")
    S = args.size or sizes["basecolor"][0]
    for name, s in sizes.items():
        if s != (S, S):
            print(f"  {name}: {s[0]}x{s[1]} -> {S}x{S} (resampled; --size given)")

    rough = Image.open(args.roughness).convert("L").resize((S, S), Image.Resampling.LANCZOS)
    metal = Image.open(args.metallic).convert("L").resize((S, S), Image.Resampling.LANCZOS)
    rough_f = np.asarray(rough, np.float32) / 255.0
    metal_f = np.asarray(metal, np.float32) / 255.0

    pack = np.zeros((S, S, 3), np.uint8)
    pack[..., 0] = 255                       # R unused
    pack[..., 1] = np.asarray(rough)         # G = roughness
    pack[..., 2] = np.asarray(metal)         # B = metallic
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(pack, "RGB").save(args.out)

    print(f"packed @ {S}x{S} -> {args.out}")
    print(f"  G = roughness mean {rough_f.mean():.3f}    B = metallic mean {metal_f.mean():.3f}"
          f"    frac(metal>0.5) {(metal_f > 0.5).mean():.3f}")
    print("  R unused (255)")
    if metal_f.mean() > 0.6:
        print("  !! WARNING: metallic is high - right for actual metal, WRONG for a dielectric")
        print("     (stone, wood, cloth). This is the failure the old QFX route produced: 0.855 on stone.")

    if args.mesh or args.glb_out:
        if not (args.mesh and args.glb_out):
            raise SystemExit("--mesh and --glb-out go together")
        import trimesh
        from trimesh.visual.material import PBRMaterial

        normal_img = Image.open(args.normal).convert("RGB")
        if args.flip_normal_green:
            a = np.asarray(normal_img).copy()
            a[..., 1] = 255 - a[..., 1]
            normal_img = Image.fromarray(a)
        scene = trimesh.load(args.mesh, force="scene")
        mat = PBRMaterial(
            baseColorTexture=Image.open(args.basecolor),
            metallicRoughnessTexture=Image.open(args.out),
            normalTexture=normal_img,
            occlusionTexture=(Image.open(args.occlusion).convert("L") if args.occlusion else None),
            baseColorFactor=[255, 255, 255, 255],
            metallicFactor=1.0,
            roughnessFactor=1.0,
        )
        for name, geom in scene.geometry.items():
            if getattr(geom.visual, "uv", None) is None:
                print(f"  ! geometry '{name}' has NO UVs - the material would be invisible; skipping")
                continue
            geom.visual.material = mat
        scene.export(args.glb_out)
        print(f"  glb -> {args.glb_out}")

        chk = trimesh.load(args.glb_out, force="scene")
        for name, geom in chk.geometry.items():
            m2 = getattr(geom.visual, "material", None)
            print(f"  verify '{name}': UV={'yes' if getattr(geom.visual, 'uv', None) is not None else 'no'} "
                  f"baseColor={'yes' if getattr(m2, 'baseColorTexture', None) is not None else 'no'} "
                  f"metalRough={'yes' if getattr(m2, 'metallicRoughnessTexture', None) is not None else 'no'} "
                  f"normal={'yes' if getattr(m2, 'normalTexture', None) is not None else 'no'} "
                  f"occlusion={'yes' if getattr(m2, 'occlusionTexture', None) is not None else 'no'} "
                  f"factors={getattr(m2, 'metallicFactor', None)}/{getattr(m2, 'roughnessFactor', None)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
