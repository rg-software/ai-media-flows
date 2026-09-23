"""Spec for 2d/workflows/upscale.json - build with scripts/build_workflow.py.

The smallest useful upscale: one x4 GAN pass, saved, plus an `ImageCompare` viewer so the result can be
judged against the source with a slider instead of by opening two files. It used to be an E4 *comparison*
workflow - a 512 px crop feeding bicubic, RealESRGAN and 4x-UltraSharp into three SaveImages - which is
where the crop came from; the comparison did its job and the winner is what runs here.
"""

NOTE = (
    "## upscale.json\n\n"
    "x4 upscale (GAN) with a before/after slider\n\n"
    "**Does:** one x4 GAN pass - **faithful**, it invents nothing, so it cannot drift away from the source. "
    "The `ImageCompare` node at the end shows the source and the result in one viewport with a slider; the "
    "`SaveImage` is the deliverable (the comparer only previews, so nothing extra is written by it).\n"
    "**Which to use:** shippable output -> `upscale-seedvr2.json` (Apache-2.0). This flow -> when you want "
    "the source respected, and you accept the licence below.\n"
    "**Trap:** `4x-UltraSharp` is **non-commercial** - do not ship its output. The loader's model dropdown "
    "can be switched to `RealESRGAN_x4plus` (permissive; over-smooths concept art a little) if you need a "
    "clean licence without changing the flow.\n"
    "**Note:** the model multiplies by 4, so a 1024 px input becomes 4096 px.\n\n"
    "---\n*How to run it: story **S9** in `HOWTO.md`  ·  Why it is this way: **E4b** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [40, 200], "size": [320, 320],
     "widgets_values": ["2d/env_cottage.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "UpscaleModelLoader", "pos": [400, 420], "size": [380, 60],
     "widgets_values": ["4x-UltraSharp.safetensors"],
     "outputs": [{"name": "UPSCALE_MODEL", "type": "UPSCALE_MODEL", "slot_index": 0}]},
    {"id": 3, "type": "ImageUpscaleWithModel", "pos": [820, 200], "size": [300, 100],
     "inputs": [{"name": "upscale_model", "type": "UPSCALE_MODEL"},
                {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 4, "type": "SaveImage", "pos": [1180, 120], "size": [400, 300],
     "widgets_values": ["2D/upscale/x4"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    # the viewer: source vs result. socketless `compare_view` state is the frontend's, stored as [].
    {"id": 5, "type": "ImageCompare", "pos": [1180, 460], "size": [420, 460],
     "inputs": [{"name": "image_a", "type": "IMAGE", "shape": 7},
                {"name": "image_b", "type": "IMAGE", "shape": 7}]},
    {"id": 6, "type": "MarkdownNote", "pos": [40, 560], "size": [420, 320]},
]

LINKS = [
    [1, 1, 0, 3, 1, "IMAGE"],        # source -> upscaler image
    [2, 2, 0, 3, 0, "UPSCALE_MODEL"],
    [3, 3, 0, 4, 0, "IMAGE"],        # result -> SaveImage
    [4, 1, 0, 5, 0, "IMAGE"],        # source -> compare A
    [5, 3, 0, 5, 1, "IMAGE"],        # result -> compare B
]
