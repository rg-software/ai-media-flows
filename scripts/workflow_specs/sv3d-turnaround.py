"""Spec for 3d/workflows/sv3d-turnaround.json - build with scripts/build_workflow.py.

Kept next to the generator it feeds so the workflow can be rebuilt instead of hand-edited.

This flow exists because `hy3d-multiview` presumes a turnaround (front/left/right/back) that nothing in
the repo produced. E9 measured that SV3D_p does produce one from a single image in 15 s at ~7 GB VRAM,
and that its `azimuth_points_string` gives exact camera control: the point index IS the frame, so
`0:(0.0), 1:(90.0), 2:(180.0), 3:(270.0)` with `batch_size=4` is a 4-view turnaround in one pass.
"""

NOTE = (
    "## sv3d-turnaround.json\n\n"
    "One image -> a consistent multi-view turnaround (no mesh needed)\n\n"
    "**Does:** SV3D_p takes a single image and renders the same object from fixed azimuths. One batch, "
    "four views at 0/90/180/270, in ~15 s on the 3090 at ~7 GB VRAM (E9).\n"
    "**Why:** `hy3d-multiview` needs front/left/right/back, and nothing in the repo made them - the flow "
    "presumed an asset we never had. This is that asset, and it needs no mesh, so it also serves cases "
    "where only views are wanted (a sprite that must read from several angles, a reference sheet).\n"
    "**The knob that matters:** `azimuth_points_string` / `elevation_points_string` - the point index is "
    "the frame, so `0:(0.0), 1:(90.0), 2:(180.0), 3:(270.0)` is four evenly spaced views and "
    "`batch_size` must equal the last index + 1. Raise `batch_size` to 21 with the default 0/180/360 "
    "points for a smooth orbit instead of four stops. `VideoLinearCFGGuidance` is required (SV3D is an "
    "image-to-video model), and `elevation` stays at 0 for a level turnaround.\n"
    "**Licence:** the SV3D weights are Stability **non-commercial** (commercial use needs a Stability "
    "Membership), so anything shipped from this flow inherits that - same posture as Kontext and "
    "4x-UltraSharp in the 2D scenario. The weights live in `models/checkpoints/sv3d_p.safetensors` and "
    "are gated on Hugging Face (`stabilityai/sv3d`).\n"
    "**See:** `3d/EXPERIMENTS.md` E9, `3d/README.md`.\n"
    "\n---\n"
    "*How to run it: story **S12** in `HOWTO.md`  \u00b7  Why it is this way: **E9** in the scenario's "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 1, "type": "ImageOnlyCheckpointLoader", "pos": [-900, 200], "size": [360, 100],
     "widgets_values": ["sv3d_p.safetensors"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0},
                 {"name": "CLIP_VISION", "type": "CLIP_VISION", "slot_index": 1},
                 {"name": "VAE", "type": "VAE", "slot_index": 2}]},
    {"id": 2, "type": "LoadImage", "pos": [-900, 380], "size": [315, 314],
     "widgets_values": ["char_knight.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 3, "type": "SV3D_BatchSchedule", "pos": [-500, 200], "size": [400, 200],
     "widgets_values": [576, 576, 4, "linear",
                        "0:(0.0),\n1:(90.0),\n2:(180.0),\n3:(270.0)",
                        "0:(0.0),\n1:(0.0),\n2:(0.0),\n3:(0.0)"],
     "inputs": [{"name": "clip_vision", "type": "CLIP_VISION"},
                {"name": "init_image", "type": "IMAGE"},
                {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2}]},
    {"id": 4, "type": "VideoLinearCFGGuidance", "pos": [-40, 200], "size": [300, 60],
     "widgets_values": [1.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 5, "type": "KSampler", "pos": [300, 200], "size": [320, 262],
     "widgets_values": [42, "fixed", 25, 2.5, "euler", "karras", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 6, "type": "VAEDecode", "pos": [660, 200], "size": [240, 60],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 7, "type": "SaveImage", "pos": [940, 200], "size": [420, 420],
     "widgets_values": ["3D/sv3d_turnaround"],
     "inputs": [{"name": "images", "type": "IMAGE"}]},
    {"id": 8, "type": "MarkdownNote", "pos": [-900, -220], "size": [720, 200]},
]

LINKS = [
    # [link_id, from_id, from_slot, to_id, to_slot, type]
    [1, 1, 1, 3, 0, "CLIP_VISION"],
    [2, 2, 0, 3, 1, "IMAGE"],
    [3, 1, 2, 3, 2, "VAE"],
    [4, 1, 0, 4, 0, "MODEL"],
    [5, 4, 0, 5, 0, "MODEL"],
    [6, 3, 0, 5, 1, "CONDITIONING"],
    [7, 3, 1, 5, 2, "CONDITIONING"],
    [8, 3, 2, 5, 3, "LATENT"],
    [9, 5, 0, 6, 0, "LATENT"],
    [10, 1, 2, 6, 1, "VAE"],
    [11, 6, 0, 7, 0, "IMAGE"],
]
