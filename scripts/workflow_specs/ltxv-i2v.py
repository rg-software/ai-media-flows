"""Spec for video/workflows/ltxv-i2v.json - build with scripts/build_workflow.py.

LTX-Video v1 image-to-video: a **still + a descriptive prompt** -> a clip (Lightricks,
LTX-Video Open-Weights 0.X licence - commercial use free under $10M revenue; output
belongs to us). The prompt drives the motion - this is the text-prompt motion source
the repo has no route for, and the fast/cheap iteration path (distilled, few steps).

E22 (2026-10-15) measured two arms on our own heroine still (`char_heroine.png`,
768x768x97, fire-spell prompt): (A) 2B-distilled-fp8 in **15 s** - motion yes, but identity
slips and the spell overgrows to engulf her (MEH); (B) 13B-distilled-fp8 in **35 s**
cold / 5 s warm at **17.3 GB** peak - identity holds, the spell stays palm-scale, framing
stable (PASS, ships as the default; 2B is the wiring/smoke-test arm via `--set`).

LTX-Video v1 (not v2): v2 is 19B under a separate community licence and does not fit
this card (fp8 ~19 GB before encoders; nvfp4 needs Blackwell). The v1 example
workflows this is flattened from are upstream's (ComfyUI_examples/ltxv/).
"""
from __future__ import annotations

POS = ("best quality, 4k, HDR, a red-haired sorceress in ornate blue and gold robes "
       "standing in a stone courtyard, she raises her right hand slowly and a bright "
       "fire spell ignites above her palm, embers drifting upward, her long hair and "
       "cloak stirring in the wind, cinematic lighting, smooth natural motion")
NEG = ("low quality, worst quality, deformed, distorted, disfigured, motion smear, "
       "motion artifacts, fused fingers, bad anatomy, weird hand, ugly")

NOTE = (
    "## ltxv-i2v.json\n\n"
    "Prompt-driven animation of our character (no driving clip)\n\n"
    "**Does:** a still + a **descriptive prompt** -> a clip of the character performing it "
    "(`LTXVImgToVideo`, Lightricks LTX-Video v1). The VAE rides inside the checkpoint "
    "(`CheckpointLoaderSimple`); text comes from `t5xxl_fp8` with CLIP type `ltxv`. LTX wants "
    "**long descriptive prompts** (upstream's own warning - a short prompt visibly degrades it) "
    "and canvases in multiples of 32 with 8n+1 frames.\n"
    "**Measured (E22, 2026-10-15):** 13B-distilled-fp8 (ships): 97 frames at 768x768 in **35 s** cold / 5 s warm, **17.3 GB** peak; identity holds and the spell stays palm-scale. 2B-distilled-fp8: 15 s but identity slips and the spell overgrows (the quick-test arm). Shared config: bundled VAE, t5xxl_fp8 with CLIP type `ltxv`, 8 steps, no STG, cfg 1.\n"
    "**Knobs:** the **prompt** (elaborate, motion-first); the **checkpoint** (13B-distilled-fp8 "
    "ships - 35 s cold; 2B-distilled-fp8 is the 15-s quick-test arm, same graph via "
    "`--set`); **steps** on `LTXVScheduler` (8 ships for distilled); canvas/frames (32 / 8n+1).\n"
    "**Traps:** distilled runs with NO STG and cfg 1 (vendor multi-scale recipe); fps is 25 "
    "(`LTXVConditioning.frame_rate` + `CreateVideo`). This is v1, not v2 - v2 is 19B and does "
    "not fit this card.\n"
    "**Siblings:** `wan-vace-reference.json` (S28) is the other prompt-driven route (14B, 45 min); "
    "this one is the fast arm.\n\n"
    "---\n*How to run it: story **S35** in `HOWTO.md`  ·  Why it is this way: **E22** in "
    "`video/EXPERIMENTS.md`.*"
)

NODES = [
    {"id": 1, "type": "CheckpointLoaderSimple", "pos": [-1400, 100], "size": [380, 90],
     "widgets_values": ["ltxv-13b-0.9.8-distilled-fp8.safetensors"],
     "inputs": [],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0},
                 {"name": "CLIP", "type": "CLIP", "slot_index": 1},
                 {"name": "VAE", "type": "VAE", "slot_index": 2}]},
    {"id": 2, "type": "CLIPLoader", "pos": [-1400, 240], "size": [380, 90],
     "widgets_values": ["t5xxl_fp8_e4m3fn_scaled.safetensors", "ltxv", "default"],
     "inputs": [],
     "outputs": [{"name": "CLIP", "type": "CLIP", "slot_index": 0}]},
    {"id": 3, "type": "CLIPTextEncode", "pos": [-980, 100], "size": [400, 140],
     "widgets_values": [POS],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 4, "type": "CLIPTextEncode", "pos": [-980, 280], "size": [400, 140],
     "widgets_values": [NEG],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 5, "type": "LoadImage", "pos": [-1400, 420], "size": [380, 420],
     "widgets_values": ["char_heroine.png", "image"],
     "inputs": [],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 6, "type": "LTXVImgToVideo", "pos": [-540, 100], "size": [340, 220],
     "widgets_values": [768, 768, 97, 1],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2}]},
    {"id": 7, "type": "LTXVConditioning", "pos": [-540, 360], "size": [340, 80],
     "widgets_values": [25.0],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1}]},
    {"id": 8, "type": "LTXVScheduler", "pos": [-540, 480], "size": [340, 160],
     "widgets_values": [8, 2.05, 0.95, True, 0.1],
     "inputs": [],
     "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "slot_index": 0}]},
    {"id": 9, "type": "KSamplerSelect", "pos": [-1400, 880], "size": [340, 60],
     "widgets_values": ["euler"],
     "inputs": [],
     "outputs": [{"name": "SAMPLER", "type": "SAMPLER", "slot_index": 0}]},
    {"id": 10, "type": "SamplerCustom", "pos": [-160, 100], "size": [360, 260],
     "widgets_values": [True, 42, "fixed", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "sampler", "type": "SAMPLER"},
                {"name": "sigmas", "type": "SIGMAS"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "output", "type": "LATENT", "slot_index": 0},
                 {"name": "denoised_output", "type": "LATENT", "slot_index": 1}]},
    {"id": 11, "type": "VAEDecode", "pos": [240, 100], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"},
                {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 12, "type": "CreateVideo", "pos": [500, 100], "size": [260, 100],
     "widgets_values": [25],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 13, "type": "SaveVideo", "pos": [800, 100], "size": [340, 300],
     "widgets_values": ["ltxv-i2v", "auto", "auto"],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": []},
    {"id": 14, "type": "MarkdownNote", "pos": [-1400, 1000], "size": [420, 340],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

LINKS = [
    (1, 1, 0, 10, 0, "MODEL"),
    (2, 1, 2, 11, 1, "VAE"),
    (3, 2, 0, 3, 0, "CLIP"),
    (4, 2, 0, 4, 0, "CLIP"),
    (5, 3, 0, 6, 0, "CONDITIONING"),
    (6, 4, 0, 6, 1, "CONDITIONING"),
    (7, 5, 0, 6, 3, "IMAGE"),
    (8, 1, 2, 6, 2, "VAE"),
    (9, 6, 0, 7, 0, "CONDITIONING"),
    (10, 6, 1, 7, 1, "CONDITIONING"),
    (11, 7, 0, 10, 1, "CONDITIONING"),
    (12, 7, 1, 10, 2, "CONDITIONING"),
    (13, 9, 0, 10, 3, "SAMPLER"),
    (14, 8, 0, 10, 4, "SIGMAS"),
    (15, 6, 2, 10, 5, "LATENT"),
    (16, 10, 0, 11, 0, "LATENT"),
    (17, 11, 0, 12, 0, "IMAGE"),
    (18, 12, 0, 13, 0, "VIDEO"),
]
