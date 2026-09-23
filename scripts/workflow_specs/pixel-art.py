"""Spec for 2d/workflows/pixel-art.json - build with scripts/build_workflow.py.

Single arm: SDXL + `pixel-art-xl` LoRA (OpenRAIL). It used to carry two arms that differed only in the base
checkpoint - Retro Diffusion 24x-64x at 512² (flat retro, but non-commercial) and this one at 1024² - and the
choice belongs in the story, not in a duplicated graph. The Retro Diffusion recipe is in the note below and
in HOWTO S10.
"""

NOTE = (
    "## pixel-art.json\n\n"
    "Pixel art (game-ready sprites)\n\n"
    "**Does:** SDXL + `pixel-art-xl` LoRA (RealVisXL, strength 1.0) at **1024²** -> `ImageScale` **nearest /16** "
    "= 64x64, then a palette pass (`PixelArtDetectorToImage`, 16 colours). Run it at 1024²: at 512² the frames "
    "come out far too tight.\n"
    "**Downscale by NEAREST with the model's KNOWN factor** (16 here). Never trust the detector's auto-detect - "
    "it mis-detects, and it is not idempotent, so only ever feed it the generation-sized image.\n"
    "**Want the flat retro look instead?** Switch the checkpoint to `RetroDiffusion24x-64xModel` at **512²**, "
    "20 steps, cfg 9.5, and divide by **8** (its grid is 8 px at 512²). That model is **non-commercial**; "
    "`pixel-art-xl` is OpenRAIL, which is why this is the shipped arm.\n"
    "**Already have a picture?** `pixel-art-convert.json` pixelises and palettises an existing image to a "
    "chosen palette instead of generating one.\n\n"
    "---\n*How to run it: story **S10** in `HOWTO.md`  ·  Why it is this way: **E5/E5b/E5f** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "CheckpointLoaderSimple", "pos": [-1500, 520], "size": [340, 100],
     "widgets_values": ["RealVisXL_V5.0_fp16.safetensors"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0},
                 {"name": "CLIP", "type": "CLIP", "slot_index": 1},
                 {"name": "VAE", "type": "VAE", "slot_index": 2}]},
    {"id": 2, "type": "LoraLoaderModelOnly", "pos": [-1140, 560], "size": [340, 90],
     "widgets_values": ["pixel-art-xl.safetensors", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 3, "type": "CLIPTextEncode", "pos": [-740, 460], "size": [440, 140],
     "widgets_values": ["detailed pixel art of a treasure chest, flat colors, cel shading, no background, "
                        "pixel art style, pixel art"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 4, "type": "CLIPTextEncode", "pos": [-740, 700], "size": [440, 120],
     "widgets_values": ["blurry, muted, dull, hazy, muddy colors, mutated, deformed, noise, borders, frame, "
                        "watermark, text, signature, cropped, out of frame"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 5, "type": "EmptyLatentImage", "pos": [-1140, 700], "size": [300, 100],
     "widgets_values": [1024, 1024, 1],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 6, "type": "KSampler", "pos": [-260, 520], "size": [320, 262],
     "widgets_values": [5501, "fixed", 25, 7.0, "euler", "normal", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}, {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"}, {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 7, "type": "VAEDecode", "pos": [120, 520], "size": [240, 60],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 8, "type": "ImageScale", "pos": [420, 380], "size": [300, 130],
     "widgets_values": ["nearest-exact", 64, 64, "disabled"],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 9, "type": "SaveImage", "pos": [780, 280], "size": [380, 300],
     "widgets_values": ["2D/E5/pixel_lora_64"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 10, "type": "PixelArtDetectorToImage", "pos": [420, 560], "size": [300, 100],
     "widgets_values": [True, 16],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 11, "type": "SaveImage", "pos": [780, 600], "size": [380, 300],
     "widgets_values": ["2D/E5/pixel_lora_64_pal"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 12, "type": "MarkdownNote", "pos": [-1500, -480], "size": [720, 200]},
]

LINKS = [
    [1, 1, 1, 3, 0, "CLIP"],
    [2, 1, 1, 4, 0, "CLIP"],
    [3, 1, 0, 2, 0, "MODEL"],
    [4, 2, 0, 6, 0, "MODEL"],
    [5, 3, 0, 6, 1, "CONDITIONING"],
    [6, 4, 0, 6, 2, "CONDITIONING"],
    [7, 5, 0, 6, 3, "LATENT"],
    [8, 6, 0, 7, 0, "LATENT"],
    [9, 1, 2, 7, 1, "VAE"],
    [10, 7, 0, 8, 0, "IMAGE"],
    [11, 8, 0, 9, 0, "IMAGE"],
    [12, 7, 0, 10, 0, "IMAGE"],
    [13, 10, 0, 11, 0, "IMAGE"],
]
