"""Spec for video/workflows/wan-infinitetalk.json - build with scripts/build_workflow.py.

Audio-driven talking heads: a **still portrait + an audio file** -> a clip of our character
speaking that audio. InfiniteTalk (MeiGen-AI, Apache-2.0) through the official
`video_wan2_1_infinitetalk` template, flattened, `single_speaker` mode.

E15 (2026-10-11) measured it at **210 s per 81-frame segment** (3.24 s of speech at 25 fps) with
identity holding through speech, and settled two route facts: the **patch applies to our on-box
720p fp8 I2V base** (the template's KJ 480p base is NOT required - new weights are only ~5.3 GB,
not 19.5), and `single_speaker` mode needs **no masks** (masks belong to the two-speaker mode).

The output video **carries the driving audio** (aac), so the artefact is a viewer's file with
sound. Lip-sync accuracy against the words needs ears and eyes together - play the mp4.
"""
from __future__ import annotations

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
       "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
       "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

NOTE = (
    "## wan-infinitetalk.json\n\n"
    "A talking head: our character speaks an audio file\n\n"
    "**Does:** a still **portrait** + an audio file -> a clip of the character speaking that audio "
    "(`WanInfiniteTalkToVideo`, InfiniteTalk single-speaker). The output **carries the audio** "
    "(aac) - a viewer's file with sound. Host: our on-box `wan2.1_i2v_720p_14B_fp8_scaled` with "
    "the InfiniteTalk patch applied (`model_patches/wan2.1_infiniteTalk_single_fp16`, 5.13 GB) + "
    "`wav2vec2-chinese-base` audio encoder + the lightx2v distill lora + umt5/VAE.\n"
    "**Measured (E15, 2026-10-11):** 81 frames (3.24 s of speech at 25 fps) in **210 s**; identity "
    "holds through speech (lip-band motion 1.9x forehead, articulation real); the patch applies to "
    "our 720p fp8 base, so the route's new weights are only ~5.3 GB. Reference = **portrait** "
    "(the E13c identity-knob lesson).\n"
    "**Knobs:** the **audio** on `LoadAudio` (replace `audio_speaker1_woman.mp3` - speech from TTS "
    "or recording; the audio is what drives the mouth); the **reference** (portrait, face clear); "
    "**`seconds`** on `PrimitiveFloat` (3.24 ships) - how much audio to speak. A "
    "`ComfyMathExpression` turns it into **`length`** rounded to the model's required 4n+1 "
    "(`floor((a*25-1)/4+0.5)*4+1`), so there is no hand arithmetic; raising it raises VRAM. "
    "**`audio_scale`** (1.0) for lip-sync strength; **`motion_frame_count`** (9). Sampling: 6 steps / "
    "euler / normal, **no `ModelSamplingSD3`** (the template has none). **fps is pinned at 25** on "
    "`CreateVideo` - InfiniteTalk's audio conditioning is resampled for 25-fps video in the node code, "
    "so any other fps would desync the mouth; it is deliberately not a knob.\n"
    "**Traps:** lip-sync was **human-confirmed** on the probe clip (E15, 2026-10-11); for your own "
    "audio, play the output mp4 (the audio is "
    "embedded). The clip speaks the FIRST `length` frames' worth of audio (`audio_start=0, "
    "`audio_end=length`): audio past that is never read, and audio shorter than the window is padded "
    "with the first audio frame (idle mouth) - so **trim your audio to `seconds`**. Longer audio = "
    "chain segments: feed this flow's output IMAGE batch into a second `WanInfiniteTalkToVideo`'s "
    "**`previous_frames`** (the official extend pattern); each continuation advances `length - "
    "motion_frame_count` frames (72 = 2.88 s at defaults - drop the node's `trim_image` leading "
    "frames when stitching), not a full segment. For real use reach for `scripts/talk_chain.py` "
    "instead of hand-wiring: it plans full chunks plus a trimmed last chunk from the audio duration, "
    "assembles in latent space, and muxes once (measured E21: 8.8 s -> 221 frames exact in 606 s). "
    "`single_speaker` needs no masks (masks are the two-speaker mode's region control). The patch loads through `ModelPatchLoader` from "
    "`models/model_patches/`.\n"
    "**Siblings:** `wan-animate-motion.json` (S15) drives motion from a *video*; this flow drives "
    "it from *audio*.\n\n"
    "---\n*How to run it: story **S32** in `HOWTO.md`  ·  Why it is this way: **E15** in "
    "`video/EXPERIMENTS.md`.*"
)

NODES = [
    {"id": 1, "type": "UNETLoader", "pos": [-1700, 100], "size": [420, 90],
     "widgets_values": ["wan2.1_i2v_720p_14B_fp8_scaled.safetensors", "default"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 2, "type": "LoraLoaderModelOnly", "pos": [-1260, 100], "size": [340, 80],
     "widgets_values": ["lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 3, "type": "ModelPatchLoader", "pos": [-1700, 240], "size": [420, 60],
     "widgets_values": ["wan2.1_infiniteTalk_single_fp16.safetensors"],
     "outputs": [{"name": "MODEL_PATCH", "type": "MODEL_PATCH", "slot_index": 0}]},
    {"id": 4, "type": "CLIPLoader", "pos": [-1700, 340], "size": [420, 100],
     "widgets_values": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "wan", "default"],
     "outputs": [{"name": "CLIP", "type": "CLIP", "slot_index": 0}]},
    {"id": 5, "type": "CLIPTextEncode", "pos": [-1260, 240], "size": [400, 120],
     "widgets_values": ["a red-haired sorceress speaking to the camera, close-up portrait"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 6, "type": "CLIPTextEncode", "pos": [-1260, 400], "size": [400, 200],
     "widgets_values": [NEG],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 7, "type": "VAELoader", "pos": [-1700, 480], "size": [420, 60],
     "widgets_values": ["Wan2_1_VAE_bf16.safetensors"],
     "outputs": [{"name": "VAE", "type": "VAE", "slot_index": 0}]},
    {"id": 8, "type": "AudioEncoderLoader", "pos": [-1700, 580], "size": [420, 60],
     "widgets_values": ["wav2vec2-chinese-base_fp16.safetensors"],
     "outputs": [{"name": "AUDIO_ENCODER", "type": "AUDIO_ENCODER", "slot_index": 0}]},
    {"id": 9, "type": "LoadAudio", "pos": [-1700, 680], "size": [420, 180],
     "widgets_values": ["audio_speaker1_woman.mp3", None, None],
     "outputs": [{"name": "AUDIO", "type": "AUDIO", "slot_index": 0}]},
    {"id": 10, "type": "AudioEncoderEncode", "pos": [-1260, 680], "size": [300, 60],
     "widgets_values": [],
     "inputs": [{"name": "audio_encoder", "type": "AUDIO_ENCODER"},
                {"name": "audio", "type": "AUDIO"}],
     "outputs": [{"name": "AUDIO_ENCODER_OUTPUT", "type": "AUDIO_ENCODER_OUTPUT", "slot_index": 0}]},
    {"id": 12, "type": "LoadImage", "pos": [-1700, 900], "size": [420, 500],
     "widgets_values": ["portrait_heroine.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 11, "type": "WanInfiniteTalkToVideo", "pos": [-700, 300], "size": [360, 300],
     "widgets_values": ["single_speaker", 480, 832, 81, 9, 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "model_patch", "type": "MODEL_PATCH"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "audio_encoder_output_1", "type": "AUDIO_ENCODER_OUTPUT"},
                {"name": "start_image", "type": "IMAGE"},
                {"name": "length", "type": "INT"}],
     "outputs": [{"name": "model", "type": "MODEL", "slot_index": 0},
                 {"name": "positive", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 2},
                 {"name": "latent", "type": "LATENT", "slot_index": 3}]},
    {"id": 13, "type": "KSampler", "pos": [-300, 300], "size": [340, 260],
     "widgets_values": [42, "fixed", 6, 1.0, "euler", "normal", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 14, "type": "VAEDecode", "pos": [100, 300], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 15, "type": "CreateVideo", "pos": [380, 220], "size": [260, 100],
     "widgets_values": [25, 8],
     "inputs": [{"name": "images", "type": "IMAGE"}, {"name": "audio", "type": "AUDIO"}],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 16, "type": "SaveVideo", "pos": [680, 220], "size": [340, 300],
     "widgets_values": ["wan-infinitetalk", "auto", "auto"],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": []},
    {"id": 18, "type": "PrimitiveFloat", "pos": [-1100, -60], "size": [300, 80],
     "widgets_values": [3.24],
     "inputs": [],
     "outputs": [{"name": "FLOAT", "type": "FLOAT", "slot_index": 0}]},
    {"id": 19, "type": "ComfyMathExpression", "pos": [-700, -60], "size": [360, 140],
     "widgets_values": ["floor((a*25-1)/4+0.5)*4+1"],
     "inputs": [{"name": "values.a", "type": "FLOAT"}],
     "outputs": [{"name": "FLOAT", "type": "FLOAT", "slot_index": 0},
                 {"name": "INT", "type": "INT", "slot_index": 1},
                 {"name": "BOOL", "type": "BOOLEAN", "slot_index": 2}]},
    {"id": 17, "type": "MarkdownNote", "pos": [-1700, 1200], "size": [420, 340],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

LINKS = [
    (1, 1, 0, 2, 0, "MODEL"),
    (2, 2, 0, 11, 0, "MODEL"),
    (3, 3, 0, 11, 1, "MODEL_PATCH"),
    (4, 4, 0, 5, 0, "CLIP"),
    (5, 4, 0, 6, 0, "CLIP"),
    (6, 7, 0, 11, 4, "VAE"),
    (7, 8, 0, 10, 0, "AUDIO_ENCODER"),
    (8, 9, 0, 10, 1, "AUDIO"),
    (9, 10, 0, 11, 5, "AUDIO_ENCODER_OUTPUT"),
    (10, 12, 0, 11, 6, "IMAGE"),
    (11, 5, 0, 11, 2, "CONDITIONING"),
    (12, 6, 0, 11, 3, "CONDITIONING"),
    (13, 11, 0, 13, 0, "MODEL"),
    (14, 11, 1, 13, 1, "CONDITIONING"),
    (15, 11, 2, 13, 2, "CONDITIONING"),
    (16, 11, 3, 13, 3, "LATENT"),
    (17, 13, 0, 14, 0, "LATENT"),
    (18, 7, 0, 14, 1, "VAE"),
    (19, 14, 0, 15, 0, "IMAGE"),
    (20, 9, 0, 15, 1, "AUDIO"),
    (21, 15, 0, 16, 0, "VIDEO"),
    (22, 18, 0, 19, 0, "FLOAT"),
    (23, 19, 1, 11, 7, "INT"),
]