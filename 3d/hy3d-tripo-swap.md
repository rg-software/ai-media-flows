# Hy3D and Tripo swap guide

Both pipelines emit/accept **GLB**, so they interoperate at mesh boundaries. This is the practical "free-first, pay-per-stage" mechanic from `pipeline-design.md`.

## When to swap (decision heuristics)

| You want… | Path |
|---|---|
| Free full pipeline (shape → texture) | `hy3d-full-workflow.json` (Hy3D only) |
| Better geometry, free texture | Hy3D shape → **Tripo texturing** (bridge below) |
| Better texture quality | Hy3D shape → Tripo texturing (Tripo texture is trained on more data) |
| Rigged/skinned character | Hy3D or Tripo shape → Tripo rig (mixamo FBX) |
| Text prompt instead of image | `workflows/scratch/tripo-chain-workflow.json` (Tripo `TextToModel`) — needs API key |

## The two swap points

### Swap point A, shape stage: Hy3D to Tripo
Replace the **shape front-end** of the full workflow:
```
(Hy3D_2_1SimpleMeshGen | Hy3DModelLoader+GenerateMesh(+VAEDecode))  →  TripoTextToModelNode (text) | TripoImageToModelNode (image)
```
Tripo text/image-gen outputs a `MODEL_TASK_ID` + `FILE_3D_GLB`. You can then either:
- bake Tripo's own texture (`TripoTextureNode → MODEL_TASK_ID`), or
- export the bare `FILE_3D_GLB`, save it, and feed *Hy3D's* texture tail.

### Swap point B, texture stage: Hy3D to Tripo (the bridge)
Take a **free Hy3D GLB** and texture it with Tripo:
```
Load3D (picks GLB from models/3d/) → TripoImportModelNode → MODEL_TASK_ID
   → TripoTextureNode → TripoConversionNode (FBX/GLB export)
```
Reference: `workflows/scratch/tripo-bridge-workflow.json` (validated schema).

## Concrete steps to texture a Hy3D GLB via Tripo

1. **Export the Hy3D mesh as GLB** (already produced by `hy3d-full` → `3D/Hy3D_untextured.glb`, or shape-only via the mid-export).
2. **Put the GLB where Load3D can see it** on the server:
   ```
   ComfyUI\models\3d\<name>.glb
   ```
   (`Load3D.model_file` dropdown enumerates `models/3d/`.)
3. **Import `workflows/scratch/tripo-bridge-workflow.json`**, set the `Load3D` dropdown to your GLB.
4. **Provide the Tripo API key** (set once; Tripo nodes use `api_key_comfy_org`). Without it the nodes error at queue.
5. Queue → textured GLB (or FBX if you set format=FBX, fbx_preset=mixamo for Unity rig import).

> Tip: use `Hy3DIMRemesh` **before** handing a mesh to Tripo — Tripo's retopology/quad tools work better on clean uniform topology. `TripoImportModelNode` accepts the GLB directly, but the cleaner the input, the better the texture alignment.

## Swapping only the *texturing* stage in Hy3D's own workflow

You don't need a separate workflow — the valuable `hy3d-full-workflow.json` already isolates stages. To replace just the paint/delight/bake tail with Tripo:
1. Keep `postprocess → remesh → UVWrap → RenderMultiView` (produces normal/position maps + renderer).
2. Branch the TRIMESH: `Hy3DExportMesh` (for Tripo import) **and** keep the Hy3D tail as fallback.
3. Run the bridge, take the `FILE_3D_GLB` and continue.

This is exactly the GLB-gate design: any stage boundary that emits GLB is a swap point.

## Cost notes (Tripo, via ComfyUSD badge on server)
- Text/Image → Model: $0.05–0.1 per task (approx, from server's `price_badge`).
- Refine: $0.3; Conversion: $0.05–0.1. Budget accordingly per revision cycle.

## Gotchas
- `TripoRefineNode` **only accepts v1.4 Tripo drafts** — you can't refine a Hy3D mesh with it (it's not a retopology for arbitrary GLB).
- `TripoImportModelNode` is the *generic* entry for Hy3D GLB → task-id. Texture/rig after import is fine.
- Hy3D texture tail needs the **cp313 `custom_rasterizer` pyd** on the server (see `../comfyui/environments.md`); Tripo nodes don't use it.