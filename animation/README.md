# Animation: scenario index

Goal: turn a still character into something that *moves*, as an **engine asset**. This scenario starts where the 2D and 3D ones stop: `2d/` makes a picture of a character, `3d/` makes a mesh of one, and neither of those moves by itself.

## Form and source (the split that organises this scenario)

Two questions, and they are independent: **what the artefact is** (form) and **where the motion comes from** (source). Most of the space belongs to the engine, which is why this scenario is small.

| form | output | consumer | status |
|---|---|---|---|
| **sprite (2D)** | frame-indexed sheet / flipbook | engine | **works** - `2d/workflows/pose-extract.json` gets a skeleton per pose, `2d/workflows/pose-skeleton.json` renders it, `scripts/atlas.py` packs the frames (E13/E13b/E13c in `../2d/EXPERIMENTS-2D.md`) |
| **parametric (3D)** | rig + skeletal clips | engine | **works with a recipe** - SAM 3D Body recovers motion from footage and exports an animated skeletal GLB headlessly (E4; gate it with `scripts/motion_quality.py`), but the skin is Meta's MHR, so retargeting onto our rig stays engine-side. Length is bounded: ~12 s of 720x1280, ~27 s of 480x848 (E15/E16). The rigger half exists (`3d/workflows/unirig-humanoid-workflow.json`). Cost and caveats: [`motion-sourcing.md`](motion-sourcing.md) |

A third form, a **video file**, is *not* here: its consumer is a viewer rather than an engine, so it is its own scenario - see [`../video/README.md`](../video/README.md).

| motion source | tool | cost | status |
|---|---|---|---|
| **an existing clip library** (Mixamo etc.) | retargeting in the engine | free | **not ours** - Unity's Humanoid avatar maps an FBX clip onto any humanoid rig, and `unirig-humanoid` already emits a Mixamo-compatible skeleton (`fbx_preset = "mixamo"`). A ComfyUI retarget flow would be a slower, non-interactive copy of an engine feature. |
| **video reference** | `../video/workflows/wan-animate-motion.json` | Wan Animate 2 int8, ~24 GB one-time | **PASS** (E1/E2) - the recording route, moved to `../video/` because it emits footage; its real animation use is motion that exists *only* as a clip |
| **keyframes / pose sequence** | skeletal keyframing, pose-to-motion | tooling we do not have | open |
| **text prompt** | video model, then retarget | large weights, two-stage | open |

**What is left of animation is generating motion we do not have** - the engine already handles *using* a rig and *retargeting* a clip. That is the frame for everything here.

## Workflow map

| Workflow (`workflows/`) | What it does | Cost | Status |
|---|---|---|---|
| `sam3d-motion.json` | **footage → a 3D body animation**, exported as an animated skeletal GLB (plus a render preview). Motion comes from the clip; the skin is Meta's MHR, so the engine retargets it onto your character. Ships the two settings upstream gets wrong (E6/E8), and is bounded to ~12 s of 720x1280 (~27 s at 480x848) per run (E15/E16). | free + ~3 GB weights | **PASS** (E4/E8; E6: fast clips keep one residual pop) |

The sprite route lives in `2d/` (S9) rather than here, because its frames *are* 2D images: `pose-extract.json` → `pose-skeleton.json` → `scripts/atlas.py`.

## Knobs

- **`format.bone_smooth_window`** (9) - the export-stage smoother, and the highest-value knob in the flow: it took breaks from 8 to 2 and the worst pop from 174 deg to 60 deg (E8). It is **not** frame duplication (E7) - it is the fix.
- **`rotation_threshold_degrees`** (0) - the template ships **15**, which was the single largest cause of breaks on fast motion (E6). Don't reset it upward.
- **resolution** - the length knob, because cost is bounded by VRAM: ~12 s at 720x1280, ~27 s at 480x848 (E15). The flow ships an `ImageResizeKJ` cap at **480x848**, which is what makes a long clip fit; downscaling costs almost nothing in pose accuracy (mean 1.48 deg, worst 4.38 deg - E16), so **cap first, don't shorten**.

## Traps (all measured on the box, RTX 3090 24 GB)

- **The recovered skeleton is Meta's MHR**, not our humanoid, so the retarget onto our rig is engine-side. That is a stated boundary, not a gap.
- **Length fails as OOM, not as an error you can read.** 290 frames at 720x1280 measured 251 s / 21.6 GB; 363 frames OOM on this card (E15). The shipped 480x848 cap is the answer, and it is nearly free in accuracy (E16).
- **Fast clips keep one residual break even after the recipe** (E6), and E8's forearm spike grows with the smoothing window, so a larger `bone_smooth_window` is not obviously better. Open as E9.
- **Two of upstream's defaults are wrong for us** (`rotation_threshold_degrees: 15`, no smoothing). The flow ships corrected values - don't reset them (E6/E8).
- **The rigger half is a separate file** (`3d/workflows/unirig-humanoid-workflow.json`, MIT), and its `fbx_preset = "mixamo"` is what makes the engine's retarget work.

## Weights (one-time, ~3 GB, versioned in `EXPERIMENTS.md` E4)

| file | where | size |
|---|---|---|
| `sam_3d_body_dinov3_bf16.safetensors` | `models/detection/` | 2.83 GB |
| `rt_detr_v4-x-hgnet_fp32.safetensors` | `models/diffusion_models/` | 0.25 GB |

The nodes are ComfyUI core (Apache-2.0); the upstream **model** licence is unchecked, so treat the output as uncleared until it is. The rigger's weights are `3d/`'s business - see `../3d/README.md`.

## Docs

| Doc | What it answers |
|---|---|
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log with verdicts and the measurements behind them (E4/E6/E7/E8/E15/E16). |
| [`motion-sourcing.md`](motion-sourcing.md) | Where motion comes from: what the free path covers, and what rare motion (video only) would cost. |
| [`../video/README.md`](../video/README.md) | The video-reference route and its own backlog. |
| `../HOWTO.md` S17 | How to actually run it. |
| `../3d/README.md` | The UniRig rigger alternatives and the out-of-scope engine boundary. |
| `../comfyui/hardware.md` | What fits on this card, measured. |
| `../comfyui/workflow-file-format.md` | How to hand-edit a workflow `.json` safely. |
