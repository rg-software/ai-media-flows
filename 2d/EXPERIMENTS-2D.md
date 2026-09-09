# 2D Experiments Log

Same discipline as `3d/EXPERIMENTS.md`: one row per run, verdicts with *why*.

| Run | Date | Variant | Stage | Input | Key params | Output | Verdict | Notes / Next |
|---|---|---|---|---|---|---|---|---|
| — | | | | | | | | | |

---
## PENDING

- [ ] E1 — SDXL base art (prose → hero image). Learn KSampler/CFG/resolution.
- [ ] E2 — ControlNet (pose/canny) → controlled art.
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