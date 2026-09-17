# PIPELINES — the capability map

**The problem this file solves.** `2d/` and `3d/` say *what you are making*, but our flows are
increasingly *operations* that cut across that: `seamless-texture` serves 2D backgrounds **and**
3D materials; `ipadapter-style` works on objects and on scenes; `pixel-art` is a stylisation, not
a scenario. So scenario folders no longer answer "which tool for this job?".

**Where things live:** scenario folders keep *assets, experiments and scenario docs*.
This file is the **capability index** — every flow, what operation it performs, on what kind of
subject, and its status.

**Which file do I want?** Three complementary views, all sharing the taxonomy below:

- **have a job** ("I need a cutout", "I need PBR maps") -> **[`HOWTO.md`](HOWTO.md)** for the steps,
  knobs and traps, plus the "I want to…" table in [`README.md`](README.md) for which flow.
- **want the landscape** (what families exist, what's supported, what licence, what knobs) -> this file.
- **adding a flow** -> this file: give it a family, subject, domain, cost, licence and key knob.

## Axis 1 — operation family (what transformation it performs)

| # | family | question it answers | flows |
|---|---|---|---|
| 1 | **generate** | prompt -> brand-new artefact of the target domain | `sdxl-base-art`, `z-image-turbo` |
| 2 | **guide** | generation constrained by structure **or reference** | `sdxl-controlnet-canny`, `controlnet-union`, `ipadapter-style`, `regional-prompting`, `kontext-character`, `instantid-character`, `pulid-identity` |
| 3 | **stylize** | rerender into a disciplined style/palette | `pixel-art` |
| 4 | **isolate** | subject out of background; masks and per-pixel maps | `remove-bg`, `sam3-segment`, `depth-normal` |
| 5 | **edit** | change part of an existing image | `inpaint`, `outpaint`, `kontext-edit` |
| 6 | **finish** | resolution / restoration / grading | `upscale`, `upscale-seedvr2` |
| 7 | **surface** | tileable textures and PBR material sets | `seamless-texture`, `pbr-from-texture`, `marigold_pbr`, `make_gltf_material` |
| 8 | **assemble** | atlases, grids, multi-image composition | `sprite-atlas`, `compose-harmonize` (+ `compose_scene.py` for placement) |
| 9 | **reconstruct** | image -> 3D geometry / texture / rig | `hy3d-full-workflow`, `hy3d-multiview-workflow`, `unirig-humanoid-workflow` |
| 10 | **tooling** | *not* an operation on an asset - harnesses for reproducing or exploring | `gen_assets.py`, `publish_assets.sh`, `sweep.py`, `lint_docs.py` |

Read the family as the answer to "what does this flow *do to* an asset?". A harness such as the
sweep runner does nothing to an asset, so it is `tooling` rather than pretending to be an operation.

## Axis 2 — subject & domain (what it is applied to)

- **subject**: `object` (single prop/character) · `scene` (composite picture) · `material` (flat surface/texture)
- **domain**: `image` (2D pixels) · `texture` (2D, tiling/PBR authoring) · `3D model` (mesh)

These are *attributes*, not folders — one flow can serve several. Record them per flow in the index.

**Extending to new modalities** (`animation`, `audio` are planned scenario folders). Operation
families are deliberately **modality-agnostic**: `generate` means *prompt → brand-new artefact*,
whether that artefact is an image, a clip or a sound. So a new modality should arrive as **new `domain`
values** (`animation`, `audio`) on the *existing* families — not as new families. Text-to-music would
be `generate / scene / audio`, not a family called "compose".

One honest caveat: the `subject` vocabulary (`object | scene | material`) is image-flavoured. Audio and
animation may want companions (`clip`, `cue`) — that is an **open question**, recorded here so it
stays a decision rather than an accident.

### Bridge flows (`from->to`)

Some flows do not produce *within* one domain, they **move data between domains**. Rather than
inventing ad-hoc strings, those are written in the domain column in an explicit, defined form:

| written             | means                                                       | flows                                                                                            |
| ------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `texture->3D model` | 2D material authoring becomes data a 3D engine/DCC consumes | `scripts/marigold_pbr.py`, `scripts/make_gltf_material.py`, `2d/workflows/pbr-from-texture.json` |

So a `domain` cell is either one of the three domains above, or an explicit `A->B` bridge. The
per-flow **notes** say what it consumes and what it emits.

## Index

| flow                                         | family      | subject      | domain            | cost              | licence                                          | key knob                                                                                                                                                                                 | status                    | how-to |
|----------------------------------------------|-------------|--------------|-------------------|-------------------|--------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------|--------|
| `2d/workflows/z-image-turbo.json`            | generate    | object/scene | image             | Z-Image 6B        | **Apache 2.0**                                   | 8 steps, cfg 1.0, `res_multistep`; `CLIPLoader type="lumina2"`; **photoreal lean**                                                                                                       | **PASS** (U3)             | S1     |
| `2d/workflows/qwen-edit-gguf.json`           | edit        | scene/object | image             | Qwen GGUF Q4      | **Apache 2.0**                                   | GGUF 12.3 GB fits (fp8 19.6 GB froze the box); **faithful** edits, 380–420 s; **multi-image (image1+image2) replaces Kontext for character placement**                                   | **PASS** (U2, E14c)       | S5, S7 |
| `2d/workflows/regional-prompting.json`       | guide       | scene        | image             | free              | core                                             | `ConditioningSetAreaPercentage` per region + `ConditioningCombine`; **fixes subject dropout** (a single prompt lost one subject)                                                         | **PASS** (E15)            | S6     |
| `scripts/sweep.py`                           | tooling     | any          | image             | free              | stdlib                                           | 2-axis scripted sweep → labelled sheet + per-cell metric + JSON manifest; **cfg 7 / 20 steps** is SDXL's value point                                                                     | **PASS** (E16)            | S12    |
| `scripts/make_gltf_material.py`              | surface     | material     | texture->3D model | free              | n/a                                              | **2D→3D bridge**: packs a glTF-correct material (G=rough, B=metal; factors 1.0) and applies it to a mesh; warns on implausible metallic                                                  | **PASS** (U7)             | S8     |
| `2d/workflows/sdxl-base-art.json`            | generate    | object/scene | image             | free              | OpenRAIL++                                       | checkpoint, cfg, steps; **SDXL now a niche pick — see U3**                                                                                                                               | **PASS** (E1/E1c/E1d)     | S1     |
| `2d/workflows/sdxl-controlnet-canny.json`    | guide       | object/scene | image             | free              | OpenRAIL++                                       | `strength` (0.8), canny thresholds                                                                                                                                                       | **PASS** (E2b)            | S2     |
| `2d/workflows/controlnet-union.json`         | guide       | object/scene | image             | free              | Apache-2.0                                       | **one model, many modes** via `SetUnionControlNetType`; **`type` values are grouped** (`canny/lineart/anime_lineart/mlsd`) and bad values fail **silently in the API**                   | **PASS** (U6b)            | S2     |
| `2d/workflows/ipadapter-style.json`          | guide       | object/scene | image             | free              | (verify)                                         | **IPAdapter `weight` 0.2–0.4 style / ≥0.6 takeover**                                                                                                                                     | **PASS** (E11)            | S13    |
| `2d/workflows/pixel-art.json`                | stylize     | object       | image             | free              | RD licence (verify)                              | model grid factor (nearest ÷8 or ÷16), palette 16                                                                                                                                        | **PASS** (E5/E5b/E5f)     | S10    |
| `2d/workflows/remove-bg.json`                | isolate     | object       | image             | free              | MIT                                              | BiRefNet; **must `InvertMask`**                                                                                                                                                          | **PASS** (E3b)            | S3     |
| `2d/workflows/inpaint.json`                  | edit        | scene/object | image             | free              | OpenRAIL++                                       | mask; **composite back with the mask**                                                                                                                                                   | **PASS** (E8)             | S5     |
| `2d/workflows/upscale-seedvr2.json`          | finish      | any          | image/texture     | free              | Apache 2.0                                       | `resolution` = **short edge**; `batch_size` 4n+1; more detail, more drift; **set `resolution` = image size for *restore* mode (E13 face restore: detail 15.7→35.5, identity cos 0.926)** | **PASS** (U1, E13f)       | S9     |
| `2d/workflows/upscale.json`                  | finish      | any          | image/texture     | free              | ⚠ **4x-UltraSharp is non-commercial**            | model: 4x-UltraSharp for art; faithful/smooth, superseded by SeedVR2 (U1)                                                                                                                | **PASS** (E4b)            | S9     |
| `2d/workflows/seamless-texture.json`         | surface     | material     | texture           | free              | GPL-3                                            | `SeamlessTiling(method=offset)`                                                                                                                                                          | **PASS** (E7c)            | S8     |
| `2d/workflows/sprite-atlas.json`             | assemble    | object       | image             | free              | n/a                                              | `ImageGrid(columns)`, tile w/h                                                                                                                                                           | **PASS** (E6)             | S10    |
| `2d/workflows/outpaint.json`                 | edit        | scene/object | image             | free              | GPL-3                                            | `InpaintCropImproved` `extend_*_factor` + `InpaintStitchImproved`                                                                                                                        | **PASS** (E9)             | S5     |
| `2d/workflows/compose-harmonize.json`        | assemble    | scene        | image             | free              | GPL-3                                            | `InpaintCropImproved` + denoise **0.45 = integrate / 0.75 = replace**                                                                                                                    | **PASS** (E10)            | S6     |
| `2d/workflows/kontext-edit.json`             | edit        | any          | image             | Flux Kontext fp8  | ⚠ non-commercial + **~1 MP ceiling**             | instruction edit (relight); upscale tail mandatory                                                                                                                                       | **PASS** (E13)            | S5     |
| `2d/workflows/kontext-character.json`        | guide       | object       | image             | Flux Kontext fp8  | ⚠ non-commercial                                 | 2× `ReferenceLatent` (scene+character); design only, **not** identity (face cos 0.187)                                                                                                   | **PASS** (E14a)           | S7     |
| `2d/workflows/instantid-character.json`      | guide       | object       | image             | InstantID + SDXL  | ⚠ insightface models are non-commercial research | face identity (cos **0.823**); face-only, bust framing                                                                                                                                   | **PASS** (E14b)           | S7     |
| `2d/workflows/pulid-identity.json`           | guide       | object       | image             | PuLID-SDXL + SDXL | ⚠ insightface                                    | identity with **compositional freedom**: full-body at 9.8% frame vs InstantID's 33% bust; `method` fidelity/style, `weight`                                                              | **PASS** (U5)             | S7     |
| `2d/workflows/sam3-segment.json`             | isolate     | object/scene | image             | SAM 3 1.63 GB     | Apache 2.0                                       | **text-prompted** segmentation; `SAM3_Detect` takes the prompt as `conditioning`; threshold / refine_iterations                                                                          | **PASS** (U6a)            | S3     |
| `2d/workflows/depth-normal.json`             | isolate     | object/scene | image             | free              | Apache                                           | DepthAnythingV2 + DSINE                                                                                                                                                                  | **PASS** (E12)            | S4     |
| `scripts/marigold_pbr.py`                    | surface     | material     | texture->3D model | free              | Apache 2.0                                       | Marigold intrinsic; **correct metallic**; albedo is de-lit; ≤768 px                                                                                                                      | **PASS** (U4)             | S8     |
| `2d/workflows/pbr-from-texture.json`         | surface     | material     | texture->3D model | free              | (verify)                                         | `QFXPBRGenerator`; **metallic inverted** — use `marigold_pbr.py` instead                                                                                                                 | **PASS w/ caveat** (E12b) | S8     |
| `3d/workflows/hy3d-full-workflow.json`       | reconstruct | object       | 3D                | free              | (verify)                                         | Hy3D shape→texture→bake                                                                                                                                                                  | **PASS** (E2a–e)          | S11    |
| `3d/workflows/hy3d-multiview-workflow.json`  | reconstruct | object       | 3D                | free              | (verify)                                         | mv model + uniform 512² views                                                                                                                                                            | **PASS** (E2d)            | S11    |
| `3d/workflows/unirig-humanoid-workflow.json` | reconstruct | object       | 3D                | free              | (verify)                                         | UniRig (bpy via pixi)                                                                                                                                                                    | **PASS** (E4-L)           | S11    |
| `scripts/add_workflow_notes.py`              | tooling     | any          | image             | free              | n/a                                              | migrates a flow's group-title note into a **MarkdownNote** panel (idempotent); `--check` audits coverage                                                                                 | **PASS**                  | S12    |

## Status — what is actually left

The 2D ladder (**E1-E16**) and the upgrade track (**U1-U7**) are complete, and the 3D scenario is
complete. Everything below is genuinely open, roughly in value order.

| # | open item | why it matters | detail |
|---|---|---|---|
| 1 | **Engine import contract** | assets are Unity-*compatible* but **not drop-in**, and Unity's defaults are actively wrong for our types: pixel art gets bilinear-filtered and compressed (needs Point + no compression); PBR maps import as sRGB (need linear, and normals need *Texture Type = Normal map*); `potion_atlas` needs *Sprite Mode = Multiple* + slice rects; there is no PPU/pivot/world-scale convention at all; and there are **zero `.meta`/`.mat` files**. The packing also differs: ours is glTF (`G`=roughness, `B`=metallic), Unity's shaders want (`R`=metal, `A`=smoothness). | U7, E6 | 
| 2 | **No engine has been opened** | the one link we cannot verify from this box; would validate the whole chain end to end (and the normal-map green-channel assumption below) | — |
| 3 | **Occlusion / AO map** | Marigold IID emits none, so occlusion is currently omitted rather than faked | E12b, U4 |
| 4 | **Normal-map green channel** | assumed OpenGL (DSINE's default); `--flip-normal-green` exists but nobody has confirmed it in a real renderer | U7 |
| 5 | **Animation** | untouched as a domain, and the natural next scenario folder; partly gated on more RAM (video models want 16-40 GB) | `3d/`, AGENTS.md |
| 6 | **E1d: fixture or production set?** | do we re-baseline the canonical assets on Z-Image/Qwen, or keep E1d purely as the fixture we exercise methods against? | `2d/ROADMAP-2D.md` |
| 7 | **Batch-tooling extensions** | `scripts/sweep.py` could take checkpoint / prompt axes as well as sampler knobs | E16 |
| 8 | **Hardware** | the box is RAM-bound, not VRAM-bound; Qwen 20B at fp8 does not fit | `comfyui/hardware.md`, `comfyui/UPGRADE-TODO.md` |

**Completed upgrades, for reference** (reasoning in `2d/AUDIT-tooling-2026-09.md` and the E/U log):
**U1 SeedVR2** (licence-clean upscaler, doubles as face restore) · **U2 Qwen-Image-Edit GGUF**
(Apache-2.0; replaces Kontext for E8/E9/E10/E13/E14c) · **U3 Z-Image Turbo** (modern base art that
fits this box) · **U4 Marigold intrinsic** (fixes E12b's inverted metallic) · **U5 PuLID** (identity
with compositional freedom) · **U6a SAM 3** (text-prompted segmentation) · **U6b ControlNet-Union**
(one model, many modes) · **U7 glTF PBR bridge**.

## Conventions

- **Name flows `<family>-<detail>.json`** in future so the flat folder is self-describing
  (existing files predate this and keep their names — renaming would churn every doc reference).
- Every flow gets: a row in the scenario's `EXPERIMENTS.md` (verdict + why) **and** a row here.
- Paid/API stages are marked `paid` in the cost column; keep them behind a GLB/PNG gate.
