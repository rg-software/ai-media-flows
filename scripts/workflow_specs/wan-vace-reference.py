"""Spec for video/workflows/wan-vace-reference.json - build with scripts/build_workflow.py.

VACE **reference-to-video**: our own character image + a prompt -> a clip that keeps her
identity and acts out the prompt, with no driving clip. Built from ComfyUI's upstream
`wan/vace_reference_to_video.json` with our filenames, our asset as the reference, and
the values E13b measured on the box (2026-10-10: 81 frames at 768x768, 20 steps, cfg 6,
shift 8 -> 2729 s / 45.5 min at 17.25 GB VRAM, identity holding across the clip).
"""
from __future__ import annotations

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
       "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
       "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

NOTE = (
    "## wan-vace-reference.json\n\n"
    "Prompt-driven animation of a character you own (no driving clip)\n\n"
    "**Does:** VACE **reference-to-video** - your character image goes in as the **reference** and the prompt says "
    "what she should *do*; the model keeps her identity and acts it out, in the reference's own look and its plain "
    "background. Wan2.1-VACE 14B fp8_scaled (`wan2.1_vace_14B_fp8_scaled.safetensors`, 17.6 GB, **Apache-2.0**) "
    "plus the umt5 text encoder and Wan VAE this box already ships. **This is the counterpart to "
    "`wan-animate-motion.json` (S18):** that flow copies motion from a *driving clip*; this one writes the motion "
    "from *words* - the one motion source we had no route for.\n"
    "**Measured (E13b, 2026-10-10):** 81 frames at 768x768, 20 steps, cfg 6, shift 8 -> **2729 s (45.5 min)** on the "
    "3090 at 17.25 GB VRAM. **Identity holds** on our own `char_heroine.png` across the clip, and the prompt's fire "
    "spell appears and grows in her hand (strip: `video/evidence/E13b-vace-single-strip.png`). **Two honest "
    "defects:** the gown's hem smears into a painterly swirl early, and the **last third drifts** (the action "
    "dominates, the figure softens) - keep the first ~two thirds if identity is what matters.\n"
    "**Knobs:** `length` on `WanVaceToVideo` (81 ships = 3.4 s at 24 fps; the value quantises in 4-frame chunks), "
    "**steps/cfg** on the sampler (20 / 6.0 - the 6-step distil LoRA the Animate flow uses is named for I2V at 480p "
    "and is untested with VACE reference mode), **shift** on `ModelSamplingSD3` (8.0), and the canvas (768x768 "
    "ships; 480x848 roughly halves the cost if you accept the crop).\n"
    "**Traps:** the reference brings its **background** with it - a busy photo gives a busy clip, so use a plain "
    "one. Never GGUF this model (the same metadata trap as Wan-Animate-2). And when you copy an upstream example, "
    "**audit every loader filename against what this box holds**: the example loads `wan_2.1_vae.safetensors`, "
    "which we do not have - ours is `Wan2_1_VAE_bf16.safetensors` (wired here).\n"
    "**Not in this flow yet:** several subjects at once and region placement (the reference pair and the "
    "`control_video` + `control_masks` arms) are measured in E13b and tracked there.\n\n"
    "---\n*How to run it: story **S28** in `HOWTO.md`  ·  Why it is this way: **E13/E13b** in the scenarios' "
    "`EXPERIMENTS` logs.*"
)

NODES = [
    {"id": 37, "type": "UNETLoader", "pos": [-1500, 460], "size": [340, 100],
     "widgets_values": ["wan2.1_vace_14B_fp8_scaled.safetensors", "default"],
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
    {"id": 52, "type": "LoadImage", "pos": [-1500, 760], "size": [340, 314],
     "widgets_values": ["char_heroine.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 6, "type": "CLIPTextEncode", "pos": [-1100, 240], "size": [440, 160],
     "widgets_values": ["a red-haired sorceress in a blue and gold gown spinning gracefully and casting a fire spell, "
                        "full body, plain background"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 7, "type": "CLIPTextEncode", "pos": [-1100, 20], "size": [440, 200],
     "widgets_values": [NEG],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 55, "type": "WanVaceToVideo", "pos": [-600, 300], "size": [340, 200],
     "widgets_values": [768, 768, 81, 1, 1],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "reference_image", "type": "IMAGE"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2},
                 {"name": "trim_latent", "type": "INT", "slot_index": 3}]},
    {"id": 3, "type": "KSampler", "pos": [-200, 300], "size": [340, 260],
     "widgets_values": [42, "fixed", 20, 6.0, "uni_pc", "simple", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 56, "type": "TrimVideoLatent", "pos": [200, 300], "size": [240, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"},
                {"name": "trim_amount", "type": "INT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 8, "type": "VAEDecode", "pos": [500, 300], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 28, "type": "SaveAnimatedWEBP", "pos": [780, 220], "size": [340, 200],
     "widgets_values": ["wan-vace-reference", 16, False, 90, "default"],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": []},
    {"id": 47, "type": "SaveWEBM", "pos": [780, 460], "size": [340, 220],
     "widgets_values": ["wan-vace-reference", "vp9", 16.0, 0],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": []},
    {"id": 60, "type": "MarkdownNote", "pos": [-1500, 1180], "size": [420, 320],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

# [link_id, src_node, src_slot, dst_node, dst_slot, type]
LINKS = [
    [1, 37, 0, 54, 0, "MODEL"],
    [2, 54, 0, 3, 0, "MODEL"],
    [3, 38, 0, 6, 0, "CLIP"],
    [4, 38, 0, 7, 0, "CLIP"],
    [5, 6, 0, 55, 0, "CONDITIONING"],
    [6, 7, 0, 55, 1, "CONDITIONING"],
    [7, 39, 0, 55, 2, "VAE"],
    [8, 52, 0, 55, 3, "IMAGE"],
    [9, 55, 0, 3, 1, "CONDITIONING"],
    [10, 55, 1, 3, 2, "CONDITIONING"],
    [11, 55, 2, 3, 3, "LATENT"],
    [12, 3, 0, 56, 0, "LATENT"],
    [13, 55, 3, 56, 1, "INT"],
    [14, 56, 0, 8, 0, "LATENT"],
    [15, 39, 0, 8, 1, "VAE"],
    [16, 8, 0, 28, 0, "IMAGE"],
    [17, 8, 0, 47, 0, "IMAGE"],
]
