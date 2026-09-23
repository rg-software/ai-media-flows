"""Spec for 2d/workflows/pixel-art-restyle.json - build with scripts/build_workflow.py.

The REDRAW conversion: an existing picture -> pixel art by re-painting it with the pixel-art LoRA, then
pixelating to a fixed size with a chosen palette. This is the step `pixel-art-convert.json` does not have
(that one only resizes and palettises, so it keeps the source exactly).

Shape: img2img at the model's NATIVE resolution (so the LoRA can redraw), then PixelArtDetectorConverter at a
fixed 64x64 for the grid + palette. Do NOT downscale before the sampler - a 64-128 px latent makes SDXL
produce mush (measured: 128 px latent at denoise 0.93 gave a colour blob). The pack's own img2img example
looks similar but is a different job: its `ImageScaleBy ... 8` is x8 UPSCALE, for restoring an existing small
sprite so the model can work at native resolution.
"""

_GRID = ("Grid settings. The values will be forwarded to the 'PixelArt Palette Converter to render the grid "
         "with all palettes from this node.'")
_OPENCV = ("OpenCV.kmeans: only when reducing is enabled.\nRANDOM_CENTERS: Fast but doesn't guarantee same "
           "labels for the same image.\nPP_CENTERS: Slow but will yield optimum and consistent results for "
           "same input image.\nattempts: to run criteria_max_iterations so it gets the best labels. "
           "Increasing this value will slow down the runtime a lot, but improves the colors!\n")
_CLEANUP = ("Clean up colors: Iterate and eliminate pixels while there was none left covering less than the "
            "'cleanup_pixels_threshold' of the image.\nOptionally, enable the 'reduce colors' option, which "
            "runs before this cleanup. Good cleanup_threshold values: between .01 & .05")

NOTE = (
    "## pixel-art-restyle.json\n\n"
    "Existing image -> pixel art, REDRAWN (img2img with the pixel-art LoRA)\n\n"
    "**Does:** re-paints the source with `pixel-art-xl` before making a sprite, so detail is simplified into "
    "the pixel idiom instead of being resampled. `KSampler` is img2img at the model's native resolution: "
    "`denoise` **0.6** is the knob - low keeps the source, high redraws it (0.8 moves noticeably further). "
    "Then `PixelArtDetectorConverter` at a **fixed 64x64** with a chosen palette makes the grid (`paletteList` "
    "from `PixelArtLoadPalettes`; pico-8 by default). Two saves: the redrawn image at full size and the 64 px "
    "sprite.\n"
    "**Do NOT downscale before the sampler.** A 64-128 px latent makes SDXL produce mush - measured: a 128 px "
    "latent at denoise 0.93 returned a colour blob, not a knight. Downscaling belongs at the END, with the "
    "known factor.\n"
    "**Faithful instead?** `pixel-art-convert.json` keeps the source exactly (resize + palette, no redraw). "
    "**Restoring an existing small sprite?** that is a third job - upscale it first so the model can work at "
    "native resolution (the `comfyui-pixelart-detector` pack ships an example for it), which is not what this "
    "flow does.\n\n"
    "---\n*How to run it: story **S10** in `HOWTO.md`  \u00b7  Why it is this way: **E5** nodes + **E31/E32** in "
    "the scenarios' `EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 200], "size": [320, 320],
     "widgets_values": ["2d/char_knight.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "CheckpointLoaderSimple", "pos": [400, 380], "size": [340, 100],
     "widgets_values": ["RealVisXL_V5.0_fp16.safetensors"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0},
                 {"name": "CLIP", "type": "CLIP", "slot_index": 1},
                 {"name": "VAE", "type": "VAE", "slot_index": 2}]},
    {"id": 3, "type": "LoraLoader", "pos": [780, 380], "size": [340, 130],
     "widgets_values": ["pixel-art-xl.safetensors", 1.0, 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}, {"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0},
                 {"name": "CLIP", "type": "CLIP", "slot_index": 1}]},
    {"id": 4, "type": "CLIPTextEncode", "pos": [1160, 120], "size": [420, 140],
     "widgets_values": ["retro game pixel art of a knight in ornate plate armor, flat colors, cel shading, "
                        "limited palette, no background"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 5, "type": "CLIPTextEncode", "pos": [1160, 320], "size": [420, 140],
     "widgets_values": ["photorealistic, 3D, realistic, blurry, smooth gradients, noise, watermark, text, "
                        "extra limbs, deformed"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 6, "type": "VAEEncode", "pos": [780, 200], "size": [240, 60],
     "inputs": [{"name": "pixels", "type": "IMAGE"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 7, "type": "KSampler", "pos": [1620, 120], "size": [320, 262],
     "widgets_values": [7701, "fixed", 25, 8.0, "euler", "normal", 0.6],
     "inputs": [{"name": "model", "type": "MODEL"}, {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"}, {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 8, "type": "VAEDecode", "pos": [1980, 120], "size": [240, 60],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 9, "type": "SaveImage", "pos": [2260, 60], "size": [400, 300],
     "widgets_values": ["2D/pixel_convert/restyled_raw"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 10, "type": "PixelArtLoadPalettes", "pos": [1980, 520], "size": [340, 300],
     "widgets_values": ["pico-8-1x.png", False, _GRID, 40, "#f40e12", "#fff", 6, True, 3],
     "outputs": [{"name": "paletteList", "type": "LIST", "slot_index": 0}]},
    {"id": 11, "type": "PixelArtDetectorConverter", "pos": [2380, 380], "size": [420, 620],
     "widgets_values": ["GAMEBOY", 64, 64, "contain", "Image.quantize", 2, False, "Image.quantize", 128,
                        True, "MAXCOVERAGE", _OPENCV, "RANDOM_CENTERS", 10, 10, "EUCLIDEAN_SQUARE",
                        _CLEANUP, False, 0.02, "none"],
     "inputs": [{"name": "images", "type": "IMAGE"}, {"name": "paletteList", "type": "LIST"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 12, "type": "SaveImage", "pos": [2860, 380], "size": [400, 300],
     "widgets_values": ["2D/pixel_convert/restyled_pal"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 13, "type": "MarkdownNote", "pos": [40, 560], "size": [420, 320]},
]

LINKS = [
    [1, 1, 0, 6, 0, "IMAGE"],
    [2, 2, 0, 3, 0, "MODEL"],
    [3, 2, 1, 3, 1, "CLIP"],
    [4, 3, 1, 4, 0, "CLIP"],
    [5, 3, 1, 5, 0, "CLIP"],
    [6, 2, 2, 6, 1, "VAE"],
    [7, 3, 0, 7, 0, "MODEL"],
    [8, 4, 0, 7, 1, "CONDITIONING"],
    [9, 5, 0, 7, 2, "CONDITIONING"],
    [10, 6, 0, 7, 3, "LATENT"],
    [11, 7, 0, 8, 0, "LATENT"],
    [12, 2, 2, 8, 1, "VAE"],
    [13, 8, 0, 9, 0, "IMAGE"],
    [14, 8, 0, 11, 0, "IMAGE"],
    [15, 10, 0, 11, 1, "LIST"],
    [16, 11, 0, 12, 0, "IMAGE"],
]
