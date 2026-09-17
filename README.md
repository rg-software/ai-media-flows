# AI Game-Dev Pipelines — start here

A working, reproducible pipeline for **generating game assets with open models on our own hardware**, plus the notes that explain *why* every choice was made. Two goals, held together deliberately:

1. **Get things done** — real assets out of a real pipeline.
2. **Understand it deeply** — every node, knob, failure mode and version, so the setup can be rebuilt or ported.

If you are new here, read this page top to bottom once, then use the **"I want to…"** table to jump. This page is the map; the deep detail lives in the linked files.

---

## The mental model

### Classifying flows

Flows are described by what they do rather their folder locations. **Browse [`PIPELINES.md`](PIPELINES.md)**, which describes every flow in detail. Flows are categorized according to two axes.

**Axis 1 — operation family** (what the flow *does to* an asset):

| family        | what it does                                                                                                        |
| ------------- | ------------------------------------------------------------------------------------------------------------------- |
| `generate` | prompt → brand-new artefact of the target domain |
| `guide`       | generation constrained by structure **or reference** — ControlNet, regional areas, style/identity references, masks |
| `stylize`     | rerender into a disciplined style/palette                                                                           |
| `isolate`     | subject out of background; masks and per-pixel maps                                                                 |
| `edit`        | change part of an existing image                                                                                    |
| `finish`      | resolution / restoration / grading                                                                                  |
| `surface`     | tileable textures and PBR material sets                                                                             |
| `assemble`    | atlases, grids, multi-image composition                                                                             |
| `reconstruct` | image → 3D geometry / texture / rig                                                                                 |
| `tooling`     | harnesses for reproducing or exploring (not an operation)                                                           |

**Axis 2 — what it is applied to**: subject `object | scene | material`, and domain
`image | texture | 3D model`. Flows that **bridge** domains are marked as `from→to`. E.g., "make a seamless stone texture and give it PBR maps" is
`surface • material • texture → 3D model` — 2D material authoring that a 3D engine consumes.

A flow's `.json` lives in whichever scenario folder it was built for. **Browse by capability rather than by folder**.

### Four kinds of files

| kind          | where                         | what it is                                                                          |
| ------------- | ----------------------------- | ----------------------------------------------------------------------------------- |
| **assets**    | `assets/`                     | the curated, tracked artefacts                                                      |
| **workflows** | `<scenario>/workflows/*.json` | ComfyUI graphs ready for running (one-off scaffoldings are in `workflows/scratch/`) |
| **scripts**   | `scripts/`                    | non-graph scripts: sweeps, generators, format packing, etc.                         |
| **docs**      | the `.md` files               | the *why*: verdicts, gotchas, measurements, decisions.                              |

### Numbering principles

- **E-numbers** (`E1`…`E16`) are **experiments** — one capability each, run in order, each with a verdict and the reasoning. `E1c`, `E4b`, `E13f` are refinements of the same experiment.
- **U-numbers** (`U1`…`U7`) are **upgrades** — swapping a working-but-suboptimal tool for a better or license-cleaner one, decided by the audit.
- Both live in **[`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md)** and **[`3d/EXPERIMENTS.md`](3d/EXPERIMENTS.md)**. **Read the verdicts, not just the results*.
- A **verdict** is `PASS` / `MEH` / `BLOCKED` with a reason. Several entries are explicit corrections of earlier entries.

---

## I want to…

| I want to…                                              | go to                                                                                                                                                                                                                          |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **See what we can already do**                          | [`PIPELINES.md`](PIPELINES.md) — capability map + status                                                                                                                                                                       |
| Generate base concept art                               | `2d/workflows/sdxl-base-art.json`, or **`2d/workflows/z-image-turbo.json`** (modern)                                                                                                                                           |
| Control composition from an existing image              | `2d/workflows/controlnet-union.json` (unified)<br>`sdxl-controlnet-canny.json` (canny-only)                                                                                                                                    |
| Cut an object out (transparent PNG)                     | `2d/workflows/remove-bg.json` (BiRefNet)                                                                                                                                                                                       |
| **Auto-mask by description** ("the knight", "the roof") | `2d/workflows/sam3-segment.json` (SAM 3, text-prompted)                                                                                                                                                                        |
| Get a **depth** or **normal** map from an image         | `2d/workflows/depth-normal.json` (DepthAnythingV2 + DSINE) - feeders for depth-ControlNet, masking and 2.5D                                                                                                                    |
| Inpaint / remove / add an object                        | `2d/workflows/inpaint.json`, then **`outpaint.json`** (Crop&Stitch — no drift outside the mask)                                                                                                                                |
| Make the picture bigger (outpaint)                      | `2d/workflows/outpaint.json`                                                                                                                                                                                                   |
| Compose a scene from parts (bg + character + prop)      | `scripts/compose_scene.py` → `2d/workflows/compose-harmonize.json`                                                                                                                                                             |
| Keep two characters from merging                        | `2d/workflows/regional-prompting.json` (a single prompt *drops* a subject)                                                                                                                                                     |
| Keep a character consistent across images               | `2d/workflows/qwen-edit-gguf.json` (design-level, Apache-2.0) · `instantid-character.json` (tight face, pose-locked) · `pulid-identity.json` (face + free composition) · `kontext-character.json` (superseded, non-commercial) |
| Relight / change the lighting of an image               | `2d/workflows/qwen-edit-gguf.json` (faithful) or `kontext-edit.json` (bolder, non-commercial)                                                                                                                                  |
| Transfer the **style** of a reference image             | `2d/workflows/ipadapter-style.json` (IPadapter, weight 0.2-0.4) - **superseded**: Qwen-Edit's multi-image reference does this without IPAdapter (E14c)                                                                         |
| Make a texture **tile seamlessly**                      | `2d/workflows/seamless-texture.json` (`method="offset"`; avoid mirror/blend_edges)                                                                                                                                             |
| Turn a texture into **PBR maps**                        | **`scripts/marigold_pbr.py`** (correct metallic) — not `pbr-from-texture.json`, whose metallic is inverted                                                                                                                     |
| Push a 2D material into **3D**                          | **`scripts/make_gltf_material.py`** → glTF-valid material + optional GLB                                                                                                                                                       |
| Upscale / restore (incl. faces)                         | `2d/workflows/upscale-seedvr2.json` (Apache-2.0). Set `resolution` = image size for **restore**, larger to upscale                                                                                                             |
| Upscale **faithfully** (GAN, invents nothing)           | `2d/workflows/upscale.json` - uses non-commercial `4x-UltraSharp`; for shippable output use SeedVR2 above                                                                                                                      |
| Pixel art                                               | `2d/workflows/pixel-art.json` (**downscale nearest ÷8 or ÷16** — never trust the detector)                                                                                                                                     |
| Build a sprite sheet / atlas                            | `2d/workflows/sprite-atlas.json` (build + slice round-trip)                                                                                                                                                                    |
| Sweep parameters and get a labelled grid                | **`scripts/sweep.py`** (`--x cfg:3,5,7 --y steps:10,20,30`)                                                                                                                                                                    |
| Reproduce the canonical asset set                       | **`scripts/gen_assets.py`**                                                                                                                                                                                                    |
| Promote assets into the repo                            | **`scripts/publish_assets.sh`** (`[2d\|3d\|all] [ids…]`)                                                                                                                                                                       |
| Make a 3D model from an image/description               | `3d/workflows/hy3d-full-workflow.json`, see [`3d/README.md`](3d/README.md)                                                                                                                                                     |
| Make a 3D model from **multiple views**                 | `3d/workflows/hy3d-multiview-workflow.json` (the multiview variant of Hy3D)                                                                                                                                                    |
| Rig a character                                         | `3d/workflows/unirig-humanoid-workflow.json` (bpy via pixi — **Linux only**)                                                                                                                                                   |
| **Check the docs** (tables/links) before committing     | `scripts/lint_docs.py`                                                                                                                                                                                                         |
| **Know what will and won't run here**                   | **[`comfyui/hardware.md`](comfyui/hardware.md)** — read *before* pulling a large model                                                                                                                                         |
| Use the server / fix a crash                            | [`comfyui/README.md`](comfyui/README.md) → gotchas · [`comfyui/setup.md`](comfyui/setup.md)                                                                                                                                    |
| Set up a new machine                                    | [`comfyui/linux-setup.md`](comfyui/linux-setup.md) · [`comfyui/linux-migration.md`](comfyui/linux-migration.md)                                                                                                                |
| Upgrade the hardware                                    | **[`comfyui/UPGRADE-TODO.md`](comfyui/UPGRADE-TODO.md)**                                                                                                                                                                       |
| Decide whether a tool is still the right one            | **[`2d/AUDIT-tooling-2026-09.md`](2d/AUDIT-tooling-2026-09.md)** — best-available vs installed, incl. licences                                                                                                                 |

---

## What exists today

| | |
|---|---|
| **2D assets** | 38 curated (`assets/2d/`) — characters, props, environments, pixel sprites, atlases, seamless + PBR textures |
| **3D assets** | 5 (`assets/3d/`) — a generated glTF PBR material + a mesh wearing it |
| **Workflows** | 23 curated graphs (`2d/workflows/`, `3d/workflows/`) |
| **Scripts** | 6 (`scripts/`) — generator, sweeper, compose, Marigold PBR, glTF material, publish |
| **Evidence** | 39 comparison sheets (`2d/evidence/`) — every claim has a picture |
| **Status** | 2D ladder **E1–E16 complete** · upgrades **U1–U7 complete** (bar low-value extras) · 3D scenario complete |

**Licence posture:** the stack is Apache-2.0/BSD-clean with **one exception** — `insightface`
(used by `instantid-character.json` and `pulid-identity.json`) is non-commercial research-only.
Everything else, including Kontext's replacement, is shippable. See
[`2d/AUDIT-tooling-2026-09.md`](2d/AUDIT-tooling-2026-09.md).

---

## How to run things

A remote Linux box runs ComfyUI as a **systemd *user* service**. We drive it over
the API and over SSH. Full detail: [`comfyui/README.md`](comfyui/README.md), [`HANDOFF.md`](HANDOFF.md).

We rely on two rules:

1. **Prefer scripts over GUI clicks.** Every run is a scripted replayable command. That is why the repo has `scripts/` rather than screenshots.
2. **One knob at a time**, and every run gets a row in the scenario's `EXPERIMENTS.md` with a verdict. See [`2d/PROTOCOL.md`](2d/PROTOCOL.md) for the contract.

**Note:** *a metric is a hint, the image is the truth.* This has bitten us three times (E7 seamless, E15 regional, U6b ControlNet). Whenever a number and your eyes disagree, look at the picture.

---

## Where the knowledge lives

| doc | answers |
|---|---|
| [`PIPELINES.md`](PIPELINES.md) | what we can do — family × subject × domain, with status |
| [`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md) | every 2D run: parameters, verdict, reasoning, corrections |
| [`2d/PROTOCOL.md`](2d/PROTOCOL.md) | the canonical asset set and the run/promotion rules |
| [`2d/ROADMAP-2D.md`](2d/ROADMAP-2D.md) | tracks A–J, the E/U backlog, and what's left |
| [`2d/AUDIT-tooling-2026-09.md`](2d/AUDIT-tooling-2026-09.md) | are we using the best tool? (quality + licence + cost to switch) |
| [`comfyui/README.md`](comfyui/README.md) | **node gotchas** — the highest-density page in the repo |
| [`comfyui/hardware.md`](comfyui/hardware.md) | measured model footprints; what fits |
| [`comfyui/workflow-file-format.md`](comfyui/workflow-file-format.md) | how to hand-edit a workflow `.json` safely |
| [`3d/README.md`](3d/README.md) · [`3d/pipeline-design.md`](3d/pipeline-design.md) | the 3D scenario and its architecture |

---

## Known gaps (honest, current)

**Engine-readiness.** Assets are in Unity-*compatible formats*, but the **import contract is missing**:
no `.meta`/`.mat` files, and Unity's defaults are actively wrong for our asset types — pixel art gets
bilinear-filtered and compressed; PBR maps import as sRGB; the atlas needs slice rects; there is no
PPU/pivot/world-scale convention. Also note the **packing difference**: our material is *glTF*-correct
(metallicRoughness = G rough, B metal), while Unity's shaders want R metal, A smoothness. Neither
engine has ever been opened to verify any of it.

**Other open items**

- No occlusion/AO map (Marigold IID emits none — don't fake it).
- Animation is untouched as a domain (new scenario folder; partly gated on more RAM).
- 23 workflows, but no single entry point that emits "a game asset set".
- `Rigged`/animated characters aren't in the repo (UniRig's Mixamo FBX lives only on the box) and no
  clips exist.
- Hardware: the box is **RAM-bound, not VRAM-bound** — see `comfyui/hardware.md` before pulling
  anything large, and `comfyui/UPGRADE-TODO.md` for the plan.

---

## Glossary

- **asset** — a curated, tracked artefact in `assets/`. Value decides inclusion, not file type.
- **flow / workflow** — a ComfyUI graph in a scenario's `workflows/`.
- **knob** — a parameter worth tuning (`strength`, `denoise`, `cfg`, `resolution`…). Each flow's
  entry in `PIPELINES.md` names its most important one.
- **evidence** — a labelled comparison sheet in `2d/evidence/`; no claim without one.
- **promotion** — the deliberate move from a staging dir into `assets/` (`scripts/publish_assets.sh`).
- **verdict** — `PASS` / `MEH` / `BLOCKED` **plus the reason**. The reason is the point.
- **gateway** — a licence or hardware constraint that decides whether output is shippable (e.g. a
  non-commercial checkpoint, or a model too large for the box).
