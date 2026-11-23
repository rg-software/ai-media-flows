# HOW TO: user stories

"I want to…" table in `README.md` tells you **which flow** fits a job. This file tells you **what to actually do**: prerequisites, steps, the knobs that matter, the trap to avoid, and what a good result looks like. Each story links the flows it uses and points at the deeper doc for the *why*.

---

## How to run flows

- **Server:** ComfyUI at [comfy.rt247a.ddns.me](https://comfy.rt247a.ddns.me) - ask the operator for the token.
- **Flows:** the `.json` graphs in `2d/workflows/`, `3d/workflows/`, `video/workflows/` and `animation/workflows/` - the folder follows the artefact (see the note in `README.md`).
- **Inputs:** any file a flow should read goes in the box's `input/` dir - root files are what the `LoadImage` dropdown lists, so keep UI-tested references there.
- **The Chinese negative prompt is standard.** Every Wan flow ships the same Chinese quality-negative block, verbatim from the official templates - the model was trained against it, and it works. Leave it as-is and edit only the **positive** (English); translating the negative is not recommended.
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

| If you need                         | Run                                                        | Value point                       | Notes                                                                                                                                                           |
| ----------------------------------- | ---------------------------------------------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Photoreal humans, portraits         | `sdxl-base-art.json` (RealVisXL, 1024²)                    | cfg 7 / 20 steps                  | Measured default; realisticVisionV60B1 as photoreal alt (both SDXL; chilloutmix is SD1.5-only with no base flow here); tolerable to ~1.5 MP, mushy at 2.1 (E19) |
| General high-quality illustration   | `sdxl-base-art.json` (juggernautXL, dreamshaper; 1024²)    | Vendor presets                    | Vendor pages carry sampler/steps/CFG presets                                                                                                                    |
| Anime, stylized                     | `sdxl-base-art.json` (ponyV6, AnythingXL, protogen; 1024²) | Per-model presets                 | Pick by look on vendor preview grids                                                                                                                            |
| Modern photographic, clean licence  | `z-image-turbo.json` (1024² *)                             | 8 steps, ~25 s                    | Apache-2.0; photoreal lean, add style words for painted; treat canvas limits as SDXL until swept                                                                |
| Modern photographic, fast iteration | `flux-schnell.json` (1024²)                                | 4 steps Euler/simple, no guidance | Apache-2.0; ~15 s; bust-leaning framing, prompt harder; off-canvas unmeasured                                                                                   |
| Legible rendered text               | `qwen-image-base.json` (1328²)                             | 20 steps, cfg 2.5, shift 3.1      | Posters, signs, UI; full multi-line text verified (E36); higher canvases unmeasured here                                                                        |
| Small output (icons, props)         | Any of the above, then downscale                           | —                                 | Never generate small — detail comes from the large canvas                                                                                                       |
| Large output (past ~2 MP)           | Generate ~1 MP, upscale (S10) or outpaint in tiles (S5)    | —                                 | 1024² SDXL/schnell, 1328² Qwen; past 2 MP the priors smear                                                                                                      |

- *Knobs:* value points live in the table; two rules travel — change one knob at a time (sweep into labeled grids), and guidance is not a quality dial on distilled models.
- *Expect:* 1024² SDXL/schnell, 1328² Qwen. Never generate base art below ~0.75 MP — small latents make mush no upscaler honestly restores. For a **solo full-body** character, say so explicitly — all base models lean bust or sheet without it.

### S2. Control composition from an existing image

- *When:* you have a reference whose **geometry** you must keep, but whose content/style should become something else - theme re-skins of a fixed layout, art-direction reroutes, style transfer with geometry held, game-screenshot ideation. *Wrong tool for:* adding or removing a detail in an otherwise-fine image (S5), tiling textures (S9), fresh content with no reference (S1). Pose from a reference pose is its own story (S16).
- *Steps:* `2d/workflows/controlnet-union.json` - load the reference into the single `LoadImage`; flip the If/Else switch (false = canny, true = depth), and set `SetUnionControlNetType` to the matching mode.

| Constraint          | Type string                                          | Keeps                                                                                                                                                                    |
| ------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Composition (edges) | `canny/`<br>`lineart/`<br>`anime_lineart/`<br>`mlsd` | Layout of things: rooflines, doorways, horizons, silhouettes                                                                                                             |
| Shape (volume)      | `depth`                                              | Spatial arrangement: mass, foreground/background, object placement - surfaces re-imagine freely; measured alongside canny in U6b (re-imagines the mass, keeps placement) |

- *One constraint per generation:* the flow applies a single mode (`canny` **or** `depth` - never both; combining them is unmeasured here). The mode is the decision: pick by what must survive. Structure also beats prompt nouns - the "gothic mansion" prompt on the cottage reference produced a cottage-shaped mansion.
- *Knobs:* `strength` - 0.8 measured as the balance point (holds structure, frees style); 0.9+ slavishly follows edges, 0.7 lets the composition loosen toward the prompt. Lower `denoise`-style integration does not apply here: this flow generates a fresh image guided by the control, it does not edit the original pixels.

### S3. Cut an object out, or mask it by description

- *When:* you need a transparent PNG, or a mask to feed an edit. The two flows differ in *who identifies the target*: SAM3 is language-driven - you name the thing ("the roof", "the second knight"), so it works in multi-subject scenes and on scene parts; BiRefNet is salience-driven - no prompt, it cuts the single most salient subject, and in a two-subject scene it is a coin flip. Polarity differs too: SAM3 masks white on the named target (inpaint convention), BiRefNet white on the subject (alpha convention) - invert when the consumer disagrees.
- *Steps:* **by description** (recommended): `2d/workflows/sam3-segment.json` — type "the knight in silver armor" and get an outline-accurate mask, even in a two-subject scene. **By subject isolation:** `2d/workflows/remove-bg.json` (BiRefNet).
- *Trap:* MASK is **1 = transparent/selected**, and `RemoveBackground` returns 1 on the *foreground* — insert `InvertMask` or you get a perfectly inverted cutout.

### S4. Get a depth map

- *When:* you want a depth map to drive a depth ControlNet, or to fake parallax or depth-of-field in an engine.
- *What it is not:* depth here is **relative** (near = light), with no absolute scale, so it is **not** a height or displacement map. An engine can use it for a parallax look, but you must curve and scale it first, and it stays approximate.
- *Steps:* `2d/workflows/depth-normal.json` (DepthAnythingV2).
- *Expect:* near = light, greyscale and low-frequency.

### S5. Edit a picture: remove, replace, extend

- *When:* fix or change part of an existing image; make the canvas bigger.
- *I want to remove or replace something* -> `2d/workflows/inpaint.json`. Mask the area - draw on the image itself (`LoadImage` -> right-click -> **Open in MaskEditor**) or use a file-based mask. The mask passes a `GrowMaskWithBlur` shipped at **0/0 = hard**; for object edits raise **expand first** (8-32 px - covers paint-line imprecision, prevents ghost remnants of the removed thing), **then blur_radius** (2-8 px - blends the seam).
- *I want a bigger canvas* -> `2d/workflows/outpaint-px.json`. Set the four **`outpaint_*_px` INT nodes** - pixels to add per side (0 = leave that side); the in-graph math converts them to factors (`f = 1 + N/W`, per side) and the canvas follows automatically. **Keep the target size `<= ~1.5 MP` and canvas sides multiples of 64** - these knobs are the budget control. The new area is **invented** (expect new content); the original region comes back untouched (E41).
- *The source is big, or I only want to extend one edge* -> `2d/workflows/outpaint-fragment.json`: the same px knobs plus a **painted mask on the edge strip** (MaskEditor). The mask localizes the sampling and marks the strip that becomes the **transition** into the new area - it is repainted by design, so keep it thin. The flow ships `context_from_mask_extend_factor` **4.0**. **Never pad the canvas with black yourself** - base SDXL will not paint over black padding (E41); the pack's own padding is edge replication and works.
- *I want to direct the edit in words* -> `2d/workflows/qwen-edit-gguf.json` ("relight this", "change the material") - instruction-style, no mask needed. The encoder node accepts **up to three images** (`image1`/`image2`/`image3` - the model's cross-image editing: "put the person from image 2 into image 1"), but the flow ships and we measured only the **single-image** case. Source dimensions are **not** preserved. If relight is not needed, you can set the relight LoRA strength to 0.
- *Prompt rule (applies to both edit flows):* describe **what the sampler sees**, not the global scene. Inpaint = the scene around the hole. Outpaint = the **seam neighborhood only** - "forest with a hut" + a seam next to the hut grows a second hut (E41 trap 3): name the continuation ("dense forest, tall trees"), never subjects that already exist in the picture - they travel through the context pixels the crop carries.

### S6. Compose a scene from parts

- *When:* you want **more than one thing in a still picture** - a background, one or more characters, props - instead of the isolated assets the other stories produce. The isolated form is deliberate; this is the image-recombination stage.
- *Steps:*
	- **isolate each element**: cut a character or prop out of a picture (`2d/workflows/sam3-segment.json` for a text-prompted mask, `2d/workflows/remove-bg.json` for a clean cutout - S3); identity comes from the element you cut, so use the character asset you like (S7);
	- **place them** with `scripts/compose_scene.py` (It handles **several items** and drops `<name>_base/_mask` pairs for the next step) or a graphical editor - pixel-exact scale, feet position and overlap, so depth ordering is a decision. In case of an editor, use layers and alpha channels to produce a mask;
	- **blend the light** with `2d/workflows/compose-harmonize.json` - this is where pasted parts become one picture;
	- run the harmonize pass to produce the composed still; it is recommended to do one pass per object, not all objects at once.
- *Knobs:*
	- **`denoise` in the harmonize pass** - **0.45 = integrate** (keeps the placed identity) / **0.75 = replace** (more coherent, less "them"). The same identity rule as S5;
	- **the plate** - any background asset or photo; the character's own background comes along if you do not cut her out;
	- **the cast variant**: when you want the *model* to draw several subjects together rather than placing cutouts, `2d/workflows/regional-prompting.json`. Measured: **a single prompt containing two subjects drops one entirely** (E15) - so the flow partitions the canvas: the scene prompt stays global, and each subject gets its own prompt fragment over its own area (`ConditioningSetAreaPercentage` half-canvas slabs + `ConditioningCombine`). The regions partition *whose subject-prompt governs where* (a coarse placement bias only); pose, scale and subject relations stay the model's choice.
- *Measured:* the scripted placement and the harmonize pass are E10 (PASS); regional prompting is E15; the two-subject example is `assets/2d/scene_two_subjects_regional.png` and a placed prop is `assets/2d/prop_chest_cutout.png`.
- *The honest gap - a prop **held**.* Placement of an object *in a scene* is solved above; an object *in a hand* was measured on VACE and came back **MEH** (it does not place). The workable routes today are a local edit at the hand (`2d/workflows/inpaint.json`, S5) or an instruction edit that moves a subject into a scene (`2d/workflows/qwen-edit-gguf.json`, multi-image, E14c).
- *More:* [`2d/README.md`](2d/README.md), E10 in [`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md), and E13b/E13c in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

### S7. Keep a character consistent across images

- *When:* the same character must appear in several shots.
- *Choose by what "consistent" means:*

| need                                                          | flow                                                                                             | reality                                                                                                                                                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| same **design** (outfit, hair, silhouette) in any composition | `qwen-edit-gguf.json`                                                                            | Apache-2.0, faithful, but the *face* is not embedding-identical                                                                                                                                       |
| same **face**, close-up                                       | `instantid-character.json`                                                                       | strongest face match; the shipped kps mirror the reference's framing (bust) - wire `image_kps` to a full-body donor with a detectable face (E14b addendum)                                            |
| same **face**, free composition                               | `pulid-identity.json`                                                                            | full-body works; weaker face score (still needs a face)                                                                                                                                               |
| same **character**, new **pose** or camera angle              | `2d/workflows/pose-skeleton.json` (skeleton-driven) · `qwen-edit-gguf.json` (instruction-driven) | the skeleton flow (see also **S16**) holds a **coarse stance** (arms out / wide) but does not bind limb angles; an instruction is still the way to a *specific* pose, and kept pose *and* design best |

- Prompt-level consistency lands around 0.14-0.19, so expect an embedding-identical face only from InstantID or PuLID.
- *New pose or camera angle?* Pose is a separate carrier from identity, so don't expect the consistency recipes above to move it. The route that works is **asking in words**: `qwen-edit-gguf.json` with "the same knight in the same armour and colours, arms spread wide" changed the pose *and* held the design closest. An instruction also handles **camera angles**, which a 2D skeleton cannot (no yaw); the 3D path is the other way to get a chosen angle.
- *What the skeleton flow actually buys:* with its shipped `strength` **1.5** and `end_percent` **0.5** it imposes a **silhouette**. Measured: a "T-pose, arms outstretched" skeleton beat a prompt that explicitly asked for the opposite and still rendered cleanly. So — coarse stance (arms out, wide, tall) → this flow; a specific pose → the instruction. `cfg` makes no difference (4.0 = 7.0), and keep IPAdapter at **0.15** so it does not fight the cue.
- If you have a photo/drawing rather than a stick figure, then you'll need to extract the skeleton first (`pose-extract.json`) before invoking the skeleton flow.
- *Turning an object to a different angle?* Don't reach for a ControlNet first: rotate the sprite in your editor, then run it through a second pass at **denoise ≈ 0.5-0.65** with a plain description of what it is.
- *Tooling caveat:* the OpenPose detector finds **no person in most of our stylised renders** (13 of 15 in one batch), so a pose can be *imposed* but not *measured* automatically — `extract` and `measure` are for real photograph.
- *Warning:* `instantid-character.json` and `pulid-identity.json` depend on **insightface**, licensed for **non-commercial research** — don't ship their output. `qwen-edit-gguf.json` is Apache-2.0.

### S8. Transfer a style or a reference look

- *When:* you want an image to adopt the palette, atmosphere or medium of a reference.
- *Steps:* use **`2d/workflows/qwen-edit-gguf.json`** with the reference as `image2` — the multi-image reference mechanism does style transfer. The older `2d/workflows/ipadapter-style.json` (IPAdapter) still works.
- *Knobs:* for IPAdapter, `weight` — 0.0–0.2 is a style hint, 0.3–0.5 blends, and **≥0.6 the reference overrides the prompt** entirely.
- *Trap:* this transfers a **look**, not a layout. If you need "keep this composition", that is ControlNet territory (S2), not style transfer.

### S9. Sprites and atlases

- *When:* you need game-ready sprites, animation frames, or packed sheets - in **any style** (pixel, anime, painted, realistic).
- *Produce the frames in your chosen style:*
	- **pixel art** -> its own story, **S31** below;
	- **any other style** -> generate each frame (S1), or restyle existing art (S8);
- *Animate a sprite across a few poses:* get one skeleton per pose with `2d/workflows/pose-extract.json` (**S16**, one photo per pose), render each with `2d/workflows/pose-skeleton.json`, then pack the frames with `scripts/atlas.py`. **Keep the IPAdapter at 0.15** - that is what holds the character's design while the pose changes; higher weights freeze the reference's own stance. **Measured limits:** poses that differ by **~40 degrees or more** read as distinct frames, but **10-30 degree steps render as the same pose**, so a 3-4 frame idle / attack / ready works (while **walk cycle does not**).
- *Generate animation frames from a rigged 3D model:* use a rigged GLB with named animation clips (see KayKit Adventurers Knight as an example). The renderer is plain `bpy`; it needs Python 3.11 and the opt-in `pose-render` uv extra. From the repo root, set `UV_PROJECT_ENVIRONMENT` to a separate env path, then run
  
  ```shell
  uv run --extra pose-render --python 3.11
    scripts/render_glb_poses.py --glb <model.glb> --out
    <ComfyUI>/input/poses --clip Idle_Rig:0.5 --clip
    1H_Melee_Attack_Chop_Rig:0.15,0.35,0.55,0.75 --yaws
    0,45,90,135,180 --gear 1H_Sword,Round_Shield
  ```

  Repeat `--clip` for another animation; `--gear` is optional, and names the weapons to keep. One fixed camera keeps scale constant across the set.
	- Style each render with your chosen style pass (for pixel art: `2d/workflows/pixel-art-convert.json` with one shared palette - **S31**; do **not** use `pixel-art-restyle` for clean renders: its redraw changes the design/pose);
	- Restore transparency: run `uv run python scripts/restore_alpha.py --source <render.png> --sprite <converted.png> --out <sprite-rgba.png>`. The helper resizes the original alpha with nearest-neighbour; pack the RGBA results with `scripts/atlas.py`.
	- For a short animation, use several fractions from one clip (e.g. `0.15,0.35,0.55,0.75`) so it samples the motion; flatten lighting to reduce palette flicker. At 128 px subtle motions can be hard to read.
- *Pack or slice a sheet:* `scripts/atlas.py`. Use with `pack --out sheet.png --columns 2 --cell 64x64 a.png b.png ...` to lay images out row-major (optional `--padding` gap between cells).

### S10. Finish: upscale and restore

- *When:* you need more resolution, or a soft/small face cleaned up.
- *Steps:* `2d/workflows/upscale-seedvr2.json` (Apache-2.0). Set `resolution` to the **short edge**; set it equal to the image size to **restore** instead of upscaling (including face restore).
- *See the result:* check the slider in the `ImageCompare` node; the `SaveImage` output is the deliverable.
- *Knobs:* `batch_size` must be 4n+1. For images, keep it 1. SeedVR2 *reconstructs* (more detail, more drift); `upscale.json`'s GAN is faithful (it invents nothing). You can use SeedVR2 with 1x scale to _reconstruct_ a damaged image.
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
- *Steps:* `3d/workflows/hy3d-full-workflow.json` (shape → texture → bake) or `hy3d-multiview-workflow.json`; rig with `3d/workflows/unirig-humanoid-workflow.json`. The exported GLB can be **re-materialed with S11** (`pbr-material.json` derives the PBR set from the flow's atlas; `make_gltf_material.py --mesh` replaces the GLB's default material with it).
- *Multiple angles:* `hy3d-multiview-workflow.json` wants front/left/right/back. four clean views are a hard requirement of that flow. `2d/workflows/sv3d-turnaround.json` can make them from a single image — but its views must be **background-removed first** and the orbit convention checked.
- *View:* the run ends in a viewer node — `Preview3D` on both Hy3D exports, `UniRigPreviewRiggedMesh` on the rig. The viewers read from `output/`, where the GLB/FBX already land.
- *Textures:* the ComfyUI 3D viewer **does show GLB textures** since core v0.46 / frontend 1.59.6. Each Hy3D flow also ends in a **Textured turntable**, which renders the textured mesh to a 12-frame 360° image batch for user review.
- *PBR:* the generated texture is **base colour only** — one atlas, a constant roughness, no PBR maps, fully metallic surface. Load base colour atlas into `2d/workflows/pbr-material.json` to get PBR textures, then pack it for the target with `scripts/make_gltf_material.py` (glTF) or `scripts/pack_pbr_material.py` (Unity).
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
- *Trap:* image nodes read **only** from `input/` - a file sitting in `output/` cannot be loaded, so upload it before running a flow that needs it. And the GUI dropdown lists **only the `input/` root**: a widget pointing at a subfolder file (`2d/name.png`) is valid via the API but renders as *missing input* in the editor, and the file never appears in the dropdown - keep every GUI-referenced file in the input root (subfolders are for script-only references). With many inputs, upload the folder once and read it with the `LoadImagesFromFolderKJ` node rather than one file at a time. And only those three dirs are served: a file anywhere else on the box (e.g. a result written into the repo) cannot be fetched at all, by any route short of SSH. That SSH route is worth having when you have no token or the file is large: `comfyui/linux-setup.md` records the two hops (box -> NAS -> Windows) and the `-O` flag the second one needs, since the Synology's sshd runs no SFTP subsystem.
- *More:* `scripts/comfy_io.py --help`.

### S15. Animate a character from a driving video

- *When:* you have a still character and a clip whose motion you want on it. The motion is transferred directly — no pose extraction and no skeleton step.
- *Steps:*
	- put your character image and your driving clip in `input/`;
	- open `video/workflows/wan-animate-motion.json` and set the **reference image** (`LoadImage`) and the **driving video** (`LoadVideo`);
	- describe **scene, background and camera** in the positive prompt's *Background description* part (the box labeled "Character Description / Background description") — *not* the motion, which comes from the video; keep the Character part pointing at the reference image, and leave the second positive box (the pose-branch prompt) at its shipped generic text.
	- run. Shipped sample generates in ~1.5 min.
- *Knobs:*
	- `length` — frames (4n+1). **It is the FIRST N frames of the clip**: a longer clip is cut off at N, a shorter one repeats its last frame. In the shipped sample, the default 33 is about 1.4 s of the footage;
	- the output plays at **the clip's own frame rate** (`CreateVideo.fps` is wired from the video), so a 30 fps clip writes a 30 fps file. The motion is frame-indexed, so a different value is a slow-motion or speed-up;
	- `pose_strength` — how literally the driving motion is copied;
	- `reference_image_strength` — identity vs motion trade;
	- **size** — edit only the two **`INT Constant` nodes** (multiples of 16): they drive all three canvas declarations — both `ImageScale` nodes and `WanAnimate2ToVideo`'s width/height — so one edit moves the whole canvas. The sources can be any size or aspect: the scale nodes normalize them (center-cropped to the canvas aspect, not stretched). The shipped 480×848 frames the character; matching a landscape clip drops the cost cap (cost ∝ pixels) and re-frames the character to the footage's aspect. The WebP/WebM save pair is migrated to `CreateVideo` → `SaveVideo` (preview is the player on those nodes).
	- the prompt's camera wording *is* the viewpoint control: the output camera is decoupled from the driving video.
- *Notes:* its negative prompt (node 6) is the family's standard Chinese block and this flow samples at **cfg 1.0**, where the negative branch has zero weight - so it is inert here, and the Chinese is kept only for consistency with S28/S29 (where cfg is 6 and it *does* matter).
- *Trap:* the output size comes from the **driving video**, snapped to a multiple of 16 — not from the node's defaults. **Don't swap the model for a GGUF quant.** Those same weights quantised that way make the flow silently ignore your driving video, while the reference image keeps working - so if the character never moves, that is why. The workflow's note has the explanation.
- *Doing it by hand:* generate a segment, then add a `LoadImage` of its **last frame** wired to `continue_motion` and set `video_frame_offset` to **last pose + 1**. The node pins the frame you pass at pose `offset - 1` and generates `length` frames from there, so for 33-frame segments the offsets are 0, 33, **65**, 97; join the pieces with `A + B[trim_image:]` (that node output says how many frames overlap). It closes the join **and holds the camera** across the cut.
- *More:* [`video/README.md`](video/README.md), and E1/E2/E3/E10/E12/E14 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).
- *Videos longer than ~1.5 sec:* the flow generates the first `length` frames and stops, so run **`uv run python scripts/wan_segment.py <clip> --ref <image> --out <result.mp4>`** - it probes the clip, works out how many segments it needs, runs each one continuing from the previous segment's last frame, and stitches them into one file at the clip's own fps. It is API-only, so it runs against the remote server from anywhere.

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
	- **subject selection** - the tracking prompt (`SAM3_VideoTrack.conditioning`) and the detector's `class_name` select *what to track*; they have no effect on the mesh's appearance. `person` is minimal-correct for a single subject; multi-person clips need a distinguishing phrase plus the boxes. `class_name` is a **closed COCO-class dropdown** (subjects outside it: skip the boxes, use the prompt or an initial mask); `BuildPoseFile.track_index` (-1 = all tracks, ≥ 0 = one) picks which tracked person is exported;
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
	- open `video/workflows/frame-interpolate.json` and set the **clip** (`LoadVideo`);
	- set the **factor** on the `INT` constant node. It is wired to both the interpolator and the output frame rate, so the clip keeps its speed;
	- run. It is the cheapest flow here: doubling a 5 s 720x1280 clip takes **15-25 s**.
- *Knobs:*
	- the **factor** - `multiplier` is the *total* factor, not the number inserted: 121 frames at x2 gives 241, at x4 gives 481;
	- the **model** - RIFE (21.6 MB, MIT) is the default; FILM (65.7 MB, Apache-2.0) measured a **tie on quality for ~1.8x the time**;
	- **smooth slow motion instead of same speed (added frames slow down playback):** edit Math Expression node's content from `a * b` to `a`, which writes the source frame rate against the extra frames.
- *Traps:* the inserted frame averages the motion blur of its two neighbours, so a fast limb goes slightly soft - inherent, since neither input holds that exposure. Interpolation cannot invent detail the source never had, and it will not fix a choppy *performance* - only the sampling of one.
- *More:* [`video/README.md`](video/README.md), and E17/E17b in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).


### S19. Generate music from a text prompt

- *When:* you want a music track from a description, with no source audio - the instrumental default and the fastest take. Singing is possible butfragile - for reliable vocals use S23.
- *Steps:*
	- open `audio/workflows/ace-step.json`.
	- describe the music in **`tags`** (genre, mood, instrumentation, production). For an instrumental leave **`lyrics`** empty; to write a song, put the words in with `[Verse]` / `[Chorus]` markers;
	- set **`duration`** (seconds) and, if you care, `bpm`, `keyscale`, `language`;
	- **for a song, write full sections and budget 2+ minutes** - measured, the vocals need room (see the trap);
	- run. A 2-minute track takes about **25 s**, including loading the model.
- *Knobs:* the two constants at the left are wired to **both** of their consumers on purpose - **seed** goes to the text encoder *and* the sampler, and **duration** goes to the encoder *and* the latent's `seconds`.
- *Trap:* **the lyric has to be song-sized, and song-shaped** (E6/E7). The model sings roughly **60% of the words it is given**, i.e. **1.5-3 words per second** - a 120 s track wants **250-350 words**, and a 40-word poem comes back instrumental however good the tags are (same tags: 209 sung words at 344 input, 1 at 40). A bare `[Verse]` marker changes nothing on its own; **verse/chorus/bridge with a repeated chorus** took one such poem from 1 sung word to **86 (74% precision)**, using only the poem's own words - its strongest line is a ready-made chorus. **Repeat a short lyric into song form until the word count matches the duration**, or accept an instrumental.
- *Trap:* **a short track will not sing.** Measured: at 30 s the flow produced **no vocal at all**, even with a full song's lyric, and at 120 s the same lyric sang (85% of the sung words came from the input). The planner builds a whole-song blueprint and the duration truncates it, so what survives short is the *instrumental intro*; a 3-line lyric also under-fills a long track. Write sections, and give it 2+ minutes.
- *Note:* `KSampler`'s **negative input looks like a mistake and is not** - it is the positive through `ConditioningZeroOut` (an empty negative), because ACE-Step's prompt has no "undesired" concept and the sampler needs a negative slot; at cfg 1.0 it is unused anyway.
- *Note on the lyric's markup:* `[Verse]` / `[Chorus]` / `[Bridge]` are **a convention the model learned, not a keyword list** - nothing parses them, and the templates themselves also use free-form ones like `[Intro - Rhodes piano and brushed drums]` or `[drum fill]`. Use the standard names for structure, a dash plus a phrase for hints; an invented name will not error. See [`audio/README.md`](audio/README.md).
- *More:* [`audio/README.md`](audio/README.md), and E1 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S20. Match the style of a reference track

- *When:* you have a track whose feel you want more of - a bed, a theme, more of the same palette - rather than something new.
- *Steps:*
	- open `audio/workflows/ace-step-style.json`; set the **target length** on the `FloatConstant` (it feeds the trim and the conditioning, so they agree);
	- put the style you *want* in **`tags`** - measured (E5), tags are a weak **nudge only**: even at high denoise the take stays close to the reference;
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
	- open `audio/workflows/yue2-cover.json` and set your reference via the **`LoadAudio`** node;
	- write the **style** to change it into (the shipped `STYLE` is industrial rock) and the **lyrics** you want - the reference's *melody* is kept, its *words* are not;
	- run. A 30 s reference covers in about **65 s**.
- *Knobs:* `max_duration` is a **ceiling, not a requested length** - you cannot pick the cover's size. The model stops when its generated song ends, so the length follows the ABC's music: E22 measured a 30 s instrumental at cap 30 coming out 27.7 s with a 188-word lyric and 29.5 s with none. A longer source helps only by giving SheetSage2 more melody to transcribe. `mode` is `melody` for a cover (`full` writes a new song instead). **Like S23, there is no voice list** - the cover's voice is the model's own reading of the style prompt + seed; record both to keep a voice you like.
- *Traps:* **you cannot add lyrics to an instrumental melody.** The lyrics do reach the model, but an instrumental's transcribed ABC has an all-rests `Vocal` line, so the words have nothing to follow - E22's added 188-word lyric was not sung. For new words on a tune, pick a source that is already sung. **The licence:** YuE 2's weights are `cc-by-nc-4.0` (**non-commercial**), so the output is research-only.

### S23. Generate a song that actually sings

- *When:* you want a **song** - lyrics actually sung, clearly - and the 8-step turbo is not delivering. There are **two MIT arms**, and E23 kept both because they split by *style*.
- *Steps:*
	- **lyric-full on clear-lead styles**: `audio/workflows/ace-step-xl-sft.json` (ACE-Step 1.5 XL, MIT) - 50 steps / cfg 7;
	- **fast and light, and on shouty styles**: `audio/workflows/ace-step-v1-35b.json` (ACE-Step v1 3.5B, MIT) - `lyrics_strength` 1.0;
	- open the arm's JSON, write the **style** (`tags`) and the **lyrics**, run.
- *Knobs:* the **style** names the voice (see traps). **There is no voice list** - the singing voice is emergent from the style prompt + seed, so iterate until you get one you like and then record both (the pair reproduces the take exactly). XL adds `steps`/`cfg` (50 / 7 as shipped), the text encoder's `cfg_scale`, `ModelSamplingAuraFlow` shift 3, and seed + duration (each wired to two consumers). v1 adds **`lyrics_strength`** - the knob that decides whether the lyric is sung, and it only works in a window (**1.0-2.0** sings it, **0.5** sings its own words, **4.0** collapses) - plus `steps`/`cfg` 50 / 5 and the `ModelSamplingSD3` shift 5 + Reinhard-tonemap recipe the 1.5 line dropped.
- *Traps:* **the style is the vocal's on/off switch, so name the voice and keep it consistent.** A style asking for a *clear, strong, close-mic lead* returned 124 of 188 lyric words sung cleanly, while the same model on a style asking for a *shouted male lead* came back **whispered** - and the turbo, on that clear-lead style, produced **no vocal at all** (E13/E13b). **Why two arms (E23):** held to one clear-lead style, XL sang 173 of 188 (92% coverage) against v1's 149 (79%), so XL is the lyric-full arm there - but v1 sang 180 words on the *industrial* style, where XL whispers. And **`lyrics_strength` is non-monotone**: turning it *up* is not "obey the lyric harder", it breaks the vocal. Like every model here the takes land near full scale, so normalise.
- *More:* [`audio/README.md`](audio/README.md), and E13/E13b/E13c/E23 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S24. Repair a region of a track (repaint)

- *When:* a take is right except for **one span** - a mispronounced word, a weak section, a deliberately deleted passage - and you want that span regenerated **without touching the rest**. This is the audio analogue of inpainting.
- *Steps:*
	- open `audio/workflows/ace-step-latent-repaint.json`, and put the source audio on `LoadAudio` with its **length in seconds** on the `FloatConstant` (these two must agree);
	- set the **span to repair** - just two numbers, `repair from (s)` and `repair to (s)`. The flow converts them to the latent frames the mask works: repairing 55-61 s of a 120 s take is simply `55` and `61`;
	- set `tags` and `lyrics` to the **take's own whole prompt** - its style and its full lyric (like an image inpaint prompts the whole picture and masks the region);
	- run; a 120 s take costs about **15 s**.
- *Knobs:* **`repair from` / `repair to`** (seconds - the span), **`tags` + `lyrics`** (the big one - see traps), `seed`, and `denoise` (**leave at 1.0**; lower values changed the band *more*, not less).
- *Traps:* **match the conditioning before touching the mask or the sampler.** The first run came back with an audible seam and a style change - and both were the *prompt*: the flow had inherited a generic `tags` line with empty lyrics, so the band was regenerated as different music. **Give it the take's whole prompt**. E19b's working run used the take's own style and its full 188-word lyric.
- *More:* [`audio/README.md`](audio/README.md), and E19/E19b in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S26. Generate narration or a voice-over from text

- *When:* you want a **spoken line** - narration, a character's voice-over, a radio bark - rather than music, and you want to choose (or clone) the voice.
- *Steps:*
	- open `audio/workflows/chatterbox-narration.json` and put the script in **`text`** - punctuation and paragraph breaks are the pacing controls, because there is no speech markup syntax;
	- optionally wire a `LoadAudio` holding **5-10 s of a voice** to **`audio_prompt`** to clone it; left unconnected, you get the model's own narrator;
	- run. A line takes seconds once the model is loaded;
	- **for paralinguistic tags** (`[laugh]`, `[sigh]`, ...) use `audio/workflows/chatterbox-narration-turbo.json` instead - the **Turbo** model *performs* them, where this one reads them aloud (E27/E28);
	- **for non-English VO: measured closed in this pack** (E40). The demoted variant lives in `workflows/scratch/`; usable at most for a stylised foreign-voice character.
- *Knobs:* **`exaggeration`** (0.25-2.0) and **`cfg_weight`** (0.2-1.0) are the expressiveness pair - they are what makes a line read as a delivery rather than a read-out, and that is **measured** (E39): exaggeration moves the take audibly (5.0 -> 7.4 s and +6 dB RMS across the range) but **2.0 repeats the closing line**, so keep it **<= 1.0**; cfg_weight paces the line (0.5 -> 1.0 cut ~0.8 s at the same seed). `temperature` is variation and `seed` is the take.
- *Traps:* the output is **24 kHz mono** where every other flow here is 48 kHz stereo, so treat it as a **VO element to place in a mix**, not a bed - and it lands near full scale, so normalise. Unlike singing, **the words are worth checking with a transcript**: for speech, ASR is a real presence test (E25). And **paralinguistic tags are not this node's**: `[laugh]`, `[sigh]` and friends are read aloud as words (E27) - they belong to the **Turbo** flow (`audio/workflows/chatterbox-narration-turbo.json`, a separate ~1 GB model), not this one - and Turbo's knobs differ (no `exaggeration`/`cfg_weight`) and it lands much quieter (peak about -8 dBFS), so raise it rather than normalise it down.
- *More:* [`audio/README.md`](audio/README.md), and E25/E27/E28 in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S27. Generate a dialogue scene

- *When:* you want a **conversation** - two voices (up to four) trading lines - not a single voice-over, and you want each line as its own file.
- *Steps:*
	- open `audio/workflows/chatterbox-dialogue.json`;
	- put the **two voices** on the `LoadAudio` nodes - `speaker_A_Audio` / `speaker_B_Audio` are **required**, 5-10 s each: your own clips, or a window of a separated vocal stem (a **sung** reference works and gives a distinct voice);
	- write the script in `dialog_text`, one line per `SPEAKER A:` / `SPEAKER B:` label;
	- run: you get the **mixed scene plus each speaker's track**, all on the same timeline (silent where the other talks) - they drop straight onto a game timeline.
- *Knobs:* `exaggeration` / `cfg_weight` / `temperature` / `seed` behave as in S26; optional `speaker_C_Audio` / `speaker_D_Audio` extend the cast to four.
- *Traps:* **the references ARE the voices** - two close clips give two close voices (E26), a sung stem or your own clips give distinct ones (E26b). **No paralinguistic tags here either** - the dialog node runs the *standard* model (verified in the pack source: `ChatterboxTTS.from_pretrained`; the pack has no Turbo dialog node), so by E27 a `[laugh]` is read aloud as a word; for acted tags, generate the line in the S26 Turbo flow instead. And this node needed a one-line pack patch on this box (torchaudio 2.11 routes `save()` to torchcodec); it is recorded in `comfyui/pinned-config.md`. Output is 24 kHz mono VO stems, near full scale - normalise.
- *More:* [`audio/README.md`](audio/README.md), and E26/E26b in [`audio/EXPERIMENTS.md`](audio/EXPERIMENTS.md).

### S28. Animate my own character from a prompt

- *When:* you have a character image you made (a hero, a mascot, a knight) and want a short clip of her *doing something* - but you have no driving clip of a person doing that motion. The prompt says what should happen; the flow keeps **her**. This is the counterpart to S15: S15 copies motion from a clip, this one writes it from words.
- *Steps:*
	- put your character image in `input/` - a **full-body, plain-background** picture (the background travels with her, so a busy photo gives a busy clip);
	- open `video/workflows/wan-vace-reference.json`, set the **image** on the `LoadImage` (node 52) and the **prompt** on the upper `CLIPTextEncode` (node 6). Write the action as one sentence, the way the shipped example does ("*a red-haired sorceress in a blue and gold gown spinning gracefully and casting a fire spell, full body, plain background*"); word-soup prompt engineering ("masterpiece, best quality, ...") makes it worse;
	- run. It is the slowest flow in the repo: 81 frames at 768x768 took **45.5 min** on this box (17.25 GB VRAM). **For a quick test** swap the UNET (node 37) to the 1.3B VACE (`wan2.1_vace_1.3B_fp16`, on the box) - the same job measured **11.3 min** on it (E13b). Start with `length` 81 and steps 20 before you sweep anything.
- *Knobs:*
	- **`length`** (node 55) - **frames**, in steps of 4 (81 = **5.1 s** at the shipped **16 fps**). This is both a time and a VRAM knob: more frames need more GPU memory as well as more compute, so extra wall time alone cannot rescue an out-of-memory run. Only 81 frames at 768x768 has been measured on the 14B (17.25 GB VRAM); longer settings are unmeasured. Lower resolution reduces the memory load; for a quick test, use the measured 1.3B VACE route above;
	- **steps / cfg** (node 3) - 20 / 6.0 ship. The 6-step distil LoRA that S15 uses is named for image-to-video at 480p and is untested here;
	- **the reference image** - the most important choice of all: identity, costume and background all come from it;
	- **shift** (node 54) - 8.0 ships.
- *Measured:* identity holds across the clip on our own `char_heroine.png`, and the prompted fire spell actually appears and grows in her hand ([`video/evidence/E13b-vace-single-strip.png`](video/evidence/E13b-vace-single-strip.png), E13b). **Two defects to plan around:** the hem smears into a painterly swirl in the early frames, and **the last third drifts** - the action takes over and the figure softens - so keep the first ~two thirds if the character is the point.
- *Traps:* never quantise this model to GGUF (the model type lives in its metadata, the same trap as S15's). The weights are a third-party fp8 reupload of the Apache-2.0 model (`wan2.1_vace_14B_fp8_scaled.safetensors`, 17.6 GB); Comfy-Org's own file is the 34.7 GB fp16 - both licence-clean, see [`comfyui/pinned-config.md`](comfyui/pinned-config.md).
- *Also measured in E13b:* co-presence (two reference images, the 1.3B) **PASS** - a recipe in the E13b row rather than a shipped flow; and placing an object in a chosen spot came back MEH on VACE and is answered by S31's Mix mode instead.
- *More:* [`video/README.md`](video/README.md), and E13/E13b in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

### S29. Give a clip a camera you chose

- *When:* you have a good still and want a clip that moves **the way you decide** - a slow push-in, a pan across the scene, an orbit. In the other motion routes the camera is text-driven and **drifts** (E18 is to fix); here the camera is an input.
- *Steps:*
	- put your still in `input/` - clean, well-lit, and composed for the move you want (the still *is* the clip's first frame, the camera departs from it);
	- open `video/workflows/wan-camera-control.json` and set the **image** on the `LoadImage`;
	- set the **trajectory** on the `WanCameraEmbedding` (node 57): `Static`, `Pan Up` / `Pan Down` / `Pan Left` / `Pan Right`, `Zoom In` / `Zoom Out`, `Anti Clockwise (ACW)` / `ClockWise (CW)`;
	- run. This is the **cheapest motion flow in the repo**: 81 frames take **115 s**.
- *Knobs:*
	- **`camera_pose`** - the whole point of the flow. `Static` is the safe default (it holds the framing *still*, which is how you notice the drift is gone); `Pan Left` and `Zoom In` are the demonstrative ones;
	- **width / height / length live on the `WanCameraEmbedding` (node 57), not on the target node** - the embedding *outputs* them and they are linked in, so the node's own canvas widgets are overridden. It ships **512x512**, which is what keeps a portrait start image whole;
	- **want 16:9?** letterbox the start image first - `uv run python scripts/letterbox_16x9.py assets/2d/char_heroine.png` with `--out` pointed at a file under `input/` - then set the embedding's width/height to **832**/**480**. Measured: a portrait still into 16:9 loses its **head**;
	- **steps / cfg** (node 3) - 20 / 6.0 ship;
	- the **start image** - a portrait still into a landscape canvas crops at the edges, and what must survive the pan is the subject.
- *Measured:* all three tested presets do what they say, identity holds, 115 s per cell ([`video/evidence/E18-camera-sheet.png`](video/evidence/E18-camera-sheet.png), E18). Weights: `wan2.1_fun_camera_v1.1_1.3B_bf16` (3.23 GB, Apache-2.0, official Comfy-Org repack).
- *Traps:* the trajectory is a **preset** - a bespoke camera path needs the node's JSON pose input, which this flow does not expose. `Static` looks "broken" on a first glance because almost nothing moves; that is the point (compare S15/S28, where the camera wanders on its own).
- *More:* [`video/README.md`](video/README.md), and E18 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

	- **the orbit specialist**: `2d/workflows/sv3d-turnaround.json` - a **single image** to a 360° orbital video of the subject, no mesh, no text - the turnaround/product-view route. The weights are **non-commercial** (Stability); documented as the multiview source for 3D in S12.

### S30. Turn a generated clip into a VFX flipbook

- *When:* you have a clip of an effect (fire, sparks, an impact, a magic aura) and want it as a **game sprite sheet** the engine can play - not a video file. The clip is the renderer here: there is no skeleton and no retargeting step, which is what makes this route cheap next to the character routes.
- *Steps:*
	- make the clip: an effect still (`2d/workflows/sdxl-base-art.json`, prompt it *isolated on pure black background*) animated with `video/workflows/wan-camera-control.json` at a short `length` (33 frames is plenty) - about 45 s on the 1.3B;
	- pack it: `uv run python scripts/flipbook.py <clip>.webp --frames 8 --cell 128 --out assets/2d/vfx/fire`;
	- read the sheet and the manifest (`<out>_manifest.json`) - the manifest carries the frame rate, cell size, grid and loop mode, which is what an engine importer needs.
- *Knobs:*
	- **`--frames`** - how many source frames to sample. 4 / 8 / 12 all read as the same effect on a flame, so this is a delivery choice, not a quality cliff;
	- **`--window START END`** - the fraction of the clip to sample. A one-shot event spends its first and last second barely moving, so sampling the whole clip gives you a sheet where half the cells look identical;
	- **`--loop`** - `pingpong` (default) is the only ordering that is seamless for *any* source: measured **0.3 px** seam. `cycle` measured a **10.8 px** wrap jump on a drifting clip, so it is only right when the source really is cyclic. `none` is a one-shot;
	- **`--key`** - `none` (additive blending: fire, sparks, energy on black need no alpha at all), `luma` (a black backdrop to real transparency) or `chroma` (any flat colour). **Chroma is not available yet**: an SDXL prompt for a green backdrop was ignored and rendered a knight instead, so there was nothing to key (E21);
	- **`--cell`** - one dimension keeps the source aspect; giving both squashes the effect.
- *Measured:* a 33-frame flame clip at 8 source frames reads as one coherent effect; the backdrop stays dead black (corner luma 14.4-16.0, peak cell-to-cell delta 0.60/255), so both the additive and the luma-keyed arms are clean. Cost: 2x45 s of generation. Evidence: `animation/evidence/E21-flipbook.png`. A shipped example lives in `assets/2d/vfx/` (`fire_column.png` + its manifest, 128 px cells, 14 frames at 12 fps, additive).
- *Traps:* the playback rate is a **delivery** decision, not the clip's - the manifest's `fps` is independent of the source's, and `scripts/atlas.py` cannot make that call because it has no notion of time. And a flipbook is an engine asset, so it belongs in `animation/`, not `video/`.
- *More:* [`animation/README.md`](animation/README.md), and E21 in [`animation/EXPERIMENTS.md`](animation/EXPERIMENTS.md).

### S31. Put our character into footage

- *When:* you have footage of a person in a real scene and want **your character** to play their part - the background, lighting and camera of the footage kept, the person replaced. This is placement: the character lands *inside* real footage, not on a generated backdrop.
- *Steps:*
	- open `video/workflows/wan-animate-mix.json`; set the **driving clip** on the `LoadVideo` and the **reference image** on the `LoadImage` (node 9);
	- the reference should be a **portrait** (face fills the frame) - this is the identity knob, measured in E13c: a full-body reference loses the face on close-up-driven footage (same outfit, a different woman), a portrait holds it;
	- run. The mask is generated in-graph (SAM3 finds the person on the first frame, `GrowMask` 10, `BlockifyMask` 32) and `background_video` is the video **with the character painted black** - the hole the model fills. 77 frames at 640x640 take **375 s**.
- *Knobs:*
	- the **reference image** - portrait, well-lit, face clear (E13c probe B vs C is the whole measurement);
	- the **mask prompt** (`person` on `SAM3_Detect`) and `GrowMask` / `BlockifyMask` (10 / 32) if the driver's person is unusual;
	- **`length`** (77 ships) and the canvas - width/height must be **multiples of 16**;
	- the **prompt** describes the scene action ("The character is dancing in the room"), not the character - the reference carries identity.
- *Measured:* replacement + motion + background preservation at 375 s per 77-frame cell ([`video/evidence/E13c-mix-probes.png`](video/evidence/E13c-mix-probes.png), E13c). Weights: `wan2.2_animate_14B_int8_convrot` (18.4 GB, Apache-2.0) + the lightx2v distill lora.
- *Traps:* the output **prepends the reference as frame 0** (81 frames out for `length` 77) - trim one second in the engine or with a slice; the mask and the video must share the canvas (a mismatch shows up as black 32-px blocks - measured); DWPose auto-downloads its detectors on first run into `custom_nodes/comfyui_controlnet_aux/ckpts/`. The **relight lora** ships in the chain (the official template includes it); measured on a neutral-lit room its integration difference is subtle (subject-vs-background palette mismatch 27.6 -> 25.5 across matched frames, E13d) - on strongly-lit scenes it should matter more, so re-measure if a composite reads pasted.
	- **size** - edit only the two `**INT Constant**` nodes (multiples of 16): they drive the `ImageScale` hub, `WanAnimateToVideo`'s canvas, and both `DWPreprocessor` map resolutions - one edit moves the whole canvas. The plate drives the size decision: set them to the plate's dimensions (cost proportional to pixels; the 6-step distill LoRA keeps it cheap). The shipped 640x640 square is the tested configuration.
- *More:* [`video/README.md`](video/README.md), and E13c in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

### S32. Make our character speak an audio file

- *When:* you have dialogue or a voice line and want **your character saying it** - a talking-head clip with the audio embedded, for cutscenes, dialogue previews or pitches. The audio drives the mouth; the face is ours.
- *Steps:*
	- open `video/workflows/wan-infinitetalk.json` and set the **reference** on the `LoadImage` (node 12) - a **portrait**, face clear;
	- set the **audio** on the `LoadAudio` (node 9) — set the `PrimitiveFloat` to the audio's duration in seconds (the math node converts it to the 4n+1 frame count at 25 fps);
- *Knobs:*
	- the **audio** - it drives the mouth; the words are its business;
	- the **reference** - portrait, well-lit;
	- **`seconds`** (3.24 ships) - a `ComfyMathExpression` turns it into **`length`**, rounded to the model's required 4n+1, so there is no hand arithmetic; raising it raises VRAM;
	- the canvas (480x832 ships; any multiple of 16, independent of the reference's pixels);
	- **`audio_scale`** (1.0) - lip-sync strength;
	- **`motion_frame_count`** (9).
	- fps is **pinned at 25** - the audio conditioning is resampled for 25-fps video inside the node, so any other fps would desync the mouth.
- *Measured:* identity holds through speech - lip-band motion 1.9x forehead with the highest-motion rows exactly at the mouth ([E15](video/EXPERIMENTS.md)). Weights: patch 5.1 GB + wav2vec2 190 MB, Apache-2.0.
- *Traps:* lip-sync was **human-confirmed** on the probe clip (E15, 2026-10-11); for your own audio, play the output mp4 - the audio is embedded. Only the FIRST `length` frames' worth of audio is spoken (audio past that is never read; shorter audio pads idle) - trim to `seconds` (the mux cuts the track to the clip, so over-long audio is dropped rather than appended). Longer audio = **chain it**: `uv run python scripts/talk_chain.py <audio> --ref <portrait> --out <clip>.mp4` builds the chained graph (full 81-frame chunks plus a trimmed last chunk, latent-space assembly, one muxed output) - an 8.8-s line measured 221 frames exact in 606 s (E21). The manual pattern behind it: feed one run's output IMAGE batch into the next `WanInfiniteTalkToVideo`'s `previous_frames` - each continuation advances 72 frames (**2.88 s** at defaults; drop the `trim_image` leading frames when stitching). `single_speaker` needs no masks (masks are the two-speaker mode).
- *More:* [`video/README.md`](video/README.md), and E15 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

### S33. Make our character perform an audio file

- *When:* you have dialogue, a song or a voice line and want **your character performing it** - head movement, expression and articulation, not just lip-sync. This is the broader sibling of S32.
- *Steps:*
	- set the **audio** on the `LoadAudio` — set the `PrimitiveFloat` to the audio's duration in seconds (the math node converts it to the 4n+1 frame count at 16 fps, minimum 73);
	- open `video/workflows/wan-s2v.json` and set the **reference** on the `LoadImage` (node 11) - a **portrait**; the shipped canvas is **640x640**, which a square portrait fits exactly;
- *Knobs:*
	- the **audio** - it drives the whole performance;
	- the **reference** - portrait, face clear;
	- **`seconds`** - a `ComfyMathExpression` turns it into **`length`**, rounded to 4n+1 (77 at defaults; the model needs at least 73, so the shortest clip this flow makes is 4.75 s); raising it raises VRAM;
	- per-route encoders: this flow uses **`wav2vec2_large_english`** - S32's chinese-base is a different encoder, do not mix them.
	- fps is **pinned at 16** - the audio bucket is built for 16-fps video inside the node, so any other fps would desync the performance.
- *Measured:* identity holds through the performance (head tilts, blinks, mouth) - [`E16`](video/EXPERIMENTS.md). Weights: `Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ` (16.65 GB) + encoder (631 MB) + the **Wan2.2 4-step lightning lora** (1.23 GB), Apache-2.0.
- *Traps:* the checkpoint keeps its **as-downloaded name** (the template's Kijai-original name is a different string - a mismatch costs a failed submission); the template's first-frame VAE hack (double frame 0 via `LatentCut`/`LatentConcat`, drop the first decode via `ImageFromBatch` 1) is wired in - do not remove it. Only the FIRST `length` frames' worth of audio drives the motion while the whole file is muxed - trim to `seconds` (the mux cuts the track to the clip, so over-long audio is dropped rather than appended). The `LatentCut`/`LatentConcat` pair is that first-frame hack, not chaining: longer audio chains through `WanSoundImageToVideoExtend`, which this flow does not wire yet, so one run covers one `seconds`-long chunk.
- *More:* [`video/README.md`](video/README.md), and E16 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).

---

### S34. Upscale a video while keeping its timebase and audio

- *When:* you already have a clip and want more resolved detail, but need its **duration, frame count, frame rate and sound** to stay put. This is restoration/upscaling, not interpolation or generating new motion.
- *Steps:*
	- open `video/workflows/video-upscale-seedvr2.json` and choose the video on `LoadVideo`;
	- run. `GetVideoComponents` passes the decoded frame batch to SeedVR2 and feeds the original FPS + audio into `CreateVideo`.
- *Knobs:*
	- **`resolution`** on `SeedVR2VideoUpscaler` is the target **short edge**, not a multiplier: **960** makes a 640x640 clip 960x960 and a 720x1280 clip 960x1706;
	- **`batch_size`** must be **4n+1** (5 ships). Larger batches give more temporal context but use more VRAM; if it OOMs, 1 is a valid lower-memory batch, with less context (not measured here);
	- **`temporal_overlap`** (2 ships) blends across batch joins; `color_correction=lab` ships;
	- the flow uses **3B fp16 + CPU offload** on the 24-GB card.
- *Measured:* two clips, both audio-retained: 80 frames of 640x640 S2V at 16 fps -> 960x960 in **150 s**; 121 frames of 720x1280 dance at 24.12 fps -> 960x1706 in **375 s**. Frame count/FPS held.
- *Traps:* SeedVR2 **reconstructs** detail; it is not a pixel-exact enlarger - the still-image test (2D U1) found more detail *and* more drift than UltraSharp. Inspect the clip, not just its dimensions.
- *More:* [`video/README.md`](video/README.md), and E20 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md). For stills, use [`2d/workflows/upscale-seedvr2.json`](2d/workflows/upscale-seedvr2.json) (S10).

### S35. Animate our character from a prompt, fast

- *When:* you want a clip of our character doing something and have no driving footage - the motion comes from **words**, and you want it in under a minute rather than S28's 45. This is the fast prompt-driven arm (LTX-Video v1, distilled).
- *Steps:*
	- open `video/workflows/ltxv-i2v.json`, set the still on the `LoadImage` and write the motion as an **elaborate prompt** on the positive `CLIPTextEncode` (LTX degrades visibly on short prompts - describe the action, the look, the light);
	- run. 97 frames at 768x768 take about **35 s**, and 5 s warm on a loaded card.
- *Knobs:*
	- the **prompt** - motion-first and elaborate; the negative ships sensible;
	- the **checkpoint** - 13B-distilled-fp8 ships (identity holds); 2B-distilled-fp8 is the 15-s quick-test arm with softer identity, same graph via `--set 1.ckpt_name:...`;
	- **steps** (8 ships for distilled), no STG, cfg 1;
	- canvas (multiples of 32) and frames (8n+1, 97 ships = ~3.9 s at 25 fps).
- *Measured:* 13B holds identity through a fire-spell performance while 2B drifts and lets the spell overgrow ([`video/evidence/E22-ltxv-arms.png`](video/evidence/E22-ltxv-arms.png), E22). Weights: 13B-distilled-fp8 (15.7 GB) + t5xxl_fp8, LTX Open-Weights 0.X (commercial free under $10M revenue; the output is ours).
- *Traps:* this is v1, not v2 - LTX-2 is 19B under a separate community licence and does not fit this card. The guide/keyframe nodes and the audio-VAE route are still deferred.
- *More:* [`video/README.md`](video/README.md), and E22 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md). For the slow quality arm see S28 (`wan-vace-reference.json`).

### S36. Animate between our own keyframe stills

- *When:* you know the start and end of a shot - a pose here, a framing there - and want the model to travel between them. Two stills pin the endpoints; the prompt describes the travel. This is the keyframed-motion source (LTX-Video v1 guides).
- *Steps:*
	- Pose-to-pose: make the second still with `2d/workflows/qwen-edit-gguf.json` instructing ONLY the pose change (vague wording does not move her; explicit wording works), then run this flow. Sweep note: `--set` splits values on commas, so keep override prompts comma-free or each chunk becomes its own grid cell.
	- build the **guide clip**: e.g., 97 frames at the canvas size - your still at frame 0, your still at frame 96, exact black everywhere else (black = no guide; anything non-black pins). Encode lossless (`ffmpeg -framerate 25 -i f%03d.png -c:v libx264 -crf 0`);
	- open `video/workflows/ltxv-guides.json`, set the guide clip on the `LoadVideo`, write the travel on the positive `CLIPTextEncode`, and run;
	- more than two guides? Add non-black frames anywhere in the 97 (batch position IS the frame) - a chest-left/chest-right/chest-left triple steers the object over and back with background holding (E23 arm E). One guide per beat; the output overshoots by ~8 frames per extra guide, so trim to plan;
	- **trim the output to the plan** (first 97 frames): the model overshoots with a 16-frame wobble tail past the last guide.
- *Knobs:*
	- the **guide stills** - identity lives here; batch position IS the frame index;
	- **strength** (1.0 ships = hard pin, shared across all guides);
	- the **prompt** - must describe the travel (push-in, rise, turn), not a pose;
	- steps 8 / euler / no STG / cfg 1 (distilled recipe; 30 steps costs 3x and keeps the same wobble, so it buys nothing).
- *Measured:* same-still guides pin near-static (40 s); full-body to portrait travels smoothly with identity holding ([`video/evidence/E23-ltxv-guides.png`](video/evidence/E23-ltxv-guides.png), E23). Defects: 113 frames out for 97 planned, ghost wobble f96-104 before re-settling, end guide lands slightly early. Weights shared with S35.
- *Traps:* the padding must decode **byte-exact black** - verify with a decode check, or every noisy frame becomes a guide. Per-guide strengths (`LTXVAddGuideMulti`) do not submit through `sweep_workflow` (DynamicCombo must nest; measured rejection) - shared strength only. Guide stills center-upscale to the canvas, so mismatched aspects crop. Guides steer composed wholes, not independent elements - the model interpolates whole frames between pins, so an object crossing the frame needs a pin per beat; output overshoots ~8 frames per extra guide, trim to plan.
- *More:* [`video/README.md`](video/README.md), and E23 in [`video/EXPERIMENTS.md`](video/EXPERIMENTS.md).


### S37. Pixel art

- *When:* you want the **pixel-art style** - for sprites, UI, or any asset. (For packing frames into sheets and atlases, see **S9**; the style and the delivery form are separate decisions.)
- *Generate:* `2d/workflows/pixel-art.json`: SDXL + `pixel-art-xl` LoRA (OpenRAIL) at 1024². **That LoRA paints on an 8 px grid**, so its native sprite is 1024/8=128 px. Make sure to set the correct target sprite size when applying pallettes. Generating at 1024² and downscaling beats generating small. For the flat retro look, Retro Diffusion ships **one checkpoint per sprite scale** with a /8 factor: `16x` at 256² -> 16 px, `24x-64x` at 512² -> **64 px**, `128x` at 1024² -> 128 px.
- *Convert an existing picture, faithfully:* `2d/workflows/pixel-art-convert.json` - resize + palette only, so the source is kept exactly, nothing is invented.
- *Convert an existing picture, redrawn:* `2d/workflows/pixel-art-restyle.json` - an img2img pass with the pixel-art LoRA first (`denoise` **0.6** is the knob: lower keeps the source, higher redraws it). More sprite-like, but it invents detail.
- *Palettes:* the **56 palettes ship inside the `comfyui-pixelart-detector` pack**, so they are already on the box - `PixelArtLoadPalettes` reads that folder (hardcoded). To use your own, drop a PNG into the pack's `palettes` folder, or derive one from an image with `PixelArtPaletteGenerator`. `render_all_palettes_in_grid` renders them all as a labelled sheet.
- *Traps:* downscale by **nearest**, and derive the divisor from the pair - 1024→128 is the LoRA's own **/8**, 1024→64 is **/16** (a deliberate decimation), Retro Diffusion 512→64 is its **/8**. Whatever the target, edit `ImageScale` **and** the palette pass together. Keep the palette pass at a **fixed** size. Do not downscale *before* an img2img pass: a 64-128 px latent makes SDXL produce mush.
- *Licence:* the Retro Diffusion models are **purchased**, and RD's terms give their **outputs to the user** (commercial use fine); do not train on RD outputs, and do not commit the weights [retrodiffusion.ai/terms, checked 2026-10-08]. `pixel-art-xl` is OpenRAIL, and it is the **different** look (richer detail), not the licence fix.
- *More:* E31/E32 and the convert-path rows in [`2d/EXPERIMENTS-2D.md`](2d/EXPERIMENTS-2D.md); for sprites and atlases, back to **S9**.


## If your job isn't here

Browse [`PIPELINES.md`](PIPELINES.md) — the capability index (operation family × subject/domain, with cost, licence, status and key knob). If a flow exists but has no story above, that's a documentation gap worth reporting; if no flow exists, it belongs in `PIPELINES.md` → "Status — what is actually left".
