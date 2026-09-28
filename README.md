# AI Game-Dev Pipelines: start here

A working, reproducible pipeline for **generating game assets with open models on our own hardware**, plus the notes that explain *why* every choice was made. We have two primary goals:

1. **Get things done** — real assets out of a real pipeline.
2. **Understand it deeply** — every node, knob, failure mode and version, so the setup can be rebuilt or ported.

**This page is the cookbook.** Find the job you have, follow the link, and the story in [`HOWTO.md`](HOWTO.md) tells you what to actually do.

---

## I want to…

<!-- jobs: generated from workflows/jobs.json by scripts/gen_job_docs.py -->

### 2D images

| I want to make / do                                | flow                                                                                                                                                                                                                                                                                 | story                                                         |
|----------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| Generate concept art from a prompt                 | `2d/workflows/z-image-turbo.json` (modern, Apache-2.0) or `2d/workflows/sdxl-base-art.json` (SDXL, painted look)                                                                                                                                                                     | [S1](HOWTO.md#s1-generate-concept-art-from-a-prompt)          |
| Control composition from an existing image         | `2d/workflows/controlnet-union.json` (one model, many modes) · `2d/workflows/sdxl-controlnet-canny.json` (canny only)                                                                                                                                                                | [S2](HOWTO.md#s2-control-composition-from-an-existing-image)  |
| Cut an object out (transparent PNG)                | `2d/workflows/remove-bg.json` (BiRefNet)                                                                                                                                                                                                                                             | [S3](HOWTO.md#s3-cut-an-object-out-or-mask-it-by-description) |
| Mask by description ("the knight", "the roof")     | `2d/workflows/sam3-segment.json` (SAM 3, text-prompted)                                                                                                                                                                                                                              | [S3](HOWTO.md#s3-cut-an-object-out-or-mask-it-by-description) |
| Get a depth map                                    | `2d/workflows/depth-normal.json` (DepthAnythingV2)                                                                                                                                                                                                                                   | [S4](HOWTO.md#s4-get-a-depth-map)                             |
| Inpaint / remove / add an object                   | `2d/workflows/inpaint.json`                                                                                                                                                                                                                                                          | [S5](HOWTO.md#s5-edit-a-picture-remove-replace-extend)        |
| Make the picture bigger (outpaint)                 | `2d/workflows/outpaint.json` (invents the new area; the original stays pixel-exact)                                                                                                                                                                                                  | [S5](HOWTO.md#s5-edit-a-picture-remove-replace-extend)        |
| Extend a frame with its own content (not invented) | `scripts/pad_image.py` (mirror band + mask) → `2d/workflows/inpaint.json`                                                                                                                                                                                                            | [S5](HOWTO.md#s5-edit-a-picture-remove-replace-extend)        |
| Fix a colour or tone cast across a result          | `scripts/color_match.py` (palette match; global cast only - see E20)                                                                                                                                                                                                                 | [S5](HOWTO.md#s5-edit-a-picture-remove-replace-extend)        |
| Relight / change the lighting                      | `2d/workflows/qwen-edit-gguf.json` (faithful)                                                                                                                                                                                                                                        | [S5](HOWTO.md#s5-edit-a-picture-remove-replace-extend)        |
| Compose a scene from parts (bg + character + prop) | `scripts/compose_scene.py` → `2d/workflows/compose-harmonize.json`                                                                                                                                                                                                                   | [S6](HOWTO.md#s6-compose-a-scene-from-parts)                  |
| Keep two subjects from merging                     | `2d/workflows/regional-prompting.json` (a single prompt *drops* one)                                                                                                                                                                                                                 | [S6](HOWTO.md#s6-compose-a-scene-from-parts)                  |
| Keep a character consistent across images          | `2d/workflows/qwen-edit-gguf.json` (design) · `2d/workflows/instantid-character.json` (tight face) · `2d/workflows/pulid-identity.json` (face + free composition)                                                                                                                    | [S7](HOWTO.md#s7-keep-a-character-consistent-across-images)   |
| Get a pose from a photo                            | `2d/workflows/pose-extract.json` (a photo of a person -> the skeleton image a ControlNet reads, plus the keypoints JSON)                                                                                                                                                             | [S16](HOWTO.md#s16-get-a-pose-from-a-photo)                   |
| Put a character in a specific pose                 | `2d/workflows/pose-extract.json` (get the pose from a photo) · `2d/workflows/qwen-edit-gguf.json` (instruction - best for a specific pose) · `2d/workflows/pose-skeleton.json` (skeleton cue - holds a **coarse stance** at `strength 1.5` + `end_percent 0.5`, but not limb angles) | [S7](HOWTO.md#s7-keep-a-character-consistent-across-images)   |
| Transfer a style or reference look                 | `2d/workflows/qwen-edit-gguf.json` (multi-image reference) · `2d/workflows/ipadapter-style.json` (superseded)                                                                                                                                                                        | [S8](HOWTO.md#s8-transfer-a-style-or-a-reference-look)        |
| Turn one image into a multi-view turnaround        | `2d/workflows/sv3d-turnaround.json` (SV3D_p; a 21-frame 360° orbit, no mesh needed — take frames 0/5/10/15 for 0/90/180/270)                                                                                                                                                         | [S8](HOWTO.md#s8-transfer-a-style-or-a-reference-look)        |
| Pixel art                                          | `2d/workflows/pixel-art.json` (from a prompt) · `pixel-art-convert.json` (existing image, faithful) · `pixel-art-restyle.json` (existing image, redrawn) · `scripts/atlas.py` (pack a sheet / slice one - local)                                                                     | [S9](HOWTO.md#s9-sprites-and-atlases)                         |
| Build a sprite sheet / atlas                       | `scripts/atlas.py` (pack images into a sheet / slice one back - local, `--verify` checks the round-trip)                                                                                                                                                                             | [S9](HOWTO.md#s9-sprites-and-atlases)                         |
| Upscale / restore (incl. faces)                    | `2d/workflows/upscale-seedvr2.json` (Apache-2.0; `resolution` = image size for *restore*)                                                                                                                                                                                            | [S10](HOWTO.md#s10-finish-upscale-and-restore)                |
| Upscale faithfully (GAN, invents nothing)          | `2d/workflows/upscale.json` — non-commercial `4x-UltraSharp`; prefer SeedVR2 above                                                                                                                                                                                                   | [S10](HOWTO.md#s10-finish-upscale-and-restore)                |

### Materials and the 3D bridge

| I want to make / do            | flow                                                                                                                                                                   | story                                                           |
|--------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| Make a texture tile seamlessly | `2d/workflows/seamless-texture.json` (`method="offset"`)                                                                                                               | [S11](HOWTO.md#s11-materials-seamless-textures-pbr-and-into-3d) |
| Turn a texture into PBR maps   | `2d/workflows/pbr-material.json` (maps) -> `scripts/pack_pbr_material.py` (the packed map Unity needs) or `scripts/make_gltf_material.py` (glTF packing, optional GLB) | [S11](HOWTO.md#s11-materials-seamless-textures-pbr-and-into-3d) |
| Push a 2D material into 3D     | `scripts/make_gltf_material.py` (glTF-valid material + optional GLB)                                                                                                   | [S11](HOWTO.md#s11-materials-seamless-textures-pbr-and-into-3d) |

### 3D models

| I want to make / do                       | flow                                                                                             | story                              |
|-------------------------------------------|--------------------------------------------------------------------------------------------------|------------------------------------|
| Make a 3D model from an image/description | `3d/workflows/hy3d-full-workflow.json` · multi-view: `3d/workflows/hy3d-multiview-workflow.json` | [S12](HOWTO.md#s12-3d-from-images) |
| Rig a character                           | `3d/workflows/unirig-humanoid-workflow.json` (bpy via pixi — Linux only)                         | [S12](HOWTO.md#s12-3d-from-images) |

### Animation

| I want to make / do                                | flow                                                                                                                                                                               | story                                                     |
|----------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| Animate a sprite across poses (make sprite sheets) | `2d/workflows/pose-extract.json` (one pose per photo) -> `2d/workflows/pose-skeleton.json` (render each; keep the contrasts ~40 deg apart) -> `scripts/atlas.py` (pack the frames) | [S9](HOWTO.md#s9-sprites-and-atlases)                     |
| Recover a 3D motion clip from a video              | `animation/workflows/sam3d-motion.json` (footage -> an animated skeletal GLB, for the engine to retarget)                                                                          | [S17](HOWTO.md#s17-recover-a-3d-motion-clip-from-a-video) |

### Video (motion as content)

| I want to make / do                      | flow                                                                                                                                                                                              | story                                                        |
|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| Animate a character from a driving video | `video/workflows/wan-animate-motion.json` (a still character + a driving video you supply; the motion is transferred directly) · use `scripts/wan_segment.py` to process longer clips in segments | [S15](HOWTO.md#s15-animate-a-character-from-a-driving-video) |
| Change a clip's frame rate               | `video/workflows/frame-interpolate.json` (in-between frames are synthesised, so a clip smoothly gains frames instead of being re-tagged - one factor knob)                                        | [S18](HOWTO.md#s18-change-a-clips-frame-rate)                |

### Audio

| I want to make / do                                       | flow                                                                                                                                                                   | story                                                         |
|-----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| Generate music or a song from a text prompt               | `audio/workflows/ace-step.json` (tags + optional lyrics -> a 2-minute track; ACE-Step 1.5, MIT, 9.3 GB all-in-one)                                                     | [S19](HOWTO.md#s19-generate-music-from-a-text-prompt)         |
| Keep a soundtrack in the same style as a reference        | `audio/workflows/ace-step-style.json` (a reference track is encoded and re-sampled at a chosen `denoise` - it retains the reference strongly rather than restyling it) | [S20](HOWTO.md#s20-match-the-style-of-a-reference-track)      |
| Generate a sound effect or an ambience from a text prompt | `audio/workflows/stable-audio.json` (footsteps, doors, impacts and field recordings - Stable Audio Open 1.0, core nodes only)                                          | [S21](HOWTO.md#s21-generate-sound-effects-from-a-text-prompt) |
| Restyle a track in a new style (cover)                    | `audio/workflows/yue2-cover.json` (YuE 2 melody transplant - **non-commercial** weights; the shippable route is ACE-Step's MIT Cover mode)                             | [S22](HOWTO.md#s22-restyle-a-track-cover-its-melody)          |

### Cross-cutting tooling

| I want to make / do                   | flow                                                                                                                                                                                                                                                   | story                                               |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|
| Sweep parameters into a labelled grid | scripts/sweep_workflow.py (any shipped flow, any widget, 1-2 axes - image-conditioned flows included) · scripts/sweep.py (plain text-to-image, sampler axes) · scripts/sweep_outpaint.py (the outpaint seam specifically, with a boundary-step metric) | [S13](HOWTO.md#s13-explore-parameters-with-a-sweep) |
| Move files to and from the box        | `scripts/comfy_io.py` (HTTP-based)                                                                                                                                                                                                                     | [S14](HOWTO.md#s14-move-files-to-and-from-the-box)  |

## Operating the box

| I need to…                                                            | go to                                                        |
| --------------------------------------------------------------------- | ------------------------------------------------------------ |
| Know what will and won't run here (read before pulling a large model) | [`comfyui/hardware.md`](comfyui/hardware.md)                 |
| Use the server / fix a crash                                          | [`comfyui/README.md`](comfyui/README.md)                     |
| Set up a machine                                                      | [`comfyui/linux-setup.md`](comfyui/linux-setup.md) |
| Roll back a ComfyUI upgrade                                           | [`comfyui/pinned-config.md`](comfyui/pinned-config.md) |
| Upgrade the hardware                                                  | [`comfyui/UPGRADE-TODO.md`](comfyui/UPGRADE-TODO.md)         |
| Decide whether a tool is still the right one                          | [`2d/AUDIT-tooling-2026-09.md`](2d/AUDIT-tooling-2026-09.md) |

---

## Where a flow's documentation lives

Four places, and you can reach all of them **from the flow itself** — no hunting:

|                    |                                                                                                                           |
|--------------------|---------------------------------------------------------------------------------------------------------------------------|
| How to run it      | the matching story in [`HOWTO.md`](HOWTO.md) — prerequisites, steps, the knobs that matter, the trap to avoid             |
| Why it is this way | its `E`/`U` row in the scenario's `EXPERIMENTS` log — the verdict *and* the measurements behind it                        |
| Reference          | its row in [`PIPELINES.md`](PIPELINES.md) — operation family, cost, licence, status, key knob, and its HOWTO story number |
| In the canvas      | every workflow carries a `MarkdownNote` panel: the recipe plus links to the story and the `EXPERIMENTS` row               |

---

## Reference

| doc                                                                                                                                                                                                            | what it is                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| [`PIPELINES.md`](PIPELINES.md)                                                                                                                                                                                 | the capability index — every flow by operation × subject × domain, plus the taxonomy and what is still open |
| [`AGENTS.md`](AGENTS.md)                                                                                                                                                                                       | repo layout, conventions, vocabulary, doc map — for working *on* the repo rather than with it               |
| [`HOWTO.md`](HOWTO.md)                                                                                                                                                                                         | the user stories (this page's "how")                                                                        |
| 2D scenario:<br>[`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md)<br>[`2d/PROTOCOL.md`](2d/PROTOCOL.md)<br>[`2d/ROADMAP-2D.md`](2d/ROADMAP-2D.md)<br>[`2d/AUDIT-tooling-2026-09.md`](2d/AUDIT-tooling-2026-09.md) | run log · canonical asset set and rules · roadmap and backlog · tooling audit                               |
| 3D scenario:<br>[`3d/README.md`](3d/README.md)<br>[`3d/EXPERIMENTS.md`](3d/EXPERIMENTS.md)<br>[`3d/pipeline-design.md`](3d/pipeline-design.md)                                                                 | scenario index · run log · architecture                                                                     |
| Animation scenario:<br>[`animation/README.md`](animation/README.md)<br>[`animation/EXPERIMENTS.md`](animation/EXPERIMENTS.md)<br>[`animation/motion-sourcing.md`](animation/motion-sourcing.md) | scenario index · run log · where motion comes from |
| Video scenario:<br>[`video/README.md`](video/README.md)<br>[`video/EXPERIMENTS.md`](video/EXPERIMENTS.md) | scenario index · run log and deferred video backlog |
| Audio scenario:<br>[`audio/README.md`](audio/README.md)<br>[`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md) | scenario index · run log (ACE-Step 1.5, E1) |
| [`comfyui/README.md`](comfyui/README.md)                                                                                                                                                                       | node gotchas (high-density)                                                                                 |
| [`comfyui/linux-setup.md`](comfyui/linux-setup.md)                                                                                                                                                             | install / restore a machine, remote access, topology                                                        |

### Not for end users

Superseded routes and headless/deterministic variants of a flow. Reach for these when you are **automating** a pipeline or reproducing an older result — not as a first choice.

| entry | what it is |
| --- | --- |
| `scripts/pbr_set.py`, `scripts/marigold_pbr.py` | headless equivalent of `pbr-material.json`: same model set from one command, for CI or when no graph is wanted |
| `2d/workflows/pbr-from-texture.json` | the old QFX-only material route — **its metallic is inverted** (E12b), which is what Marigold replaced |

**Licence posture:** the **2D** stack is Apache-2.0/BSD-clean except `insightface` (InstantID/PuLID, non-commercial research) and the Retro Diffusion pixel-art models (non-commercial); Kontext and `4x-UltraSharp` are non-commercial but superseded. The **3D** stack is not clean: Hy3D runs under the **Tencent Hunyuan 3D Community License**, which excludes the **EU, UK and South Korea** and needs a licence above 1M monthly users (UniRig is MIT). See the [audit](2d/AUDIT-tooling-2026-09.md) and the `licence` column in [`PIPELINES.md`](PIPELINES.md).
