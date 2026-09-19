#!/usr/bin/env python3
"""Sweep the outpaint seam: two axes over the shipped `outpaint.json` chain, with a seam metric.

Why a separate harness: `scripts/sweep.py` builds its own txt2img graph and sweeps KSampler widgets,
and its metric is detail variance - neither reaches `InpaintCropImproved` nor answers "is there a step
at the boundary". This one mirrors the shipped outpaint chain in API form:

    LoadImage -> InpaintCropImproved -> InpaintModelConditioning -> KSampler -> VAEDecode
                                     \\-> InpaintStitchImproved <-/          -> SaveImage

Non-axis values are copied from `2d/workflows/outpaint.json` so the sweep tests the shipped recipe.
Two seams are measured (the original sits in the middle, extended left/right):

    step      = mean |dI/dx| across the seam  /  the same 120 px inside the original
    tone_step = |mean colour left of the seam - mean colour right of it|  (the "colour jump")

Usage (on the box, from the repo root):
    uv run python scripts/sweep_outpaint.py --image 2d/env_cottage.png --out 2D/E17/outpaint_seam \
        --x mask_blend_pixels:8,32,64 --y denoise:1.0,0.9,0.8

E17 result (why the defaults are these axes): `mask_blend_pixels` is the seam knob (8/32/64 -> seam
19.6/13.4/11.7 on a 0-255 scale), `denoise` ~0.9 matches the colour best (and <=0.8 ghosts the mirrored
extension fill). **`mask_expand_pixels` and `context_from_mask_extend_factor` do nothing here** - the
node manipulates the mask *before* `extend_for_outpainting`, and with no mask wired in it expands an
empty one. Results are written under ComfyUI's own output/ so `scripts/comfy_io.py get` can fetch them.

No third-party deps beyond numpy/PIL (already in the repo env).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COMFY_INPUT = Path.home() / "Projects-Git" / "ComfyUI" / "input"
COMFY_OUT = Path.home() / "Projects-Git" / "ComfyUI" / "output"   # SaveImage writes here

# ---- values copied from 2d/workflows/outpaint.json (the shipped recipe) --------------
CROP = {
    "downscale_algorithm": "bilinear", "upscale_algorithm": "bicubic", "preresize": False,
    "preresize_mode": "ensure minimum resolution", "preresize_min_width": 1024,
    "preresize_min_height": 1024, "preresize_max_width": 16384, "preresize_max_height": 16384,
    "mask_fill_holes": True, "mask_expand_pixels": 0, "mask_invert": False,
    "mask_blend_pixels": 32, "mask_hipass_filter": 0.1, "extend_for_outpainting": True,
    "extend_up_factor": 1.0, "extend_down_factor": 1.0, "extend_left_factor": 1.5,
    "extend_right_factor": 1.5, "context_from_mask_extend_factor": 1.2,
    "output_resize_to_target_size": False, "output_target_width": 512,
    "output_target_height": 512, "output_padding": "32", "device_mode": "gpu (much faster)",
}
SAMPLER = {"seed": 9101, "steps": 25, "cfg": 6.0, "sampler_name": "euler",
           "scheduler": "normal", "denoise": 1.0}
POS = ("medieval fantasy cottage in a lush garden, stone wall, tall trees, overcast sky, "
       "environment concept art, highly detailed digital painting, seamless continuation")
NEG = ("blurry, lowres, text, watermark, jpeg artifacts, deformed, seams, horizon mismatch")
CKPT = "RealVisXL_V5.0_fp16.safetensors"


def build_graph(image: str, crop: dict, sampler: dict, prefix: str) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image}},
        "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["2", 1]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 1]}},
        "5": {"class_type": "InpaintCropImproved", "inputs": {**crop, "image": ["1", 0]}},
        "6": {"class_type": "InpaintModelConditioning",
              "inputs": {"noise_mask": True, "positive": ["3", 0], "negative": ["4", 0],
                         "vae": ["2", 2], "pixels": ["5", 1], "mask": ["5", 2]}},
        "7": {"class_type": "KSampler", "inputs": {**sampler, "model": ["2", 0],
                                                   "positive": ["6", 0], "negative": ["6", 1],
                                                   "latent_image": ["6", 2]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["2", 2]}},
        "9": {"class_type": "InpaintStitchImproved",
              "inputs": {"stitcher": ["5", 0], "inpainted_image": ["8", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["9", 0]}},
    }


def parse_axis(spec: str):
    name, _, values = spec.partition(":")
    if not name or not values:
        raise SystemExit(f"bad axis {spec!r}; expected name:v1,v2,...")
    out = []
    for v in values.split(","):
        try:
            out.append(int(v))
        except ValueError:
            try:
                out.append(float(v))
            except ValueError:
                out.append(v)
    return name, out


def seam_metrics(png: Path, left_new: int, orig_w: int):
    """Local seam statistics, in 0-255 units.

    seam  = mean |I(x-2) - I(x+2)| across the boundary, in luminance
    ratio = seam / the same statistic over columns +/-20 px either side (its own neighbourhood)
            (>1 means the boundary stands out from its surroundings)
    tone  = |mean RGB left of the seam - mean RGB right of it|  (the "colour jump")

    An earlier version normalised against a column 100 px INSIDE the image - which lands on foliage -
    and made an obviously visible seam read as "smooth". A metric is a hint; the image is the truth.
    """
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(png).convert("RGB"), np.float32)
    g = np.asarray(Image.open(png).convert("L"), np.float32)
    ratios, seams, tones = [], [], []
    for x in (left_new, left_new + orig_w):
        seam = float(np.abs(g[:, x - 2] - g[:, x + 2]).mean())
        near = [float(np.abs(g[:, c - 2] - g[:, c + 2]).mean())
                for c in list(range(x - 20, x - 2)) + list(range(x + 3, x + 21))]
        seams.append(seam)
        ratios.append(seam / max(float(np.median(near)), 1e-6))
        left = a[:, x - 16:x - 4].reshape(-1, 3).mean(0)
        right = a[:, x + 4:x + 16].reshape(-1, 3).mean(0)
        tones.append(float(np.abs(left - right).mean()))
    n = len(seams)
    return float(sum(ratios) / n), float(sum(seams) / n), float(sum(tones) / n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8188")
    ap.add_argument("--token", default="")
    ap.add_argument("--image", default="2d/env_cottage.png")
    ap.add_argument("--out", default="2D/E17/outpaint_seam")
    ap.add_argument("--x", default="mask_blend_pixels:8,32,64")
    ap.add_argument("--y", default="denoise:1.0,0.9,0.8")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    xname, xvals = parse_axis(a.x)
    yname, yvals = parse_axis(a.y)

    from PIL import Image
    src = COMFY_INPUT / a.image
    with Image.open(src) as im:
        orig_w, orig_h = im.size
    left_new = round(orig_w * (CROP["extend_left_factor"] - 1.0))
    print(f"input {src.name} {orig_w}x{orig_h}; seams at x={left_new} and x={left_new + orig_w}")

    def url(path, **params):
        if a.token:
            params["token"] = a.token
        return f"{a.base}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")

    def get(path, **params):
        with urllib.request.urlopen(url(path, **params), timeout=60) as r:
            return json.load(r)

    def post(obj):
        req = urllib.request.Request(url("/prompt"), data=json.dumps(obj).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
            return json.load(r)

    outdir = COMFY_OUT / Path(a.out).parent
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for yi, yv in enumerate(yvals):
        for xi, xv in enumerate(xvals):
            crop = dict(CROP)
            sampler = dict(SAMPLER)
            (crop if xname in CROP else sampler)[xname] = xv
            (crop if yname in CROP else sampler)[yname] = yv
            prefix = f"{a.out}_x{xi}_y{yi}"
            t0 = time.time()
            try:
                resp = post({"prompt": build_graph(a.image, crop, sampler, prefix)})
            except urllib.error.HTTPError as e:
                print(f"  [{xname}={xv} {yname}={yv}] SUBMIT FAILED {e.code}: {e.read()[:200]!r}")
                continue
            pid = resp.get("prompt_id")
            files, err = [], None
            for _ in range(a.timeout // 3):
                entry = get(f"/history/{pid}").get(pid)
                if entry:
                    st = entry.get("status", {})
                    if st.get("completed") or st.get("status_str") == "error":
                        for o in entry.get("outputs", {}).values():
                            files += o.get("images", [])
                        if st.get("status_str") == "error":
                            err = json.dumps(st.get("messages", []))[:200]
                        break
                time.sleep(3)
            dt = time.time() - t0
            if not files:
                print(f"  {xname}={xv:<16} {yname}={yv:<8} {dt:5.1f}s  NO OUTPUT {err or ''}")
                continue
            local = COMFY_OUT / (files[-1].get("subfolder") or "") / files[-1]["filename"]
            ratio = seam = tone = None
            if local.exists():
                ratio, seam, tone = seam_metrics(local, left_new, orig_w)
            results.append({"x": {"name": xname, "value": xv}, "y": {"name": yname, "value": yv},
                            "seconds": round(dt, 1), "file": files[-1]["filename"],
                            "seam": round(seam, 1) if seam is not None else None,
                            "seam_ratio": round(ratio, 2) if ratio is not None else None,
                            "tone_step": round(tone, 1) if tone is not None else None})
            shown = (f"seam {seam:5.1f}  ratio {ratio:.2f}  tone {tone:5.1f}"
                     if ratio is not None else "seam ?  ratio ?  tone ?")
            print(f"  {xname}={xv:<16} {yname}={yv:<8} {dt:5.1f}s  {shown}  -> {files[-1]['filename']}")

    manifest = COMFY_OUT / Path(a.out).parent / "_sweep.json"
    manifest.write_text(json.dumps({"x": {xname: xvals}, "y": {yname: yvals}, "cells": results},
                                   indent=1), encoding="utf-8")
    print(f"manifest -> {manifest}")

    # ---- sheet ------------------------------------------------------------------------
    import numpy as np
    from PIL import Image, ImageDraw
    W, pad, lab = 420, 8, 30
    th = int(W * orig_h / (orig_w + 2 * left_new))
    sheet = Image.new("RGB", (len(xvals) * (W + pad) + 150, len(yvals) * (th + lab + pad) + lab + 30),
                      (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    d.text((6, 6), f"X = {xname}   Y = {yname}   (outpaint seam; step = |dI/dx| at seam / inside)",
           fill=(235, 235, 235))
    for xi, xv in enumerate(xvals):
        d.text((150 + xi * (W + pad), 18), f"{xname}={xv}", fill=(255, 220, 120))
    for yi, yv in enumerate(yvals):
        y = 30 + lab + yi * (th + lab + pad)
        d.text((6, y + th // 2), f"{yname}={yv}", fill=(255, 220, 120))
        for xi, xv in enumerate(xvals):
            hits = sorted((COMFY_OUT / Path(a.out).parent).glob(f"{Path(a.out).name}_x{xi}_y{yi}_*.png"))
            x = 150 + xi * (W + pad)
            if not hits:
                d.text((x + 8, y + 8), "(missing)", fill=(200, 80, 80)); continue
            img = Image.open(hits[-1]).convert("RGB")
            sheet.paste(img.resize((W, th), Image.Resampling.LANCZOS), (x, y))
            rt, st, tn = seam_metrics(hits[-1], left_new, orig_w)
            d.text((x + 4, y + th - 16), f"seam {st:.0f}  ratio {rt:.2f}  tone {tn:.0f}",
                   fill=(120, 255, 120))
    sheet.save(COMFY_OUT / Path(a.out).parent / "_sheet.png")
    print(f"sheet -> {COMFY_OUT / Path(a.out).parent}/_sheet.png {sheet.size}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
