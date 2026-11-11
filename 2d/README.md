# 2D Asset Generation: scenario index

Goal: produce game-ready 2D assets (base art, sprites, textures, UI, pixel art, icons, BGs) on the ComfyUI server. This becomes the **high-volume** pipeline — env props, characters sheets, spritesheets, tileable textures, promotional art.

> Comes after the `3d/` scenario, which banked all the transferable ComfyUI infra (workflows, `/object_info` habit, environments).

## What the server has (verified 2026-11-10, from disk)

**Base models available** (`models/checkpoints`, 129 GB total):

| Model | Use |
|---|---|
| RealVisXL_V5.0 (+ Lightning baked-VAE variant) | realistic humans; flow default |
| sd_xl_base_1.0 + refiner | general SDXL baseline |
| juggernautXL / dreamshaper / architecturerealmix / realisticVision / AnythingXL | general high-quality |
| protogen anime / ponyDiffusionV6 / chilloutmix | anime/stylized |
| chilloutmix / Deliberate_v2 / v1.5-pruned | SD1.5 ecosystem (LoRA-rich) |
| **RetroDiffusion** (16x / 24-64x / 128x) | **pixel-art generation** (purchased; outputs are the user's) |
| 512-inpainting-ema | inpainting |
| sv3d_p | turnarounds (multi-view orbit) |
| ltxv 13B + 2B (distilled fp8) | video (not 2D canvas) |
| ace_step 1.5 + v1 3.5b / stable_audio_3 / yue2 int8 | audio (not 2D canvas) |

**LoRAs present** (`models/loras`): `pixel-art-xl`, Qwen relight, WanAnimate relight, lightx2v I2V, wan2.2 cover, z-image-turbo patch. Vendor-recommended settings live on each model's own page (CivitAI etc.) — the repo records measured knobs per flow instead of duplicating them.

**Node packs present:** Flux CLIP/es, ControlNet (ACN, SD1.5/3/Flux), IPAdapter, LoRA hooks, KSampler family, SUPIR/RealESRGAN upscalers, rembg, seamless-tiling, ColorMatch, WAS (resize, masks, etc.).

**Not present (note for future):** no Flux *checkpoint* (only Flux CLIP/controlnet tooling).

## Design: first experiments

Same methodology as `3d/`:
- Valuable workflows in `workflows/`, scaffolding → `workflows/scratch/`, one `EXPERIMENTS-2D.md`, one `README` per scenario.
- Free-first; pay at the margins.
- The **ladder** (from the cheatsheet): base art → control (pose/edge/composition) → upscale → remove-BG → spritesheet/atlas → pixelate/recolor/vectorize/font.

**Suggested E1..En (each ~30–60 min):**
1. **E1 — SDXL base art** (prose→hero image), learn KSampler/CFG/resolution basics. Input: prompt; output PNG.
2. **E2 — ControlNet pose/edge** — composer (pose) or canny → controlled base art. Input: prompt + control image (sketch/pose).
3. **E3 — remove-BG / isolate** (rembg/BRIA) — sprite out of an illustration.
4. **E4 — upscale** (SUPIR/RealESRGAN) — final res bump for prints/UI.
5. **E5 — pixel-art downscale** (RetroDiffusion or "downsample hi-res" trick from the cheatsheet).
6. **E6 — spritesheet/atlas** — row/col slicing of a strip → per-frame assets (feed 3D/fx later).
7. **E7 — tileable texture** (seamless-tiling) — for env assets; cross-pollinates with 3D texturing.

## Docs

- `PROTOCOL.md` — the **experiment protocol**: canonical asset set, run/sweep rules, evaluation, promotion.
- `ROADMAP-2D.md` — the **bigger picture**: tracks beyond isolated assets (inpaint, outpaint, composition, IPAdapter/reference transfer, consistency, finishing) + the full E-number backlog **and the tooling upgrade backlog (U1–U6)**.
- `AUDIT-tooling-2026-09.md` — **are we using the best available?** Per-step comparison of what we use vs. current best, incl. **licence** (several of our tools are non-commercial) and the cost to switch. Read this before choosing a tool for new work.
- `EXPERIMENTS-2D.md` — run log (verdicts with *why*).
- `workflows/` — valuable pipelines; `workflows/scratch/` — scaffolding.
- `../scripts/gen_assets.py` — generator for the canonical `input/2d/` asset set (E1b).

(this README grows as experiments land)