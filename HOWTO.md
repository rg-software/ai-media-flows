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
- *Trap:* the union `type` strings are **grouped** — `"canny"` is invalid, it's `"canny/lineart/anime_lineart/mlsd"`. A bad value **fails silently**.

### S3. Cut an object out, or mask it by description

- *When:* you need a transparent PNG, or a mask to feed an edit.
- *Steps:* **by description** (recommended): `2d/workflows/sam3-segment.json` — type "the knight in silver armor" and get an outline-accurate mask, even in a two-subject scene. **By subject isolation:** `2d/workflows/remove-bg.json` (BiRefNet).
- *Trap:* MASK is **1 = transparent/selected**, and `RemoveBackground` returns 1 on the *foreground* — insert `InvertMask` or you get a perfectly inverted cutout.

### S4. Get depth or normal maps

- *When:* you want depth-ControlNet, depth-ordered composition, relighting, or a 2.5D effect.
- *Steps:* `2d/workflows/depth-normal.json` (DepthAnythingV2 + DSINE). No extra weights; first run downloads, then it's seconds.
- *Expect:* depth reads near = light; tangentspace normals are flat ≈ (128,128,255).

### S5. Edit a picture: remove, replace, extend

- *When:* fix or change part of an existing image; make the canvas bigger.
- *Steps:*
	- inpaint `2d/workflows/inpaint.json`;
	- outpaint `2d/workflows/outpaint.json`
	  (`extend_left/right_factor` 1.5 = +50% per side).
	- For an **instruction-style** edit ("relight this", "change the material") use `2d/workflows/qwen-edit-gguf.json`.
	  The older `kontext-edit.json` (Flux Kontext) did this bolder, but it is **superseded** now.
- *Knobs:* denoise. For harmonisation, **0.45 integrates while keeping the subject; 0.75 replaces it** — and small subjects break first.
- *Trap:* raw inpaint drifts ~5/255 *outside* the mask (VAE round-trip). Crop&Stitch avoids this entirely; if you use the older path, composite back with the mask.

### S6. Compose a scene from parts

- *When:* you have a background, a character cutout and props, and need one coherent picture.
- *Steps:* `scripts/compose_scene.py` places them (pixel-exact scale/feet/overlap), then `2d/workflows/compose-harmonize.json` blends the lighting.
- *Knobs:* the same denoise rule as S5 - this is the *identity* knob.
- *Two subjects that keep merging?* Put each in its own region with `2d/workflows/regional-prompting.json` - a single prompt containing both subjects **drops one of them entirely** (the model rendered only the sorceress and never the knight). Regional area conditioning fixed it with zero cross-bleed.

### S7. Keep a character consistent across images

- *When:* the same character must appear in several shots.
- *Choose by what "consistent" means:*

| need                                                          | flow                       | reality                                                         |
| ------------------------------------------------------------- | -------------------------- | --------------------------------------------------------------- |
| same **design** (outfit, hair, silhouette) in any composition | `qwen-edit-gguf.json`      | Apache-2.0, faithful, but the *face* is not embedding-identical |
| same **face**, close-up                                       | `instantid-character.json` | strongest face match, but it **forces a bust**                  |
| same **face**, free composition                               | `pulid-identity.json`      | full-body works; weaker face score; still needs insightface     |
| same **design**, via the older Kontext route                  | `kontext-character.json`   | **superseded** by `qwen-edit-gguf.json`; non-commercial, ~1 MP  |

- *Trap:* judge identity by **measurement, not eye** — two renders can look identical yet score far apart. Prompt-level consistency lands around 0.14-0.19, so expect an embedding-identical face only from InstantID or PuLID.

### S8. Materials: seamless textures, PBR, and into 3D

- *When:* you need a tileable texture, or a texture's PBR maps, or a material an engine can use.
- *Steps:*
	- Tile it. `2d/workflows/seamless-texture.json` with `method="offset"`. 
	- PBR. **`scripts/marigold_pbr.py`** (albedo/roughness/metallic; **correct metallic**; albedo is de-lit).
	- Into 3D. **`scripts/make_gltf_material.py`** packs a glTF-correct material and can apply it to a mesh.
- *Traps:* `mirror`/`blend_edges` score well on continuity metrics and look awful — use `offset`. Don't use `pbr-from-texture.json` for metallic; its output is inverted. glTF wants `G`=roughness/`B`=metallic, Unity's own shaders want `R`=metal/`A`=smoothness.

### S9. Finish: upscale and restore

- *When:* you need more resolution, or a soft/small face cleaned up.
- *Steps:* `2d/workflows/upscale-seedvr2.json` (Apache-2.0). Set `resolution` to the **short edge**; set it equal to the image size to **restore** instead of upscaling — that also works as face restore.
- *Knobs:* `batch_size` must be 4n+1. SeedVR2 *reconstructs* (more detail, more drift, slower); `upscale.json`'s GAN is faithful but **non-commercial**.

### S10. Sprites and atlases

- *When:* you need game-ready sprites.
- *Steps:* pixel art — `2d/workflows/pixel-art.json`, then **downscale nearest ÷8 or ÷16** by the model's grid factor. Atlas — `2d/workflows/sprite-atlas.json` (`ImageGrid`) builds and slices round-trip verified.
- *Trap:* never trust the pixel-art detector's auto-detection (it mis-detects 16x), and it isn't idempotent — don't feed it an already-downscaled image.

### S11. 3D from images

- *When:* you want a mesh, a textured model, multiple views, or a rig.
- *Steps:* `3d/workflows/hy3d-full-workflow.json` (shape → texture → bake) or `hy3d-multiview-workflow.json`; rig with `3d/workflows/unirig-humanoid-workflow.json`.
- *More:* `3d/README.md`.

### S12. Explore parameters with a sweep

- *When:* you want to find a value yourself rather than take a story's default - the defaults quoted in these stories came from exactly this.
- *Steps:* `scripts/sweep.py` runs a two-axis grid over a flow and writes a labelled sheet plus a per-cell metric, e.g. `--x cfg:3,5,7 --y steps:10,20,30`.
- *Knobs:* which two axes you sweep; hold everything else fixed.
- *Trap:* the sheet's metric is a hint, not a verdict - judge it by eye.

### S13. Transfer a style or a reference look

- *When:* you want an image to adopt the palette, atmosphere or medium of a reference.
- *Steps:* use **`2d/workflows/qwen-edit-gguf.json`** with the reference as `image2` — the multi-image reference mechanism does style transfer. The older `2d/workflows/ipadapter-style.json` (IPAdapter) still works.
- *Knobs:* for IPAdapter, `weight` — 0.0–0.2 is a style hint, 0.3–0.5 blends, and **≥0.6 the reference overrides the prompt** entirely.
- *Trap:* this transfers a **look**, not a layout. If you need "keep this composition", that is ControlNet territory (S2), not style transfer.

### S14. Move files to and from the box

- *When:* you need to put your own inputs into the box, or bring a run's outputs back (using the ComfyUI URL and token).
- *Steps:*
	- `uv run python scripts/comfy_io.py upload art/*.png` uploads into `input/`;
	- `... outputs latest` (or a prompt id) lists what a run produced;
	- `... fetch latest --dest from-box` downloads those files and records what it fetched in a small `manifest.json`.
- *Knobs:*
	- `--base`/`COMFY_BASE` and `--token`/`COMFY_TOKEN` (ask for both);
	- `--subfolder refs` keeps uploads tidy;
	- `--dest` chooses where downloads land.
- *Trap:* image nodes read **only** from `input/` - a file sitting in `output/` cannot be loaded, so upload it before running a flow that needs it. With many inputs, upload the folder once and read it with the `LoadImagesFromFolderKJ` node rather than one file at a time.
- *More:* `scripts/comfy_io.py --help`.

---

## If your job isn't here

Browse [`PIPELINES.md`](PIPELINES.md) — the capability index (operation family × subject/domain, with cost, licence, status and key knob). If a flow exists but has no story above, that's a documentation gap worth reporting; if no flow exists, it belongs in `PIPELINES.md` → "Status — what is actually left".
