#!/usr/bin/env python3
"""E16 - the "sheet" primitive at scale: a reusable 2-axis sweep harness.

Why scripted rather than a GUI XY-plot node: it is reproducible, diffable, headless,
and it records the parameters next to the output (our PROTOCOL asks for exactly that).
Point it at a prompt and two KSampler axes and it produces a labelled contact sheet
plus a per-cell metric table, so "which settings are actually better" is answerable
in one look instead of a folder of files.

Usage (on the ComfyUI box):
    venv/bin/python scripts/sweep.py \
        --prompt "..." --ckpt RealVisXL_V5.0_fp16.safetensors \
        --x cfg:3,5,7,9 --y steps:10,20,30 \
        --width 1024 --height 1024 --seed 1101 \
        --out 2D/E16/cfg_x_steps

Axes (repeatable, exactly two): any KSampler widget -
    cfg:3,5,7,9      steps:10,20,30      sampler:euler,dpmpp_2m      scheduler:normal,karras
    denoise:0.6,0.8  seed:1,2,3
Values are ints/floats/strings as appropriate; the axis name must be a KSampler input.

No third-party deps: stdlib urllib + PIL for the sheet.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

NEG = ("blurry, lowres, text, watermark, signature, jpeg artifacts, "
       "deformed, extra limbs, cropped")


def coerce(v: str):
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def parse_axis(spec: str):
    name, _, values = spec.partition(":")
    if not name or not values:
        raise SystemExit(f"bad axis {spec!r}; expected name:v1,v2,...")
    return name, [coerce(v) for v in values.split(",")]


def build_graph(ckpt, prompt, neg, width, height, seed):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 25, "cfg": 7.0, "sampler_name": "euler",
            "scheduler": "normal", "denoise": 1.0,
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "E16sweep", "images": ["6", 0]}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8188")
    ap.add_argument("--token", default="")
    ap.add_argument("--ckpt", default="RealVisXL_V5.0_fp16.safetensors")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=1101)
    ap.add_argument("--x", required=True, help="axis spec, e.g. cfg:3,5,7")
    ap.add_argument("--y", required=True, help="axis spec, e.g. steps:10,20,30")
    ap.add_argument("--out", required=True, help="output prefix (subfolder/name)")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    xname, xvals = parse_axis(args.x)
    yname, yvals = parse_axis(args.y)

    def url(path, **params):
        if args.token:
            params["token"] = args.token
        return f"{args.base}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")

    def get(path, **params):
        with urllib.request.urlopen(url(path, **params), timeout=30) as r:
            return json.load(r)

    def post(path, obj):
        req = urllib.request.Request(url(path), data=json.dumps(obj).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=args.timeout) as r:
            return json.load(r)

    cells = {}   # (xi, yi) -> local path of the saved png
    meta = []
    for yi, yv in enumerate(yvals):
        for xi, xv in enumerate(xvals):
            g = build_graph(args.ckpt, args.prompt, args.negative, args.width, args.height, args.seed)
            g["5"]["inputs"][xname] = xv
            g["5"]["inputs"][yname] = yv
            g["7"]["inputs"]["filename_prefix"] = f"{args.out}_x{xi}_y{yi}"
            t0 = time.time()
            resp = post("/prompt", {"prompt": g})
            if "prompt_id" not in resp:
                print(f"  [{xname}={xv} {yname}={yv}] SUBMIT FAILED: {json.dumps(resp)[:200]}")
                continue
            pid = resp["prompt_id"]
            files = []
            for _ in range(args.timeout // 3):
                entry = get(f"/history/{pid}").get(pid)
                if entry:
                    st = entry.get("status", {})
                    if st.get("completed") or st.get("status_str") == "error":
                        for o in entry.get("outputs", {}).values():
                            for im in o.get("images", []):
                                files.append(im)
                        if st.get("status_str") == "error":
                            for m in st.get("messages", []):
                                if m and m[0] == "execution_error":
                                    print("    ERROR:", json.dumps(m[1])[:300])
                        break
                time.sleep(3)
            dt = time.time() - t0
            print(f"  {xname}={xv:<10} {yname}={yv:<6} {dt:6.1f}s -> {files[-1]['filename'] if files else 'NONE'}")
            meta.append({xname: xv, yname: yv, "seconds": round(dt, 1), "file": files[-1] if files else None})

    outdir = Path("output") / Path(args.out).parent
    outdir.mkdir(parents=True, exist_ok=True)
    meta_path = Path("output") / f"{args.out}_sweep.json"
    meta_path.write_text(json.dumps({"x": {xname: xvals}, "y": {yname: yvals}, "cells": meta},
                                    indent=2), encoding="utf-8")
    print(f"manifest -> {meta_path}")

    # ---- contact sheet + metric table -------------------------------------
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError:
        print("(PIL/numpy unavailable - skipping contact sheet)")
        return
    sub = Path(args.out).parent
    tiles = []
    for yi, yv in enumerate(yvals):
        row = []
        for xi, xv in enumerate(xvals):
            hits = sorted(Path(f"output/{sub}").glob(f"{Path(args.out).name}_x{xi}_y{yi}_*.png"))
            row.append(Image.open(hits[-1]).convert("RGB") if hits else None)
        tiles.append(row)
    if not tiles or not any(tiles[0]):
        print("(no images found for the sheet)")
        return
    W = 320
    th = int(W * args.height / args.width)
    resample = Image.Resampling.LANCZOS
    pad, lab = 6, 26
    Wtot = len(xvals) * (W + pad) + 90
    Htot = len(yvals) * (th + pad) + lab + 60
    sheet = Image.new("RGB", (Wtot, Htot), (18, 18, 18))
    d = ImageDraw.Draw(sheet)

    def sharp(im):
        a = np.asarray(im.convert("L"), np.float32)
        gy, gx = np.gradient(a)
        return float(np.sqrt(gx ** 2 + gy ** 2).var())

    d.text((6, 6), f"X = {xname}   Y = {yname}   (cfg 7 / 25 steps defaults elsewhere)", fill=(235, 235, 235))
    for xi, xv in enumerate(xvals):
        d.text((90 + xi * (W + pad), lab + 4), f"{xname}={xv}", fill=(255, 220, 120))
    for yi, yv in enumerate(yvals):
        y = lab + 22 + yi * (th + pad)
        d.text((6, y + th // 2), f"{yname}={yv}", fill=(255, 220, 120))
        for xi in range(len(xvals)):
            im = tiles[yi][xi]
            x = 90 + xi * (W + pad)
            if im is None:
                d.text((x + 6, y + 6), "(missing)", fill=(200, 80, 80)); continue
            sheet.paste(im.resize((W, th), resample), (x, y))
            d.text((x + 4, y + th - 16), f"detail {sharp(im):.0f}", fill=(120, 255, 120))
    sheet.save(f"output/{sub}/_sheet.png")
    print(f"sheet -> output/{sub}/_sheet.png {sheet.size}")


if __name__ == "__main__":
    main()
