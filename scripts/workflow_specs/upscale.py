"""Spec for 2d/workflows/upscale.json - build with scripts/build_workflow.py.

Smaller than it was: this flow was an E4 *comparison* (a 512 px crop feeding bicubic, RealESRGAN and
4x-UltraSharp side by side). The comparison served its purpose; what a user needs is the one pass that won,
so the crop and the two extra arms are gone.
"""

NOTE = (
    "## upscale.json\n\n"
    "x4 upscale (GAN)\n\n"
    "**Does:** one x4 GAN pass - **faithful**, it invents nothing, so it cannot drift away from the source. "
    "That is the opposite trade from `upscale-seedvr2.json`, which reconstructs more detail (grad-var 137 vs "
    "98) but moves further from the original (drift 2.70 vs 1.29) and takes ~6x as long.\n"
    "**Which to use:** shippable output -> `upscale-seedvr2.json` (Apache-2.0). This flow -> when you want "
    "the source respected, and you accept the licence below.\n"
    "**Trap:** `4x-UltraSharp` is **non-commercial** - do not ship its output. The loader's model dropdown "
    "can be switched to `RealESRGAN_x4plus` (permissive; over-smooths concept art a little) if you need a "
    "clean licence without changing flow.\n"
    "**Note:** the model multiplies by 4, so a 1024 px input becomes 4096 px. There is no crop here any more "
    "- E4 cropped to 512 only so three methods could be compared quickly on the same tile.\n\n"
    "---\n*How to run it: story **S9** in `HOWTO.md`  ·  Why it is this way: **E4b** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 200], "widgets_values": ["2d/env_cottage.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "UpscaleModelLoader", "pos": [360, 200],
     "widgets_values": ["4x-UltraSharp.safetensors"],
     "outputs": [{"name": "UPSCALE_MODEL", "type": "UPSCALE_MODEL", "slot_index": 0}]},
    {"id": 3, "type": "ImageUpscaleWithModel", "pos": [700, 200],
     "inputs": [{"name": "upscale_model", "type": "UPSCALE_MODEL"},
                {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 4, "type": "SaveImage", "pos": [1040, 200], "widgets_values": ["2D/upscale/x4"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 5, "type": "MarkdownNote", "pos": [40, 420]},
]

LINKS = [
    [1, 1, 0, 3, 1, "IMAGE"],
    [2, 2, 0, 3, 0, "UPSCALE_MODEL"],
    [3, 3, 0, 4, 0, "IMAGE"],
]
