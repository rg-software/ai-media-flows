#!/usr/bin/env python3
"""U4 - texture -> PBR set via Marigold intrinsic decomposition (CreativeML OpenRAIL++-M).

Replaces `QFXPBRGenerator`, whose Metallic output is inverted (mean 0.855 on stone,
85% of pixels > 0.5 - see 2d/EXPERIMENTS-2D.md E12b/U4). Marigold predicts
physically-plausible intrinsics, so a dielectric stone comes out ~non-metallic.

Run on the ComfyUI box, from ~/Projects-Git/ComfyUI:
    venv/bin/python ~/Projects-Git/ai-gamedev-tasks/scripts/marigold_pbr.py [input.png] [outdir]

Outputs: albedo.png, roughness.png, metallic.png, shading.png (+ a .npy per map).

Notable API details (both cost time to rediscover):
  * the checkpoints ship ONLY fp16 variants -> `variant="fp16"` is mandatory
    (otherwise: "Error no file named model.safetensors ... in text_encoder").
  * `MarigoldIntrinsicsPipeline` returns ONE stacked array, not a dict:
        appearance -> (2, H, W, 3): [0] = albedo, [1] = material stack
        material stack channels = (roughness, metallicity, unused)
        lighting   -> (3, H, W, 3): albedo, shading, residual
  * Marigold is meant to run around 768 px; higher processing_resolution costs a lot
    and past that the tiling behaviour changes.
"""
import os
import sys

import numpy as np
import torch
from diffusers import MarigoldIntrinsicsPipeline
from diffusers.utils import logging as dlog
from PIL import Image

dlog.set_verbosity_error()
torch.set_grad_enabled(False)

SRC = sys.argv[1] if len(sys.argv) > 1 else "input/2d/tex_stone_seamless.png"
OUT = sys.argv[2] if len(sys.argv) > 2 else "output/2D/U4"
RES = 768
STEPS = 10

os.makedirs(OUT, exist_ok=True)


def pipeline(ckpt):
    p = MarigoldIntrinsicsPipeline.from_pretrained(
        f"models/diffusers/{ckpt}", torch_dtype=torch.float16, variant="fp16"
    ).to("cuda")
    p.set_progress_bar_config(disable=True)
    return p


def save(name, arr):
    a = np.asarray(arr, dtype=np.float32)
    if a.ndim == 3 and a.shape[-1] == 1:
        a = a[..., 0]
    np.save(f"{OUT}/{name}.npy", a)
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(f"{OUT}/{name}.png")
    return a


img = Image.open(SRC).convert("RGB").resize((RES, RES), Image.LANCZOS)
print(f"input {SRC} -> {RES}x{RES}  steps={STEPS}")

p = pipeline("marigold-iid-appearance-v1-1")
pred = np.asarray(p(img, num_inference_steps=STEPS, ensemble_size=1,
                    processing_resolution=RES, output_type="np").prediction)
albedo = save("albedo", pred[0])
roughness = save("roughness", pred[1][..., 0])
metallic = save("metallic", pred[1][..., 1])
del p
torch.cuda.empty_cache()

p = pipeline("marigold-iid-lighting-v1-1")
pred = np.asarray(p(img, num_inference_steps=STEPS, ensemble_size=1,
                    processing_resolution=RES, output_type="np").prediction)
shading = save("shading", pred[1])
del p
torch.cuda.empty_cache()

print(f"  albedo    mean={albedo.mean():.3f}")
print(f"  roughness mean={roughness.mean():.3f}")
print(f"  metallic  mean={metallic.mean():.3f}  frac>0.5={(metallic > 0.5).mean():.3f}"
      "   <- dielectrics must be low; QFX gave 0.855")
print(f"  shading   mean={shading.mean():.3f}")
print(f"wrote {OUT}/ (albedo, roughness, metallic, shading)")
