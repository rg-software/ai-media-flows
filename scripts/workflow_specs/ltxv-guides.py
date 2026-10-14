"""Spec for video/workflows/ltxv-guides.json - build with scripts/build_workflow.py.

LTX-Video v1 keyframe guides: stills pinned at chosen frame indices + a prompt ->
a clip that travels between them. This is the keyframed-motion source the repo has
no route for (PIPELINES.md item 1): pose-to-pose animation becomes "S7 stills in,
clip out".

WIRING NOTE (measured): the grown-guide node `LTXVAddGuideMulti` is a DynamicCombo
whose sub-inputs must arrive nested under the combo key - our sweep_workflow flattens
every link top-level, which the server rejects (`unexpected keyword argument
'image_1'`). So this flow uses the flat sibling `LTXVAddGuidesFromBatch` instead:
a full-length IMAGE batch where non-black frames pin guides at their own indices
(batch index == frame index, strength shared). The batch is built offline (two
stills + exact-black padding, lossless H264 so the padding survives byte-exact)
and arrives via LoadVideo -> GetVideoComponents. Dynamic-combo support in
sweep_workflow is the deferred tooling fix if per-guide strengths are ever needed.

E23 (2026-10-15) probes two arms on our own art at 768x768x97 (13B-distilled-fp8,
8 steps, no STG, cfg 1, t5xxl_fp8/CLIP-ltxv, strength 1.0): (A) CONTROL - the same
still at both ends, expecting a near-static clip (validates pinning); (B)
full-body heroine @0 -> portrait heroine @96 (framing interpolation).
"""
from __future__ import annotations

POS = ("best quality, 4k, HDR, a red-haired sorceress in ornate blue and gold robes, "
       "the view drifts slowly from a full-body framing into a close-up portrait, "
       "her expression calm, hair and cloak stirring gently, cinematic lighting, "
       "smooth continuous motion, no cuts")
NEG = ("low quality, worst quality, deformed, distorted, disfigured, motion smear, "
       "motion artifacts, fused fingers, bad anatomy, weird hand, ugly, static, "
       "abrupt cuts, flicker")

NOTE = (
    "## ltxv-guides.json\n\n"
    "Keyframe animation: our stills pinned at chosen frames\n\n"
    "**Does:** a guide clip (two stills + exact-black padding) + a prompt -> a clip that "
    "travels between the stills (`LTXVAddGuidesFromBatch`: batch index == frame index, "
    "strength 1.0 shared). The latent is empty (`EmptyLTXVLatentVideo`) - every pixel of "
    "direction comes from the guides and the prompt. Build the guide clip offline (see E23) - "
    "the padding must decode byte-exact black or every noisy frame becomes a guide. Host: "
    "13B-distilled-fp8 + t5xxl_fp8 (`ltxv`), 768x768 (multiples of 32), 97 frames (8n+1).\n"
    "**Measured (E23, 2026-10-15):** PROBE - (A) same-still control, (B) full-body -> portrait.\n"
    "**Knobs:** the **guide stills** (identity lives here); **which frames** (batch position); "
    "**strength** (1.0 = hard pin, shared across guides); the **prompt** (must describe the "
    "TRAVEL, not a pose); steps 8 / euler / no STG / cfg 1 (distilled recipe).\n"
    "**Traps:** `LTXVAddGuideMulti` (per-guide strengths) does NOT submit through our "
    "sweep_workflow - its DynamicCombo sub-inputs must nest under the combo key and the "
    "sweeper flattens them (measured rejection E23). More guides = more non-black frames, no "
    "graph change. Guide stills are center-upscaled to the canvas, so mismatched aspects crop.\n"
    "**Siblings:** `ltxv-i2v.json` (S35) is prompt-only; this one pins frames.\n\n"
    "---\n*How to run it: story **S36** in `HOWTO.md`  ·  Why it is this way: **E23** in "
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
    {"id": 5, "type": "LoadVideo", "pos": [-1400, 420], "size": [380, 100],
     "widgets_values": ["guide_flf.mp4"],
     "inputs": [],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 6, "type": "GetVideoComponents", "pos": [-980, 420], "size": [300, 150],
     "widgets_values": [],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": [{"name": "images", "type": "IMAGE", "slot_index": 0},
                 {"name": "audio", "type": "AUDIO", "slot_index": 1},
                 {"name": "fps", "type": "FLOAT", "slot_index": 2},
                 {"name": "bit_depth", "type": "COMBO", "slot_index": 3},
                 {"name": "color_space", "type": "COMBO", "slot_index": 4}]},
    {"id": 7, "type": "EmptyLTXVLatentVideo", "pos": [-980, 620], "size": [340, 120],
     "widgets_values": [768, 768, 97, 1],
     "inputs": [],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 8, "type": "LTXVAddGuidesFromBatch", "pos": [-540, 100], "size": [360, 160],
     "widgets_values": [1.0],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "latent", "type": "LATENT"},
                {"name": "images", "type": "IMAGE"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2}]},
    {"id": 9, "type": "LTXVConditioning", "pos": [-540, 340], "size": [340, 80],
     "widgets_values": [25.0],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1}]},
    {"id": 10, "type": "LTXVScheduler", "pos": [-540, 460], "size": [340, 160],
     "widgets_values": [8, 2.05, 0.95, True, 0.1],
     "inputs": [],
     "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "slot_index": 0}]},
    {"id": 11, "type": "KSamplerSelect", "pos": [-1400, 820], "size": [340, 60],
     "widgets_values": ["euler"],
     "inputs": [],
     "outputs": [{"name": "SAMPLER", "type": "SAMPLER", "slot_index": 0}]},
    {"id": 12, "type": "SamplerCustom", "pos": [-160, 100], "size": [360, 260],
     "widgets_values": [True, 42, "fixed", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "sampler", "type": "SAMPLER"},
                {"name": "sigmas", "type": "SIGMAS"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "output", "type": "LATENT", "slot_index": 0},
                 {"name": "denoised_output", "type": "LATENT", "slot_index": 1}]},
    {"id": 13, "type": "VAEDecode", "pos": [240, 100], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"},
                {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 14, "type": "CreateVideo", "pos": [500, 100], "size": [260, 100],
     "widgets_values": [25],
     "inputs": [{"name": "images", "type": "IMAGE"}],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 15, "type": "SaveVideo", "pos": [800, 100], "size": [340, 300],
     "widgets_values": ["ltxv-guides", "auto", "auto"],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": []},
    {"id": 16, "type": "MarkdownNote", "pos": [-1400, 980], "size": [420, 340],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

LINKS = [
    (1, 1, 0, 12, 0, "MODEL"),
    (2, 1, 2, 13, 1, "VAE"),
    (3, 2, 0, 3, 0, "CLIP"),
    (4, 2, 0, 4, 0, "CLIP"),
    (5, 3, 0, 8, 0, "CONDITIONING"),
    (6, 4, 0, 8, 1, "CONDITIONING"),
    (7, 5, 0, 6, 0, "VIDEO"),
    (8, 6, 0, 8, 4, "IMAGE"),
    (9, 7, 0, 8, 3, "LATENT"),
    (10, 1, 2, 8, 2, "VAE"),
    (11, 8, 0, 9, 0, "CONDITIONING"),
    (12, 8, 1, 9, 1, "CONDITIONING"),
    (13, 9, 0, 12, 1, "CONDITIONING"),
    (14, 9, 1, 12, 2, "CONDITIONING"),
    (15, 11, 0, 12, 3, "SAMPLER"),
    (16, 10, 0, 12, 4, "SIGMAS"),
    (17, 8, 2, 12, 5, "LATENT"),
    (18, 12, 0, 13, 0, "LATENT"),
    (19, 13, 0, 14, 0, "IMAGE"),
    (20, 14, 0, 15, 0, "VIDEO"),
]
