# Animation: scenario index

Goal: turn a still character into something that *moves*. This scenario starts where the 2D and 3D ones stop: `2d/` makes a picture of a character, `3d/` makes a mesh of one, and neither of those moves by itself.

## Form and source (the split that organises this scenario)

Two questions, and they are independent: **what the artefact is** (form) and **where the motion comes from** (source). Most of the space belongs to the engine, which is why this scenario is small.

| form | output | consumer | status |
|---|---|---|---|
| **sprite (2D)** | frame-indexed sheet / flipbook | engine | **works** - `2d/workflows/pose-extract.json` gets a skeleton per pose, `2d/workflows/pose-skeleton.json` renders it, `scripts/atlas.py` packs the frames (E13/E13b/E13c in `../2d/EXPERIMENTS-2D.md`) |
| **video** (reference) | a video file | a viewer, not an engine | **works, and runs on the box** - `workflows/wan-animate-motion.json` (E1) |
| **parametric (3D)** | rig + skeletal clips | engine | **open** - costed in [`motion-sourcing.md`](motion-sourcing.md); the rigger half already exists (`3d/workflows/unirig-humanoid-workflow.json`) |

| motion source | tool | cost | status |
|---|---|---|---|
| **video reference** | `workflows/wan-animate-motion.json` | Wan Animate 2 GGUF, ~20 GB one-time | **PASS** (E1) |
| **an existing clip library** (Mixamo etc.) | retargeting in the engine | free | **not ours** - Unity's Humanoid avatar maps an FBX clip onto any humanoid rig, and `unirig-humanoid` already emits a Mixamo-compatible skeleton (`fbx_preset = "mixamo"`). A ComfyUI retarget flow would be a slower, non-interactive copy of an engine feature. |
| **keyframes / pose sequence** | skeletal keyframing, pose-to-motion | tooling we do not have | open |
| **text prompt** | video model, then retarget | large weights, two-stage | open |

**What is left of animation is generating motion we do not have** - the engine already handles *using* a rig and *retargeting* a clip. That is the frame for everything here.

## Workflow map

| Workflow (`workflows/`) | What it does | Cost | Status |
|---|---|---|---|
| `wan-animate-motion.json` | still character + **driving video** → animated video. Motion is transferred directly, with no pose extraction or skeleton step; the video is the motion source. | free + ~20 GB weights | **PASS (E1)** |

**A flat rebuild, deliberately.** The official upstream template is built from *subgraphs*, which are a frontend construct: they cannot be POSTed to `/prompt`, so an upstream flow cannot be scripted or swept as shipped. This file is the same graph flattened, which is what makes it runnable from a script (and by `scripts/sweep_workflow.py`).

**Output is a video - a viewer, not an engine asset.** Turning this motion into *skeletal clips* is the open parametric cell above, and it is a genuinely separate problem: this flow proves the motion is obtainable, not that it is retargetable.

## Knobs

- **`length`** (frames, `4n+1`) - the main cost knob. Default 33 ≈ 1.4 s at 24 fps.
- **`pose_strength`** - how literally the driving motion is copied.
- **`reference_image_strength`** - identity vs motion trade.
- **the prompt** describes **scene, background and camera**, not the motion (the motion comes from the video). This is also where viewpoint control lives: the camera is decoupled from the driving clip, so you can name a different angle and get one.

## Traps (all measured on the box, RTX 3090 24 GB)

- **Export as GGUF, not fp8.** The 3090 rejects `fp8e4nv` (`type fp8e4nv not supported in this architecture`). This is the same Ampere limitation `../comfyui/hardware.md` records for Qwen. The official repo's `int8_convrot` is what the template ships with; `wan_animate_2-Q5_K_M.gguf` (11.4 GB) is what runs here.
- **Peak VRAM was 20.8 GB at 480x848, 33 frames**, i.e. ~3 GB of headroom. Cost grows with frame count in the temporal-attention phase, so a longer clip needs the upstream template's `ContextWindowsManual` chunking rather than a bigger `length`.
- **There are two CLIP-vision encodes** - the reference image *and* the pose video's first frame. Dropping the second does not error, it just quietly degrades the result.
- **Output size comes from the driving video**, snapped to a multiple of 16 in both axes: a requested height of 854 comes back as 848.

## Weights (one-time, ~20 GB, versioned in `EXPERIMENTS.md` E1)

| file | where | size |
|---|---|---|
| `wan_animate_2-Q5_K_M.gguf` | `models/unet/` | 11.4 GB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `models/text_encoders/` | 6.3 GB |
| `clip_vision_h.safetensors` | `models/clip_vision/` | 1.2 GB |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | `models/loras/` | 0.7 GB |
| `Wan2_1_VAE_bf16.safetensors` | `models/vae/` | 0.24 GB |

The diffusion model is [Wan Animate 2](https://huggingface.co/Comfy-Org/Wan-Animate-2) (Apache-2.0). The GGUF quant is the one deviation from the official repo, for the Ampere reason above.

## Docs

| Doc | What it answers |
|---|---|
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log with verdicts and the measurements behind them. |
| [`motion-sourcing.md`](motion-sourcing.md) | Where motion comes from: what the free path covers, and what rare motion (video only) would cost. |
| `../HOWTO.md` S15 | How to actually run it. |
| `../comfyui/hardware.md` | What fits on this card, measured - and why GGUF. |
| `../comfyui/workflow-file-format.md` | How to hand-edit a workflow `.json` safely. |
