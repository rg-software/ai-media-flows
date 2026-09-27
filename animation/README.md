# Animation: scenario index

Goal: turn a still character into something that *moves*. This scenario starts where the 2D and 3D ones stop: `2d/` makes a picture of a character, `3d/` makes a mesh of one, and neither of those moves by itself.

## Form and source (the split that organises this scenario)

Two questions, and they are independent: **what the artefact is** (form) and **where the motion comes from** (source). Most of the space belongs to the engine, which is why this scenario is small.

| form | output | consumer | status |
|---|---|---|---|
| **sprite (2D)** | frame-indexed sheet / flipbook | engine | **works** - `2d/workflows/pose-extract.json` gets a skeleton per pose, `2d/workflows/pose-skeleton.json` renders it, `scripts/atlas.py` packs the frames (E13/E13b/E13c in `../2d/EXPERIMENTS-2D.md`) |
| **video** (reference) | a video file | a viewer, not an engine | **works, and runs on the box** - `workflows/wan-animate-motion.json` (E1) |
| **parametric (3D)** | rig + skeletal clips | engine | **works with a recipe** - SAM 3D Body recovers motion from footage and exports an animated skeletal GLB headlessly (E4; gate it with `scripts/motion_quality.py`), but the skin is Meta's MHR, so retargeting onto our rig stays engine-side. Length is bounded: ~12 s of 720x1280, ~27 s of 480x848 (E15/E16). The rigger half exists (`3d/workflows/unirig-humanoid-workflow.json`). Cost and caveats: [`motion-sourcing.md`](motion-sourcing.md) |

| motion source | tool | cost | status |
|---|---|---|---|
| **video reference** | `workflows/wan-animate-motion.json` | Wan Animate 2 int8, ~24 GB one-time | **PASS** (E1/E2) |
| **an existing clip library** (Mixamo etc.) | retargeting in the engine | free | **not ours** - Unity's Humanoid avatar maps an FBX clip onto any humanoid rig, and `unirig-humanoid` already emits a Mixamo-compatible skeleton (`fbx_preset = "mixamo"`). A ComfyUI retarget flow would be a slower, non-interactive copy of an engine feature. |
| **keyframes / pose sequence** | skeletal keyframing, pose-to-motion | tooling we do not have | open |
| **text prompt** | video model, then retarget | large weights, two-stage | open |

**What is left of animation is generating motion we do not have** - the engine already handles *using* a rig and *retargeting* a clip. That is the frame for everything here.

## Workflow map

| Workflow (`workflows/`) | What it does | Cost | Status |
|---|---|---|---|
| `wan-animate-motion.json` | still character + **driving video** → animated video. Motion is transferred directly, with no pose extraction or skeleton step; the video is the motion source. | free + ~24 GB weights (16.7 GB model) | **PASS** (E1/E2; length and segmenting E3/E12/E14) |
| `sam3d-motion.json` | **footage → a 3D body animation**, exported as an animated skeletal GLB (plus a render preview). Motion comes from the clip; the skin is Meta's MHR, so the engine retargets it onto your character. Ships the two settings upstream gets wrong (E6/E8), and is bounded to ~12 s of 720x1280 (~27 s at 480x848) per run (E15/E16). | free + ~3 GB weights | **PASS** (E4/E8; E6: fast clips keep one residual pop) |

**Why the Wan flow is a flat rebuild.** Its upstream template is built from *subgraphs*, a frontend construct that cannot be POSTed to `/prompt`, so it cannot be scripted or swept as shipped - this file is the same graph flattened. (`sam3d-motion.json` needed no such treatment: upstream's is already flat, so it is that template with two values changed.)

**Two different artefacts, and they are complements rather than stages.** `wan-animate-motion.json` emits a **video** - a viewer's file that an engine does not consume. `sam3d-motion.json` emits an **animated skeletal GLB**, which is the parametric cell above; putting that skeleton on your own rig is then the engine's retarget. So reach for the first when you want the footage, the second when you want the skeleton, and note that only the second needs `scripts/motion_quality.py`.

## Knobs

- **`length`** (frames, `4n+1`) - the main cost knob, and it covers the **first** N frames of the clip, not a resampling. Default 33 ≈ 1.4 s at 24 fps; for more than that, `scripts/wan_segment.py` runs the flow in segments and joins them.
- **`pose_strength`** - how literally the driving motion is copied.
- **`reference_image_strength`** - identity vs motion trade.
- **the prompt** describes **scene, background and camera**, not the motion (the motion comes from the video). This is also where viewpoint control lives: the camera is decoupled from the driving clip, so you can name a different angle and get one.

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

## Docs

| Doc | What it answers |
|---|---|
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log with verdicts and the measurements behind them. |
| [`motion-sourcing.md`](motion-sourcing.md) | Where motion comes from: what the free path covers, and what rare motion (video only) would cost. |
| `../HOWTO.md` S15 | How to actually run it. |
| `../comfyui/hardware.md` | What fits on this card, measured. |
| `../comfyui/workflow-file-format.md` | How to hand-edit a workflow `.json` safely. |
