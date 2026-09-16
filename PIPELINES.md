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

## Index

| flow | family | subject | domain | cost | key knob | status |
|---|---|---|---|---|---|---|
| `2d/workflows/sdxl-base-art.json` | generate | object/scene | image | free | checkpoint, cfg, steps | **PASS** (E1/E1c/E1d) |
| `2d/workflows/sdxl-controlnet-canny.json` | guide | object/scene | image | free | `strength` (0.8), canny thresholds | **PASS** (E2b) |
| `2d/workflows/ipadapter-style.json` | guide | object/scene | image | free | **IPAdapter `weight` 0.2–0.4 style / ≥0.6 takeover** | **PASS** (E11) |
| `2d/workflows/pixel-art.json` | stylize | object | image | free | model grid factor (nearest ÷8 or ÷16), palette 16 | **PASS** (E5/E5b/E5f) |
| `2d/workflows/remove-bg.json` | isolate | object | image | free | BiRefNet; **must `InvertMask`** | **PASS** (E3b) |
| `2d/workflows/inpaint.json` | edit | scene/object | image | free | mask; **composite back with the mask** | **PASS** (E8) |
| `2d/workflows/upscale.json` | finish | any | image/texture | free | model: **4x-UltraSharp** for art | **PASS** (E4b) |
| `2d/workflows/seamless-texture.json` | surface | material | texture | free | `SeamlessTiling(method=offset)` | **PASS** (E7c) |
| `2d/workflows/sprite-atlas.json` | assemble | object | image | free | `ImageGrid(columns)`, tile w/h | **PASS** (E6) |
| `2d/workflows/depth-normal.json` | isolate | object/scene | image | free | DepthAnythingV2 + DSINE | **PASS** (E12) |
| `2d/workflows/pbr-from-texture.json` | surface | material | texture→3D | free | `QFXPBRGenerator`; **metallic output suspect** | **PASS w/ caveat** (E12b) |
| `3d/workflows/hy3d-full-workflow.json` | reconstruct | object | 3D | free | Hy3D shape→texture→bake | **PASS** (E2a–e) |
| `3d/workflows/hy3d-multiview-workflow.json` | reconstruct | object | 3D | free | mv model + uniform 512² views | **PASS** (E2d) |
| `3d/workflows/unirig-humanoid-workflow.json` | reconstruct | character | 3D | free | UniRig (bpy via pixi) | **PASS** (E4-L) |

## Planned / not yet built

| family | next | notes |
|---|---|---|
| isolate | ~~E12 depth/normal/SAM masks~~ **done** | depth+normal landed; SAM masks still open |
| surface | ~~E12b texture → PBR set~~ **done (caveat: metallic)** | `QFXPBRGenerator`; the 2D↔3D crossover |
| edit | E9 outpaint · E10 composition | core nodes only |
| finish | E13 face restore / IC-Light relight | CodeFormer linked; IC-Light to install |
| guide | E14 consistency (InstantID/FaceID) | weights not pulled |
| guide | E15 regional / multi-subject | nodes present |
| generate | E16 batch/iteration system | XY plots, seeds |

## Conventions

- **Name flows `<family>-<detail>.json`** in future so the flat folder is self-describing
  (existing files predate this and keep their names — renaming would churn every doc reference).
- Every flow gets: a row in the scenario's `EXPERIMENTS.md` (verdict + why) **and** a row here.
- Paid/API stages are marked `paid` in the cost column; keep them behind a GLB/PNG gate.
