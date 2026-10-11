"""Spec for video/workflows/wan-s2v.json - build with scripts/build_workflow.py.

Audio-driven performance: a **still portrait + an audio file** -> a clip of our character
*performing* that audio - head movement, expression and articulation, not just lip-sync
(Wan2.2-S2V-14B, "Audio-Driven Cinematic Video Generation", Apache-2.0). The official
`video_wan2_2_14B_s2v` template, flattened, single chunk.

E16 (2026-10-11) measured it at **140 s for a 5-s clip** (80 frames at 16 fps) with identity
holding through the performance. Route facts: the checkpoint keeps its as-downloaded name
(`Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors`); the audio encoder is **wav2vec2-large-english**
(NOT InfiniteTalk's chinese-base - the two routes use different encoders, both on box); the speed
lora is the **Wan2.2 4-step lightning one** (not our lightx2v I2V lora).

The template's first-frame VAE hack is replicated: the sampler latent is LatentCut(0:1)'d and
LatentConcat'd back so the VAE's overbaked first decode is dropped via ImageFromBatch(1).
The output video carries the audio (aac).
"""
from __future__ import annotations

NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
       "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
       "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

NOTE = (
    "## wan-s2v.json\n\n"
    "An audio-driven performance: our character performs an audio file\n\n"
    "**Does:** a still **portrait** + an audio file -> a clip of the character *performing* it - "
    "head movement, expression and articulation (`WanSoundImageToVideo`, Wan2.2-S2V-14B). Broader "
    "than S32's lip-sync: the whole performance is audio-driven. The output **carries the audio** "
    "(aac). Host: `Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ` (16.65 GB, Apache-2.0) + "
    "**`wav2vec2_large_english`** audio encoder (631 MB - a different encoder from S32's "
    "chinese-base) + the **Wan2.2 4-step lightning lora** (1.23 GB - not our lightx2v I2V lora) + "
    "umt5/VAE.\n"
    "**Measured (E16, 2026-10-11):** a 5-s clip (80 frames at 16 fps) in **140 s** - the 4-step "
    "lora recipe. Identity holds through the performance (head tilts, blinks, mouth). Canvas "
    "**640x640** - a square portrait fits exactly.\n"
    "**Knobs:** the **audio** (drives the performance); the **reference** (portrait, face clear); "
    "**`length`** - 77 is the chunk default from the official code (the model needs at least 73; "
    "higher risks OOM); longer audio chains chunks via the template's "
    "`LatentCut`/`LatentConcat` extend plumbing (batch sizes = chunk count). Sampling: **4 steps / "
    "cfg 1.0 / uni_pc / simple** with the Wan2.2 4-step lora.\n"
    "**Traps:** the checkpoint keeps its **as-downloaded name** (`Wan2_2-S2V-14B_fp8_e4m3fn_scaled_"
    "KJ.safetensors` - the template's Kijai-original name is a different string). The audio encoder "
    "is per-route: S32 uses chinese-base, this flow uses large-english. The template's first-frame "
    "VAE hack (double frame 0, drop the first decode) is wired in - do not remove it.\n"
    "**Siblings:** `wan-infinitetalk.json` (S32) is the lip-sync route; this one performs.\n\n"
    "---\n*How to run it: story **S33** in `HOWTO.md`  ·  Why it is this way: **E16** in "
    "`video/EXPERIMENTS.md`.*"
)

NODES = [
    {"id": 1, "type": "UNETLoader", "pos": [-1700, 100], "size": [440, 90],
     "widgets_values": ["Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors", "default"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 2, "type": "LoraLoaderModelOnly", "pos": [-1240, 100], "size": [360, 80],
     "widgets_values": ["wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 3, "type": "ModelSamplingSD3", "pos": [-860, 100], "size": [220, 60],
     "widgets_values": [8.0],
     "inputs": [{"name": "model", "type": "MODEL"}],
     "outputs": [{"name": "MODEL", "type": "MODEL", "slot_index": 0}]},
    {"id": 4, "type": "CLIPLoader", "pos": [-1700, 240], "size": [440, 100],
     "widgets_values": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "wan", "default"],
     "outputs": [{"name": "CLIP", "type": "CLIP", "slot_index": 0}]},
    {"id": 5, "type": "CLIPTextEncode", "pos": [-1240, 240], "size": [400, 120],
     "widgets_values": ["a red-haired sorceress singing affectionately and gently, close-up portrait"],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 6, "type": "CLIPTextEncode", "pos": [-1240, 400], "size": [400, 200],
     "widgets_values": [NEG],
     "inputs": [{"name": "clip", "type": "CLIP"}],
     "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}]},
    {"id": 7, "type": "VAELoader", "pos": [-1700, 480], "size": [440, 60],
     "widgets_values": ["Wan2_1_VAE_bf16.safetensors"],
     "outputs": [{"name": "VAE", "type": "VAE", "slot_index": 0}]},
    {"id": 8, "type": "AudioEncoderLoader", "pos": [-1700, 580], "size": [440, 60],
     "widgets_values": ["wav2vec2_large_english_fp16.safetensors"],
     "outputs": [{"name": "AUDIO_ENCODER", "type": "AUDIO_ENCODER", "slot_index": 0}]},
    {"id": 9, "type": "LoadAudio", "pos": [-1700, 680], "size": [440, 180],
     "widgets_values": ["video_wan2_2_14B_s2v_input_audio.MP3", None, None],
     "outputs": [{"name": "AUDIO", "type": "AUDIO", "slot_index": 0}]},
    {"id": 10, "type": "AudioEncoderEncode", "pos": [-1240, 680], "size": [300, 60],
     "widgets_values": [],
     "inputs": [{"name": "audio_encoder", "type": "AUDIO_ENCODER"},
                {"name": "audio", "type": "AUDIO"}],
     "outputs": [{"name": "AUDIO_ENCODER_OUTPUT", "type": "AUDIO_ENCODER_OUTPUT", "slot_index": 0}]},
    {"id": 11, "type": "LoadImage", "pos": [-1700, 900], "size": [440, 500],
     "widgets_values": ["2d/portrait_heroine.png", "image"],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0},
                 {"name": "MASK", "type": "MASK", "slot_index": 1}]},
    {"id": 12, "type": "WanSoundImageToVideo", "pos": [-700, 300], "size": [360, 300],
     "widgets_values": [640, 640, 77, 1],
     "inputs": [{"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "vae", "type": "VAE"},
                {"name": "audio_encoder_output", "type": "AUDIO_ENCODER_OUTPUT"},
                {"name": "ref_image", "type": "IMAGE"}],
     "outputs": [{"name": "positive", "type": "CONDITIONING", "slot_index": 0},
                 {"name": "negative", "type": "CONDITIONING", "slot_index": 1},
                 {"name": "latent", "type": "LATENT", "slot_index": 2}]},
    {"id": 13, "type": "KSampler", "pos": [-300, 300], "size": [340, 260],
     "widgets_values": [42, "fixed", 4, 1.0, "uni_pc", "simple", 1.0],
     "inputs": [{"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 14, "type": "LatentCut", "pos": [100, 520], "size": [220, 100],
     "widgets_values": ["t", 0, 1],
     "inputs": [{"name": "samples", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 15, "type": "LatentConcat", "pos": [100, 660], "size": [220, 80],
     "widgets_values": ["t"],
     "inputs": [{"name": "samples1", "type": "LATENT"}, {"name": "samples2", "type": "LATENT"}],
     "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}]},
    {"id": 16, "type": "VAEDecode", "pos": [100, 300], "size": [220, 80],
     "widgets_values": [],
     "inputs": [{"name": "samples", "type": "LATENT"}, {"name": "vae", "type": "VAE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 17, "type": "ImageFromBatch", "pos": [380, 300], "size": [240, 80],
     "widgets_values": [1, 4096],
     "inputs": [{"name": "image", "type": "IMAGE"}],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}]},
    {"id": 18, "type": "CreateVideo", "pos": [660, 300], "size": [260, 100],
     "widgets_values": [16],
     "inputs": [{"name": "images", "type": "IMAGE"}, {"name": "audio", "type": "AUDIO"}],
     "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}]},
    {"id": 19, "type": "SaveVideo", "pos": [960, 300], "size": [340, 300],
     "widgets_values": ["wan-s2v", "auto", "auto"],
     "inputs": [{"name": "video", "type": "VIDEO"}],
     "outputs": []},
    {"id": 20, "type": "MarkdownNote", "pos": [-1700, 1200], "size": [420, 340],
     "widgets_values": [""],
     "inputs": [], "outputs": []},
]

LINKS = [
    (1, 1, 0, 2, 0, "MODEL"),
    (2, 2, 0, 3, 0, "MODEL"),
    (3, 3, 0, 13, 0, "MODEL"),
    (4, 4, 0, 5, 0, "CLIP"),
    (5, 4, 0, 6, 0, "CLIP"),
    (6, 7, 0, 12, 2, "VAE"),
    (7, 8, 0, 10, 0, "AUDIO_ENCODER"),
    (8, 9, 0, 10, 1, "AUDIO"),
    (9, 10, 0, 12, 3, "AUDIO_ENCODER_OUTPUT"),
    (10, 11, 0, 12, 4, "IMAGE"),
    (11, 5, 0, 12, 0, "CONDITIONING"),
    (12, 6, 0, 12, 1, "CONDITIONING"),
    (13, 12, 0, 13, 1, "CONDITIONING"),
    (14, 12, 1, 13, 2, "CONDITIONING"),
    (15, 12, 2, 13, 3, "LATENT"),
    (16, 13, 0, 14, 0, "LATENT"),
    (17, 13, 0, 15, 1, "LATENT"),
    (18, 14, 0, 15, 0, "LATENT"),
    (19, 15, 0, 16, 0, "LATENT"),
    (20, 7, 0, 16, 1, "VAE"),
    (21, 16, 0, 17, 0, "IMAGE"),
    (22, 17, 0, 18, 0, "IMAGE"),
    (23, 9, 0, 18, 1, "AUDIO"),
    (24, 18, 0, 19, 0, "VIDEO"),
]