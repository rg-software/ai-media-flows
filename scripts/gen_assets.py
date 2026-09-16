#!/usr/bin/env python3
"""Generate the canonical 2D example-asset set against a running ComfyUI.

This script is the source of truth for the E1 asset prompts/seeds. It is
reproducible: every asset has a fixed seed and size, and a manifest.json is
written next to the outputs recording every parameter used.

Usage (on the ComfyUI box):
    python gen_assets.py
    python gen_assets.py --only char_knight
    python gen_assets.py --base http://127.0.0.1:8188 --token "$(head -1 ~/Projects-Git/ComfyUI/login/PASSWORD)"
    python gen_assets.py --prefix 2D/E1 --dry-run

No third-party deps: stdlib urllib only.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_CKPT = "RealVisXL_V5.0_fp16.safetensors"  # chosen in E1c (best detail, frames full-body solo)
DEFAULT_NEG = ("blurry, lowres, text, watermark, signature, jpeg artifacts, "
               "deformed, extra limbs, cropped")

# id, prompt, seed, width, height, extra notes
ASSETS = [
    {
        "id": "char_knight",
        "prompt": ("full body game character concept art of a single heroic fantasy knight in "
                   "ornate plate armor, standing relaxed pose, arms at sides, solo, isolated on a "
                   "plain light gray background, no border, no frame, no text, clean silhouette, "
                   "highly detailed digital painting, neutral studio lighting"),
        "negative": (DEFAULT_NEG + ", character sheet, multiple views, multiple figures, border, "
                     "frame, ornate frame, panel, collage, decorative background"),
        "seed": 1101, "width": 1024, "height": 1024,
        "note": "E3 cutout / E6 sprite / consistency baseline",
    },
    {
        "id": "prop_chest",
        "prompt": ("single fantasy treasure chest, wooden planks with iron bands, closed lid, "
                   "centered, plain light gray background, game prop, three-quarter view, highly "
                   "detailed, soft studio lighting"),
        "seed": 1102, "width": 1024, "height": 1024,
        "note": "E3 cutout / 3D cross-check",
    },
    {
        "id": "env_cottage",
        "prompt": ("medieval fantasy cottage exterior, stone masonry, thatched roof, warm lit "
                   "windows, mossy garden, overcast sky, environment concept art, highly detailed "
                   "digital painting"),
        "seed": 1103, "width": 1024, "height": 1024,
        "note": "E2 control / E10 composition",
    },
    {
        "id": "bg_forest",
        "prompt": ("dense misty pine forest background plate, layered depth, god rays, no "
                   "characters, matte painting, atmospheric perspective"),
        "seed": 1104, "width": 1024, "height": 1024,
        "note": "E9 outpaint / E10 composition",
    },
    {
        "id": "char_heroine",
        "prompt": ("full body game character concept art of a single heroic fantasy sorceress, "
                   "clearly visible unobstructed face, long auburn hair, ornate blue and gold "
                   "mage robes, standing relaxed pose, arms at sides, solo, isolated on a plain "
                   "light gray background, no border, no frame, no text, clean silhouette, "
                   "highly detailed digital painting, neutral studio lighting, sharp focus"),
        "negative": (DEFAULT_NEG + ", character sheet, multiple views, multiple figures, border, "
                     "frame, ornate frame, panel, collage, decorative background, helmet, mask, "
                     "obscured face"),
        "seed": 1106, "width": 1024, "height": 1024,
        "note": "E1e - face-bearing character; unblocks E14 identity (InstantID/PuLID) and E13 face restore",
    },
    {
        "id": "portrait_heroine",
        "prompt": ("head and shoulders portrait of a heroic fantasy sorceress, clearly visible "
                   "face centered and large in frame, long auburn hair, ornate blue and gold mage "
                   "robes, symmetrical composition, neutral expression, looking at camera, isolated "
                   "on a plain light gray background, highly detailed digital painting, neutral "
                   "studio lighting, sharp focus on the eyes"),
        "negative": (DEFAULT_NEG + ", full body, multiple figures, border, frame, panel, collage, "
                     "decorative background, helmet, mask, obscured face, sunglasses"),
        "seed": 1107, "width": 1024, "height": 1024,
        "note": "E1e - large-face reference for face-ID embedding (full body only gives ~60px faces)",
    },
    {
        "id": "tex_stone",
        "prompt": ("seamless stone wall texture, irregular grey blocks, weathered, flat "
                   "orthographic view, even lighting, high detail material reference"),
        "seed": 1105, "width": 1024, "height": 1024,
        "note": "E7 tileable / 3D texturing",
    },
]


def build_graph(ckpt, positive, negative, width, height, seed, steps, cfg, sampler, scheduler, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler,
            "scheduler": scheduler, "denoise": 1.0,
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["6", 0]}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8188")
    ap.add_argument("--token", default="")
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--prefix", default="2D/E1", help="SaveImage filename prefix")
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--sampler", default="euler")
    ap.add_argument("--scheduler", default="normal")
    ap.add_argument("--only", action="append", default=[], help="asset id (repeatable)")
    ap.add_argument("--manifest", default="output/2D/E1/manifest.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)

    wanted = [a for a in ASSETS if not args.only or a["id"] in args.only]
    if not wanted:
        raise SystemExit(f"no assets match --only {args.only}")

    if not args.dry_run:
        obj = get("/object_info/CheckpointLoaderSimple")
        models = obj["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        if args.ckpt not in models:
            raise SystemExit(f"checkpoint {args.ckpt!r} not found; available: {models}")

    manifest = []
    for a in wanted:
        prefix = f"{args.prefix}/{a['id']}"
        print(f"[{a['id']}] seed={a['seed']} {a['width']}x{a['height']} -> {prefix}_*.png")
        print(f"    prompt: {a['prompt']}")
        if args.dry_run:
            continue
        graph = build_graph(args.ckpt, a["prompt"], a.get("negative", DEFAULT_NEG), a["width"], a["height"],
                            a["seed"], args.steps, args.cfg, args.sampler, args.scheduler, prefix)
        resp = post("/prompt", {"prompt": graph})
        if "prompt_id" not in resp:
            print(f"    SUBMIT FAILED: {json.dumps(resp)[:400]}")
            continue
        pid = resp["prompt_id"]
        files = []
        for _ in range(200):
            entry = get(f"/history/{pid}").get(pid)
            if entry:
                st = entry.get("status", {})
                if st.get("completed") or st.get("status_str") == "error":
                    for o in entry.get("outputs", {}).values():
                        for im in o.get("images", []):
                            files.append(f"{im.get('subfolder')}/{im.get('filename')}")
                    if st.get("status_str") == "error":
                        for m in st.get("messages", []):
                            if m and m[0] == "execution_error":
                                print("    ERROR:", json.dumps(m[1])[:500])
                    break
            time.sleep(3)
        print(f"    -> {files or 'TIMEOUT'}")
        manifest.append({**a, "outputs": files, "ckpt": args.ckpt,
                         "negative": a.get("negative", DEFAULT_NEG),
                         "steps": args.steps, "cfg": args.cfg, "sampler": args.sampler,
                         "scheduler": args.scheduler})

    if not args.dry_run:
        mp = Path(args.manifest)
        mp.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if mp.exists():
            try:
                existing = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        by_id = {e["id"]: e for e in existing if isinstance(e, dict) and "id" in e}
        for e in manifest:
            by_id[e["id"]] = e
        merged = [by_id[a["id"]] for a in ASSETS if a["id"] in by_id]
        merged += [e for k, e in by_id.items() if k not in {a["id"] for a in ASSETS}]
        mp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        print(f"manifest -> {mp} ({len(merged)} assets)")


if __name__ == "__main__":
    main()
