# 2D Experiments Log

Same discipline as `3d/EXPERIMENTS.md`: one row per run, verdicts with *why*.

| Run | Date | Variant | Stage | Input | Key params | Output | Verdict | Notes / Next |
|---|---|---|---|---|---|---|---|---|---|
| E1 | 2026-09-11 | base (free) | base art | prose prompt | sd_xl_base_1.0.safetensors, 1024², 25 steps euler/7.0 | output/2D/sdxl_smoke_00001_.png | **PASS** | first 2D run on Linux; checkpoint downloaded fresh (Windows models not carried). Validates CheckpointLoaderSimple→KSampler→VAEDecode path. Next: E2 ControlNet. |
| E2 | 2026-09-15 | base (free) | control | `house.png` (canny edges) | `xinsir-canny-sdxl-v2`, canny 100/200 res1024, strength 0.8, 25 steps euler/7.0, seed 12345, 1024² | output/2D/controlnet_00001_.png (+ canny map `2D/controlnet/canny_00001_.png`) | **PASS** | Installed `comfyui_controlnet_aux` (ACN, 1034 nodes total) + `models/controlnet/xinsir-canny-sdxl-v2.safetensors` (2.4 GB). Output silhouette follows the canny edges exactly; prompt recolours material to medieval stone cottage. Workflow `workflows/sdxl-controlnet-canny.json`. Ran via API. Next: E3 remove-BG. |

---
## PENDING

- [x] E1 — SDXL base art (prose → hero image). Learn KSampler/CFG/resolution. **PASS on Linux (2026-09-11)** — smoke only (single prompt); full param-tuning run still open.
- [x] E2 — ControlNet canny → controlled art. **PASS (2026-09-15).** Installed `comfyui_controlnet_aux` + `xinsir-canny-sdxl-v2.safetensors`; workflow `workflows/sdxl-controlnet-canny.json`; silhouette follows edges, style follows prompt. (pose/depth variants still open — same recipe, swap preprocessor + weight.)
- [ ] E3 — remove-BG (rembg/BRIA) → isolated sprite.
- [ ] E4 — upscale (SUPIR / RealESRGAN).
- [ ] E5 — pixel-art (RetroDiffusion, or downsample hi-res).
- [ ] E6 — spritesheet slicing → per-frame assets.
- [ ] E7 — tileable texture (seamless-tiling).

---
## Template

```
## EX-<n>: <title>
- Date:
- Stage: base | control | bg | upscale | pixel | sheet | tile | ...
- Workflow: <filename>
- Input:
- Params:
- Output:
- Verdict:
- Observations:
- Next:
```