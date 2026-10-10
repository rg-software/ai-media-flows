# Video: scenario index

Goal: motion as **content** - the deliverable is a video file, which a viewer plays rather than an engine importing it. Its sibling is `animation/`, which produces *engine assets* (a sprite sheet, a rig); the border between the two is **who consumes the artefact**, not what it looks like. A clip of a character dancing is this scenario; a sprite sheet or a skeletal GLB of the same dance is `animation/`.

The two scenarios share a border and cross-reference: the driving-video route here is also the answer for animation's "motion that exists only as footage" cell, and [`../animation/motion-sourcing.md`](../animation/motion-sourcing.md) is the decision doc for when to reach for it instead of a free clip library.

## Workflow map

| Workflow (`workflows/`) | What it does | Cost | Status |
|---|---|---|---|
| `wan-animate-motion.json` | still character + **driving video** → animated video. Motion is transferred directly, with no pose extraction or skeleton step; the video is the motion source. | free + ~24 GB weights (16.7 GB model) | **PASS** (E1/E2; length and segmenting E3/E10/E12/E14) |

**Why this flow is a flat rebuild.** Its upstream template is built from *subgraphs*, a frontend construct that cannot be POSTed to `/prompt`, so it cannot be scripted or swept as shipped - this file is the same graph flattened. (`../animation/workflows/sam3d-motion.json` needed no such treatment: upstream's is already flat.)

## Knobs

- **`length`** (frames, `4n+1`) - the main cost knob, and it covers the **first** N frames of the clip, not a resampling. Default 33 ≈ 1.4 s at 24 fps; for more than that, `scripts/wan_segment.py` runs the flow in segments and joins them.
- **`pose_strength`** - how literally the driving motion is copied.
- **`reference_image_strength`** - identity vs motion trade.
- **the prompt** describes **scene, background and camera**, not the motion (the motion comes from the video). This is also where viewpoint control lives: the camera is decoupled from the driving clip, so you can name a different angle and get one.
- **the output frame rate is the clip's**, wired through from `GetVideoComponents.fps` (`CreateVideo.fps`). So the flow is 1:1 in time and changing that value changes *playback speed* - a speed-up or slow-motion, not a retime. Synthesising in-between frames is a different operation (E17).

## Traps (all measured on the box, RTX 3090 24 GB)

- **Never quantise this model to GGUF.** Wan-Animate-2's *identity is in the file's metadata* (`{"config": {"transformer": {"model_type": "animate2"}}}`), and ComfyUI lets it override its own key-based detection. A GGUF has no such config, so the same weights load as a plain **image-to-video** model - and then the reference image still works while **the driving video is ignored completely** (measured: swapping the clip changed the output by **0.00**). The log is the tell: `Requested to load WAN21` instead of `WAN_Animate2`. int8 is fine on this card; it is the *metadata*, not the precision, that decides this.
- **Peak VRAM was 20.8 GB at 480x848, 33 frames**, i.e. ~3 GB of headroom, and cost grows super-linearly with frame count (81 frames measured 1000 s / 23.7 GB, where context windows at least made it fit). So a longer clip is **segmented**, not lengthened: `scripts/wan_segment.py` runs it in pieces, each continuing from the previous piece's last frame (E12/E14).
- **There are two CLIP-vision encodes** - the reference image *and* the pose video's first frame. Dropping the second does not error, it just quietly degrades the result.
- **Output size comes from the driving video**, snapped to a multiple of 16 in both axes: a requested height of 854 comes back as 848.

## Weights (one-time, ~24 GB, versioned in `EXPERIMENTS.md` E1)

| file | where | size |
|---|---|---|
| `wan_animate_2_int8_convrot.safetensors` | `models/diffusion_models/` | 16.7 GB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `models/text_encoders/` | 6.3 GB |
| `clip_vision_h.safetensors` | `models/clip_vision/` | 1.2 GB |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | `models/loras/` | 0.7 GB |
| `Wan2_1_VAE_bf16.safetensors` | `models/vae/` | 0.24 GB |

The diffusion model is [Wan Animate 2](https://huggingface.co/Comfy-Org/Wan-Animate-2) (Apache-2.0). It is taken as the official int8 safetensors rather than a quant - see the metadata trap above.

## What is deferred

The backlog is in [`EXPERIMENTS.md`](EXPERIMENTS.md) → PENDING, and deliberately long because this scenario is the destination for most of the unused video-model surface on the box (~100 node types): frame interpolation (E17), camera control (E18), motion tracking as an explicit trajectory input (E19), combinations of subjects/objects/background (E13, needing a new model), and the rest - LTXV, MiniMax H3, Hunyuan video super-resolution, Mochi, Cosmos, audio-driven talking heads. One route is explicitly **not** planned: video → sprite sheet, because a sheet wants a few carefully chosen frames rather than a whole clip, and the character-preservation that matters there is already targeted directly by the sprite path in `2d/` (S9).

## Docs

| Doc | What it answers |
|---|---|
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log with verdicts, the measurements behind them, and the deferred backlog. |
| [`../animation/motion-sourcing.md`](../animation/motion-sourcing.md) | When to use this route at all: what the free path covers, and what rare motion (video only) costs. |
| `../HOWTO.md` S15 | How to actually run it. |
| `../comfyui/hardware.md` | What fits on this card, measured. |
| `../comfyui/workflow-file-format.md` | How to hand-edit a workflow `.json` safely. |
