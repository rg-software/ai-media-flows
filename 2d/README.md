# 2D Asset Generation — scenario index

Goal: produce game-ready 2D assets (base art, sprites, textures, UI, pixel art, icons, BGs) on the ComfyUI server. This becomes the **high-volume** pipeline — env props, characters sheets, spritesheets, tileable textures, promotional art.

> Comes after the `3d/` scenario, which banked all the transferable ComfyUI infra (workflows, `/object_info` habit, environments).

## What the server has (verified 2026-09-09)

**Base models available** (`models/checkpoints`):
| Model | Use |
|---|---|
| sd_xl_base_1.0 + refiner | general SDXL |
| RealVisXL_V5.0 / realvisxlV50_v40Lightning | realistic humans |
| AnythingXL / PonyV6 / protogen anime | anime/stylized |
| juggernautXL / dreamshaper / f222 | general high-quality |
| **RetroDiffusion** (128/16/24×) | **pixel-art generation** |
| v1.5 / chilloutmix / Deliberate | SD1.5 ecosystem (LoRA-rich) |
| 512-inpainting-ema | inpainting |

**Node packs present:** Flux CLIP/es, ControlNet (ACN, SD1.5/3/Flux), IPAdapter, LoRA hooks, KSampler family, SUPIR/RealESRGAN upscalers, rembg, seamless-tiling, ColorMatch, WAS (resize, masks, etc.).

**Not present (note for future):** no Flux *checkpoint* (only Flux CLIP/controlnet tooling), no LoRAs downloaded yet.

> **Linux box — actual inventory (2026-09-15):** the table above is the *old Windows* server. On
> Linux we have only `sd_xl_base_1.0` (checkpoints) and node packs: `comfyui_controlnet_aux` (ACN),
> KJNodes, Hy3D wrapper, UniRig, ComfyUI-Login, ComfyUI-Manager, CameraPack (1034 nodes total).
> ControlNet weights: `models/controlnet/xinsir-canny-sdxl-v2.safetensors` (2.4 GB). Re-pull others on demand.

## Design / first experiments

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

- `ROADMAP-2D.md` — the **bigger picture**: tracks beyond isolated assets (inpaint, outpaint,
  composition, IPAdapter/reference transfer, consistency, finishing) + the full E-number backlog.
- `EXPERIMENTS-2D.md` — run log (verdicts with *why*).
- `workflows/` — valuable pipelines; `workflows/scratch/` — scaffolding.

(this README grows as experiments land)