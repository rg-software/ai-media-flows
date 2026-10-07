# HOW TO: user stories

"I want to…" table in `README.md` tells you **which flow** fits a job. This file tells you **what to actually do**: prerequisites, steps, the knobs that matter, the trap to avoid, and what a good result looks like. Each story links the flows it uses and points at the deeper doc for the *why*.

---

## How to run flows

- **Server:** ComfyUI at [comfy.rt247a.ddns.me](https://comfy.rt247a.ddns.me) - ask the operator for the token.
- **Flows:** the `.json` graphs in `2d/workflows/` and `3d/workflows/`.
- **Inputs:** any file a flow should read goes in the box's `input/` dir.
- **Outputs:** everything a run produces lands in `output/`.

**Two ways to run a flow:**

1. **GUI** - open the ComfyUI web UI, drag a `.json` onto the canvas, set the inputs, Queue. Each graph carries its own note (the coloured group box) with its recipe, its gotchas, and why its settings are what they are.
2. **Scripted** - submit the graph over the API when you want automation or repetition. Examples to copy: `scripts/sweep.py` (parameter grids) and `scripts/marigold_pbr.py` (a non-ComfyUI pipeline).

**The loop for producing an asset**

1. Put your inputs in `input/` - drag-and-drop onto a `LoadImage` node, or upload a batch with `scripts/comfy_io.py upload` (S14).
2. Run the flow (GUI or script). Outputs land in `output/`.
3. Bring the results to your machine - view them in the web UI, or download them with `scripts/comfy_io.py fetch` (S14).
4. Use them.

**When something goes wrong**

- **A run reports success in ~2 s and saves nothing** - a known failure mode; the API still says success (a bad node setting). Note which flow it was and tell the operator, who can read the service journal.
- **The box freezes, or a model won't fit** - read `comfyui/hardware.md` *before* pulling anything large. The box is RAM-bound, not VRAM-bound, and the service has a memory guard that kills ComfyUI rather than the machine.
- **Masks come out inverted** - the MASK convention is *1 = transparent/selected*; see `comfyui/README.md` (node gotchas).

**Two habits that matter more than any knob:** change **one knob at a time**, and trust the **image over the metric** - the numbers have looked fine on images that were clearly wrong.

**Before you ship anything,** check its `licence` in [`PIPELINES.md`](PIPELINES.md). A few flows are non-commercial (each is flagged in its story below, and marked there); everything else is Apache-2.0/BSD-clean.

---

## User stories

### S1. Generate concept art from a prompt

- *When:* you need a character, prop, environment or texture from scratch.
- *Prereqs:* none — the base checkpoints are on the box.
- *Steps:* run `2d/workflows/z-image-turbo.json` (modern, Apache-2.0, fits; 8 steps, ~25 s) or `2d/workflows/sdxl-base-art.json` (SDXL; more "painted").
- *Knobs:* `cfg` and `steps` — **cfg 7 / 20 steps** is SDXL's value point (cfg 3 washes out, cfg 9 over-burns, 30 steps buys nothing). Z-Image leans **photoreal**; add style words or a LoRA for a painted look.
- *Expect:* 1024². For a **solo full-body** character, say so explicitly — baseline SDXL otherwise renders a two-view sheet or a bust.

### S2. Control composition from an existing image

- *When:* you have a sketch, a screenshot, or an asset whose *layout* you want to keep but whose content/style you want to replace.
- *Steps:* `2d/workflows/controlnet-union.json` — one 2.34 GB model covering many modes; pick the mode with `SetUnionControlNetType` and feed the matching preprocessed image (`CannyEdgePreprocessor`, `DepthAnythingV2Preprocessor`, …). Canny-only: `2d/workflows/sdxl-controlnet-canny.json`.
- *Knobs:* `strength` ≈ 0.8 holds structure while freeing style.
- *Trap:* the union `type` strings are **grouped** — `"canny"` is invalid, use `"canny/lineart/anime_lineart/mlsd"`. A bad value **fails silently**.

### S3. Cut an object out, or mask it by description

- *When:* you need a transparent PNG, or a mask to feed an edit.
- *Steps:* **by description** (recommended): `2d/workflows/sam3-segment.json` — type "the knight in silver armor" and get an outline-accurate mask, even in a two-subject scene. **By subject isolation:** `2d/workflows/remove-bg.json` (BiRefNet).
- *Trap:* MASK is **1 = transparent/selected**, and `RemoveBackground` returns 1 on the *foreground* — insert `InvertMask` or you get a perfectly inverted cutout.

### S4. Get a depth map

- *When:* you want a depth map to drive a depth ControlNet, or to fake parallax or depth-of-field in an engine.
- *What it is not:* depth here is **relative** (near = light), with no absolute scale, so it is **not** a height or displacement map. An engine can use it for a parallax look, but you must curve and scale it first, and it stays approximate.
- *Steps:* `2d/workflows/depth-normal.json` (DepthAnythingV2).
- *Expect:* near = light, greyscale and low-frequency.

### S5. Edit a picture: remove, replace, extend

- *When:* fix or change part of an existing image; make the canvas bigger.
- *Steps:*
	- inpaint `2d/workflows/inpaint.json`;
	- outpaint `2d/workflows/outpaint.json` (`extend_left/right_factor` 1.5 = +50% per side).
	- For an **instruction-style** edit ("relight this", "change the material") use `2d/workflows/qwen-edit-gguf.json`.
- *Outpaint:* `2d/workflows/outpaint.json` **invents** the new area (expect new content), but the original region comes back untouched.
- *Knobs:* denoise. For harmonisation, **0.45 integrates while keeping the subject; 0.75 replaces it** — and small subjects break first. For outpaint, also try `mask_blend_pixels`.
- *Colour step at the seam*. If two sides of the same seam are not of the same colour, fix it at generation: lower `denoise` or try inpaint of the affected area. A palette match (`scripts/color_match.py`, or `ColorMatch` in the canvas) is only for a **global** cast.
- *Extending without inventing:* when you want the same existing objects (trees/sky/etc.) carried outward, pad the canvas with `scripts/pad_image.py --mirror-band 128 --mask-feather 24` — a mirrored **band** at the seam, invented beyond — then run `2d/workflows/inpaint.json` on it at `denoise` ~0.65–0.75 so it refines the fill instead of replacing it.
- *Trap:* raw inpaint drifts ~5/255 *outside* the mask (VAE round-trip). Crop&Stitch avoids this entirely; if you use the older path, composite back with the mask.
- *Warning:* the Kontext route is **non-commercial** — don't ship its output. `qwen-edit-gguf.json` does the same job under Apache-2.0.

### S6. Compose a scene from parts

- *When:* you have a background, a character cutout and props, and need one coherent picture.
- *Steps:* `scripts/compose_scene.py` places them (pixel-exact scale/feet/overlap), then `2d/workflows/compose-harmonize.json` blends the lighting.
- *Knobs:* the same denoise rule as S5 - this is the *identity* knob.
- *Two subjects that keep merging?* Put each in its own region with `2d/workflows/regional-prompting.json` - a single prompt containing both subjects **drops one of them entirely** (the model rendered only the sorceress and never the knight). Regional area conditioning fixed it with zero cross-bleed.

### S7. Keep a character consistent across images

- *When:* the same character must appear in several shots.
- *Choose by what "consistent" means:*

| need                                                          | flow                                                                                               | reality                                                                                                                                                                                               |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| same **design** (outfit, hair, silhouette) in any composition | `qwen-edit-gguf.json`                                                                              | Apache-2.0, faithful, but the *face* is not embedding-identical                                                                                                                                       |
| same **face**, close-up                                       | `instantid-character.json`                                                                         | strongest face match, but it **forces a bust**                                                                                                                                                        |
| same **face**, free composition                               | `pulid-identity.json`                                                                              | full-body works; weaker face score; still needs insightface                                                                                                                                           |
| same **character**, new **pose** or camera angle              | `2d/workflows/pose-skeleton.json` (skeleton-driven) · `qwen-edit-gguf.json` (instruction, easiest) | the skeleton flow (see also **S16**) holds a **coarse stance** (arms out / wide) but does not bind limb angles; an instruction is still the way to a *specific* pose, and kept pose *and* design best |

- *Trap:* judge identity by **measurement, not eye** — two renders can look identical yet score far apart. Prompt-level consistency lands around 0.14-0.19, so expect an embedding-identical face only from InstantID or PuLID.
- *New pose or camera angle?* Pose is a separate carrier from identity, so don't expect the consistency recipes above to move it. The route that works is **asking in words**: `qwen-edit-gguf.json` with "the same knight in the same armour and colours, arms spread wide" changed the pose *and* held the design closest. An instruction also handles **camera angles**, which a 2D skeleton cannot (no yaw); the 3D path is the other way to get a chosen angle.
- *What the skeleton flow actually buys:* with its shipped `strength` **1.5** and `end_percent` **0.5** it imposes a **silhouette**. Measured: a "T-pose, arms outstretched" skeleton beat a prompt that explicitly asked for the opposite and still rendered cleanly. So — coarse stance (arms out, wide, tall) → this flow; a specific pose → the instruction. `cfg` makes no difference (4.0 = 7.0), and keep IPAdapter at **0.15** so it does not fight the cue.
- *Turning an object to a different angle?* Don't reach for a ControlNet first: rotate the sprite in your editor, then run it through a second pass at **denoise ≈ 0.5-0.65** with a plain description of what it is.
- *Tooling caveat:* the OpenPose detector finds **no person in most of our stylised renders** (13 of 15 in one batch), so a pose can be *imposed* but not *measured* automatically — `extract` and `measure` are for real photograph.
- *Warning:* `instantid-character.json` and `pulid-identity.json` depend on **insightface**, licensed for **non-commercial research** — don't ship their output. `qwen-edit-gguf.json` is Apache-2.0.

### S8. Transfer a style or a reference look

- *When:* you want an image to adopt the palette, atmosphere or medium of a reference.
- *Steps:* use **`2d/workflows/qwen-edit-gguf.json`** with the reference as `image2` — the multi-image reference mechanism does style transfer. The older `2d/workflows/ipadapter-style.json` (IPAdapter) still works.
- *Knobs:* for IPAdapter, `weight` — 0.0–0.2 is a style hint, 0.3–0.5 blends, and **≥0.6 the reference overrides the prompt** entirely.
- *Trap:* this transfers a **look**, not a layout. If you need "keep this composition", that is ControlNet territory (S2), not style transfer.

### S9. Sprites and atlases

- *When:* you need game-ready sprites (generated, converted from existing art, packed into a sheet, or unpacked from one).
- *Generate:* `2d/workflows/pixel-art.json`: SDXL + `pixel-art-xl` LoRA (OpenRAIL) at 1024². **That LoRA paints on an 8 px grid**, so its native sprite is 1024/8=128 px. Make sure to set the correct target sprite size when applying pallettes. Generating at 1024² and downscaling beats generating small. For the flat retro look, Retro Diffusion ships **one checkpoint per sprite scale** with a /8 factor: `16x` at 256² -> 16 px, `24x-64x` at 512² -> **64 px**, `128x` at 1024² -> 128 px. Those models are possibly **non-commercial**.
- *Convert an existing picture, faithfully:* `2d/workflows/pixel-art-convert.json` - resize + palette only, so the source is kept exactly, nothing is invented.
- *Convert an existing picture, redrawn:* `2d/workflows/pixel-art-restyle.json` - an img2img pass with the pixel-art LoRA first (`denoise` **0.6** is the knob: lower keeps the source, higher redraws it). More sprite-like, but it invents detail.
- *Animate a sprite across a few poses:* get one skeleton per pose with `2d/workflows/pose-extract.json` (**S16**, one photo per pose), render each with `2d/workflows/pose-skeleton.json`, then pack the frames with `scripts/atlas.py`. **Keep the IPAdapter at 0.15** - that is what holds the character's design while the pose changes; higher weights freeze the reference's own stance. **Measured limits:** poses that differ by **~40 degrees or more** read as distinct frames, but **10-30 degree steps render as the same pose**, so a 3-4 frame idle / attack / ready works (while **walk cycle does not**).
- *Pack or slice a sheet:* `scripts/atlas.py`. Use with `pack --out sheet.png --columns 2 --cell 64x64 a.png b.png ...` to lay images out row-major (optional `--padding` gap between cells).
- *Palettes:* the **56 palettes ship inside the `comfyui-pixelart-detector` pack**, so they are already on the box - `PixelArtLoadPalettes` reads that folder (hardcoded). To use your own, drop a PNG into the pack's `palettes` folder, or derive one from an image with `PixelArtPaletteGenerator`. `render_all_palettes_in_grid` renders them all as a labelled sheet.
- *Traps:* downscale by **nearest**, and derive the divisor from the pair - 1024→128 is the LoRA's own **/8**, 1024→64 is **/16** (a deliberate decimation), Retro Diffusion 512→64 is its **/8**. Whatever the target, edit `ImageScale` **and** the palette pass together. Keep the palette pass at a **fixed** size. Do not downscale *before* an img2img pass: a 64-128 px latent makes SDXL produce mush.
- *Warning:* Retro Diffusion's pixel-art models are **non-commercial** (the vendor says outputs are the creator's); `pixel-art-xl` is OpenRAIL and cleaner.

### S10. Finish: upscale and restore

- *When:* you need more resolution, or a soft/small face cleaned up.
- *Steps:* `2d/workflows/upscale-seedvr2.json` (Apache-2.0). Set `resolution` to the **short edge**; set it equal to the image size to **restore** instead of upscaling (including face restore).
- *See the result:* check the slider in the `ImageCompare` node; the `SaveImage` output is the deliverable.
- *Knobs:* `batch_size` must be 4n+1. SeedVR2 *reconstructs* (more detail, more drift, slower); `upscale.json`'s GAN is faithful (it invents nothing).
- *Warning:* don't ship output from `upscale.json` — its `4x-UltraSharp` model is **non-commercial**. `upscale-seedvr2.json` is Apache-2.0.

### S11. Materials: seamless textures, PBR, and into 3D

- *When:* you need a tileable texture, or a complete PBR material an engine can use.
- *Steps:*
	- **Tile it (if your UVs repeat).** `2d/workflows/seamless-texture.json` (`method="offset"`) when the UVs repeat across a surface (grid/tiled UVs, or a 3D mesh whose UVs tile).
	- **Create Material.** `2d/workflows/pbr-material.json` produces the full PBR set — feed it a square texture around 768 px. You can choose `albedo_source` for the base color (pick the more unlit, neutral-looking one). Output lands in ComfyUI's `output/2D/pbr_material/`; pull it down with `comfy_io.py get 2D/pbr_material/<file>.png` (S14).
	- **Prepare for Unity.** Run `uv run python scripts/pack_pbr_material.py --roughness <png> --metallic <png> --out metallicSmoothness.png` to obtain a combined "metallic/smoothness map". Unity reads one map in `_MetallicGlossMap` with **R=metallic, A=smoothness**.
	- **Prepare glTF.** Run `uv run python scripts/make_gltf_material.py --basecolor <png> --normal <png> --roughness <png> --metallic <png> --occlusion <png> --out metallicRoughness.png` to obtain a combined "metallic/roughness map" needed in glTF (**G=roughness, B=metallic**). Add `--mesh <glb> --glb-out <out.glb>` to apply the obtained material to a mesh (mesh needs **UVs**; its material is **replaced**).
	- **Adjust settings.** Data maps as **linear** (sRGB off), the normal as *Texture Type = Normal map*, the packed map's **alpha kept** (DXT1/BC1 has none), and **Metallic = 1** on the material.
- *Traps:* `mirror`/`blend_edges` tile without a visible seam but look visibly wrong (a mirrored building becomes a second cottage) — use `offset`. Marigold's metallic is an **estimate**: on stone it sits near 0.36 where a dielectric should be ~0, so a faint sheen in-engine is the *value*, not the packing — remap or override it per material.
- *Normal direction:* the normal map is **OpenGL (+Y up)** as glTF expects. If your renderer disagrees, pass `--flip-normal-green`.

### S12. 3D from images

- *When:* you want a mesh, a textured model, multiple views, or a rig.
- *Steps:* `3d/workflows/hy3d-full-workflow.json` (shape → texture → bake) or `hy3d-multiview-workflow.json`; rig with `3d/workflows/unirig-humanoid-workflow.json`. Its `Hy3DMeshUVWrap` node is what gives a generated mesh its UVs, which is why a Hy3D mesh can take a material straight from S11.
- *Multiple angles:* `hy3d-multiview-workflow.json` wants front/left/right/back. `2d/workflows/sv3d-turnaround.json` makes them from a single image — four views in one batch (if you want only the views, that flow is the whole job).
- *View:* the run ends in a viewer node — `Preview3D` on both Hy3D exports, `UniRigPreviewRiggedMesh` on the rig. The viewers read from `output/`, where the GLB/FBX already land.
- *Textures:* the ComfyUI 3D viewer does not show GLB textures (both `Preview3D` and `Load3D` tested, plus a third-party viewer; it is a frontend limitation, not in your file - re-checked on 1.53.6, 2026-09-28: unchanged - and on every frontend upgrade, `PIPELINES.md`). Each Hy3D flow therefore also ends in a **Textured turntable**, which renders the textured mesh to a 12-frame 360° image batch.
- *PBR:* the generated texture is **base colour only** — one atlas, a constant roughness, no PBR maps (and our GLB omits `metallicFactor`, which glTF then defaults to **1.0**, i.e. fully metallic). Each flow also saves that **atlas as an image**; load it into `2d/workflows/pbr-material.json` to get PBR textures, then pack it for the target with `scripts/make_gltf_material.py` (glTF) or `scripts/pack_pbr_material.py` (Unity).
- *Warning:* Hy3D runs under the **Tencent Hunyuan 3D Community License**, which **excludes the EU, UK and South Korea** and requires a licence from Tencent above 1M monthly users. UniRig (rigging) is MIT.
- *More:* `3d/README.md`.

### S13. Explore parameters with a sweep

- *Any flow, not just text-to-image:* `scripts/sweep_workflow.py <flow.json> --set "<node_id>.<widget>:v1,v2" [--set ...] --out PREFIX`. Widgets are named (or an index), resolved against the live schema before anything runs, so a typo fails loudly; up to two axes make a grid; `--image` overrides every `LoadImage` so image-conditioned flows sweep too. `scripts/sweep.py` remains the simpler path for plain text-to-image.
- *When:* you want to find a value yourself rather than take a story's default - the defaults quoted in these stories came from exactly this.
- *Steps:* `scripts/sweep.py` runs a two-axis grid over a flow and writes a labelled sheet plus a per-cell metric, e.g. `--x cfg:3,5,7 --y steps:10,20,30`.
- *Knobs:* which two axes you sweep; hold everything else fixed.
- *Trap:* the sheet's metric is a hint, not a verdict - judge it by eye.

### S14. Move files to and from the box

- *When:* you need to put your own inputs into the box, or bring a run's outputs back (using the ComfyUI URL and token).
- *Steps:*
	- `uv run python scripts/comfy_io.py upload art/*.png` uploads into `input/`;
	- `... outputs latest` (or a prompt id) lists what a run produced;
	- `... fetch latest --dest from-box` downloads those files and records what it fetched in a small `manifest.json`;
	- `... get 2D/pbr_set/<texture>/material/normal.png` downloads **any** file under ComfyUI's `output/`, `input/` or `temp/` — including ones a script wrote (a PBR material, a contact sheet), which never appear in a run's history.
- *Knobs:*
	- `--base`/`COMFY_BASE` — the ComfyUI URL;
	- `--token`/`COMFY_TOKEN` — **ask the operator**. It lives on the server as the first line of `~/Projects-Git/ComfyUI/login/PASSWORD`.
	- `--subfolder refs` keeps uploads tidy;
	- `--dest` chooses where downloads land.
- *Trap:* image nodes read **only** from `input/` - a file sitting in `output/` cannot be loaded, so upload it before running a flow that needs it. With many inputs, upload the folder once and read it with the `LoadImagesFromFolderKJ` node rather than one file at a time. And only those three dirs are served: a file anywhere else on the box (e.g. a result written into the repo) cannot be fetched at all, by any route short of SSH. That SSH route is worth having when you have no token or the file is large: `comfyui/linux-setup.md` records the two hops (box -> NAS -> Windows) and the `-O` flag the second one needs, since the Synology's sshd runs no SFTP subsystem.
- *More:* `scripts/comfy_io.py --help`.

### S15. Animate a character from a driving video

- *When:* you have a still character and a clip whose motion you want on it. The motion is transferred directly — no pose extraction and no skeleton step.
- *Steps:*
	- put your character image and your driving clip in `input/`;
	- open `video/workflows/wan-animate-motion.json` and set the **reference image** (`LoadImage`) and the **driving video** (`LoadVideo`);
	- describe **scene, background and camera** in the positive prompt — *not* the motion, which comes from the video;
	- run. Shipped sample generates in ~1.5 min.
- *Knobs:*
	- `length` — frames (4n+1). **It is the FIRST N frames of the clip**: a longer clip is cut off at N, a shorter one repeats its last frame. In the shipped sample, the default 33 is about 1.4 s of the footage;
	- the output plays at **the clip's own frame rate** (`CreateVideo.fps` is wired from the video), so a 30 fps clip writes a 30 fps file. The motion is frame-indexed, so a different value is a slow-motion or speed-up;
	- `pose_strength` — how literally the driving motion is copied;
	- `reference_image_strength` — identity vs motion trade;
	- the prompt's camera wording *is* the viewpoint control: the output camera is decoupled from the driving video.
- *Trap:* the output size comes from the **driving video**, snapped to a multiple of 16 — not from the node's defaults. **Don't swap the model for a GGUF quant.** Those same weights quantised that way make the flow silently ignore your driving video, while the reference image keeps working - so if the character never moves, that is why. The workflow's note has the explanation.
- *Videos longer than ~1.5 sec:* the flow generates the first `length` frames and stops, so run **`uv run python scripts/wan_segment.py <clip> --ref <image> --out <result.mp4>`** - it probes the clip, works out how many segments it needs, runs each one continuing from the previous segment's last frame, and stitches them into one file at the clip's own fps. It is API-only, so it runs against the remote server from anywhere.
- *Doing it by hand:* generate a segment, then add a `LoadImage` of its **last frame** wired to `continue_motion` and set `video_frame_offset` to **last pose + 1**. The node pins the frame you pass at pose `offset - 1` and generates `length` frames from there, so for 33-frame segments the offsets are 0, 33, **65**, 97; join the pieces with `A + B[trim_image:]` (that node output says how many frames overlap). It closes the join **and holds the camera** across the cut.
- *More:* [`video/README.md`](video/README.md), and E1/E2/E3/E10/E12/E14 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

### S16. Get a pose from a photo

- *When:* you have a photo of a person in the pose you want and need that pose as a skeleton — to put a character into it (S7), or to render sprite frames (S9).
- *Steps:*
	- open `2d/workflows/pose-extract.json` and set `LoadImage` to your photo (it ships a working example, `2d/char_heroine.png`);
	- run it. It writes **two** things: the skeleton **image** (`2D/pose_extract_*.png`) and the **keypoints JSON** (`2D/pose_keypoints_*.json`);
	- put the skeleton image in `input/` — or pick it straight from `output/` with a `LoadImageOutput` node — and point `pose-skeleton.json`'s node 1 at it. One photo per pose.
- *Knobs:*
	- `resolution` — 1024 keeps the joints crisp on a 1024-square photo;
	- `detect_hand`/`detect_face` — they add keypoints to the JSON; the body joints are what a pose ControlNet uses.
- *Trap:* the detector needs a photoreal-enough person. Measured on our own assets, `char_heroine` yields all 18 joints while the armoured `char_knight` yields **none** — so on stylised art this flow silently produces nothing.
- _Note:_ if you have a 3D model, it is possible to export COCO pose keypoints and labels directly or with simple tools.
- *More:* the note inside [`2d/workflows/pose-extract.json`](2d/workflows/pose-extract.json), and E21 in [`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md).

### S17. Recover a 3D motion clip from a video

- *When:* the motion you want exists only as footage. This flow recovers it as a 3D animation for the engine to retarget onto your own character.
- *Steps:*
	- put the clip in `input/` (the flow ships pointing at the upstream example, `woman_holding_water_glass.mp4`);
	- open `animation/workflows/sam3d-motion.json`;
	- run it. You get an animated **skeletal GLB** (in `3d/`) and a render preview of the recovered motion (in `video/`);
	- check the GLB by opening it (Blender, an engine, any glTF viewer).
- *Knobs:*
	- `bone_smooth_window` (9) — the export-stage smoother, and **bigger is not better**;
	- `rotation_threshold_degrees` (0) — at its upstream value of 15 it *disables* smoothing whenever the motion gets fast;
	- `camera_translation` (`off`) — whether the **root travels at all**. Here `off` holds the root at its **bind position** every frame, so the clip is articulation only (right when the engine drives locomotion itself); `centered` animates the root with `pred_cam_t - pred_cam_t[0]`, a **delta from frame 0**, so the travel inside the footage survives but starts at the origin; `absolute` is the **raw** solve. If the deliverable does not need the body to move through the world, use `off`; otherwise use `centered`; to match a known camera, use `absolute`. It changes the **root translation channel only**.
	- **the face** — this flow exports it as **72 blendshape morph targets** on the GLB's body mesh. The knobs are on `SAM3DBody_FaceExpression`: `mouth_strength`/`eye_strength`/`brow_strength` (MediaPipe under-reports the eye and brow end, hence 2) and `blendshape_smooth_window` (**15** - the facial twin of `bone_smooth_window`). The shapes are **unnamed**, so a rig's face maps onto them by index; The shapes are **unnamed in the GLB but emitted in basis order**, so target `k` is MHR axis `k` - [`face-shapes.md`](animation/face-shapes.md) names the 44 of 72 that video can drive;
	- `Video Slice` — **how much footage is processed**.
- *How much footage fits:* `Video Slice` (5 s as shipped) is the knob. Roughly **27 s at the 480x848 the flow now caps its input to**, or **12 s at the 720x1280 source**. The cap is an `ImageResizeKJ` with `keep_proportion` on, so it fits within the box and keeps the aspect; raise its `width`/`height` for full-size joints and a full-size preview. Exceeding the budget is a hard CUDA out-of-memory.
- *Trap:* the export style can hide the face. `BuildPoseFile`'s `mesh_style` ships **`body_mesh`**; the smaller `scail` stick figure carries the same skeleton but **no body mesh, so the 72 blendshapes are silently dropped** (728 KB against 18 MB).
- *Traps:* the **render preview is not smoothed** — only the exported file is — so judge the GLB, not the overlay. The skin is Meta's **MHR**, not your rig, so the retarget is your engine's job. And **fast or spinning footage can still break**, so watch the render for a limb that snaps.
- *More:* [`animation/motion-sourcing.md`](animation/motion-sourcing.md) for what the free path already covers and what this costs, and E4/E6/E8/E15/E16 in [`animation/EXPERIMENTS.md`](animation/EXPERIMENTS.md).

### S18. Change a clip's frame rate

- *When:* a clip is choppy to watch, or you want smooth slow motion. In-between frames are **synthesised**, so the clip gains real frames instead of being re-tagged.
- *Steps:*
	- put your clip in `input/`;
	- open `video/workflows/frame-interpolate.json` and set the **clip** (`LoadVideo`);
	- set the **factor** on the `INT` constant (node 5, 2-16). It is wired to both the interpolator and the output frame rate, so the clip keeps its speed;
	- run. It is the cheapest flow here: doubling a 5 s 720x1280 clip takes **15-25 s**.
- *Knobs:*
	- the **factor** - `multiplier` is the *total* factor, not the number inserted: 121 frames at x2 gives 241, at x4 gives 481;
	- the **model** - RIFE (21.6 MB, MIT) is the default; FILM (65.7 MB, Apache-2.0) measured a **tie on quality for ~1.8x the time**;
	- **smooth slow motion instead of same speed (added frames slow down playback):** edit node 6's expression from `a * b` to `a`, which writes the source frame rate against the extra frames.
- *Traps:* the inserted frame averages the motion blur of its two neighbours, so a fast limb goes slightly soft - inherent, since neither input holds that exposure. Interpolation cannot invent detail the source never had, and it will not fix a choppy *performance* - only the sampling of one.
- *More:* [`video/README.md`](video/README.md), and E17/E17b in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).


### S19. Generate music from a text prompt

- *When:* you want a music track from a description, with no source audio.
- *Steps:*
	- open `audio/workflows/ace-step.json`. The checkpoint `ace_step_1.5_turbo_aio.safetensors` must be in `models/checkpoints/` (9.3 GB);
	- describe the music in **`tags`** (genre, mood, instrumentation, production). For an instrumental leave **`lyrics`** empty; to write a song, put the words in with `[Verse]` / `[Chorus]` markers;
	- set **`duration`** (seconds) and, if you care, `bpm`, `keyscale`, `language`;
	- **for a song, write full sections and budget 2+ minutes** - measured, the vocals need room (see the trap);
	- run. A 2-minute track takes about **25 s**, including loading the model.
- *Knobs:* the two constants at the left are wired to **both** of their consumers on purpose - **seed** goes to the text encoder *and* the sampler, and **duration** goes to the encoder *and* the latent's `seconds`. Change them there, not on the nodes, or the condition and the sample will disagree about what is being made.
- *Trap:* **the lyric has to be song-sized, and song-shaped** (E6/E7). The model sings roughly **60% of the words it is given**, i.e. **1.5-3 words per second** - a 120 s track wants **250-350 words**, and a 40-word poem comes back instrumental however good the tags are (same tags: 209 sung words at 344 input, 1 at 40). A bare `[Verse]` marker changes nothing on its own; **verse/chorus/bridge with a repeated chorus** took one such poem from 1 sung word to **86 (74% precision)**, using only the poem's own words - its strongest line is a ready-made chorus. **Repeat a short lyric into song form until the word count matches the duration**, or accept an instrumental.
- *Trap:* **a short track will not sing.** Measured: at 30 s the flow produced **no vocal at all**, even with a full song's lyric, and at 120 s the same lyric sang (85% of the sung words came from the input). The planner builds a whole-song blueprint and the duration truncates it, so what survives short is the *instrumental intro*; a 3-line lyric also under-fills a long track. Write sections, and give it 2+ minutes.
- *Note:* `KSampler`'s **negative input looks like a mistake and is not** - it is the positive through `ConditioningZeroOut` (an empty negative), because ACE-Step's prompt has no "undesired" concept and the sampler needs a negative slot; at cfg 1.0 it is unused anyway.
- *Trap:* you cannot listen to the result from here. Judge it by the level numbers (`peak`/`RMS` should sit near -1/-14 dBFS, i.e. mastered rather than raw), by duration and sample rate, and - as we do - by a **spectrogram**: harmonic lines mean pitch, regular vertical transients mean a beat, a flat wash means noise. See `audio/README.md`.
- *Note on the lyric's markup:* `[Verse]` / `[Chorus]` / `[Bridge]` are **a convention the model learned, not a keyword list** - nothing parses them, and the templates themselves also use free-form ones like `[Intro - Rhodes piano and brushed drums]` or `[drum fill]`. Use the standard names for structure, a dash plus a phrase for hints; an invented name will not error. See [`audio/README.md`](audio/README.md).
- *More:* [`audio/README.md`](audio/README.md), and E1 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S20. Match the style of a reference track

- *When:* you have a track whose feel you want more of - a bed, a theme, more of the same palette - rather than something new.
- *Steps:*
	- put your reference in ComfyUI's `input/` (flac/wav/mp3) and set `LoadAudio` to it;
	- open `audio/workflows/ace-step-style.json`; set the **target length** on the `FloatConstant` (it feeds the trim and the conditioning, so they agree);
	- put the style you *want* in **`tags`** - although see the trap;
	- set **`denoise`** and run. A take costs about 5 s.
- *Knobs:* **`denoise`** - measured, this is a *retention* dial: 0.3-0.5 gives the same piece re-rendered (spectral similarity to the reference 0.99), and even 0.9 stays closer to the reference than to a text-only take of the same tags. The curve is not monotone (0.7 came out least like the reference), and with the turbo's 8 steps `denoise` is quantised to eighths.
- *Trap:* **this is "more of this", not "make this industrial".** It keeps the reference's character, so it is the tool for a consistent soundtrack; for a genuine restyle use **S22** (YuE, non-commercial). And a rhythmic reference needs its `duration` matched, since the conditioning and the encoded latent must agree.
- *More:* [`audio/README.md`](audio/README.md), and E5 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S21. Generate sound effects from a text prompt

- *When:* you need a footstep, a door, an impact, a weapon, or a short ambience - the non-musical half of a game's sound.
- *Steps:*
	- open `audio/workflows/stable-audio-3-sfx.json` and write the effect in the **positive prompt**, concretely: `footsteps on gravel`, `a heavy wooden door creaking`, `a sword drawn from a scabbard`;
	- set **`seconds`** on `EmptyLatentAudio` - **at least ~10, then trim**: a 4 s request comes back with the content stopping around 2.8 s and a tiling artefact after it;
	- run - about **5 s per take**.
- *Knobs:* the prompt (**terse is fine**); `seconds` (>= 10, up to 2 minutes for ambiences); `seed`; and the sampler, which **must match the checkpoint** (see traps).
- *Traps:* **the sampler recipe is per-checkpoint, not per-family.** Upstream ships two SA3 templates and they disagree: `medium_base` (the **pre-trained** checkpoint, for fine-tuning) runs **50 steps / cfg 7**, while `medium` (the **post-trained** one, for generation) runs **8 steps / cfg 1**. `small_sfx` is post-trained, so it wants **8 / 1**. And the correct recipe's takes come back **much quieter** (footsteps rms -42 dB against -15), so **level-match before judging**.

### S22. Restyle a track (cover its melody)

- *When:* you have a track, a loop, or a hook you like, and you want **the same tune in a different idiom** ("make this industrial"). This is the only *restyle* route in the repo - **S20** can hold a reference's character, but it cannot change it.
- *Steps:*
	- open `audio/workflows/yue2-cover.json` and put your reference in ComfyUI's `input/`, picked on the **`LoadAudio`** node;
	- write the **style** to change it into (the shipped `STYLE` is industrial rock) and the **lyrics** you want - the reference's *melody* is kept, its *words* are not;
	- run. A 30 s reference covers in about **65 s**.
- *Knobs:* `max_duration` is a **ceiling, not a requested length** - you cannot pick the cover's size. The model stops when its generated song ends, so the length follows the ABC's music: E22 measured a 30 s instrumental at cap 30 coming out 27.7 s with a 188-word lyric and 29.5 s with none. A longer source helps only by giving SheetSage2 more melody to transcribe. `mode` is `melody` for a cover (`full` writes a new song instead).
- *Traps:* **you cannot add lyrics to an instrumental melody.** The lyrics do reach the model, but an instrumental's transcribed ABC has an all-rests `Vocal` line, so the words have nothing to follow - E22's added 188-word lyric was not sung. For new words on a tune, pick a source that is already sung. **The licence:** YuE 2's weights are `cc-by-nc-4.0` (**non-commercial**), so the output is research-only.

### S23. Generate a song that actually sings

- *When:* you want a **song** - lyrics actually sung, clearly - and the 8-step turbo is not delivering. There are **two MIT arms**, and E23 kept both because they split by *style*.
- *Steps:*
	- **lyric-full on clear-lead styles**: `audio/workflows/ace-step-xl-sft.json` (ACE-Step 1.5 XL, MIT) - 50 steps / cfg 7;
	- **fast and light, and on shouty styles**: `audio/workflows/ace-step-v1-35b.json` (ACE-Step v1 3.5B, MIT) - `lyrics_strength` 1.0;
	- open the arm's JSON, write the **style** (`tags`) and the **lyrics**, run.
- *Knobs:* the **style** names the voice (see traps). XL adds `steps`/`cfg` (50 / 7 as shipped), the text encoder's `cfg_scale`, `ModelSamplingAuraFlow` shift 3, and seed + duration (each wired to two consumers). v1 adds **`lyrics_strength`** - the knob that decides whether the lyric is sung, and it only works in a window (**1.0-2.0** sings it, **0.5** sings its own words, **4.0** collapses) - plus `steps`/`cfg` 50 / 5 and the `ModelSamplingSD3` shift 5 + Reinhard-tonemap recipe the 1.5 line dropped.
- *Traps:* **the style is the vocal's on/off switch, so name the voice and keep it consistent.** A style asking for a *clear, strong, close-mic lead* returned 124 of 188 lyric words sung cleanly, while the same model on a style asking for a *shouted male lead* came back **whispered** - and the turbo, on that clear-lead style, produced **no vocal at all** (E13/E13b). **Why two arms (E23):** held to one clear-lead style, XL sang 173 of 188 (92% coverage) against v1's 149 (79%), so XL is the lyric-full arm there - but v1 sang 180 words on the *industrial* style, where XL whispers. And **`lyrics_strength` is non-monotone**: turning it *up* is not "obey the lyric harder", it breaks the vocal. Like every model here the takes land near full scale, so normalise.
- *More:* [`audio/README.md`](audio/README.md), and E13/E13b/E13c/E23 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S24. Repair a region of a track (repaint)

- *When:* a take is right except for **one span** - a mispronounced word, a weak section, a deliberately deleted passage - and you want that span regenerated **without touching the rest**. This is the audio analogue of inpainting.
- *Steps:*
	- open `audio/workflows/ace-step-latent-repaint.json`, and put the source audio on `LoadAudio` with its **length in seconds** on the `FloatConstant` (the flow sizes the latent from it, so the two must agree);
	- set the **span to repair** - just two numbers, `repair from (s)` and `repair to (s)`. The flow converts them to the latent frames the mask works: repairing 55-61 s of a 120 s take is simply `55` and `61`;
	- set `tags` and `lyrics` to the **take's own whole prompt** - its style and its full lyric (like an image inpaint prompts the whole picture and masks the region);
	- run; a 120 s take costs about **15 s**.
- *Knobs:* **`repair from` / `repair to`** (seconds - the span), **`tags` + `lyrics`** (the big one - see traps), `seed`, and `denoise` (**leave at 1.0**; lower values changed the band *more*, not less).
- *Traps:* **match the conditioning before touching the mask or the sampler.** The first run came back with an audible seam and a style change - and both were the *prompt*: the flow had inherited a generic `tags` line with empty lyrics, so the band was regenerated as different music. **Give it the take's whole prompt**. E19b's working run used the take's own style and its full 188-word lyric.
- *More:* [`audio/README.md`](audio/README.md), and E19/E19b in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S26. Generate narration or a voice-over from text

- *When:* you want a **spoken line** - narration, a character's voice-over, a radio bark - rather than music, and you want to choose (or clone) the voice.
- *Steps:*
	- open `audio/workflows/chatterbox-narration.json` and put the script in **`text`** - punctuation and paragraph breaks are the pacing controls, because there is no SSML;
	- optionally wire a `LoadAudio` holding **5-10 s of a voice** to **`audio_prompt`** to clone it; left unconnected, you get the model's own narrator;
	- run. A line takes seconds once the model is loaded - the first run downloads ~1 GB to `models/chatterbox/`.
- *Knobs:* **`exaggeration`** (0.25-2.0) and **`cfg_weight`** (0.2-1.0) are the expressiveness pair - they are what makes a line read as a delivery rather than a read-out; `temperature` is variation and `seed` is the take.
- *Traps:* the output is **24 kHz mono** where every other flow here is 48 kHz stereo, so treat it as a **VO element to place in a mix**, not a bed - and it lands near full scale, so normalise. Unlike singing, **the words are worth checking with a transcript**: for speech, ASR is a real presence test (E25).
- *More:* [`audio/README.md`](audio/README.md), and E25 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S27. Generate a dialogue scene

- *When:* you want a **conversation** - two voices (up to four) trading lines - not a single voice-over, and you want each line as its own file.
- *Steps:*
	- open `audio/workflows/chatterbox-dialogue.json`;
	- put the **two voices** on the `LoadAudio` nodes - `speaker_A_Audio` / `speaker_B_Audio` are **required**, 5-10 s each: your own clips, or a window of a separated vocal stem (a **sung** reference works and gives a distinct voice - E26b);
	- write the script in `dialog_text`, one line per `SPEAKER A:` / `SPEAKER B:` label;
	- run: you get the **mixed scene plus each speaker's track**, all on the same timeline (silent where the other talks) - they drop straight onto a game timeline.
- *Knobs:* `exaggeration` / `cfg_weight` / `temperature` / `seed` behave as in S26; optional `speaker_C_Audio` / `speaker_D_Audio` extend the cast to four.
- *Traps:* **the references ARE the voices** - two close clips give two close voices (E26), a sung stem or your own clips give distinct ones (E26b). And this node needed a one-line pack patch on this box (torchaudio 2.11 routes `save()` to torchcodec); it is recorded in `comfyui/pinned-config.md`. Output is 24 kHz mono VO stems, near full scale - normalise.
- *More:* [`audio/README.md`](audio/README.md), and E26/E26b in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).



---

## If your job isn't here

Browse [`PIPELINES.md`](PIPELINES.md) — the capability index (operation family × subject/domain, with cost, licence, status and key knob). If a flow exists but has no story above, that's a documentation gap worth reporting; if no flow exists, it belongs in `PIPELINES.md` → "Status — what is actually left".
