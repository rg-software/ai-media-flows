"""Spec for 2d/workflows/pixel-art.json - build with scripts/build_workflow.py.

Single arm (SDXL + pixel-art-xl LoRA, OpenRAIL) with TWO outputs at the SAME size: the plain nearest-/16
downscale, and the same 64 px sprite palettised to a chosen palette.

It used to have a second arm that differed only in the base checkpoint (Retro Diffusion, non-commercial) -
that choice now lives in the story and the note. Its palette pass was `PixelArtDetectorToImage`, which
auto-detects the pixel grid: measured on a 1024 px generation it returned **128 px**, not the 64 px sprite,
and it is not idempotent. The palette pass is now `PixelArtDetectorConverter` with a FIXED 64x64 resize, the
same node the convert/restyle flows use, so both outputs are 64 px and the palette is one you choose.
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
    "## pixel-art.json\n\n"
    "Pixel art from a prompt (game-ready sprites)\n\n"
    "**Does:** SDXL + `pixel-art-xl` LoRA (RealVisXL, strength 1.0) at **1024\u00b2**, then `ImageScale` "
    "**nearest /16 -> 64x64**, then `PixelArtDetectorConverter` at a **fixed 64x64** with a chosen palette "
    "(`paletteList` from `PixelArtLoadPalettes`, pico-8 by default). Both outputs are 64 px, so they are "
    "directly comparable.\n"
    "**The grid is 8 px, not 16 (measured).** This LoRA paints on an **8 px grid at 1024\u00b2** - the "
    "adjacent-column step ratio peaks at period 8 (6.38, vs 5.35 at 16) and the modal gap between column "
    "spikes is 8 px - so **/8 is its native factor and 128 px its native sprite**. The shipped /16 -> 64 px is "
    "a deliberate *smaller* target: each output pixel covers 2x2 of the LoRA's pixels, so half the painted "
    "detail is gone. For the native size instead, set `ImageScale` to **128x128** and the converter's "
    "`resize_w`/`resize_h` to **128**.\n"
    "**Never auto-detect.** `PixelArtDetectorToImage`'s grid detection is unreliable (measured: it returned "
    "128 px from a 1024\u00b2 image) and is not idempotent - which is why the palette pass here uses a FIXED "
    "size and never an already-downscaled input.\n"
    "**Flat retro instead?** `RetroDiffusion24x-64xModel` at 512\u00b2, 20 steps, cfg 9.5, with **its** "
    "measured factor /8 -> 64 px. That model is **non-commercial**; `pixel-art-xl` is OpenRAIL, which is why "
    "this is the shipped arm.\n"
    "**Converting an existing picture?** `pixel-art-convert.json` keeps the source exactly (resize + palette); "
    "`pixel-art-restyle.json` redraws it with the LoRA first.\n\n"
    "---\n*How to run it: story **S10** in `HOWTO.md`  \u00b7  Why it is this way: **E5/E5b/E5f** in the "
    "scenarios' `EXPERIMENTS` logs.*"
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
    {"id": 10, "type": "PixelArtLoadPalettes", "pos": [420, 900], "size": [340, 300],
     "widgets_values": ["pico-8-1x.png", False, _GRID, 40, "#f40e12", "#fff", 6, True, 3],
     "outputs": [{"name": "paletteList", "type": "LIST", "slot_index": 0}]},
    {"id": 11, "type": "PixelArtDetectorConverter", "pos": [820, 700], "size": [420, 620],
     "widgets_values": ["GAMEBOY", 64, 64, "contain", "Image.quantize", 2, False, "Image.quantize", 128,
                        True, "MAXCOVERAGE", _OPENCV, "RANDOM_CENTERS", 10, 10, "EUCLIDEAN_SQUARE",
                        _CLEANUP, False, 0.02, "none"],
     "inputs": [{"name": "images", "type": "IMAGE"}, {"name": "paletteList", "type": "LIST"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 12, "type": "SaveImage", "pos": [1300, 700], "size": [380, 300],
     "widgets_values": ["2D/E5/pixel_lora_64_pal"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 13, "type": "MarkdownNote", "pos": [-1500, -480], "size": [720, 200]},
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
    [12, 8, 0, 11, 0, "IMAGE"],
    [13, 10, 0, 11, 1, "LIST"],
    [14, 11, 0, 12, 0, "IMAGE"],
]
