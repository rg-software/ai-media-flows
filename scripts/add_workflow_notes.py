#!/usr/bin/env python3
"""Migrate a workflow's inline documentation from a group *title* into a MarkdownNote node.

Why: group titles render as a cramped label on the group header, not as readable text — so a
user opening a flow in ComfyUI sees a clipped label instead of documentation. ComfyUI's own
convention is a `MarkdownNote` panel (357 of its 559 shipped templates use one); none of ours
did. This puts each flow's documentation where the user already is, and gives every note the
same header so the cross-references are always present:

    ## <flow>
    <existing body text>
    ---
    *How to run: story **S5** (`HOWTO.md`) · Why: **E9** (`2d/EXPERIMENTS-2D.md`)*

Idempotent: a workflow that already has a MarkdownNote is skipped, so it is safe to re-run
after adding a workflow (add an entry to MAPPING/NOTES first).

Usage (from the repo root):  python scripts/add_workflow_notes.py [--check]
    --check   report only, change nothing, exit 1 if any flow is undocumented
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# flow -> (short group label, story id(s), E/U reference(s))
MAPPING = {
    "z-image-turbo.json":             ("Z-Image Turbo base art",        "S1", "U3"),
    "sdxl-base-art.json":             ("SDXL base art",                 "S1", "E1/E1c/E1d"),
    "sdxl-controlnet-canny.json":     ("ControlNet canny",              "S2", "E2b"),
    "controlnet-union.json":          ("ControlNet-Union SDXL",         "S2", "U6b"),
    "regional-prompting.json":        ("Regional prompting",            "S6", "E15"),
    "remove-bg.json":                 ("Cutout (BiRefNet)",             "S3", "E3b"),
    "sam3-segment.json":              ("SAM 3 text-prompted mask",      "S3", "U6a"),
    "depth-normal.json":              ("Depth + normal maps",           "S4", "E12"),
    "inpaint.json":                   ("Inpaint",                       "S5", "E8"),
    "outpaint.json":                  ("Outpaint",                      "S5", "E9"),
    "kontext-edit.json":              ("Relight (Kontext, superseded)", "S5", "E13 -> see U2"),
    "qwen-edit-gguf.json":            ("Instruction edit + consistency","S5, S7", "U2/E14c"),
    "compose-harmonize.json":         ("Compose + harmonize",           "S6", "E10"),
    "instantid-character.json":       ("Face identity (InstantID)",     "S7", "E14b"),
    "pulid-identity.json":            ("Identity + free composition",   "S7", "U5"),
    "kontext-character.json":         ("Character ref (superseded)",    "S7", "E14a -> see E14c"),
    "ipadapter-style.json":           ("Style reference (superseded)",  "S13", "E11"),
    "seamless-texture.json":          ("Seamless tiling",               "S8", "E7c"),
    "pbr-from-texture.json":          ("PBR set (metallic inverted)",   "S8", "E12b -> see U4"),
    "upscale-seedvr2.json":           ("SeedVR2 upscale / restore",     "S9", "U1/E13f"),
    "upscale.json":                   ("GAN upscale (non-commercial)",  "S9", "E4b"),
    "pixel-art.json":                 ("Pixel art",                     "S10", "E5/E5b/E5f"),
    "sprite-atlas.json":              ("Sprite atlas",                  "S10", "E6"),
    "hy3d-full-workflow.json":        ("Hy3D shape -> texture",         "S11", "E2a-e"),
    "hy3d-multiview-workflow.json":   ("Hy3D multiview",                "S11", "E2d"),
    "unirig-humanoid-workflow.json":  ("UniRig (Linux only)",           "S11", "E4-L"),
}

# Authored bodies for flows that had no usable note (or a too-thin one).
NOTES = {
    "sdxl-base-art.json":
        "**Does:** prompt -> still image with SDXL (RealVisXL_V5.0_fp16 is the default checkpoint).\n"
        "**Knobs:** `cfg` and `steps` — **cfg 7 / 20 steps** is the value point; cfg 3 washes out, cfg 9\n"
        "over-burns, 30 steps buys nothing over 20.\n"
        "**Trap:** SDXL will not reliably give a full-body **solo** figure at 1024² — say \"solo, single\n"
        "figure, full body\" or you get a two-view sheet or a bust.\n"
        "**Note:** SDXL is now a **niche pick** — `z-image-turbo.json` is the modern, licence-clean\n"
        "base model. Kept because the canonical asset set (E1d) came from here.",
    "sdxl-controlnet-canny.json":
        "**Does:** generation constrained by the *structure* of an input image (Canny edges) — the\n"
        "layout transfers, the content and style are replaced.\n"
        "**Knobs:** `strength` ~0.8 holds structure while freeing style; the canny low/high thresholds\n"
        "control edge density.\n"
        "**Superseded:** `controlnet-union.json` does this and more from **one** model. Use this only\n"
        "if you specifically want the SDXL-v2 canny model.",
    "remove-bg.json":
        "**Does:** subject mask / transparent cutout with BiRefNet.\n"
        "**Trap (cost real debugging time):** the MASK convention is **1 = transparent/selected**, and\n"
        "`RemoveBackground` returns 1 on the *foreground* — so you must insert **`InvertMask`** before\n"
        "`JoinImageWithAlpha`/`SaveImageWithAlpha`, or you get a perfectly inverted cutout.\n"
        "**Note:** `RemoveBackground` outputs a MASK, not an image.",
    "upscale.json":
        "**Does:** x4 GAN upscale — faithful, invents nothing.\n"
        "**Trap:** `4x-UltraSharp` is **non-commercial**; for shippable output use\n"
        "`upscale-seedvr2.json` (Apache-2.0) instead.\n"
        "**Trade-off:** a GAN is faithful but soft/blurry at 2x; SeedVR2 reconstructs more detail but\n"
        "drifts further from the source.",
    "seamless-texture.json":
        "**Does:** makes an image tile seamlessly, in image space (TextureAlchemy).\n"
        "**Knobs:** `method` — use **`offset`**. `mirror`/`blend_edges` score perfectly on continuity\n"
        "metrics and look visibly awful (symmetric kaleidoscope / blurry cross).\n"
        "**Avoid:** `SeamlessTile` (comfyui-seamless-tiling) patches the MODEL and **segfaults** the\n"
        "server in libcuda; the circular-VAE route crashes on a second run in one session.",
    "depth-normal.json":
        "**Does:** monocular depth (DepthAnythingV2) and tangent-space normals (DSINE) from a single\n"
        "image. No extra weights — ACN downloads them on first use.\n"
        "**Reads:** depth = light is *near*; normals are flat ≈ (128,128,255).\n"
        "**Feeds:** depth-ControlNet, mask-aware editing, depth-ordered composition, and the\n"
        "PBR / 2.5D bridge.",
    "ipadapter-style.json":
        "**Does:** transfers the style/look of a reference image (IPAdapter).\n"
        "**Knobs:** `weight` — 0.0-0.2 style hint only; 0.3-0.5 blend; **>=0.6 the reference overrides\n"
        "the prompt** (content takeover).\n"
        "**Superseded:** Qwen-Edit's multi-image reference does this without IPAdapter and with an\n"
        "Apache-2.0 licence (E14c; see `qwen-edit-gguf.json`).",
    "hy3d-full-workflow.json":
        "**Does:** image -> 3D mesh -> texture -> bake, with Hunyuan3D 2.x.\n"
        "**Note:** the shape and the texture are exported separately (untextured and textured GLB) so\n"
        "the shape can be rigged/retopo'd before texturing.\n"
        "**See:** `3d/README.md`, `3d/pipeline-design.md`, and the widget reference in `3d/hy3d-knobs.md`.",
    "hy3d-multiview-workflow.json":
        "**Does:** the multiview variant of Hy3D — several consistent views (uniform 512²) feed the\n"
        "shape model, which usually beats a single-view guess on occluded geometry.\n"
        "**See:** `3d/README.md`, `3d/EXPERIMENTS.md` E2d.",
    "unirig-humanoid-workflow.json":
        "**Does:** auto-rigs a humanoid mesh and exports a **Mixamo-compatible FBX** (Unity-friendly).\n"
        "**Platform:** **Linux only** — UniRig needs `bpy` (Blender-as-Python), which the pack provides\n"
        "in its own pixi/conda env. It failed on Windows with a native DLL error (E4).\n"
        "**See:** `3d/EXPERIMENTS.md` E4-L, `3d/pipeline-design.md`.",
}


def note_markdown(flow: str, body: str) -> str:
    label, story, ref = MAPPING[flow]
    footer = f"*How to run it: story **{story}** in `HOWTO.md`  ·  Why it is this way: **{ref}** in the scenarios' `EXPERIMENTS` logs.*"
    body = (body or "").strip()
    return f"## {flow}\n\n{label}\n\n{body}\n\n---\n{footer}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if a flow is undocumented")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(REPO, "2d", "workflows", "*.json"))) + \
            sorted(glob.glob(os.path.join(REPO, "3d", "workflows", "*.json")))
    problems, changed = [], []

    for p in paths:
        flow = os.path.basename(p)
        d = json.load(open(p, encoding="utf-8"))
        nodes = d.get("nodes", [])
        existing = next((n for n in nodes if n.get("type") == "MarkdownNote"), None)
        if existing:
            continue

        labels = [g.get("title", "") for g in (d.get("groups") or [])]
        body = "\n".join(t for t in labels if t)
        authored = NOTES.get(flow, "")
        if len(body) < len(authored):
            body = authored
        if not body:
            problems.append(f"{flow}: no note text (add an entry to NOTES)")
            continue
        if flow not in MAPPING:
            problems.append(f"{flow}: missing from MAPPING")
            continue

        if args.check:
            changed.append(flow)
            continue

        # place the panel above the graph, left-aligned with it
        xs = [n.get("pos", [0, 0])[0] for n in nodes] or [0]
        ys = [n.get("pos", [0, 0])[1] for n in nodes] or [0]
        md = note_markdown(flow, body)
        new_id = max([n.get("id", 0) for n in nodes] + [d.get("last_node_id", 0)]) + 1
        lines = md.count("\n")
        nodes.append({
            "id": new_id,
            "type": "MarkdownNote",
            "pos": [min(xs), min(ys) - max(220, 18 * lines)],
            "size": [720, max(200, 17 * lines)],
            "flags": {},
            "order": 0,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "properties": {},
            "widgets_values": [md],
            "color": "#332922",
            "bgcolor": "#593930",
        })
        d["nodes"] = nodes
        d["last_node_id"] = new_id
        # shorten the group titles so they read as labels, not paragraphs
        for g in d.get("groups") or []:
            if g.get("title"):
                g["title"] = MAPPING[flow][0]
        json.dump(d, open(p, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
        changed.append(flow)

    verb = "would add a note to" if args.check else "added a MarkdownNote to"
    for f in changed:
        print(f"  {verb} {f}")
    for p in problems:
        print(f"  PROBLEM {p}")
    print(f"\n{len(changed)} workflow(s) {'to do' if args.check else 'updated'}, {len(problems)} problem(s)")
    return 1 if (problems or (args.check and changed)) else 0


if __name__ == "__main__":
    sys.exit(main())
