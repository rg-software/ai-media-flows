"""Spec for video/workflows/wan-camera-control.json - build with scripts/build_workflow.py.

Camera-controlled video from a still: the start image plus a **preset camera trajectory**
(Static / Pan / Zoom / orbit) instead of the model inventing its own camera (which drifts).
Built from ComfyUI's upstream `wan/camera_image_to_video_wan_example.json` with our
filenames and our asset; E18 (2026-10-10) measured this graph at **115 s per 81-frame cell**
on the official 3.23 GB Fun-Camera 1.3B, with Static holding the framing still, Pan Left
walking the subject across frame and Zoom In pushing in - the drift simply absent.

Note the gotcha the example hides: `WanCameraEmbedding` *outputs* width/height/length and
they are linked into `WanCameraImageToVideo`, so **the embedding owns the canvas** - the
target node's own width/height widgets are overridden (shipped 832x480; the example's
512x512 embedding is what its own run produced).
"""
from __future__ import annotations

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
       "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
       "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

NOTE = (
    "## wan-camera-control.json\n\n"
    "A clip with a camera you chose, not one the model invents\n\n"
    "**Does:** takes a **still** as the first frame and animates it along a **preset camera trajectory** - "
    "`Static`, `Pan Up/Down/Left/Right`, `Zoom In/Out`, `Anti Clockwise` / `ClockWise` (`WanCameraEmbedding`). "
    "The reason this flow exists: in the other Wan routes the camera is **text-driven and drifts** (E18's own "
    "finding), and here it is an input instead. Host: `wan2.1_fun_camera_v1.1_1.3B_bf16` (3.23 GB, "
    "**Apache-2.0**, official Comfy-Org repack) + the umt5 encoder, `clip_vision_h` and the Wan VAE we ship.\n"
    "**Measured (E18, 2026-10-10):** 81 frames per cell in **115 s** - about 1/20th of the VACE 14B route - with "
    "**identity holding** in all three cells tested (Static / Pan Left / Zoom In). The evidence sheet "
    "(`video/evidence/E18-camera-sheet.png`) shows exactly what each preset does: Static keeps the framing "
    "dead-still (drift gone), Pan Left walks the subject across frame, Zoom In goes full body -> chest close-up.\n"
    "**Knobs:** `camera_pose` (the preset) is the point of the flow; **width/height/length live on the "
    "`WanCameraEmbedding`, not on the target node** - the embedding *outputs* them and they are linked in, so its "
    "512x512 in the upstream example silently overrides the node's own 832x480. It ships **512x512** because a portrait start image is *cropped* in 16:9 (measured: our own `char_heroine.png` loses her head at 832x480) - for 16:9, letterbox the start image first (`scripts/letterbox_16x9.py`, one command) and set the embedding's width/height to **832**/**480**. Also `steps`/`cfg` (20 / 6.0) and "
    "the **start image**: give it a clean, well-lit still - the first frame is the clip's first frame, so its "
    "composition is what the camera departs from.\n"
    "**Traps:** a portrait still into a landscape canvas crops - measured, the head goes first, which is what the letterbox step is for - and the subject is what must survive the "
    "pan), and the trajectory is a **fixed preset** - a bespoke camera path needs the node's JSON pose input, which "
    "this flow does not expose.\n"
    "**Siblings:** `wan-animate-motion.json` (S15) copies motion from a driving clip; "
    "`wan-vace-reference.json` (S28) writes motion from a prompt. This one is the cheap one.\n\n"
    "---\n*How to run it: story **S29** in `HOWTO.md`  ·  Why it is this way: **E18** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 37, "type": "UNETLoader", "pos": [-1500, 460], "size": [340, 100],
     "widgets_values": ["wan2.1_fun_camera_v1.1_1.3B_bf16.safetensors", "default"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 54, "type": "ModelSamplingSD3", "pos": [-1100, 460], "size": [220, 80],
     "widgets_values": [8.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 38, "type": "CLIPLoader", "pos": [-1500, 240], "size": [340, 100],
     "widgets_values": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "wan", "default"],
     "outputs": [{"name": "CLIP", "type": "CLIP", "slot_index": 0}]},
    {"id": 39, "type": "VAELoader", "pos": [-1500, 20], "size": [340, 80],
     "widgets_values": ["Wan2_1_VAE_bf16.safetensors"],
     "outputs": [{"name": "VAE", "type": "VAE", "slot_index": 0}]},
    {"id": 49, "type": "CLIPVisionLoader", "pos": [-1500, 700], "size": [340, 80],
     "widgets_values": ["clip_vision_h.safetensors"],
     "outputs": [{"name": "CLIP_VISION", "type": "CLIP_VISION", "slot_index": 0}]},
    {"id": 52, "type": "LoadImage", "pos": [-1500, 900], "size": [340, 314],
     "widgets_values": ["char_heroine.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 51, "type": "CLIPVisionEncode", "pos": [-1100, 700], "size": [240, 120],
     "widgets_values": ["none"],
     "inputs": [{"name": "clip_vision", "type": "CLIP_VISION"}, {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "CLIP_VISION_OUTPUT", "type": "CLIP_VISION_OUTPUT", "slot_index": 0}]},
    {"id": 6, "type": "CLIPTextEncode", "pos": [-1100, 240], "size": [440, 160],
     "widgets_values": ["a red-haired sorceress in a blue and gold gown standing calmly, full body, plain background"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 7, "type": "CLIPTextEncode", "pos": [-1100, 20], "size": [440, 200],
     "widgets_values": [NEG],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 57, "type": "WanCameraEmbedding", "pos": [-1100, 1020], "size": [300, 220],
     "widgets_values": ["Static", 512, 512, 81, 1.0, 0.5, 0.5, 0.5, 0.5],
     "inputs": [],
     "outputs": [{"name": "camera_embedding", "type": "WAN_CAMERA_EMBEDDING", "slot_index": 0},
                 {"name": "width", "type": "INT", "slot_index": 1},
                 {"name": "height", "type": "INT", "slot_index": 2},
                 {"name": "length", "type": "INT", "slot_index": 3}]},
    {"id": 56, "type": "WanCameraImageToVideo", "pos": [-600, 400], "size": [340, 220],
     "widgets_values": [512, 512, 81, 1],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "clip_vision_output", "type": "CLIP_VISION_OUTPUT"},
                {"name": "start_image", "type": "IMAGE"},
                {"name": "camera_conditions", "type": "WAN_CAMERA_EMBEDDING"},
                {"name": "width", "type": "INT"},
                {"name": "height", "type": "INT"},
                {"name": "length", "type": "INT"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2}]},
    {"id": 3, "type": "KSampler", "pos": [-200, 400], "size": [340, 260],
     "widgets_values": [42, "fixed", 20, 6.0, "uni_pc", "simple", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 8, "type": "VAEDecode", "pos": [200, 400], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 28, "type": "SaveAnimatedWEBP", "pos": [480, 320], "size": [340, 200],
     "widgets_values": ["wan-camera-control", 16, False, 90, "default"],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": []},
    {"id": 47, "type": "SaveWEBM", "pos": [480, 560], "size": [340, 220],
     "widgets_values": ["wan-camera-control", "vp9", 16.0, 0],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": []},
    {"id": 60, "type": "MarkdownNote", "pos": [-1500, 1300], "size": [420, 320],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

# [link_id, src_node, src_slot, dst_node, dst_slot, type]
LINKS = [
    [1, 37, 0, 54, 0, "MODEL"],
    [2, 54, 0, 3, 0, "MODEL"],
    [3, 38, 0, 6, 0, "CLIP"],
    [4, 38, 0, 7, 0, "CLIP"],
    [5, 39, 0, 56, 2, "VAE"],
    [6, 39, 0, 8, 1, "VAE"],
    [7, 49, 0, 51, 0, "CLIP_VISION"],
    [8, 52, 0, 51, 1, "IMAGE"],
    [9, 52, 0, 56, 4, "IMAGE"],
    [10, 51, 0, 56, 3, "CLIP_VISION_OUTPUT"],
    [11, 6, 0, 56, 0, "CONDITIONING"],
    [12, 7, 0, 56, 1, "CONDITIONING"],
    [13, 57, 0, 56, 5, "WAN_CAMERA_EMBEDDING"],
    [14, 57, 1, 56, 6, "INT"],
    [15, 57, 2, 56, 7, "INT"],
    [16, 57, 3, 56, 8, "INT"],
    [17, 56, 0, 3, 1, "CONDITIONING"],
    [18, 56, 1, 3, 2, "CONDITIONING"],
    [19, 56, 2, 3, 3, "LATENT"],
    [20, 3, 0, 8, 0, "LATENT"],
    [21, 8, 0, 28, 0, "IMAGE"],
    [22, 8, 0, 47, 0, "IMAGE"],
]
