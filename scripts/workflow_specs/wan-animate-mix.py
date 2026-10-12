"""Spec for video/workflows/wan-animate-mix.json - build with scripts/build_workflow.py.

Placement: put OUR character into footage, keeping the footage. WanAnimateToVideo's **Mix
mode** (character replacement) from the official `video_wan2_2_14B_animate` template, rebuilt
flat with our filenames. E13c (2026-10-10/11) measured it at **375 s for 77 frames at 640x640**
(240 s for 33 at 848x480) on the official Wan2.2-Animate 14B - the 6-step / cfg 1.0 lightx2v
distill recipe makes the 14B route cheap instead of the E19-class 25 minutes.

The three findings that shaped this flow:
- **The reference's face size is the identity knob.** A full-body reference LOSES the face on
  close-up-driven footage (probe B: same outfit and hair, a different woman); a **portrait**
  reference holds it (probe C). Ships `portrait_heroine.png`.
- The character mask is generated **in-graph** (SAM3 text-prompted person on the first frame,
  GrowMask 10, BlockifyMask 32) - no staged mask PNG, no absent SAM2.
- `background_video` is NOT the raw frames: it is the video **with the character region painted
  black** (DrawMaskOnImage) - the black hole is what the model fills with the reference.
"""
from __future__ import annotations

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
       "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
       "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

NOTE = (
    "## wan-animate-mix.json\n\n"
    "Put YOUR character into footage, keeping the footage\n\n"
    "**Does:** character replacement (WanAnimateToVideo **Mix mode**) - a driving clip of a person "
    "in a scene + a **portrait** reference of our character -> the character plays that person's "
    "part, background and lighting kept. This is placement: the character lands *inside* real "
    "footage, not on a generated backdrop. Host: `wan2.2_animate_14B_int8_convrot` (18.4 GB, "
    "**Apache-2.0**, already on the box) + the lightx2v distill lora + our usual umt5/VAE/clip_vision.\n"
    "**Measured (E13c, 2026-10-11):** 77 frames at 640x640 in **375 s**; 33 frames at 848x480 in "
    "**240 s** - DWPose preprocessing included, so this is the *cheap* 14B route (the 6-step / "
    "cfg 1.0 distill recipe). Identity holds with a **portrait** reference; probe B proved a "
    "full-body reference loses the face on close-up-driven footage (same outfit, different woman).\n"
    "**Knobs:** the **reference image** (portrait! that is the identity knob); the **mask prompt** "
    "(`person` on `SAM3_Detect`) and `GrowMask`/`BlockifyMask` (10 / 32) if the driver's person is "
    "unusual; `length` (77 ships); the **prompt** describes the scene action, not the character "
    "(the reference already carries identity). Motion comes from `pose_video` (DWPose hand+body) "
    "and `face_video` (DWPose face), `reference_image_strength`-style tightening is not exposed on "
    "this node.\n"
    "**Traps:** the socket order is `positive, negative, vae, clip_vision_output, reference_image, "
    "face_video, pose_video, background_video, character_mask` - `reference_image` sits AFTER "
    "`clip_vision_output`. The mask and the video must share the canvas (a mismatched mask shows up "
    "as black 32-px blocks - measured). The output prepends the reference as frame 0 (81 frames out "
    "for `length` 77) - trim one second in the engine or with a slice. DWPose auto-downloads its "
    "detectors on first run (`custom_nodes/comfyui_controlnet_aux/ckpts/`). The "
    "relight lora ships in the chain (lightx2v -> relight - the official template includes it): "
    "measured on a\n    neutral-lit room the integration difference is subtle (subject-vs-background palette "
    "mismatch 27.6 -> 25.5\n    across matched frames, E13d) - on strongly-lit scenes it should matter "
    "more; re-measure if a composite\n    reads pasted.\n"
    "**Siblings:** `wan-animate-motion.json` (S15) is the Move mode - motion transfer onto a "
    "generated backdrop; this flow keeps the *footage's* background instead.\n\n"
    "---\n*How to run it: story **S31** in `HOWTO.md`  ·  Why it is this way: **E13c** in "
    "`video/EXPERIMENTS.md`.*"
)

NODES = [
    {"id": 1, "type": "UNETLoader", "pos": [-1700, 100], "size": [340, 90],
     "widgets_values": ["wan2.2_animate_14B_int8_convrot.safetensors", "default"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 2, "type": "LoraLoaderModelOnly", "pos": [-1330, 100], "size": [300, 80],
     "widgets_values": ["lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 38, "type": "LoraLoaderModelOnly", "pos": [-1330, 190], "size": [300, 80],
     "widgets_values": ["WanAnimate_relight_lora_fp16.safetensors", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 3, "type": "ModelSamplingSD3", "pos": [-1000, 100], "size": [220, 60],
     "widgets_values": [8.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 4, "type": "CLIPLoader", "pos": [-1700, 240], "size": [340, 100],
     "widgets_values": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "wan", "default"],
     "outputs": [{"name": "CLIP", "type": "CLIP", "slot_index": 0}]},
    {"id": 5, "type": "CLIPTextEncode", "pos": [-1330, 240], "size": [380, 140],
     "widgets_values": ["The character is dancing in the room"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 6, "type": "CLIPTextEncode", "pos": [-1330, 420], "size": [380, 200],
     "widgets_values": [NEG],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 7, "type": "VAELoader", "pos": [-1700, 560], "size": [340, 60],
     "widgets_values": ["Wan2_1_VAE_bf16.safetensors"],
     "outputs": [{"name": "VAE", "type": "VAE", "slot_index": 0}]},
    {"id": 8, "type": "CLIPVisionLoader", "pos": [-1700, 660], "size": [340, 60],
     "widgets_values": ["clip_vision_h.safetensors"],
     "outputs": [{"name": "CLIP_VISION", "type": "CLIP_VISION", "slot_index": 0}]},
    {"id": 9, "type": "LoadImage", "pos": [-1700, 760], "size": [340, 314],
     "widgets_values": ["portrait_heroine.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 10, "type": "LoadVideo", "pos": [-1700, 1120], "size": [340, 300],
     "widgets_values": ["video_wan2_2_14B_animate_original_video.mp4", "image"],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 11, "type": "GetVideoComponents", "pos": [-1330, 1120], "size": [220, 150],
     "widgets_values": [],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": [{"name": "images", "type": "IMAGE", "slot_index": 0},
                 {"name": "audio", "type": "AUDIO", "slot_index": 1},
                 {"name": "fps", "type": "FLOAT", "slot_index": 2}]},
    {"id": 12, "type": "ImageScale", "pos": [-1080, 1120], "size": [260, 130],
     "widgets_values": ["lanczos", 640, 640, "center"],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 13, "type": "DWPreprocessor", "pos": [-790, 1120], "size": [300, 200],
     "widgets_values": ["disable", "disable", "enable", 640,
                        "yolox_l.onnx", "dw-ll_ucoco_384_bs5.torchscript.pt", "disable"],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "POSE_KEYPOINT", "type": "POSE_KEYPOINT", "slot_index": 1}]},
    {"id": 14, "type": "DWPreprocessor", "pos": [-790, 1360], "size": [300, 200],
     "widgets_values": ["enable", "enable", "disable", 640,
                        "yolox_l.onnx", "dw-ll_ucoco_384_bs5.torchscript.pt", "disable"],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "POSE_KEYPOINT", "type": "POSE_KEYPOINT", "slot_index": 1}]},
    {"id": 15, "type": "ImageFromBatch", "pos": [-790, 1600], "size": [240, 80],
     "widgets_values": [0, 1],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 16, "type": "CheckpointLoaderSimple", "pos": [-790, 1720], "size": [300, 100],
     "widgets_values": ["sam3.1_multiplex_fp16.safetensors"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0},
                 {"name": "CLIP", "type": "CLIP", "slot_index": 1},
                 {"name": "VAE", "type": "VAE", "slot_index": 2}]},
    {"id": 17, "type": "SAM3_Detect", "pos": [-460, 1600], "size": [300, 200],
     "widgets_values": [0.5, 2, False],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "image", "type": "IMAGE"},
                {"name": "conditioning", "type": "CONDITIONING"}],
     "outputs": [{"name": "masks", "type": "MASK", "slot_index": 0},
                 {"name": "bboxes", "type": "BOUNDING_BOX", "slot_index": 1}]},
    {"id": 18, "type": "CLIPTextEncode", "pos": [-460, 1900], "size": [280, 100],
     "widgets_values": ["person"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 19, "type": "GrowMask", "pos": [-130, 1600], "size": [220, 80],
     "widgets_values": [10, True],
     "inputs": [{"name": "mask", "type": "MASK"}],
     "outputs": [{"name": "MASK", "type": "MASK", "slot_index": 0}]},
    {"id": 20, "type": "BlockifyMask", "pos": [-130, 1720], "size": [220, 60],
     "widgets_values": [32],
     "inputs": [{"name": "masks", "type": "MASK"}],
     "outputs": [{"name": "mask", "type": "MASK", "slot_index": 0}]},
    {"id": 21, "type": "DrawMaskOnImage", "pos": [120, 1600], "size": [240, 80],
     "widgets_values": ["0, 0, 0"],
     "inputs": [{"name": "image", "type": "IMAGE"}, {"name": "mask", "type": "MASK"}],
     "outputs": [{"name": "images", "type": "IMAGE", "slot_index": 0}]},
    {"id": 22, "type": "CLIPVisionEncode", "pos": [-1330, 760], "size": [240, 100],
     "widgets_values": ["none"],
     "inputs": [{"name": "clip_vision", "type": "CLIP_VISION"}, {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "CLIP_VISION_OUTPUT", "type": "CLIP_VISION_OUTPUT", "slot_index": 0}]},
    {"id": 23, "type": "WanAnimateToVideo", "pos": [80, 400], "size": [360, 300],
     "widgets_values": [640, 640, 77, 1, 5, 0],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "clip_vision_output", "type": "CLIP_VISION_OUTPUT"},
                {"name": "reference_image", "type": "IMAGE"},
                {"name": "face_video", "type": "IMAGE"},
                {"name": "pose_video", "type": "IMAGE"},
                {"name": "background_video", "type": "IMAGE"},
                {"name": "character_mask", "type": "MASK"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2}]},
    {"id": 24, "type": "KSampler", "pos": [480, 400], "size": [340, 260],
     "widgets_values": [42, "fixed", 6, 1.0, "euler", "simple", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 25, "type": "VAEDecode", "pos": [860, 400], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 26, "type": "CreateVideo", "pos": [1120, 400], "size": [240, 80],
     "widgets_values": [16],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 27, "type": "SaveVideo", "pos": [1400, 400], "size": [340, 300],
     "widgets_values": ["wan-animate-mix", "auto", "auto"],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": []},
    {"id": 28, "type": "MarkdownNote", "pos": [-1700, 1500], "size": [420, 340],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

# [link_id, src_node, src_slot, dst_node, dst_slot, type]
LINKS = [
    [1, 1, 0, 2, 0, "MODEL"],
    [2, 2, 0, 38, 0, "MODEL"],
    [39, 38, 0, 3, 0, "MODEL"],
    [3, 3, 0, 24, 0, "MODEL"],
    [4, 4, 0, 5, 0, "CLIP"],
    [5, 4, 0, 6, 0, "CLIP"],
    [6, 7, 0, 23, 2, "VAE"],
    [7, 7, 0, 25, 1, "VAE"],
    [8, 8, 0, 22, 0, "CLIP_VISION"],
    [9, 9, 0, 22, 1, "IMAGE"],
    [10, 9, 0, 23, 4, "IMAGE"],
    [11, 10, 0, 11, 0, "VIDEO"],
    [12, 11, 0, 12, 0, "IMAGE"],
    [13, 12, 0, 13, 0, "IMAGE"],
    [14, 12, 0, 14, 0, "IMAGE"],
    [15, 12, 0, 15, 0, "IMAGE"],
    [16, 12, 0, 21, 0, "IMAGE"],
    [17, 13, 0, 23, 5, "IMAGE"],
    [18, 14, 0, 23, 6, "IMAGE"],
    [19, 15, 0, 17, 1, "IMAGE"],
    [20, 16, 0, 17, 0, "MODEL"],
    [21, 16, 1, 18, 0, "CLIP"],
    [22, 18, 0, 17, 2, "CONDITIONING"],
    [23, 17, 0, 19, 0, "MASK"],
    [24, 19, 0, 20, 0, "MASK"],
    [25, 20, 0, 23, 8, "MASK"],
    [26, 20, 0, 21, 1, "MASK"],
    [27, 21, 0, 23, 7, "IMAGE"],
    [28, 22, 0, 23, 3, "CLIP_VISION_OUTPUT"],
    [29, 5, 0, 23, 0, "CONDITIONING"],
    [30, 6, 0, 23, 1, "CONDITIONING"],
    [31, 23, 0, 24, 1, "CONDITIONING"],
    [32, 23, 1, 24, 2, "CONDITIONING"],
    [33, 23, 2, 24, 3, "LATENT"],
    [34, 24, 0, 25, 0, "LATENT"],
    [35, 25, 0, 26, 0, "IMAGE"],
    [36, 26, 0, 27, 0, "VIDEO"],
]
