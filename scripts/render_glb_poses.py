#!/usr/bin/env python3
"""Render a rigged GLB's animation clips as a pose/facing sheet of PNGs, headless with bpy.

Why this exists: a *facing* set (E24) and a *posed* facing set (E24d/E24e) are sprite
inputs, and the way to get them from a rigged model is to pose it and orbit a camera. This
does that in one pass, and carries the four things that actually went wrong the first time:

  1. **One fixed camera for the whole sheet.** The distance is sized on the union bounding
     box of the FIRST clip's frames, so no frame changes scale. A facing/pose set must not
     change size between frames; a *prone* pose cannot be framed by a fixed camera at all,
     which is why standing stances are the default set.
  2. **The gear knob.** KayKit-style GLBs carry every weapon as a rigid, bone-parented mesh
     (`1H_Sword` -> `handslot.r`), so *all* of them render at once. `--gear` names the ones
     to keep; everything else matching Sword/Shield is hidden. (Extra gear is easier to
     delete than to add, which is why the knob hides by default.)
  3. **A flat light rig.** `--ambient`/`--sun` default to mostly-ambient because the
     downscale-to-palette step quantises *shading*: harder lighting puts more distinct
     shades in play, which shows up as colour patches (and, frame to frame, as flicker).
  4. **Multi-frame clips.** `--clip Name:0.15,0.4,0.65,0.9` renders several frames of one
     animation, which is what a sprite animation needs (E24e proved the mechanism and named
     palette flicker as the remaining defect).

Output: `output/3d/<...>/<clip>_f<i>_yaw<deg>.png`, transparent RGBA at `--res`.

Not box-bound: this is plain `bpy` with no ComfyUI in it, so it runs anywhere with a bpy env -
the box (`~/bpyenv`, already built) or a local one (`bpy==4.2.0` ships Linux and Windows wheels;
~1.6 GB installed). Only the *next* step is ComfyUI, so if you render away from the box, upload the
PNGs to its `input/` before pixelating them.
Env:  python3.11 -m venv ~/bpyenv && ~/bpyenv/bin/pip install bpy==4.2.0
Run:  ~/bpyenv/bin/python scripts/render_glb_poses.py --glb input/Knight.glb \
          --out output/3d/poses --clip Idle_Rig:0.5 --clip 1H_Melee_Attack_Chop_Rig:0.15,0.35,0.55,0.75
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import bpy
import mathutils


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Render a rigged GLB's clips as pose x facing PNGs.")
    ap.add_argument("--glb", required=True, help="path to the .glb, as the machine running this script sees it")
    ap.add_argument("--out", required=True, help="output directory (on the box, point it into ComfyUI's input/ so the pixelation step can read it)")
    ap.add_argument("--clip", action="append", required=True,
                    help="ActionName:frac[,frac...] - one stance is ActionName:0.5; repeatable")
    ap.add_argument("--yaws", default="0,45,90,135,180", help="comma-separated camera yaws in degrees")
    ap.add_argument("--gear", default="", help="comma-separated weapon objects to KEEP visible (default: none)")
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--ambient", type=float, default=0.7, help="world/ambient strength (flat rig)")
    ap.add_argument("--sun", type=float, default=1.5, help="sun strength")
    ap.add_argument("--margin", type=float, default=1.15, help="framing margin multiplier")
    return ap.parse_args()


def main() -> int:
    a = parse_args()
    clips = []
    for spec in a.clip:
        name, _, fracs = spec.partition(":")
        clips.append((name, [float(x) for x in (fracs or "0.5").split(",")]))
    yaws = [int(y) for y in a.yaws.split(",")]
    gear = tuple(g for g in a.gear.split(",") if g)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    scene = bpy.context.scene
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm is None:
        raise SystemExit("no armature in %s" % a.glb)

    for o in bpy.data.objects:
        if o.type == "MESH" and ("Sword" in o.name or "Shield" in o.name) and o.name not in gear:
            o.hide_render = True

    def posed_bbox():
        dg = bpy.context.evaluated_depsgraph_get()
        mn = [1e9] * 3
        mx = [-1e9] * 3
        for o in bpy.data.objects:
            if o.type != "MESH" or o.hide_render:
                continue
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            for v in me.vertices:
                w = ev.matrix_world @ v.co
                for k in range(3):
                    mn[k] = min(mn[k], w[k])
                    mx[k] = max(mx[k], w[k])
            ev.to_mesh_clear()
        return mn, mx

    def set_action(name):
        act = bpy.data.actions.get(name)
        if act is None:
            raise SystemExit("no action %r; the GLB has %s" % (name, sorted(x.name for x in bpy.data.actions)[:8]))
        arm.animation_data_create()
        arm.animation_data.action = act
        return act

    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("c"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    so = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    scene.collection.objects.link(so)
    so.data.energy = a.sun
    so.data.angle = math.radians(30)
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = a.ambient
    scene.render.film_transparent = True
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
    except Exception as e:  # noqa: BLE001 - a CPU fallback is the right answer here
        print("GPU setup failed, using CPU:", e)
        scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = a.res
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    os.makedirs(a.out, exist_ok=True)

    # the fixed camera: sized on the union bbox of the FIRST clip, so every frame keeps scale
    mn = [1e9] * 3
    mx = [-1e9] * 3
    act = set_action(clips[0][0])
    x0, y0 = act.frame_range
    for t in clips[0][1]:
        scene.frame_set(int(x0 + t * (y0 - x0)))
        bpy.context.view_layer.update()
        lo, hi = posed_bbox()
        for k in range(3):
            mn[k] = min(mn[k], lo[k])
            mx[k] = max(mx[k], hi[k])
    cx = (mn[0] + mx[0]) / 2
    cy = (mn[1] + mx[1]) / 2
    cz = (mn[2] + mx[2]) / 2
    size = max(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
    dist = (size / 2) / math.tan(cam.data.angle / 2) * a.margin
    print(f"framing: size={size:.2f} dist={dist:.2f} gear={gear} ambient={a.ambient} sun={a.sun}")

    for name, fracs in clips:
        act = set_action(name)
        x, y = act.frame_range
        for i, t in enumerate(fracs):
            scene.frame_set(int(x + t * (y - x)))
            bpy.context.view_layer.update()
            for yaw in yaws:
                r = math.radians(yaw)
                cam.location = (cx + dist * math.sin(r), cy - dist * math.cos(r), cz)
                cam.rotation_euler = (mathutils.Vector((cx, cy, cz)) - mathutils.Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
                so.rotation_euler = cam.rotation_euler
                so.location = cam.location
                scene.render.filepath = os.path.join(a.out, f"{name}_f{i}_yaw{yaw:03d}.png")
                bpy.ops.render.render(write_still=True)
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
