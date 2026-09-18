# Hy3D knobs reference (Hunyuan3D-2.1 wrapper)

Every node in the Hy3D pipeline, what it does, its knobs (with defaults from the upstream `hy3d_example_01.json` / `hy3d_multiview_example_02.json`), and what tweaking each does. Source of truth for exact widget order: `/object_info/Hy3D*` on the server; this doc is the *human* version (what to touch when).

## Pipeline at a glance

```
[image(s)] → shape gen → [VAE decode] → postprocess → [UV wrap] → render multiview
          → paint (SampleMultiView) → delight (DelightImage) → bake → apply → export
```

Two shape-gen flavours:
- **Single image**: `Hy3D_2_1SimpleMeshGen` (fast path, our `hy3d-full`)
- **Multi-view**: `Hy3DModelLoader` + `Hy3DGenerateMeshMultiView` (+ `Hy3DVAEDecode`) — needs the **mv checkpoint** (see below)

---

## Shape generation

### `Hy3D_2_1SimpleMeshGen` (single image to TRIMESH)
| Knob | Default | Effect |
|---|---|---|
| `model` | `hy3dgen\model.fp16.ckpt` | base 2.1 checkpoint (diffusion_models combo) |
| `steps` | 50 (range 1–100) | 30 = fast/draft, 80+ = finer surface, slower |
| `guidance_scale` | 5.0 (range 1–30) | higher = adheres tighter to source shape/content, can stiffness/warp; lower = smoother, more generic |
| `octree_resolution` | 384 (32–1024) | **geometry density** — the biggest quality lever. 512+ = finer details (slow), 256 = blocky |

### `Hy3DModelLoader` and `Hy3DGenerateMesh` and `Hy3DVAEDecode` (manual or multiview path)
- `Hy3DModelLoader`: `model` (diffusion combo), `attention_mode` (sdpa|sageattn — use sdpa), `cublas_ops` (bool speedup), `compile_args` (torch.compile, requires triton — leave off).
- `Hy3DGenerateMesh`: `pipeline` (HY3DMODEL), `image`, `guidance_scale`, `steps`, `seed`, `mask` (opt), `scheduler` FlowMatchEuler|ConsistencyFlowMatch. Outputs `latents`.
- `Hy3DGenerateMeshMultiView`: `pipeline`, front/left/right/back (opt IMAGE), `guidance_scale=5.5`, `steps=30`, `seed`, `scheduler`. Outputs latents+image+mask.
- `Hy3DVAEDecode`: `vae`, `latents`, `box_v=1.01` (bounding box scale), `octree_resolution=256` (multiview example) / 384 (single), `num_chunks=32000` (decodes in chunks to fit VRAM), `mc_level=0`, `mc_algo=mc|dmc`. Outputs TRIMESH.

> **Model variants matter — and the two loaders want DIFFERENT file formats (hard-won):**
> - `Hy3D_2_1SimpleMeshGen` (single-image path) uses the **hy3dshape** loader → wants the **nested `.ckpt`** (`ckpt['model']`). A `.safetensors` here → `KeyError: 'model'`.
> - `Hy3DModelLoader` (multiview / manual path) uses the **shapegen** loader → **re-nests flat `.safetensors` itself** (`if ckpt_path.endswith('.safetensors')`), so it wants the **`.safetensors`**; a `.ckpt` here → `new_sd` empty → `KeyError: 'model'`.
> - Single-image 2.1 checkpoint: `tencent/Hunyuan3D-2.1 → hunyuan3d-dit-v2-1/model.fp16.ckpt`.
> - Multiview checkpoint: `tencent/Hunyuan3D-2mv → hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors` (fast) or `hunyuan3d-dit-v2-mv` (normal).
> Don't feed the single-image ckpt to multiview node (dimension mismatch), and don't swap `.ckpt`/`.safetensors` between the two loaders.

## Postprocess and retopology

### `Hy3DPostprocessMesh`
| Knob | Default | Effect |
|---|---|---|
| `remove_floaters` | true | drops disconnected specks/tiny islands |
| `remove_degenerate_faces` | true | deletes zero-area/glued faces |
| `reduce_faces` | true | run mesh simplification |
| `max_facenum` | 50000 | target face ceiling — lower = lighter GLB, coarser; 100k+ = finer, bigger |
| `smooth_normals` | false | smooth vertex normals — set true for cleaner light/shading on organic shapes |

### Retopology (change polygon/vertex structure)
| Node | Knobs | Use |
|---|---|---|
| `Hy3DIMRemesh` | `merge_vertices`, `vertex_count` (target), `smooth_iter`, `align_to_boundaries`, `triangulate_result`, `max_facenum` | InstantMesh remesh — retarget a clean, uniform quad-ish topology to a target vertex budget |
| `Hy3DFastSimplifyMesh` | `target_count`, `aggressiveness`, `max_iterations`, `update_rate`, `preserve_border`, `lossless`, `threshold_lossless` | FAST mesh simplify with lossless option — pick when you just want fewer faces fast |

### `Hy3DBPT` (point/geometry refinement, optional)
`enable_bpt` (bool), `seed`, `temperature`, `pc_num`, `samples` — BPT shape refinement using the michelangelo point cloud refinery. Optional + heavy; off by default in examples.

## UV and rendering (texture prep)

### `Hy3DMeshUVWrap`: **required before bake** (with a UV-UV wrap onto the mesh). Without it the bake crashes (`NoneType`, `back_project`). No knobs.

### `Hy3DCameraConfig`
Controls the 6 camera views the paint/bake system uses.

| Knob | Default (string of 6) | Effect |
|---|---|---|
| `camera_azimuths` | `0, 90, 180, 270, 0, 180` | which angles to look from |
| `camera_elevations` | `0, 0, 0, 0, 90, -90` | 4 side + top + bottom |
| `view_weights` | `1, 0.1, 0.5, 0.1, 0.05, 0.05` | **painting emphasis per view** — front=1, sides=0.1/0.5, top/bottom=0.05. If the *back* looks ghost/unpainted, raise the back view's weight (e.g. 0.1→0.6) |
| `camera_distance` | 1.45 | camera distance for orthographic render |
| `ortho_scale` | 1.2 | orthographic zoom/scale |

### `Hy3DRenderMultiView`
| Knob | Default | Effect |
|---|---|---|
| `render_size` | 1024 | resolution of rendered normal/position maps (texture detail floor) |
| `texture_size` | 2048 | **texture map resolution** — higher = sharper UV texture, slower |
| `normal_space` | `world` \| `tangent` | normal map coordinate space (world = absolute, tangent = surface-local — affects believability of artifact-driven lighting) |

## Texture synthesis

### `Hy3DSampleMultiView` (paint: the actual texture generator)
| Knob | Default | Effect |
|---|---|---|
| `view_size` | 512 | per-view render size for painting |
| `steps` | 25–30 | diffusion steps — 20 = fast/rough, 40 = crisp |
| `seed` | 1024 (ex) | changes texture pattern entirely — **try several** |
| `denoise_strength` | 1.0 | 1 = full repaint, ~0.5 = keep more of geometry colors / reference |
| `scheduler` | fixed | FlowMatch defaults |

### `Hy3DDelightImage` (remove baked-in shading to flat albedo)
| Knob | Default | Effect |
|---|---|---|
| `steps` | 50 | re-light diffusion steps |
| `width/height` | 512 | image size to delight |
| `cfg_image` | 1.0 | how strongly to enforce unlighting (1 = neutral) |
| `seed` | 42 | seed |

> Note (upstream): source image **background level** affects delighting a lot — full-black makes result red, too dark = red tinge, pure white = overbright. Mid-gray background is safest.

### `Hy3DBakeFromMultiview`
Applies the painted views onto the mesh using the renderer + camera config. No widgets (uses renderer + `camera_config` optional). Outputs the baked texture + mask + renderer.

### `Hy3DMeshVerticeInpaintTexture`: `CV2InpaintTexture` (touch-up)
Fill missed seams/holes in the baked texture. `Hy3DMeshVerticeInpaintTexture` (texture+mask+renderer) is the GPU/CPU inpainter; `CV2InpaintTexture` (texture+mask) is OpenCV-based. Only needed when bake leaves gaps.

### `Hy3DApplyTexture`
Final: write texture onto the TRIMESH. No knobs (texture + renderer).

## PBR (optional, engine materials)

| Node | Knobs | What |
|---|---|---|
| `Hy3DGetMeshPBRTextures` | `texture` ∈ `base_color`\|`emissive`\|`metallic_roughness`\|`normal`\|`occlusion` | extract a channel as an IMAGE — export each to build the 5-map set |
| `Hy3DSetMeshPBRTextures` | `texture` (same enum) + `image` | set a channel from an image |
| `Hy3DSetMeshPBRAttributes` | `baseColorFactor`, `emissiveFactor`, `metallicFactor`, `roughnessFactor`, `doubleSided` | per-channel gain factors (fine-tune after extract) |

## Export

### `Hy3DExportMesh`
`filename_prefix` (e.g. `3D/Hy3D_textured`), `file_format` (`glb`|`obj`|`ply`|`stl`|`3mf`|`dae`), `save_file` (bool). `glb` is the Unity-friendly one.

---

## Quick "what do I turn when it looks…" table

| Symptom | Knobs to try |
|---|---|
| Geometry blocky / simplistic | `octree_resolution` 384→512, `steps` 50→80 |
| Shape doesn't match source | `guidance_scale` 5→7 |
| Back/generic sides unbuilt | switch to **multiview** model + provide back view image |
| Texture blurry in places | `view_weights` for that side ↑; `Hy3DRenderMultiView.texture_size` 2048→4096 |
| Texture "hallucinated"/wrong pattern | `Hy3DSampleMultiView.seed` (retry), `denoise_strength` ↑ from reference |
| Painted texture looks baked/shiny | `Hy3DDelightImage.cfg_image` ↑ (stronger unlight), check source bg not black/white |
| Bake ghosts/smears on one side | fix `view_weights` for that azimuth |
| Mesh too heavy for game | `Hy3DPostprocessMesh.max_facenum` ↓, or `Hy3DFastSimplifyMesh` |
| Artist wants flat albedo (no shading) | ensure Delight ran + `normal_space=world` |

