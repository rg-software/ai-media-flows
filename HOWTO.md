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
	- For an **instruction-style** edit ("relight this", "change the material") use `2d/workflows/qwen-edit-gguf.json`. The older `kontext-edit.json` (Flux Kontext) did this bolder, but it is **superseded** now.
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

| need                                                          | flow                                                                                               | reality                                                                                                                                                                            |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| same **design** (outfit, hair, silhouette) in any composition | `qwen-edit-gguf.json`                                                                              | Apache-2.0, faithful, but the *face* is not embedding-identical                                                                                                                    |
| same **face**, close-up                                       | `instantid-character.json`                                                                         | strongest face match, but it **forces a bust**                                                                                                                                     |
| same **face**, free composition                               | `pulid-identity.json`                                                                              | full-body works; weaker face score; still needs insightface                                                                                                                        |
| same **design**, via the older Kontext route                  | `kontext-character.json`                                                                           | **superseded** by `qwen-edit-gguf.json`; non-commercial, ~1 MP                                                                                                                     |
| same **character**, new **pose** or camera angle              | `2d/workflows/pose-skeleton.json` (skeleton-driven) · `qwen-edit-gguf.json` (instruction, easiest) | the skeleton flow holds a **coarse stance** (arms out / wide) but does not bind limb angles; an instruction is still the way to a *specific* pose, and kept pose *and* design best |

- *Trap:* judge identity by **measurement, not eye** — two renders can look identical yet score far apart. Prompt-level consistency lands around 0.14-0.19, so expect an embedding-identical face only from InstantID or PuLID.
- *New pose or camera angle?* Pose is a separate carrier from identity, so don't expect the consistency recipes above to move it. The route that works is **asking in words**: `qwen-edit-gguf.json` with "the same knight in the same armour and colours, arms spread wide" changed the pose *and* held the design closest. An instruction also handles **camera angles**, which a 2D skeleton cannot (no yaw); the 3D path is the other way to get a chosen angle.
- *What the skeleton flow actually buys:* with its shipped `strength` **1.5** and `end_percent` **0.5** it imposes a **silhouette**. Measured: a "T-pose, arms outstretched" skeleton beat a prompt that explicitly asked for the opposite ("both arms lowered, hanging straight down at his sides") and still rendered cleanly — while the same skeleton at strength 0.9 for the *whole* run was ignored, and at 1.5 for the whole run it traced the sticks through the picture and wrecked it (which is what older notes here warned about). Ending the ControlNet's window early is what turns "overpowered and destructive" into "usable". It does **not** bind the limbs: a 45° cue still renders arms at the sides, an asymmetric cue (one arm up) is ignored, and "both arms up" comes back as shoulder horns. So — coarse stance (arms out, wide, tall) → this flow; a specific pose → the instruction. `cfg` makes no difference (4.0 = 7.0), and keep IPAdapter at **0.15** so it does not fight the cue.
- *If you still want a skeleton cue* — e.g. to try it with a different pose ControlNet — there are three ways to make one with `scripts/pose_probe.py` (it talks to the server over HTTP, so run it from anywhere with `--base <url> --token <token>`). **(1) Preset** — `template /tmp/pose.json --preset standing|arms_spread|t_pose`, or `--arm 30` for any arm angle, `--rotate -10` to lean the figure. **(2) Edit the numbers** — the file is 18 joints, each `x, y, confidence` in pixels, one named joint per line: `0 nose, 1 neck, 2/3/4 R shoulder/elbow/wrist, 5/6/7 L shoulder/elbow/wrist, 8/9/10 R hip/knee/ankle, 11/12/13 L hip/knee/ankle, 14-17 eyes and ears` (**R** means the subject's right, which is image left); re-run `draw /tmp/pose.json <out.png> --labels` to print every joint's index on the picture. **(3) Copy a photo** — `extract <photo.png>` detects the pose and hands back a skeleton you can reuse (it needs a realistic person: it finds none in our stylised assets, but it read all 18 joints off a photorealistic render). The flow ships a working example — `input/2d/pose_arms_spread.png`, source `assets/2d/pose_arms_spread.json` — so it runs as-is; make your own only for a different pose.
- *Turning an object to a different angle?* Don't reach for a ControlNet first: rotate the sprite in your editor, then run it through a second pass at **denoise ≈ 0.5-0.65** with a plain description of what it is. The rotation is kept and the object is re-rendered to fit the scene — a bottle rotated 90° came back lying on its side, re-lit and clean (the same pass kept its colour even though the prompt said otherwise). A ControlNet can hold an angle too, but only if the hint is scaled to the object's **real size in the frame**: a hint occupying ~5% of the picture is ignored entirely and the model returns a canonical upright object, while the same hint at ~50% is followed.
- *Tooling caveat:* the OpenPose detector finds **no person in most of our stylised renders** (13 of 15 in one batch), so a pose can be *imposed* but not *measured* automatically — `extract` and `measure` are for real photographs (see `comfyui/README.md`).
- *Warning:* `instantid-character.json` and `pulid-identity.json` depend on **insightface**, licensed for **non-commercial research** — don't ship their output. `qwen-edit-gguf.json` is Apache-2.0, and the older Kontext route is non-commercial too.

### S8. Materials: seamless textures, PBR, and into 3D

- *When:* you need a tileable texture, or a complete PBR material an engine can use.
- *Steps:*
	- **Tile it — only if your UVs repeat.** One quad or one UV island spanning the texture needs nothing; make it tile with `2d/workflows/seamless-texture.json` (`method="offset"`) when the UVs repeat across a surface (grid/tiled UVs, or a 3D mesh whose UVs tile), because nothing hides the join.
	- **Material.** `2d/workflows/pbr-material.json` writes albedo, normal, roughness, metallic, AO and a packed map. Feed it a square texture around 768 px. `albedo_source` picks which Marigold albedo to use (`appearance` or `lighting` — take the one that looks de-lit); leave the rest at their defaults. Output lands in ComfyUI's `output/2D/pbr_material/`; pull it down with `comfy_io.py get 2D/pbr_material/<file>.png` (S14).
	- **Into 3D — two small tools, by target; both run on your machine (no ComfyUI).** Fetch the maps (S14). The flow already writes them all at one size, so **only the packed map is missing** and nothing else is rewritten: basecolor and normal are used as they are, and a grayscale AO already satisfies both consumers (glTF reads occlusion from R, Unity's `_OcclusionMap` from G, and grayscale has R=G=B).
	- **Unity — `scripts/pack_pbr_material.py`.** `uv run python scripts/pack_pbr_material.py --roughness <png> --metallic <png> --out metallicSmoothness.png`. Unity reads one map in `_MetallicGlossMap` as **R=metallic, A=smoothness**, where glTF packs roughness in G — that difference is why this tool exists (a roughness map in that slot inverts the surface, making rough stone look polished). It refuses mismatched input sizes rather than silently resampling; `--size` forces it.
	- **glTF — `scripts/make_gltf_material.py`.** `uv run python scripts/make_gltf_material.py --basecolor <png> --normal <png> --roughness <png> --metallic <png> --occlusion <png> --out metallicRoughness.png` packs **G=roughness, B=metallic** (glTF has no separate roughness/metallic textures — that single image is the format's requirement). Add `--mesh <glb> --glb-out <out.glb>` and it also applies the material to a mesh (mesh needs **UVs**; its material is **replaced**), giving a **self-contained GLB** — textures embedded, material already wired, so one file is all you ship and Unity/Godot/Blender/three.js import it directly. With `--out` is then optional (it defaults next to the GLB). Without a mesh you get just the packed map, for assembling the material yourself or adding it to a GLB built elsewhere.
	- **Import settings are yours** (neither tool writes `.meta`): data maps as **linear** (sRGB off), the normal as *Texture Type = Normal map*, the packed map's **alpha kept** (DXT1/BC1 has none), and **Metallic = 1** on the material. Importing the GLB usually handles these, which makes it the more forgiving route.
- *Traps:* `mirror`/`blend_edges` tile without a visible seam but look visibly wrong (a mirrored building becomes a second cottage) — use `offset`. Marigold's metallic is an **estimate**: on stone it sits near 0.36 where a dielectric should be ~0, so a faint sheen in-engine is the *value*, not the packing — remap or override it per material.
- *Normal direction:* the normal map is **OpenGL (+Y up)** as glTF expects. If your renderer disagrees, pass `--flip-normal-green`.
- *Legacy asset:* the sample material in `assets/3d/stone_material/` predates this flow — its normal is **DSINE-derived** (non-commercial). Regenerate it before shipping anything that depends on it.

### S9. Finish: upscale and restore

- *When:* you need more resolution, or a soft/small face cleaned up.
- *Steps:* `2d/workflows/upscale-seedvr2.json` (Apache-2.0). Set `resolution` to the **short edge**; set it equal to the image size to **restore** instead of upscaling — that also works as face restore.
- *Knobs:* `batch_size` must be 4n+1. SeedVR2 *reconstructs* (more detail, more drift, slower); `upscale.json`'s GAN is faithful (it invents nothing) but see the warning.
- *Warning:* don't ship output from `upscale.json` — its `4x-UltraSharp` model is **non-commercial**. `upscale-seedvr2.json` is Apache-2.0.

### S10. Sprites and atlases

- *When:* you need game-ready sprites.
- *Steps:* pixel art — `2d/workflows/pixel-art.json`, then **downscale nearest ÷8 or ÷16** by the model's grid factor. Atlas — `2d/workflows/sprite-atlas.json` (`ImageGrid`) builds and slices round-trip verified.
- *Trap:* never trust the pixel-art detector's auto-detection (it mis-detects 16x), and it isn't idempotent — don't feed it an already-downscaled image.
- *Warning:* the pixel-art model (Retro Diffusion) is **non-commercial** — the vendor says its outputs are yours to use, but the model itself may not be used commercially, so clear it before shipping. The `pixel-art-xl` LoRA is OpenRAIL and cleaner.

### S11. 3D from images

- *When:* you want a mesh, a textured model, multiple views, or a rig.
- *Steps:* `3d/workflows/hy3d-full-workflow.json` (shape → texture → bake) or `hy3d-multiview-workflow.json`; rig with `3d/workflows/unirig-humanoid-workflow.json`. Its `Hy3DMeshUVWrap` node is what gives a generated mesh its UVs, which is why a Hy3D mesh can take a material straight from S8.
- *Warning:* Hy3D runs under the **Tencent Hunyuan 3D Community License**, which **excludes the EU, UK and South Korea** and requires a licence from Tencent above 1M monthly users. You own the meshes you generate, but only within those limits. UniRig (rigging) is MIT.
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
	- `... fetch latest --dest from-box` downloads those files and records what it fetched in a small `manifest.json`;
	- `... get 2D/pbr_set/<texture>/material/normal.png` downloads **any** file under ComfyUI's `output/`, `input/` or `temp/` — including ones a script wrote (a PBR material, a contact sheet), which never appear in a run's history.
- *Knobs:*
	- `--base`/`COMFY_BASE` — the ComfyUI URL;
	- `--token`/`COMFY_TOKEN` — **ask the operator**. It lives on the server as the first line of `~/Projects-Git/ComfyUI/login/PASSWORD`.
	- `--subfolder refs` keeps uploads tidy;
	- `--dest` chooses where downloads land.
- *Trap:* image nodes read **only** from `input/` - a file sitting in `output/` cannot be loaded, so upload it before running a flow that needs it. With many inputs, upload the folder once and read it with the `LoadImagesFromFolderKJ` node rather than one file at a time. And only those three dirs are served: a file anywhere else on the box (e.g. a result written into the repo) cannot be fetched at all, by any route short of SSH.
- *More:* `scripts/comfy_io.py --help`.

---

## If your job isn't here

Browse [`PIPELINES.md`](PIPELINES.md) — the capability index (operation family × subject/domain, with cost, licence, status and key knob). If a flow exists but has no story above, that's a documentation gap worth reporting; if no flow exists, it belongs in `PIPELINES.md` → "Status — what is actually left".
