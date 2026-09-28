# 2D Roadmap: beyond isolated assets

`2d/README.md` defines the **first ladder** (E1–E7): single-subject work, one prompt → one cutout-able asset. This file is the **bigger picture**: everything that turns assets into *images* — scenes, edits, references, consistency, finishing — plus the **tooling upgrade backlog** (see `AUDIT-tooling-2026-09.md`).

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
| **F** | Regional / multi-ref | core `ConditioningSetAreaPercentage` + `ConditioningCombine` | **E15 PASS** |
| **G** | Masking / utility | BiRefNet, **SAM 3 (text-prompted)**, DepthAnythingV2, DSINE | **E3, E12, U6a PASS** |
| **H** | Finishing | Flux Kontext relight, **SeedVR2** (upscale + restore/face restore) | **E13 PASS** |
| **I** | Text / UI | **Z-Image Turbo** (legible text, 20 s) + `vtracer`/`cairosvg` for vector | **PASS, split** (E34: text solved; vector via trace, or authored exactly) |
| **J** | Batch / consistency system | scripts/sweep.py (scripted XY + sheet) | **E16 PASS** |

## Backlog: experiments

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
- [x] **E15 - Regional / multi-subject. PASS 2026-09-16.** Core `ConditioningSetAreaPercentage` + `ConditioningCombine` (no install). A single prompt with both subjects **dropped one entirely**; regional rendered both correctly placed (separation 9.9 -> 30.0). `workflows/regional-prompting.json`.
- [x] **E16 - Batch/iteration. PASS 2026-09-16.** Built scripts/sweep.py (reusable 2-axis harness: labelled sheet + per-cell detail metric + JSON manifest) rather than a GUI XY node - reproducible and headless. Result: **cfg 7 / 20 steps** is SDXL value point; cfg 3 washes out, cfg 9 over-burns, 30 steps buys nothing.


- [ ] **E24 - 2D -> 3D -> pixel-art bridge. Phase 1 PASS 2026-09-28** (facings work at 128 px with one shared palette, and the cape proves the backs are not mirrored; arms measured in E24b: `pixel-art-restyle` (arm b) wins - it keeps the character's design where the direct-2D control is prettier but a different knight; open: arm (b) across facings, and Phase 2 needs the rig - see `EXPERIMENTS-2D.md` E24/E24b). Question: can one 3D model produce a whole facing set - the thing 2D generation cannot do, since a COCO skeleton carries no yaw (E22)? Prereq: we own **no rigged humanoid** (only `assets/3d/stone_statue.glb`), so Phase 0 is `char_knight` -> Hy3D shape -> UniRig -> GLB. Phase 1 (yaw only): Blender orthographic camera, 8 azimuths at 45 deg, one flat key light, 512 px renders; then three stylisation arms - (a) deterministic nearest /8 + palette reduce (~14 colours, no AI), (b) pixel-art model restyle then /16, (c) a moderate-denoise style pass that keeps the render's geometry - judged against a control of a **direct** 2D pixel-art generation of the same character, front view. Phase 2 (poses, only if Phase 1 passes): 3 bone poses at one azimuth. Pick an asymmetric design (sword vs shield) so a mirrored 180 deg facing is detectable. Judge at 1x for identity, palette consistency across facings and the mirror check. Known cap: a single input image means Hy3D **invents the back**, so the invented side bounds the whole turnaround - test that separately by feeding a Qwen-Edit "seen from behind" as the multiview back input.
## Upgrade backlog: best-quality and licence-clean

Full reasoning and sources: **`AUDIT-tooling-2026-09.md`**. Ordered by "unlocks the most downstream steps per GB", licence-clean first. **This list supersedes the old "dependencies to clear" section.**

- [x] **U1. SeedVR2 — DONE 2026-09-16** (Apache 2.0, `numz/ComfyUI-SeedVR2_VideoUpscaler` + weights in `models/SEEDVR2/`). Replaces the non-commercial `4x-UltraSharp` in E4 and E13, and covers face/photo restoration. At 2×: more detail (grad-var **137.0 vs 97.7**) but more drift (**2.70 vs 1.29**) and slower (39 s vs 6 s) — it regenerates rather than enlarges. `workflows/upscale-seedvr2.json`.
- [x] **U2. Qwen-Image-Edit-2511 GGUF - DONE 2026-09-16** (Apache 2.0, `unsloth/...-GGUF` Q4_K_M 12.34 GB + `city96/ComfyUI-GGUF`). **The fp8 build hard-froze the box; the Q4 quant fits and completed in 380 s at a 20.0 GB cgroup peak** (467 soft-limit throttles, 0 hard-limit hits, 0 OOM kills - the service memory guard worked). Far more *faithful* than Flux Kontext, which re-dramatises; 5.5x slower. `workflows/qwen-edit-gguf.json`. *(Original entry: replaces Flux Kontext for E8/E9/E10/E13 with a licence-clean model.)*
- [x] **U3. Z-Image Turbo - DONE 2026-09-16** (Apache 2.0, `z_image_turbo_bf16` + `qwen_3_4b_fp8_mixed` encoder). 8 steps, ~25 s, 19.3 GB peak — modern base art that fits the box. `workflows/z-image-turbo.json`.
- [x] **U4. Marigold intrinsic - DONE 2026-09-16** (CreativeML OpenRAIL++-M, `marigold-iid-appearance/lighting` under `models/diffusers/`). Fixes E12b's inverted metallic (0.36 mean / 0.02% >0.5, against QFX's 0.855 / 85%) though its own value is an estimate. `scripts/marigold_pbr.py`, driven by `scripts/pbr_set.py`.
- [x] **U5. PuLID - DONE 2026-09-16** (SDXL v1.1, `cubiq/PuLID_ComfyUI` + facexlib). Identity with **compositional freedom**: same prompt as E14b gave a full-body scene (face 9.8% of frame, cos 0.313) where InstantID forced a bust (33%, cos 0.823). Not a replacement — a different job. Note it still depends on insightface. `workflows/pulid-identity.json`.
- [x] **U6. Smaller follow-ups - MOSTLY DONE (2026-09-16).** ✅ **SAM 3** text-prompted segmentation (U6a, core nodes) — closed track G's auto-mask half. ✅ **ControlNet-Union SDXL** (U6b) — one 2.34 GB model replaces three specialist CNs (see the silent-`type`-failure gotcha). ✅ **E11 style transfer is covered by Qwen-Edit**: E14c already proved the `image1 + image2` reference mechanism that does exactly this, so the 2024-era IPAdapter path is superseded without a new experiment. □ Remaining (low value): further E16 batch-tooling extensions to `scripts/sweep.py`.

## Dependencies (updated)

- **On the box now:** SD1.5 + SDXL checkpoints (RealVisXL V5.0 is the default), RetroDiffusion ×3, ControlNets (SD1.5 depth/openpose/scribble, xinsir-canny-SDXL, **ControlNet-Union SDXL**), upscalers (`4x-UltraSharp`, `RealESRGAN_x4plus`, **SeedVR2 3B/7B**), `ip-adapter-plus_sdxl_vit-h` + CLIP-ViT-H, codeformer, sam_vit_b, **SAM 3**, **BiRefNet**, BLIP, **Marigold diffusers ×7**, **Flux.1 Kontext dev fp8 + T5 + CLIP-L + `ae.safetensors`**, **InstantID + insightface 2.0 + antelopev2**, **PuLID + facexlib**, **Z-Image Turbo**, **Qwen-Image-Edit-2511** (GGUF Q4_K_M + fp8), **Qwen-Image-Edit-2509-Relight LoRA**, and the QFX/Material-Map-Generator PBR nodes.
- **Still absent:** nothing we currently need — the whole U1–U7 set is on disk. Deliberately skipped: **SAM 2** (SAM 3 supersedes it) and a Flux *generation* checkpoint (Z-Image Turbo / Qwen cover it).
- **Licence watch-list** (do not ship output): **Retro Diffusion pixel-art models** (non-commercial), **DSINE** (non-commercial; removed from `depth-normal.json`), Flux.1 dev / Kontext dev, SUPIR, `4x-UltraSharp`, StableSR, InvSR, insightface pretrained models (InstantID/PuLID), CodeFormer (verify). **Territorial:** Hy3D (Tencent Hunyuan 3D licence — no EU/UK/South Korea). See `PIPELINES.md`'s licence column.

## 2D→3D bridge (U7)

- [x] **U7. glTF PBR material from 2D maps — DONE 2026-09-16.** `scripts/make_gltf_material.py` turns 2D-generated maps (Marigold albedo/roughness/metallic + DSINE normal) into a **glTF-valid, engine-importable material**, and optionally applies it to a mesh and exports a GLB. Verified from the exported GLB's embedded texture: G=roughness, B=metallic, factors 1.0/1.0.
- **Not RAM-bound** — everything it uses already fits (Marigold ~2.5 GB, QFX small, Hy3D mesh). No need to wait for the RAM upgrade.
- **Flagged:** the committed `assets/3d/stone_material/` predates `scripts/pbr_set.py` — its normal is **DSINE-derived** (non-commercial, camera-space). Regenerate it before shipping anything that depends on it.
- **Closed since:** occlusion is now produced (QFX supplies AO; `pbr_set.py` packs an `occlusionTexture`), and the normal's Y convention is **checked** rather than assumed — the packed normal agrees with QFX's own height map under glTF/OpenGL (mean cos **+0.38** over 71% of tilted pixels, vs −0.10 flipped).
- **Still open:** a visual check in a real engine (Unity/Godot) — this box has none; and the same path should be re-run for a *character* (skin/cloth) to prove it generalises beyond hard-surface materials.

## Cross-scenario links

- **3D** — E7 tileable + E12 depth/normal maps feed 3D texturing and 2.5D.
- **Animation (future)** — E14 consistency is the prerequisite for frame-to-frame characters; SeedVR2 (U1) also serves video.
- **Vault** — `C:\Vault\Notes\Generative AI solutions.md` stays the high-level map; this file is operational.

## Open questions

1. **Re-baseline E1 on Qwen-Image (U3)?** It would invalidate the E1d set's "best model" claim and therefore its derivatives. Cheaper path: keep the E1d set as the **fixture** for exercising methods, and add a production set once we ship.
2. *(Resolved in practice, 2026-09-19.)* **How much do we care about commercial cleanliness now?** If the goal stays learning, Kontext/ InstantID remain usable and we only *record* the constraint.
3. *(Answered by U2.)* **Is 24 GB enough for Qwen-Image at fp8?** ~20 GB of weights plus a 7B VL encoder needs offloading — expect slower iteration and OOM pressure.
4. *(Done: both.)* Do E15/E16 first, or start the upgrade backlog? *(Current call: decide before E15 — see audit "Recommended order".)*
