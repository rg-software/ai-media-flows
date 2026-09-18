# 3D Asset Pipeline: Cookbook (Tripo and Hy3D on ComfyUI)

> **SUPERSEDED by** [`pipeline-design.md`](pipeline-design.md) (free-first, GLB-compatible architecture) + [`EXPERIMENTS.md`](EXPERIMENTS.md) (run log). Keep this file as reference for raw node signatures.

Server: `https://comfy.rt247a.ddns.me` (RTX 3090 · ComfyUI-Login protected) Auth: POST `/login` with the password → capture `AIOHTTP_SESSION` cookie. Node source via `/object_info` (1759 nodes available).

> Status: schemas verified against the live server.

---

## 1. Minimal "cookbook" chain (the one to build first)

**Goal:** prompt → textured, rigged, exported 3D asset (GLB/FBX).

```
TripoTextToModelNode
   └─ prompt (+ optional model_version, style, texture=true, pbr=true, seeds)
      │
      ▼ MODEL_TASK_ID
TripoRefineNode            ← retopology step
   └─ TripoTextureNode     ← texturing step (texture prompt, quality, pbr)
      │
      ▼ RIG_TASK_ID
   └─ TripoRigNode         ← skeletal rigging
      │
      ▼ RIG_TASK_ID
   └─ TripoConversionNode  ← export: fbx_preset, format, bake, with_animation
      │
      ▼ TRIMESH
   └─ TrimeshSave          ← writes GLB/OBJ/PLY/STL/3MF/DAE
```

**Notes**
- Task IDs flow stage-to-stage; you cannot skip ahead (all stages take the previous task ID).
- `TripoRefineNode` takes only a `MODEL_TASK_ID` — no control knobs.
- `TripoConversionNode` is where FBX/pivot/quad/symmetry decisions happen (`fbx_preset`, `force_symmetry`, `flatten_bottom`, `pivot_to_center_bottom`, `bake`, `with_animation`).
- API key is injected via hidden `api_key_comfy_org` (set once; persists on the node).

---

## 2. Free/weights fallback chain (Hy3D and ComfyUI-3D-Pack)

Use this when you don't want to spend API credits or want to run locally.

```
 [image] → Hy3DGenerateMesh      (pipeline: HY3DMODEL, guidance_scale, steps, seed)
              └─ Hy3DIMRemesh        (remesh to target vertex_count)
                 └─ Hy3DPostprocessMesh  (remove floaters, degenerate faces, reduce)
                    └─ TrimeshSave
```

**Caveats**
- No native text-to-3D from the node; you feed an **image** (or a text-generated 2D image) into `Hy3DGenerateMesh`.
- No PBR texturing step; `Hy3DApplyTexture` just wraps a flat texture `IMAGE` onto the mesh. Full PBR via `Hy3DSetMeshPBRTextures` requires the material channels (base_color / emissive / metallic_roughness / normal / occlusion) — so the practical route is: generate the mesh → texture it with a separate 2D gen → apply.
- `Hy3D2_1SimpleMeshGen` is **not installed** on this server (only `Hy3DGenerateMesh`).

---

## 3. The full Tripo line (what else is installed)

| Task (per cheatsheet) | Nodes present |
| --- | --- |
| Generate 3D mesh (text) | TripoTextToModelNode, TripoP1TextToModelNode |
| Generate 3D mesh (image/multiview) | TripoImageToModelNode, TripoP1ImageToModelNode, TripoMultiviewToModelNode, TripoP1MultiviewToModelNode |
| Import existing model | TripoImportModelNode (for re-texture / re-rig of an existing 3D asset) |
| Retopology | TripoRefineNode |
| Texturing | TripoTextureNode (incl. PBR) |
| Rigging | TripoRigNode |
| Retarget | TripoRetargetNode |
| Export | TripoConversionNode → TrimeshSave |

**P1 variants** (P1Text/P1Image/P1Multiview): newer generation — expose `output_mode`, `auto_size`, `compress_geometry`, `export_uv`, `face_limit`. **P1 is the recommendable starting point** over the v1 `TripoTextToModelNode` if credits aren't a concern. I'll verify which `output_mode` options a P1 node accepts on the live API (dynamic combo, hence only resolvable at runtime).

---

## 4. Extras installed (secondary experiments)

- **UniRig** (rigging/animation on the server): `UniRigAutoRig`, `UniRigExtractSkeletonNew`, `UniRigApplySkinningMLNew`, `UniRigApplyAnimation`, `UniRigExportPosedFBX`. Needs a `UNIRIG_MODEL` checkpoint — free, and an alternative to Tripo rigging.
- **Gaussian Splats (3DGS)**: `File3DToSplat`, `RenderSplat`, `SplatToMesh`, `TransformSplat`, `SaveGaussianSplat`, `TripoSplat*` — world/scan-based capture → 3D (the gap I flagged in the cheatsheet).
- **Texture tooling**: `TextureAnalyzer`, `TextureAtlasBuilder`, `TextureTiler`, `TextureOffset`, `TextureScaler`, `TextureEqualizer`, `SmartTextureResizer`, `BoundedImageBlend` — useful for PBR maps, blending, atlas building.
- **Cloud vision for reference** (for prompt/reference prep): Gemini/HiDream/Grok/Flux nodes — handy to pre-process reference images before feeding the 3D chain.

---

## 5. Next steps: open questions

1. **Set the Tripo API key** as a ComfyUI org secret so all Tripo nodes pick it up (`api_key_comfy_org`), and confirm billing/quota in the Tripo account.
2. **Build the chain wiring in the UI** (or I can draft the workflow JSON to POST to `/prompt` and iterate). Once it runs, save the exported JSON here.
3. **Decide the triangulation of tasks**: skip `Refine` if texture quality is insufficient (refine changes topology, so texture after refine). Compare P1 vs v1 output; try both seed controls.
4. **Test the texture stage with a separate prompt** (`texture_prompt`), and verify PBR exports produce the 4–5 emissive/metallic/normal/occlusion maps needed by your engine's material system.
5. **Compare against Hy3D fallback** for a simple prop where an image ref is cheaper than API credits.

---

*Open question for you:* want me to draft the Tripo workflow JSON so you can POST it and iterate (faster to debug from logs), or do you prefer building it visually in the UI first and then exporting? I'll start on whichever you choose.