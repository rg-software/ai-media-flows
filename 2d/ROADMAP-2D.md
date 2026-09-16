# 2D Roadmap — beyond isolated assets

`2d/README.md` defines the **first ladder** (E1–E7). That ladder is *single-subject* work:
one prompt → one cutout-able asset. This file is the **bigger picture**: everything that
turns assets into *images* — scenes, edits, references, consistency, finishing.

Framing: 2D work splits along two axes.

```
                generate            edit
   isolated     E1  base art         E3  remove-BG
   (one subject) E2  control art      E5  pixelate
                E4  upscale          ...
                E6  spritesheet
                E7  tileable
   scene /      E10 composition       E8  inpaint
   picture      E11 ref/style         E9  outpaint
                E14 consistency       E13 relight / finish
```

E1–E7 (top-left/top-right) are **banked or planned**. The gap the user flagged is the
**bottom row**: "pictures", not "props". This roadmap records that gap so it is tracked,
even while we execute E2→E7 in order.

## Tracks

| # | Track | Use cases | Core nodes / models | Status |
|---|---|---|---|---|
| **A** | Isolated assets | base art, ControlNet, cutout, upscale, pixelate, spritesheet, tileable | SDXL, ACN, rembg, RetroDiffusion, SUPIR | E1 ✅ · E2–E7 planned |
| **B** | Inpainting / editing | remove object, add prop, fix hands/faces, replace sky, extend canvas (outpaint) | SDXL-inpaint, `SetLatentNoiseMask`, `InpaintModelConditioning`, differential diffusion | **weights to pull** |
| **C** | Composition | background + character + props, layered scenes, blockout→render, matte painting | `ImageCompositeMasked`, latent composite, Multi-ControlNet (depth+edge+pose) | nodes ✅ · **workflow to design** |
| **D** | Image→image / references | restyle at strength, style transfer, "make it look like this", pic/pic combos | img2img, **IPAdapter** (+clip vision, +IPAdapter models), reference-only CN | nodes ✅ · **models to pull** |
| **E** | Character consistency | sheets, storyboards, same face across scenes | **IPAdapter FaceID / InstantID** (+antelopev2), LoRA, pose CN | **models to pull** |
| **F** | Regional / multi-ref | different content per region, attention coupling, multi-subject | regional prompter / attention-couple, Multi-IPAdapter | nodes ✅ |
| **G** | Masking / utility | auto-masks for inpaint/cutout, depth/normal extraction | **SAM / GroundingDINO**, DepthAnything | **nodes to install** |
| **H** | Finishing | tiled upscale, face restore, relight, colour grade | Ultimate SD Upscale / SUPIR, CodeFormer, **IC-Light**, ColorMatch | nodes ✅ · IC-Light to pull |
| **I** | Text / UI | logos, icon sets, type lockups | Flux (best at text) | **no Flux checkpoint** |
| **J** | Batch / consistency system | XY plots, prompt travel, seeded variation grids | efficiency-nodes, KSampler grid | partial |

## Backlog

### Track A — isolated assets (current ladder)
- [x] **E1** — SDXL base art (prose → hero image). **PASS on Linux** (smoke; param-tuning run still open).
- [ ] **E2** — ControlNet pose/canny → controlled art. *(in progress; weights to pull)*
- [ ] **E3** — remove-BG (rembg/BRIA) → isolated sprite.
- [ ] **E4** — upscale (SUPIR / RealESRGAN).
- [ ] **E5** — pixel-art (RetroDiffusion, or downsample hi-res).
- [ ] **E6** — spritesheet slicing → per-frame assets.
- [ ] **E7** — tileable texture (seamless-tiling).

### Tracks B–H — pictures, edits, references (proposed)
- [x] **E8 — Inpaint.** Mask → fill. Gateway edit op (remove/add/fix). Enables the rest of B.
- [x] **E9 — Outpaint.** Canvas extension / wide backgrounds. "Make the picture bigger".
- [x] **E10 — Composition.** Background + subject + prop; layered assembly (pic/pic combo, literal).
- [x] **E11 — Reference/style transfer (IPAdapter).** Image *as* style/composition (pic/pic combo, semantic).
- [x] **E12 — Segmentation + depth (SAM / GroundingDINO / DepthAnything).** Auto-masks + depth maps;
      feeds E8–E10 and 2.5D later.
- [x] **E13 — Finishing.** Tiled upscale + face restore + relight + colour match. **PASS** - relight done with **Flux.1 Kontext** (installed; instruction edit beat ColorMatch outright), not IC-Light. Face restore still untested: no asset in the set has a visible face.
- [x] **E14 — Consistency.** InstantID/FaceID + pose CN → character sheets across scenes.
- [ ] **E15 — Regional / multi-subject.** Regional prompting / attention-couple; multiple characters.
- [ ] **E16 — Batch/iteration system.** XY plots, seeds, prompt grids — the "sheet" primitive at scale.

## Dependencies to clear

**Weights (≈6–10 GB, pull once):** SDXL-inpainting, IPAdapter (+ CLIP-Vision + IPAdapter model),
InstantID (+ antelopev2), ControlNet sets (partially present: ACN, SD1.5/3/Flux), SAM/GroundingDINO,
DepthAnything, IC-Light.

**Node packs (may need install):** SAM / GroundingDINO wrappers, IC-Light, maybe efficiency-nodes.

**No Flux checkpoint** on the box — text/UI (track I) needs one pulled if we want it.

## Cross-scenario links

- **3D** — E15 tileable + E12 depth/normal maps feed 3D texturing and 2.5D.
- **Animation (future)** — E14 consistency is the prerequisite for frame-to-frame characters.
- **Vault** — `C:\Vault\Notes\Generative AI solutions.md` stays the high-level map; this file is operational.

## Open questions

1. Do E2→E7 first (finish the isolated-asset ladder), or jump to B/C/D once E2 lands? *(Current call: finish E2, then go wide.)*
2. Which consistency route for characters — InstantID, IPAdapter-FaceID, or LoRA training? (Cost/quality trade.)
3. Do we want a Flux checkpoint for text/UI? (quality win, ~12–24 GB pull.)
