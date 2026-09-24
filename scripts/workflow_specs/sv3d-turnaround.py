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
    "**Does:** SV3D_p takes a single image and renders the same object from fixed azimuths. Ships a "
    "**21-frame orbit** (18 deg per frame): ~45 s on the 3090 at ~7 GB VRAM, all frames saved, and you "
    "take whatever views you need.\n"
    "**Why the orbit and not four stops:** measured on `char_knight.png` (E9b) - asking for four "
    "independent 90 deg jumps makes the model hallucinate the back badly, because it is a *video* "
    "diffusion model and is far better at advancing the camera a little than teleporting it.\n"
    "A smooth orbit sampled at the compass points gives a coherent rear view instead of a jumble "
    "(compare rows A and C of `3d/evidence/E9b-knight-sv3d-variants.png`). No text prompt is involved "
    "and none can be: the node conditions on CLIP *vision* embeds and camera pose only, with an "
    "all-zeros negative (see `SV3D_Conditioning.execute`).\n"
    "**Picking views:** with 21 frames the increment is 360/20 = 18 deg, so **frame 0 = 0 deg, "
    "5 = 90, 10 = 180, 15 = 270** and frame 20 wraps back to 0 deg. Those four are what "
    "`hy3d-multiview-workflow.json` wants for front/left/right/back.\n"
    "**The knob that matters:** `batch_size` must equal the last point index + 1. `azimuth_points_string` "
    "`0:(0.0), 9:(180.0), 20:(360.0)` is a full orbit; put more points in for finer sampling. Elevation "
    "stays 0 for a level turnaround. `VideoLinearCFGGuidance` is required (SV3D is an image-to-video "
    "model); 25 steps / cfg 2.5 is fine - 40/3.5 changed nothing much.\n"
    "**Licence:** the SV3D weights are Stability **non-commercial** (commercial use needs a Stability "
    "Membership), so anything shipped from this flow inherits that - same posture as Kontext and "
    "4x-UltraSharp in the 2D scenario. The weights live in `models/checkpoints/sv3d_p.safetensors` and "
    "are gated on Hugging Face (`stabilityai/sv3d`).\n"
    "**See:** `3d/EXPERIMENTS.md` E9/E9b, `3d/README.md`.\n"
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
     "widgets_values": [576, 576, 21, "linear",
                        "0:(0.0),\n9:(180.0),\n20:(360.0)",
                        "0:(0.0),\n9:(0.0),\n20:(0.0)"],
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
