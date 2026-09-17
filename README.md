# AI Game-Dev Pipelines — start here

A working, reproducible pipeline for **generating game assets with open models on our own hardware**, plus the notes that explain *why* every choice was made. We have two primary goals:

1. **Get things done** — real assets out of a real pipeline.
2. **Understand it deeply** — every node, knob, failure mode and version, so the setup can be rebuilt or ported.

**This page is the cookbook.** Find the job you have, follow the link, and the story in
[`HOWTO.md`](HOWTO.md) tells you what to actually do.

---

## I want to make…

| I want to make / do                                    | flow                                                                                                                                                                                                                   | story |
|--------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|
| **Generate concept art from a prompt**                 | `2d/workflows/z-image-turbo.json` (modern, Apache-2.0) or `2d/workflows/sdxl-base-art.json` (SDXL, painted look)                                                                                                       | S1    |
| **Control composition from an existing image**         | `2d/workflows/controlnet-union.json` (one model, many modes) · `2d/workflows/sdxl-controlnet-canny.json` (canny only)                                                                                                  | S2    |
| **Cut an object out** (transparent PNG)                | `2d/workflows/remove-bg.json` (BiRefNet)                                                                                                                                                                               | S3    |
| **Mask by description** ("the knight", "the roof")     | `2d/workflows/sam3-segment.json` (SAM 3, text-prompted)                                                                                                                                                                | S3    |
| **Get a depth or normal map**                          | `2d/workflows/depth-normal.json` (DepthAnythingV2 + DSINE)                                                                                                                                                             | S4    |
| **Inpaint / remove / add an object**                   | `2d/workflows/inpaint.json`                                                                                                                                                                                            | S5    |
| **Make the picture bigger** (outpaint)                 | `2d/workflows/outpaint.json` (Crop&Stitch — no drift outside the mask)                                                                                                                                                 | S5    |
| **Compose a scene from parts** (bg + character + prop) | `scripts/compose_scene.py` → `2d/workflows/compose-harmonize.json`                                                                                                                                                     | S6    |
| **Keep two subjects from merging**                     | `2d/workflows/regional-prompting.json` (a single prompt *drops* one)                                                                                                                                                   | S6    |
| **Keep a character consistent across images**          | `2d/workflows/qwen-edit-gguf.json` (design) · `2d/workflows/instantid-character.json` (tight face) · `2d/workflows/pulid-identity.json` (face + free composition) · `2d/workflows/kontext-character.json` (superseded) | S7    |
| **Relight / change the lighting**                      | `2d/workflows/qwen-edit-gguf.json` (faithful) · `2d/workflows/kontext-edit.json` (bolder, superseded)                                                                                                                  | S5    |
| **Transfer a style or reference look**                 | `2d/workflows/qwen-edit-gguf.json` (multi-image reference) · `2d/workflows/ipadapter-style.json` (superseded)                                                                                                          | S13   |
| **Make a texture tile seamlessly**                     | `2d/workflows/seamless-texture.json` (`method="offset"`)                                                                                                                                                               | S8    |
| **Turn a texture into PBR maps**                       | **`scripts/marigold_pbr.py`** (correct metallic — not `2d/workflows/pbr-from-texture.json`, whose metallic is inverted)                                                                                                | S8    |
| **Push a 2D material into 3D**                         | **`scripts/make_gltf_material.py`** (glTF-valid material + optional GLB)                                                                                                                                               | S8    |
| **Upscale / restore** (incl. faces)                    | `2d/workflows/upscale-seedvr2.json` (Apache-2.0; `resolution` = image size for *restore*)                                                                                                                              | S9    |
| **Upscale faithfully** (GAN, invents nothing)          | `2d/workflows/upscale.json` — non-commercial `4x-UltraSharp`; prefer SeedVR2 above                                                                                                                                     | S9    |
| **Pixel art**                                          | `2d/workflows/pixel-art.json` (**downscale nearest ÷8 or ÷16**)                                                                                                                                                        | S10   |
| **Build a sprite sheet / atlas**                       | `2d/workflows/sprite-atlas.json` (build + slice round-trip)                                                                                                                                                            | S10   |
| **Sweep parameters into a labelled grid**              | **`scripts/sweep.py`** (`--x cfg:3,5,7 --y steps:10,20,30`)                                                                                                                                                            | S12   |
| **Reproduce the canonical asset set**                  | **`scripts/gen_assets.py`**                                                                                                                                                                                            | S12   |
| **Promote assets into the repo**                       | **`scripts/publish_assets.sh`** (`[2d\|3d\|all] [ids…]`)                                                                                                                                                               | S12   |
| **Make a 3D model** from an image/description          | `3d/workflows/hy3d-full-workflow.json` · multi-view: `3d/workflows/hy3d-multiview-workflow.json`                                                                                                                       | S11   |
| **Rig a character**                                    | `3d/workflows/unirig-humanoid-workflow.json` (bpy via pixi — **Linux only**)                                                                                                                                           | S11   |

---

## Operating the box

| I need to…                                                                | go to                                                                                                           |
|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| **Know what will and won't run here** (read before pulling a large model) | [`comfyui/hardware.md`](comfyui/hardware.md)                                                                    |
| Use the server / fix a crash                                              | [`comfyui/README.md`](comfyui/README.md) → gotchas · [`comfyui/setup.md`](comfyui/setup.md)                     |
| Set up or migrate a machine                                               | [`comfyui/linux-setup.md`](comfyui/linux-setup.md) · [`comfyui/linux-migration.md`](comfyui/linux-migration.md) |
| Upgrade the hardware                                                      | [`comfyui/UPGRADE-TODO.md`](comfyui/UPGRADE-TODO.md)                                                            |
| Decide whether a tool is still the right one                              | [`2d/AUDIT-tooling-2026-09.md`](2d/AUDIT-tooling-2026-09.md)                                                    |
| Check the docs (tables, links, flow coverage) before committing           | `scripts/lint_docs.py` (tables, links, coverage) · `scripts/mdtable.py` (table AST) · `scripts/add_workflow_notes.py`                                                        |

---

## Where a flow's documentation lives

Four places, and you can reach all of them **from the flow itself** — no hunting:

|                        |                                                                                                                               |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| **How to run it**      | the matching story in [`HOWTO.md`](HOWTO.md) — prerequisites, steps, the knobs that matter, the trap to avoid                 |
| **Why it is this way** | its `E`/`U` row in the scenario's `EXPERIMENTS` log — the verdict *and* the measurements behind it                            |
| **Reference**          | its row in [`PIPELINES.md`](PIPELINES.md) — operation family, cost, **licence**, status, key knob, and its HOWTO story number |
| **In the canvas**      | every workflow carries a `MarkdownNote` panel: the recipe plus links to the story and the `EXPERIMENTS` row                   |

---

## Reference

| doc                                                                                       | what it is                                                                                                      |
|-------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| [`PIPELINES.md`](PIPELINES.md)                                                            | the **capability index** — every flow by operation × subject × domain, plus the taxonomy and what is still open |
| [`AGENTS.md`](AGENTS.md)                                                                  | repo layout, conventions, vocabulary, doc map — for working *on* the repo rather than with it                   |
| [`HOWTO.md`](HOWTO.md)                                                                    | the user stories (this page's "how")                                                                            |
| [`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md) · [`3d/EXPERIMENTS.md`](3d/EXPERIMENTS.md) | every run: parameters, verdict, reasoning, corrections                                                          |
| [`comfyui/README.md`](comfyui/README.md)                                                  | **node gotchas** — the highest-density page in the repo                                                         |
| [`3d/README.md`](3d/README.md) · [`3d/pipeline-design.md`](3d/pipeline-design.md)         | the 3D scenario and its architecture                                                                            |

**Licence posture:** the stack is Apache-2.0/BSD-clean with **one exception** — `insightface` (used by `instantid-character.json` and `pulid-identity.json`) is non-commercial research-only. Everything else, including Kontext's replacement, is shippable. See the [audit](2d/AUDIT-tooling-2026-09.md).
