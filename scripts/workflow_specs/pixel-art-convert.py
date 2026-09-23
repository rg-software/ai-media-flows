"""Spec for 2d/workflows/pixel-art-convert.json - build with scripts/build_workflow.py.

An EXISTING picture -> pixel art with a CHOSEN palette. This is the palettise route the old Windows-era
`RR Paltest.json` used (comfyui-pixelart-detector's `PixelArtLoadPalettes` -> `PixelArtDetectorConverter`),
and it answers two needs at once: forcing a project palette onto a sprite, and turning a non-pixel-art image
into one without generating anything new (the source composition is kept).

The palette comes from an image bundled with the pack (56 of them: NES, Game Boy, pico-8, Sweetie-16,
DawnBringer-32, ...) and is wired into the converter's `paletteList`. `palette` (NES/GAMEBOY) stays on its
default; the wired list is what the run uses - verify by eye, the two disagree in principle.
"""

NOTE = (
    "## pixel-art-convert.json\n\n"
    "Existing image -> pixel art, with a chosen palette\n\n"
    "**Does:** pixelises and palettises a **picture you already have** - no generation, so the composition is "
    "kept. `PixelArtLoadPalettes` supplies the palette from an image bundled with the "
    "`comfyui-pixelart-detector` pack (**56 of them**: `nintendo-entertainment-system-1x.png`, "
    "`nintendo-gameboy-bgb-1x.png`, `pico-8-1x.png`, `sweetie-16-1x.png`, `dawnbringer-32-1x.png`, ...), wired "
    "into the converter's `paletteList`.\n"
    "**Output size** is `resize_w`/`resize_h` (64x64 here) with `resize_type=contain`, which is the sprite "
    "size you get - change both if you want 32 or 128.\n"
    "**Dither** is `none`: for game sprites a clean ramp usually beats dithering, and dithering is what makes "
    "a downscale look noisy (try `floyd-steinberg` if you want it).\n"
    "**Generating instead?** `pixel-art.json` makes a fresh sprite from a prompt; this flow is for converting.\n\n"
    "---\n*How to run it: story **S10** in `HOWTO.md`  ·  Why it is this way: **E5/E6** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

_GRID_SETTINGS = ("Grid settings. The values will be forwarded to the 'PixelArt Palette Converter to render "
                  "the grid with all palettes from this node.'")
_OPENCV_SETTINGS = ("OpenCV.kmeans: only when reducing is enabled.\nRANDOM_CENTERS: Fast but doesn't "
                    "guarantee same labels for the same image.\nPP_CENTERS: Slow but will yield optimum and "
                    "consistent results for same input image.\nattempts: to run criteria_max_iterations so "
                    "it gets the best labels. Increasing this value will slow down the runtime a lot, but "
                    "improves the colors!\n")
_CLEANUP = ("Clean up colors: Iterate and eliminate pixels while there was none left covering less than the "
            "'cleanup_pixels_threshold' of the image.\nOptionally, enable the 'reduce colors' option, which "
            "runs before this cleanup. Good cleanup_threshold values: between .01 & .05")

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 200], "size": [320, 320],
     "widgets_values": ["2d/char_knight.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    # palette order matches the pack's own listing; pico-8 is 16 colours and instantly recognisable
    {"id": 2, "type": "PixelArtLoadPalettes", "pos": [400, 420], "size": [340, 300],
     "widgets_values": ["pico-8-1x.png", False, _GRID_SETTINGS, 40, "#f40e12", "#fff", 6, True, 3],
     "outputs": [{"name": "paletteList", "type": "LIST", "slot_index": 0}]},
    {"id": 3, "type": "PixelArtDetectorConverter", "pos": [800, 200], "size": [420, 620],
     "widgets_values": ["GAMEBOY", 64, 64, "contain", "Image.quantize", 2, False, "Image.quantize", 128,
                        True, "MAXCOVERAGE", _OPENCV_SETTINGS, "RANDOM_CENTERS", 10, 10, "EUCLIDEAN_SQUARE",
                        _CLEANUP, False, 0.02, "none"],
     "inputs": [{"name": "images", "type": "IMAGE"},
                {"name": "paletteList", "type": "LIST"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 4, "type": "SaveImage", "pos": [1280, 200], "size": [400, 300],
     "widgets_values": ["2D/pixel_convert/sprite"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 5, "type": "MarkdownNote", "pos": [40, 620], "size": [420, 320]},
]

LINKS = [
    [1, 1, 0, 3, 0, "IMAGE"],
    [2, 2, 0, 3, 1, "LIST"],
    [3, 3, 0, 4, 0, "IMAGE"],
]
