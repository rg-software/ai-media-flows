# Sourcing motion: what is free, and what rare motion costs

One question decides whether this topic needs anything from us: does the motion you want **already exist as a clip**, or does it exist **only as a video**?

## Generic motion is free, and the retarget is deliberately not ours

Clip libraries answer most of it. Five Mixamo clips are already on the box (`input/animation_templates/mixamo/`), rigging works (`3d/workflows/unirig-humanoid-workflow.json`, E4-L), and Unity's Humanoid avatar maps any FBX clip onto any humanoid rig — ours included, since `unirig-humanoid` emits a Mixamo-compatible skeleton by construction.

So "rig once, then retarget any clip in the engine" is already a complete user path, and we do **not** build the retarget. `UniRigApplyAnimation` + `UniRigExportPosedFBX` *can* bake a Mixamo or SMPL clip onto a rig inside ComfyUI, but what comes out is a baked FBX, where the engine gives a re-targetable clip with a timeline and playback. The in-pipeline version is a slower, non-interactive copy of an engine feature — which is why this branch was pruned rather than built.

**For a user, generic motion means: take a clip from a library, retarget it in the engine.** Nothing to generate, nothing to download.

## The case that is not free: motion that exists only as a video

A specific gesture, a particular dance, a real-world action nobody has a clip of. No library answers it, so the motion has to be recovered from the footage — and that is the only reason to spend anything here.

**The finding: the cost is small, and most of it is already installed.**

| what | status |
|---|---|
| SAM 3D Body nodes | **already installed** — ComfyUI core: `SAM3DBody_Loader` / `_Predict` / `_Smooth` / `_Render` / `_FaceExpression` |
| a workflow | **ships with ComfyUI** — `utility_sam3d_body.json` ("extract 3D human mesh from video") |
| `models/checkpoints/sam3.1_multiplex_fp16.safetensors` (tracking) | **present** |
| `models/geometry_estimation/moge_2_vitl_normal_fp16.safetensors` (geometry) | **present** |
| `models/detection/sam_3d_body_dinov3_bf16.safetensors` | **missing — 2.64 GB** (or the int8 variant, 1.86 GB) |
| `models/diffusion_models/rt_detr_v4-x-hgnet_fp32.safetensors` (person detector) | **missing** — a third, small file |

So the whole capability is **roughly 3 GB of download** on a box that already holds two of the four files, and the model keeps **~3.4 GB resident on the GPU** with activations under 100 MB. On a 24 GB card it is not a VRAM question at all.

**What it produces:** the node `BuildPoseFile` (its aliases include "3D animation", "mocap", "glb", "bvh") writes either an **animated GLB** — mesh + bones, or a keypoint overlay — or a **BVH mocap clip**. Both are engine-consumable: Unity takes the GLB through its glTF importer, and BVH is the classic mocap interchange format.

The shape is one pass over the frames: `LoadVideo` → `GetVideoComponents` → `SAM3DBody_Predict` → `SAM3DBody_Smooth` → `BuildPoseFile`. `track_data` from `SAM3_VideoTrack` is optional and only needed for more than one person.

## Caveats, before this looks like a solved problem

- **The skeleton is MHR, not ours.** SAM 3D Body estimates Meta's *Momentum Human Rig*, so what comes out is not a UniRig humanoid. Putting it on our rigs is a retarget — the same engine-side step the free path already depends on. The animated GLB/BVH is the deliverable; "our rig, animated" still finishes in the engine.
- **Monocular 3D pose is ambiguous and jittery.** Depth and absolute scale are not observable from a single camera, which is why `fov` and the `camera_translation` bake exist; per-frame estimates wobble, which is why `SAM3DBody_Smooth` exists. **Quality is unmeasured here** — we have not run it.
- **It answers a narrower question than it looks like.** It recovers the motion of a *person in footage*. It does not invent motion, and it does not animate a non-humanoid.
- **The licence of the upstream model has not been checked** for this use — `facebook/sam-3d-body-dinov3` is sourced from `Comfy-Org/sam-3d-body`, and no licence decision has been recorded.

## What we are choosing

Not implementing it now. The point of this page is that the cost is small enough to make it a **one-experiment question rather than a project**: one ~3 GB download and one template run would say whether the output is usable. Spending that is a separate decision, and the free path above stands on its own without it.
