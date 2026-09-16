# PIPELINES — the capability map

**The problem this file solves.** `2d/` and `3d/` say *what you are making*, but our flows are
increasingly *operations* that cut across that: `seamless-texture` serves 2D backgrounds **and**
3D materials; `ipadapter-style` works on objects and on scenes; `pixel-art` is a stylisation, not
a scenario. So scenario folders no longer answer "which tool for this job?".

**Where things live:** scenario folders keep *assets, experiments and scenario docs*.
This file is the **capability index** — every flow, what operation it performs, on what kind of
subject, and its status. When in doubt, start here.

## Axis 1 — operation family (what transformation it performs)

| # | family | question it answers | flows |
|---|---|---|---|
| 1 | **generate** | prompt → brand-new image | `sdxl-base-art` |
| 2 | **guide** | generation constrained by structure or reference | `sdxl-controlnet-canny`, `ipadapter-style` |
| 3 | **stylize** | rerender into a disciplined style/palette | `pixel-art` |
| 4 | **isolate** | subject out of background; masks | `remove-bg` (+ SAM in E12) |
| 5 | **edit** | change part of an existing image | `inpaint` (+ outpaint in E9) |
| 6 | **finish** | resolution / restoration / grading | `upscale` (+ face restore, relight) |
| 7 | **surface** | tileable textures and PBR material sets | `seamless-texture` (+ PBR in E12b) |
| 8 | **assemble** | atlases, grids, multi-image composition | `sprite-atlas` (+ E10 composition) |
| 9 | **reconstruct** | image → 3D geometry / texture / rig | `hy3d-full-workflow`, `hy3d-multiview-workflow`, `unirig-humanoid-workflow` |

## Axis 2 — subject & domain (what it is applied to)

- **subject**: `object` (single prop/character) · `scene` (composite picture) · `material` (flat surface/texture)
- **domain**: `image` (2D pixels) · `texture` (2D, tiling/PBR-authoring) · `3D` (mesh)

These are *attributes*, not folders — one flow can serve several. Record them per flow in the index.

**Licence column convention: ⚠ = derived from a non-commercial model, fine to learn with, do NOT ship
output.** Confirmed by the 2026-09 audit (`2d/AUDIT-tooling-2026-09.md`): Flux.1 dev / Kontext dev,
SUPIR, `4x-UltraSharp`, StableSR, InvSR, insightface pretrained models (so InstantID/FaceID/PuLID),
CodeFormer (verify). Licence-clean alternatives: Qwen-Image + Qwen-Image-Edit (Apache 2.0),
SeedVR2 (Apache), Real-ESRGAN (BSD), 4xNomos2 (CC-BY), Z-Image / Chroma / FLUX.2 klein 4B (Apache).

## Index

| flow | family | subject | domain | cost | licence | key knob | status |
|---|---|---|---|---|---|---|---|
| `2d/workflows/z-image-turbo.json` | generate | object/scene | image | Z-Image 6B | **Apache 2.0** | 8 steps, cfg 1.0, `res_multistep`; `CLIPLoader type="lumina2"`; **photoreal lean** | **PASS** (U3) |
| `2d/workflows/qwen-edit-gguf.json` | edit | scene/object | image | Qwen GGUF Q4 | **Apache 2.0** | GGUF 12.3 GB fits (fp8 19.6 GB froze the box); **faithful** edits, 380–420 s; **multi-image (image1+image2) replaces Kontext for character placement** | **PASS** (U2, E14c) |
| `2d/workflows/regional-prompting.json` | guide | scene | image | free | core | `ConditioningSetAreaPercentage` per region + `ConditioningCombine`; **fixes subject dropout** (a single prompt lost one subject) | **PASS** (E15) |
| `scripts/sweep.py` | assemble | any | image | free | stdlib | 2-axis scripted sweep → labelled sheet + per-cell metric + JSON manifest; **cfg 7 / 20 steps** is SDXL's value point | **PASS** (E16) |
| `2d/workflows/sdxl-base-art.json` | generate | object/scene | image | free | OpenRAIL++ | checkpoint, cfg, steps; **SDXL now a niche pick — see U3** | **PASS** (E1/E1c/E1d) |
| `2d/workflows/sdxl-controlnet-canny.json` | guide | object/scene | image | free | OpenRAIL++ | `strength` (0.8), canny thresholds | **PASS** (E2b) |
| `2d/workflows/ipadapter-style.json` | guide | object/scene | image | free | (verify) | **IPAdapter `weight` 0.2–0.4 style / ≥0.6 takeover** | **PASS** (E11) |
| `2d/workflows/pixel-art.json` | stylize | object | image | free | RD licence (verify) | model grid factor (nearest ÷8 or ÷16), palette 16 | **PASS** (E5/E5b/E5f) |
| `2d/workflows/remove-bg.json` | isolate | object | image | free | MIT | BiRefNet; **must `InvertMask`** | **PASS** (E3b) |
| `2d/workflows/inpaint.json` | edit | scene/object | image | free | OpenRAIL++ | mask; **composite back with the mask** | **PASS** (E8) |
| `2d/workflows/upscale-seedvr2.json` | finish | any | image/texture | free | Apache 2.0 | `resolution` = **short edge**; `batch_size` 4n+1; more detail, more drift; **set `resolution` = image size for *restore* mode (E13 face restore: detail 15.7→35.5, identity cos 0.926)** | **PASS** (U1, E13f) |
| `2d/workflows/upscale.json` | finish | any | image/texture | free | ⚠ **4x-UltraSharp is non-commercial** | model: 4x-UltraSharp for art; faithful/smooth, superseded by SeedVR2 (U1) | **PASS** (E4b) |
| `2d/workflows/seamless-texture.json` | surface | material | texture | free | GPL-3 | `SeamlessTiling(method=offset)` | **PASS** (E7c) |
| `2d/workflows/sprite-atlas.json` | assemble | object | image | free | n/a | `ImageGrid(columns)`, tile w/h | **PASS** (E6) |
| `2d/workflows/outpaint.json` | edit | scene/object | image | free | GPL-3 | `InpaintCropImproved` `extend_*_factor` + `InpaintStitchImproved` | **PASS** (E9) |
| `2d/workflows/compose-harmonize.json` | assemble | scene | image | free | GPL-3 | `InpaintCropImproved` + denoise **0.45 = integrate / 0.75 = replace** | **PASS** (E10) |
| `2d/workflows/kontext-edit.json` | finish | any | image | Flux Kontext fp8 | ⚠ non-commercial + **~1 MP ceiling** | instruction edit (relight); upscale tail mandatory | **PASS** (E13) |
| `2d/workflows/kontext-character.json` | assemble | object | image | Flux Kontext fp8 | ⚠ non-commercial | 2× `ReferenceLatent` (scene+character); design only, **not** identity (face cos 0.187) | **PASS** (E14a) |
| `2d/workflows/instantid-character.json` | assemble | object | image | InstantID + SDXL | ⚠ insightface models are non-commercial research | face identity (cos **0.823**); face-only, bust framing | **PASS** (E14b) |
| `2d/workflows/depth-normal.json` | isolate | object/scene | image | free | Apache | DepthAnythingV2 + DSINE | **PASS** (E12) |
| `scripts/marigold_pbr.py` | surface | material | texture→3D | free | Apache 2.0 | Marigold intrinsic; **correct metallic**; albedo is de-lit; ≤768 px | **PASS** (U4) |
| `2d/workflows/pbr-from-texture.json` | surface | material | texture→3D | free | (verify) | `QFXPBRGenerator`; **metallic inverted** — use `marigold_pbr.py` instead | **PASS w/ caveat** (E12b) |
| `3d/workflows/hy3d-full-workflow.json` | reconstruct | object | 3D | free | (verify) | Hy3D shape→texture→bake | **PASS** (E2a–e) |
| `3d/workflows/hy3d-multiview-workflow.json` | reconstruct | object | 3D | free | (verify) | mv model + uniform 512² views | **PASS** (E2d) |
| `3d/workflows/unirig-humanoid-workflow.json` | reconstruct | character | 3D | free | (verify) | UniRig (bpy via pixi) | **PASS** (E4-L) |

## Planned / not yet built

| family | next | notes |
|---|---|---|
| isolate | ~~E12 depth/normal/SAM masks~~ **done** | depth+normal landed; SAM masks still open |
| surface | ~~E12b texture → PBR set~~ **done (caveat: metallic)** | `QFXPBRGenerator`; the 2D↔3D crossover |
| edit | ~~E9~~ · ~~E10~~ · ~~E13~~ · ~~E14 consistency~~ **done** · E15 regional **done (fixes subject dropout)** | E16 batch next | **Flux.1 Kontext fp8 + InstantID added 2026-09-16** — the box is no longer SD1.5/SDXL-only. Matching tool to job: Kontext = design/scene edit, InstantID = faces |
| finish | E13 face restore | CodeFormer linked but unrun, **and likely non-commercial** — verify or use SeedVR2 (U1) |

## Upgrade backlog

Best-quality / licence-clean swaps, from `2d/AUDIT-tooling-2026-09.md`: **U1 SeedVR2** (kills the ⚠ on upscale) · **U2 Qwen-Image-Edit-2511** (replaces Kontext: Apache 2.0, native 2K, multi-image refs, Relight LoRA) · **U3 Qwen-Image-2512** (replaces SDXL base art; shares U2's encoder+VAE) · **U4 Marigold intrinsic** (fixes E12b, already on disk) · **U5 PuLID-Flux** · **U6** union ControlNet, ref-based style, SAM 2, batch tooling.
| guide | E14 consistency (InstantID/FaceID) | weights not pulled |
| guide | E15 regional / multi-subject | nodes present |
| generate | E16 batch/iteration system | XY plots, seeds |

## Conventions

- **Name flows `<family>-<detail>.json`** in future so the flat folder is self-describing
  (existing files predate this and keep their names — renaming would churn every doc reference).
- Every flow gets: a row in the scenario's `EXPERIMENTS.md` (verdict + why) **and** a row here.
- Paid/API stages are marked `paid` in the cost column; keep them behind a GLB/PNG gate.
