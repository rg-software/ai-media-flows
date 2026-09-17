# HOW TO — user stories

`README.md`'s "I want to…" table tells you **which flow** fits a job. This file tells you **what to
actually do**: prerequisites, steps, the knobs that matter, the trap to avoid, and what a good result
looks like. Each story links the flows it uses and points at the deeper doc for the *why*.

New here? Read **Part 1** once — every story assumes it. Then jump to the story you need.

---

## Part 1 — How to run a flow at all

**Where everything lives**

| | |
|---|---|
| Server | ComfyUI on the Linux box. URL/password with the user. Manage the service with `systemctl --user restart comfyui` (**never** `sudo`). |
| Flows | `2d/workflows/*.json`, `3d/workflows/*.json` — openable, editable graphs |
| Flow inputs | the ComfyUI **`input/`** dir on the box. **`LoadImage` reads only from `input/`** — a file sitting in `output/` cannot be loaded |
| Flow outputs | `output/<prefix>/` on the box |
| Curation | `input/2d/` and `input/3d/` are the **staging** dirs; promote from there into `assets/` |

**Two ways to run a flow**

1. **GUI** — open the ComfyUI web UI, drag a `.json` onto the canvas, set the inputs, Queue. Good for
   exploring; the graph's own note (the coloured group box) explains its recipe and gotchas.
2. **Scripted** (preferred, and what this repo's evidence comes from) — submit the graph over the API.
   Working examples to copy: `scripts/gen_assets.py` (single generation), `scripts/sweep.py` (grids),
   `scripts/marigold_pbr.py` (a non-ComfyUI pipeline).

**The loop for producing a real asset**

1. Put your input in the box's `input/` dir (e.g. `input/2d/char_knight.png`).
2. Run the flow (GUI or script) — outputs land in `output/…`.
3. Look at it. If it's good, copy it to the staging dir: `input/2d/<name>.png`.
4. Promote it into the repo, md5-verified: `bash scripts/publish_assets.sh 2d` (or `… 2d <id>`).
5. Commit. Add a row to the scenario's `EXPERIMENTS-2D.md` with a verdict **and the reason**.

**When something goes wrong**

- **A run "succeeds" in ~2 s and saves nothing** — the API lied; read the journal:
  `journalctl --user -u comfyui`. This is a real, documented failure mode (a bad `type` string).
- **The box freezes / the model won't fit** — read `comfyui/hardware.md` *before* pulling anything
  large. The box is RAM-bound, not VRAM-bound; the service has a memory guard that kills ComfyUI
  rather than the machine.
- **Masks come out inverted** — the MASK convention is *1 = transparent/selected*; see
  `comfyui/README.md` → Node gotchas.

**Two habits that matter more than any knob:** change **one knob at a time**, and remember that
**a metric is a hint, the image is the truth** (it has misled us three times).

---

## Part 2 — User stories

### S1. Generate concept art from a prompt

*When:* you need a character, prop, environment or texture from scratch.
*Prereqs:* none — the base checkpoints are on the box.
*Steps:* run `2d/workflows/z-image-turbo.json` (modern, Apache-2.0, fits; 8 steps, ~25 s) or
`2d/workflows/sdxl-base-art.json` (SDXL; more "painted", the canonical asset set came from it).
*Knobs:* `cfg` and `steps` — **cfg 7 / 20 steps** is SDXL's value point (cfg 3 washes out, cfg 9
over-burns, 30 steps buys nothing). Z-Image leans **photoreal**; add style words or a LoRA for a
painted look.
*Expect:* 1024². For a **solo full-body** character, say so explicitly — baseline SDXL otherwise
renders a two-view sheet or a bust.
*Go deeper:* `2d/EXPERIMENTS-2D.md` E1/E1c/E1d, U3.

### S2. Control composition from an existing image

*When:* you have a sketch, a screenshot, or an asset whose *layout* you want to keep but whose
content/style you want to replace.
*Steps:* `2d/workflows/controlnet-union.json` — one 2.34 GB model covering many modes; pick the mode
with `SetUnionControlNetType` and feed the matching preprocessed image (`CannyEdgePreprocessor`,
`DepthAnythingV2Preprocessor`, …). Canny-only: `2d/workflows/sdxl-controlnet-canny.json`.
*Knobs:* `strength` ≈ 0.8 holds structure while freeing style.
*Trap:* the union `type` strings are **grouped** — `"canny"` is invalid, it's
`"canny/lineart/anime_lineart/mlsd"`. A bad value **fails silently** (see Part 1).
*Go deeper:* E2/E2b, U6b.

### S3. Cut an object out, or mask it by description

*When:* you need a transparent PNG, or a mask to feed an edit.
*Steps:* **by description** (recommended): `2d/workflows/sam3-segment.json` — type "the knight in
silver armor" and get an outline-accurate mask, even in a two-subject scene. **By subject isolation:**
`2d/workflows/remove-bg.json` (BiRefNet).
*Trap:* MASK is **1 = transparent/selected**, and `RemoveBackground` returns 1 on the *foreground* —
insert `InvertMask` or you get a perfectly inverted cutout.
*Go deeper:* E3b, U6a.

### S4. Get depth or normal maps

*When:* you want depth-ControlNet, depth-ordered composition, relighting, or a 2.5D effect.
*Steps:* `2d/workflows/depth-normal.json` (DepthAnythingV2 + DSINE). No extra weights; first run
downloads, then it's seconds.
*Expect:* depth reads near = light; tangentspace normals are flat ≈ (128,128,255).
*Go deeper:* E12.

### S5. Edit a picture — remove, replace, extend

*When:* fix or change part of an existing image; make the canvas bigger.
*Steps:* inpaint `2d/workflows/inpaint.json`; outpaint `2d/workflows/outpaint.json`
(`extend_left/right_factor` 1.5 = +50% per side). For an **instruction-style** edit ("relight this",
"change the material") use `2d/workflows/qwen-edit-gguf.json`.
*Knobs:* denoise. For harmonisation, **0.45 integrates while keeping the subject; 0.75 replaces it** —
and small subjects break first.
*Trap:* raw inpaint drifts ~5/255 *outside* the mask (VAE round-trip). Crop&Stitch avoids this
entirely; if you use the older path, composite back with the mask.
*Go deeper:* E8, E9, E10, U2.

### S6. Compose a scene from parts

*When:* you have a background, a character cutout and props, and need one coherent picture.
*Steps:* `scripts/compose_scene.py` places them (pixel-exact scale/feet/overlap), then
`2d/workflows/compose-harmonize.json` blends the lighting.
*Knobs:* the same denoise rule as S5 — this is the *identity* knob.
*Go deeper:* E10.

### S7. Keep a character consistent across images

*When:* the same character must appear in several shots.
*Choose by what "consistent" means:*

| need | flow | reality |
|---|---|---|
| same **design** (outfit, hair, silhouette) in any composition | `qwen-edit-gguf.json` | Apache-2.0, faithful, but the *face* is not embedding-identical |
| same **face**, close-up | `instantid-character.json` | strongest face match, but it **forces a bust** |
| same **face**, free composition | `pulid-identity.json` | full-body works; weaker face score; still needs insightface |

*Trap:* judge identity by **measurement, not eye** — two renders that look identical to us scored
far apart. And beware: our own two "same character" assets only score ~0.14 against each other, so
~0.14–0.19 is *normal* prompt-level consistency, not a failure.
*Go deeper:* E14a/b/c, U5.

### S8. Materials — seamless textures, PBR, and into 3D

*When:* you need a tileable texture, or a texture's PBR maps, or a material an engine can use.
*Steps:* tile it — `2d/workflows/seamless-texture.json` with `method="offset"`. PBR —
**`scripts/marigold_pbr.py`** (albedo/roughness/metallic; **correct metallic**; albedo is de-lit).
Into 3D — **`scripts/make_gltf_material.py`** packs a glTF-correct material and can apply it to a mesh.
*Traps:* `mirror`/`blend_edges` score well on continuity metrics and look awful — use `offset`.
Don't use `pbr-from-texture.json` for metallic; its output is inverted. glTF wants
`G`=roughness/`B`=metallic, Unity's own shaders want `R`=metal/`A`=smoothness.
*Go deeper:* E7c, E12b, U4, U7.

### S9. Finish — upscale and restore

*When:* you need more resolution, or a soft/small face cleaned up.
*Steps:* `2d/workflows/upscale-seedvr2.json` (Apache-2.0). Set `resolution` to the **short edge**;
set it equal to the image size to **restore** instead of upscaling — that also works as face restore.
*Knobs:* `batch_size` must be 4n+1. SeedVR2 *reconstructs* (more detail, more drift, slower);
`upscale.json`'s GAN is faithful but **non-commercial**.
*Go deeper:* E4b, U1, E13f.

### S10. Sprites and atlases

*When:* you need game-ready sprites.
*Steps:* pixel art — `2d/workflows/pixel-art.json`, then **downscale nearest ÷8 or ÷16** by the
model's grid factor. Atlas — `2d/workflows/sprite-atlas.json` (`ImageGrid`) builds and slices
round-trip verified.
*Trap:* never trust the pixel-art detector's auto-detection (it mis-detects 16x), and it isn't
idempotent — don't feed it an already-downscaled image.
*Go deeper:* E5/E5b/E5f, E6.

### S11. 3D from images

*When:* you want a mesh, a textured model, multiple views, or a rig.
*Steps:* `3d/workflows/hy3d-full-workflow.json` (shape → texture → bake) or
`hy3d-multiview-workflow.json`; rig with `3d/workflows/unirig-humanoid-workflow.json` (**Linux only** —
bpy via pixi).
*Go deeper:* `3d/README.md`, `3d/pipeline-design.md`, `3d/EXPERIMENTS.md`.

### S12. Reproduce, sweep, promote

*When:* you're regenerating the canonical set, exploring parameters, or landing work in the repo.
*Steps:* `scripts/gen_assets.py` (canonical asset set, writes a manifest recording the checkpoint);
`scripts/sweep.py` (2-axis grids with a labelled sheet + per-cell metric); `scripts/publish_assets.sh`
(`2d`/`3d`/`all`, md5-verified). Before committing docs: `scripts/lint_docs.py`.
*Go deeper:* `2d/PROTOCOL.md` (the run/sweep/promotion contract), E16.

---

## If your job isn't here

Browse [`PIPELINES.md`](PIPELINES.md) — the capability index (operation family × subject/domain, with
cost, licence, status and key knob). If a flow exists but has no story above, that's a documentation
gap worth reporting; if no flow exists, it belongs in `PIPELINES.md` → "Status — what is actually left".
