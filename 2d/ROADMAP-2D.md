# 2D Roadmap — beyond isolated assets

`2d/README.md` defines the **first ladder** (E1–E7): single-subject work, one prompt → one
cutout-able asset. This file is the **bigger picture**: everything that turns assets into
*images* — scenes, edits, references, consistency, finishing — plus the **tooling upgrade
backlog** (see `AUDIT-tooling-2026-09.md`).

2D work splits along two axes. As of 2026-09-16 **every cell has at least one PASS**:

```
                 generate              edit
    isolated     E1  base art ✅        E3  remove-BG ✅
    (one subject) E2  control art ✅     E5  pixelate ✅
                 E4  upscale ✅         E6  spritesheet ✅
                 E7  tileable ✅        E12 depth/normal/PBR ✅
    scene /      E10 composition ✅     E8  inpaint ✅
    picture      E11 ref/style ✅       E9  outpaint ✅
                 E14 consistency ✅     E13 relight / finish ✅
```

## Tracks

| # | Track | Core nodes / models **in use** | Status |
|---|---|---|---|
| **A** | Isolated assets | SDXL (RealVisXL), ACN, BiRefNet, RetroDiffusion, 4x-UltraSharp | **E1–E7 PASS** |
| **B** | Inpainting / editing | CropAndStitch (`InpaintCropImproved`/`InpaintStitchImproved`) | **E8 PASS** |
| **C** | Composition | `scripts/compose_scene.py` + CropAndStitch harmonize | **E10 PASS** |
| **D** | Image→image / references | IPAdapter-plus SDXL; Flux Kontext multi-reference | **E11, E14a PASS** |
| **E** | Character consistency | InstantID + insightface; Kontext design refs | **E14 PASS** |
| **F** | Regional / multi-ref | attention-couple / conditioning-set-mask | **E15 open** |
| **G** | Masking / utility | BiRefNet, DepthAnythingV2, DSINE | **E3, E12 PASS** (SAM still open) |
| **H** | Finishing | Flux Kontext relight, 4x-UltraSharp, CodeFormer (linked, unrun) | **E13 PASS** |
| **I** | Text / UI | — (Flux text encoders now present, no generation model yet) | **open** |
| **J** | Batch / consistency system | XY plots, seeded grids | **E16 open** |

## Backlog — experiments

### Ladder A (done)
- [x] **E1** — base art + model shoot-out (RealVisXL_V5.0_fp16) ✓ · E1b–E1e
- [x] **E2** — ControlNet pose/canny ✓
- [x] **E3** — remove-BG (BiRefNet) ✓
- [x] **E4** — upscale (4x-UltraSharp) ✓
- [x] **E5** — pixel art (RetroDiffusion) ✓
- [x] **E6** — spritesheet build + slice ✓
- [x] **E7** — tileable texture ✓

### Tracks B–J (done)
- [x] **E8** inpaint · **E9** outpaint · **E10** composition · **E11** ref/style
- [x] **E12** depth/normal · **E12b** texture→PBR (caveat: metallic inverted)
- [x] **E13** finishing/relight (Kontext) · **E14** consistency (Kontext vs InstantID)

### Remaining in order
- [ ] **E15 — Regional / multi-subject.** Regional prompting / attention-couple; multiple characters.
- [ ] **E16 — Batch/iteration system.** XY plots, seeds, prompt grids — the "sheet" primitive at scale.

## Upgrade backlog — best-quality & licence-clean

Full reasoning and sources: **`AUDIT-tooling-2026-09.md`**. Ordered by "unlocks the most
downstream steps per GB", licence-clean first. **This list supersedes the old
"dependencies to clear" section.**

- [x] **U1. SeedVR2 — DONE 2026-09-16** (Apache 2.0, `numz/ComfyUI-SeedVR2_VideoUpscaler` + weights in
      `models/SEEDVR2/`). Replaces the non-commercial `4x-UltraSharp` in E4 and E13, and covers
      face/photo restoration. At 2×: more detail (grad-var **137.0 vs 97.7**) but more drift
      (**2.70 vs 1.29**) and slower (39 s vs 6 s) — it regenerates rather than enlarges.
      `workflows/upscale-seedvr2.json`.
- [ ] **U2. Qwen-Image-Edit-2511** (Apache 2.0, `qwen_image_edit_2511_fp8mixed` 19.1 GB) + VL
      encoder + VAE (~28 GB total, shared with U3) — replaces Flux Kontext for E8/E9/E10/E13:
      **native 2K** (kills Kontext's ~1 MP ceiling and its mandatory upscale tail), multi-image
      refs, multi-person fusion, native ControlNet, and a **`Relight` LoRA** (0.2 GB).
      Also the licence-clean answer for E14 consistency.
- [ ] **U3. Qwen-Image-2512** (Apache 2.0, 19.0 GB — **reuses U2's encoder/VAE**) — replaces SDXL
      as the base-art model for E1; re-run the E1c shoot-out on a modern footing.
- [ ] **U4. Marigold intrinsic** (`iid-lighting` / `iid-appearance` — **already on disk**) — fixes
      E12b's inverted metallic via intrinsic decomposition. No download.
- [ ] **U5. PuLID-Flux** — licence-cleaner and far less pose-locked than InstantID; **check the
      insightface terms first**, since that is the real restriction.
- [ ] **U6. Smaller follow-ups:** E2 ControlNet-Union SDXL (one model, many modes); E11 style via
      Qwen/Redux refs instead of 2024-era IPAdapter; E13 face restore (CodeFormer is likely
      non-commercial — verify or swap); SAM 2 for the still-open auto-mask half of track G;
      E16 batch tooling.

## Dependencies (updated)

- **On the box now:** SD1.5 + SDXL checkpoints, RetroDiffusion ×3, ControlNets (SD1.5 depth/
  openpose/scribble, xinsir-canny-SDXL), upscalers (`4x-UltraSharp`, `RealESRGAN_x4plus`),
  `ip-adapter-plus_sdxl_vit-h` + CLIP-ViT-H, codeformer, sam_vit_b, BLIP, Marigold diffusers ×5,
  **Flux.1 Kontext dev fp8 + T5 + CLIP-L + `ae.safetensors`**, **InstantID + insightface 2.0 +
  antelopev2**.
- **Still absent:** Qwen-Image family (U2/U3), SeedVR2 (U1), PuLID (U5), SAM 2, a Flux
  *generation* (non-editing) checkpoint.
- **Licence watch-list** (non-commercial — do not ship output): Flux.1 dev / Kontext dev, SUPIR,
  `4x-UltraSharp`, StableSR, InvSR, insightface pretrained models, CodeFormer (verify).

## Cross-scenario links

- **3D** — E7 tileable + E12 depth/normal maps feed 3D texturing and 2.5D.
- **Animation (future)** — E14 consistency is the prerequisite for frame-to-frame characters;
  SeedVR2 (U1) also serves video.
- **Vault** — `C:\Vault\Notes\Generative AI solutions.md` stays the high-level map; this file is operational.

## Open questions

1. **Re-baseline E1 on Qwen-Image (U3)?** It would invalidate the E1d set's "best model" claim and
   therefore its derivatives. Cheaper path: keep the E1d set as the **fixture** for exercising
   methods, and add a production set once we ship.
2. **How much do we care about commercial cleanliness now?** If the goal stays learning, Kontext/
   InstantID remain usable and we only *record* the constraint.
3. **Is 24 GB enough for Qwen-Image at fp8?** ~20 GB of weights plus a 7B VL encoder needs
   offloading — expect slower iteration and OOM pressure.
4. Do E15/E16 first, or start the upgrade backlog? *(Current call: decide before E15 — see audit
   "Recommended order".)*
