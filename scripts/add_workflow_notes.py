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

Usage (from the repo root):  python scripts/add_workflow_notes.py [--check] [--update]
--check   report only, change nothing, exit 1 if any flow is undocumented
--update  also rewrite existing notes from NOTES (use after editing a note's text)
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
    "z-image-turbo.json":             ("Z-Image Turbo base art",        "U3"),
    "sdxl-base-art.json":             ("SDXL base art",                 "E1/E1c/E1d"),
    "sdxl-controlnet-canny.json":     ("ControlNet canny",              "E2b"),
    "controlnet-union.json":          ("ControlNet-Union SDXL",         "U6b"),
    "regional-prompting.json":        ("Regional prompting",            "E15"),
    "remove-bg.json":                 ("Cutout (BiRefNet)",             "E3b"),
    "sam3-segment.json":              ("SAM 3 text-prompted mask",      "U6a"),
    "depth-normal.json":              ("Depth map",                     "E12"),
    "inpaint.json":                   ("Inpaint",                       "E8"),
    "outpaint.json":                  ("Outpaint",                      "E9, E17"),

    "qwen-edit-gguf.json":            ("Instruction edit + consistency","U2/E14c"),
    "pose-skeleton.json":             ("Pose from a skeleton",           "E21"),
    "compose-harmonize.json":         ("Compose + harmonize",           "E10"),
    "instantid-character.json":       ("Face identity (InstantID)",     "E14b"),
    "pulid-identity.json":            ("Identity + free composition",   "U5"),

    "ipadapter-style.json":           ("Style reference (superseded)",  "E11"),
    "seamless-texture.json":          ("Seamless tiling",               "E7c"),
    "pbr-from-texture.json":          ("PBR set (metallic inverted)",   "E12b -> see U4"),
    "upscale-seedvr2.json":           ("SeedVR2 upscale / restore",     "U1/E13f"),
    "upscale.json":                   ("GAN upscale (non-commercial)",  "E4b"),
    "pixel-art.json":                 ("Pixel art",                     "E5/E5b/E5f"),
    "hy3d-full-workflow.json":        ("Hy3D shape -> texture",         "E2a-e"),
    "hy3d-multiview-workflow.json":   ("Hy3D multiview",                "E2d"),
    "unirig-humanoid-workflow.json":  ("UniRig (Linux only)",           "E4-L"),
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
    "outpaint.json":
        "**Does:** outpaint to a wider canvas (Crop&Stitch). `extend_left/right_factor=1.5` is +50% width\n"
        "per side. The original region returns at mean|diff| **0.041/255** (pixel-identical) because the\n"
        "stitcher never VAE round-trips unmasked pixels; the core `ImagePadForOutpaint` baseline drifted\n"
        "6.477/255. `device_mode=\"gpu (much faster)\"` matters 30-100x.\n"
        "**By design:** the new area is *invented* (the node pads the canvas by edge-clamp and the\n"
        "sampler replaces it). For a *controlled* extension - the same trees/sky carried outward - pad\n"
        "the canvas with `scripts/pad_image.py` and run `inpaint.json` at denoise ~0.7 instead (S5, E18).\n"
        "**Resolution (E19):** samples at **1536x768**, not the raw 2048x1024 crop - at 2.1 MP\n"
        "SDXL goes mushy (blurry foliage, smeared wall); 1536x768 is crisp and ~33% faster (12 s vs\n"
        "18 s). Keep the target's aspect equal to the crop's. `preresize` cannot help: it runs\n"
        "BEFORE the extension, so it never sees the padded canvas.\n"
        "**Seam (E17):** this graph ships `mask_blend_pixels` **64** - the border knob (seam step\n"
        "19.6 -> 11.7 of 255; at 64 the boundary no longer stands out from its own surroundings) - with\n"
        "`denoise` **0.9** for the colour match (colour step 16.1 -> 11.7). At ~0.8 and below the model\n"
        "starts *inventing* rather than refining - on the cottage it painted a second, different cottage\n"
        "(the extension fill is an **edge-clamp smear**, not a mirror, so what survives is not the source).\n"
        "**`mask_expand_pixels` and\n"
        "`context_from_mask_extend_factor` do nothing here**: the mask ops run before the extension and\n"
        "no mask is wired in. A clipped object (half a tree) is not continued by any blend width - the\n"
        "new area is invented.",
    "pose-skeleton.json":
        "**Does:** puts the character in a POSE you supply as a skeleton - ControlNet-Union's `openpose`\n"
        "mode drives the SILHOUETTE while IPAdapter carries the design. It is a coarse-stance tool rather\n"
        "than a pose editor; the measurement below says exactly how far it goes.\n"
        "**WHAT THE CUE ACTUALLY BUYS (E22).** The shipped `strength 1.5` + `end_percent 0.5` is the point.\n"
        "With the CN applied for ALL steps it is ignored at 0.9-1.2 and destroys the image at 1.5 (E21c),\n"
        "but ending the window early lets `1.5` impose the cue over a prompt that explicitly says the\n"
        "opposite: a 'T-pose, arms outstretched' cue beat 'both arms lowered, hanging straight down at his\n"
        "sides' and still rendered clean. It works at the level of the SILHOUETTE only - a 45-deg cue still\n"
        "renders arms at the sides, an asymmetric cue (one arm up) is ignored, and a 'both arms up' cue\n"
        "comes back as shoulder horns rather than arms. Use this flow for a coarse stance (arms out / wide /\n"
        "tall) and an instruction (`qwen-edit-gguf.json`) for a specific pose. CFG is NOT a lever (4.0 = 7.0).\n"
        "**Skeleton in:** the ControlNet reads node 1. It ships a working example -\n"
        "`2d/pose_arms_spread.png` (published from `assets/2d/`) - so the flow runs as-is; point node 1\n"
        "elsewhere for your own pose.\n"
        "**Getting a pose from a photo:** `2d/workflows/pose-extract.json` (S16) lifts one off a photo and\n"
        "writes both the skeleton image and the keypoints JSON - put that image in `input/` and point node 1\n"
        "at it, one photo per pose. The joints are 18 of `x, y, confidence` in pixels:\n"
        "`0 nose, 1 neck, 2/3/4 R shoulder/elbow/wrist, 5/6/7 L shoulder/elbow/wrist, 8/9/10 R hip/knee/\n"
        "ankle, 11/12/13 L hip/knee/ankle, 14-17 eyes and ears` (R = the subject's right = image left).\n"
        "The detector needs a photoreal-enough person (`char_heroine` reads, the armoured `char_knight`\n"
        "returns `people: []`), so on stylised art the skeleton has to be authored **by hand** instead -\n"
        "18 joints of `x, y, confidence`, or a keypoint export from a 3D tool.\n"
        "**Knobs:** the CN **window** is the one that matters - `strength 1.5` with `end_percent 0.5` (loud\n"
        "enough to override the prompt, ended early enough that the sampler renders the last half freely).\n"
        "IPAdapter `weight` **0.15**: it fights the cue (0.35 erased a 45-deg spread; >=0.6 freezes the\n"
        "reference's own stance, E21/E11). Say the stance you want in the prompt and forbid the one you\n"
        "don't in the negative (`arms at sides, hands on hips`).\n"
        "**Limits:** a 2D COCO skeleton has no yaw, so a **camera angle** change is not this flow's job -\n"
        "use an instruction edit, or the 3D path (`Hy3DCameraConfig` + `Hy3DRenderMultiview`).",
    "seamless-texture.json":
        "**Does:** makes an image tile seamlessly, in image space (TextureAlchemy).\n"
        "**Knobs:** `method` — use **`offset`**. `mirror`/`blend_edges` score perfectly on continuity\n"
        "metrics and look visibly awful (symmetric kaleidoscope / blurry cross).\n"
        "**Avoid:** `SeamlessTile` (comfyui-seamless-tiling) patches the MODEL and **segfaults** the\n"
        "server in libcuda; the circular-VAE route crashes on a second run in one session.",
    "depth-normal.json":
        "**Does:** monocular depth (DepthAnythingV2) from a single image. No extra weights - ACN\n"
        "downloads it on first use.\n"
        "**Reads:** depth = light is *near*. Depth is **relative** (no absolute scale), so it is a\n"
        "guidance/parallax cue, **not** a height or displacement map.\n"
        "**Feeds:** depth-ControlNet, depth-ordered composition, engine parallax.\n"
        "**Note:** DSINE was removed from this graph - it is non-commercial and camera-space. A\n"
        "material normal belongs to the PBR path.",
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


def _story_of(flow: str) -> str:
    """The story for a flow comes from the one registry (jobs.json at the repo root), never a local copy."""
    reg = json.load(open(os.path.join(REPO, "jobs.json"), encoding="utf-8"))
    meta = reg["flows"].get(flow)
    if not meta:
        raise SystemExit(f"jobs.json has no story claim for {flow}")
    return ", ".join(meta.get("stories") or [meta["story"]])


def note_markdown(flow: str, body: str) -> str:
    label, ref = MAPPING[flow]
    story = _story_of(flow)
    footer = f"*How to run it: story **{story}** in `HOWTO.md`  ·  Why it is this way: **{ref}** in the scenarios' `EXPERIMENTS` logs.*"
    body = (body or "").strip()
    return f"## {flow}\n\n{label}\n\n{body}\n\n---\n{footer}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if a flow is undocumented")
    ap.add_argument("--update", action="store_true",
                    help="rewrite existing notes from their authored NOTES entry (review the diff)")
    ap.add_argument("flows", nargs="*", help="with --update: only these flow files (e.g. depth-normal.json)")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(REPO, "*", "workflows", "*.json")))
    problems, changed = [], []

    for p in paths:
        flow = os.path.basename(p)
        d = json.load(open(p, encoding="utf-8"))
        nodes = d.get("nodes", [])
        existing = next((n for n in nodes if n.get("type") == "MarkdownNote"), None)
        labels = [g.get("title", "") for g in (d.get("groups") or [])]
        body = "\n".join(t for t in labels if t)
        authored = NOTES.get(flow, "")
        if len(body) < len(authored):
            body = authored

        if existing:
            # --update is deliberately conservative: it rewrites a note ONLY from that flow's authored
            # NOTES entry. Falling back to group titles here would silently downgrade notes whose body
            # was authored from the (now-shortened) group titles, i.e. it would lose text.
            if not args.update or not authored or (args.flows and flow not in args.flows):
                continue
            md = note_markdown(flow, authored)
            if (existing.get("widgets_values") or [None])[0] == md:
                continue
            if args.check:
                changed.append(flow)
                continue
            existing["widgets_values"] = [md]
            for g in d.get("groups") or []:
                if g.get("title"):
                    g["title"] = MAPPING[flow][0]
            json.dump(d, open(p, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
            changed.append(flow)
            continue

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
