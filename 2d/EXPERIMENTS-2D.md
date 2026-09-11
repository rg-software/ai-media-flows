# 2D Experiments Log

Same discipline as `3d/EXPERIMENTS.md`: one row per run, verdicts with *why*.

| Run | Date | Variant | Stage | Input | Key params | Output | Verdict | Notes / Next |
|---|---|---|---|---|---|---|---|---|---|
| E1 | 2026-09-11 | base (free) | base art | prose prompt | sd_xl_base_1.0.safetensors, 1024², 25 steps euler/7.0 | output/2D/sdxl_smoke_00001_.png | **PASS** | first 2D run on Linux; checkpoint downloaded fresh (Windows models not carried). Validates CheckpointLoaderSimple→KSampler→VAEDecode path. Next: E2 ControlNet. |

---
## PENDING

- [x] E1 — SDXL base art (prose → hero image). Learn KSampler/CFG/resolution. **PASS on Linux (2026-09-11)** — smoke only (single prompt); full param-tuning run still open.
- [ ] E2 — ControlNet (pose/canny) → controlled art. Needs controlnet weights (not carried over; `ComfyUI-Manager` available to pull them).
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