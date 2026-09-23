"""Spec for 2d/workflows/upscale-seedvr2.json - build with scripts/build_workflow.py.

SeedVR2 upscale/restore, with the same `ImageCompare` viewer as `upscale.json` so the result can be judged
against the source with a slider.

Widget values matter positionally (see the node gotcha in comfyui/README.md): the frontend stores an extra
`control_after_generate` string right after a `seed` widget, so `SeedVR2VideoUpscaler` carries 13 values for
12 widgets. Shipping 12 was the bug that made this flow fail validation at run time with errors that named
the wrong fields (`resolution` reading 0, `latent_noise_scale` reading 'cpu').
"""

NOTE = (
    "## upscale-seedvr2.json\n\n"
    "SeedVR2 upscale / restore, with a before/after slider\n\n"
    "U1 - SeedVR2 (Apache 2.0) replaces the non-commercial 4x-UltraSharp. RESOLUTION IS THE SHORT EDGE, not "
    "a multiplier: resolution=2048 on a 1024 input gives 2048. batch_size must follow 4n+1 (use 1 for a "
    "single still). color_correction='lab' is the recommended highest-fidelity mode. 24 GB -> 7B fp16 with no "
    "memory tricks (offload_device=none on the loaders); drop to 3B fp16 or 7B fp8 + blocks_to_swap/offloading "
    "if it OOMs. Measured vs 4x-UltraSharp at 2x: more reconstructed detail (grad-var 137.0 vs 97.7) but more "
    "drift from the source (2.70 vs 1.29) and slower (39 s vs 6 s) - it regenerates rather than enlarges.\n"
    "**Slider:** `ImageCompare` shows the source against the result; the `SaveImage` is the deliverable.\n\n"
    "---\n*How to run it: story **S9** in `HOWTO.md`  ·  Why it is this way: **U1/E13f** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "LoadImage", "pos": [-1000, 0], "size": [320, 320],
     "widgets_values": ["2d/char_knight.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 2, "type": "SeedVR2LoadDiTModel", "pos": [-1000, 400], "size": [380, 220],
     "widgets_values": ["seedvr2_ema_7b_fp16.safetensors", "cuda:0", 0, False, "none", False, "sdpa"],
     "outputs": [{"name": "SEEDVR2_DIT", "type": "SEEDVR2_DIT", "slot_index": 0}]},
    {"id": 3, "type": "SeedVR2LoadVAEModel", "pos": [-1000, 700], "size": [380, 300],
     "widgets_values": ["ema_vae_fp16.safetensors", "cuda:0", False, 1024, 128, False, 1024, 128, "false",
                        "none", False],
     "outputs": [{"name": "SEEDVR2_VAE", "type": "SEEDVR2_VAE", "slot_index": 0}]},
    # 13 values: seed, control_after_generate, resolution, max_resolution, batch_size, uniform_batch_size,
    # color_correction, temporal_overlap, prepend_frames, input_noise_scale, latent_noise_scale,
    # offload_device, enable_debug
    {"id": 4, "type": "SeedVR2VideoUpscaler", "pos": [-560, 0], "size": [360, 480],
     "widgets_values": [42, "fixed", 2048, 0, 1, False, "lab", 0, 0, 0.0, 0.0, "cpu", False],
     "inputs": [{"name": "image", "type": "IMAGE"},
                {"name": "dit", "type": "SEEDVR2_DIT"},
                {"name": "vae", "type": "SEEDVR2_VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 5, "type": "SaveImage", "pos": [-140, 0], "size": [400, 300],
     "widgets_values": ["2D/U1/seedvr2"], "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 6, "type": "ImageCompare", "pos": [-140, 400], "size": [420, 460],
     "inputs": [{"name": "image_a", "type": "IMAGE", "shape": 7},
                {"name": "image_b", "type": "IMAGE", "shape": 7}]},
    {"id": 7, "type": "MarkdownNote", "pos": [-1000, -220], "size": [720, 200]},
]

LINKS = [
    [1, 1, 0, 4, 0, "IMAGE"],
    [2, 2, 0, 4, 1, "SEEDVR2_DIT"],
    [3, 3, 0, 4, 2, "SEEDVR2_VAE"],
    [4, 4, 0, 5, 0, "IMAGE"],        # result -> SaveImage
    [5, 1, 0, 6, 0, "IMAGE"],        # source -> compare A
    [6, 4, 0, 6, 1, "IMAGE"],        # result -> compare B
]
