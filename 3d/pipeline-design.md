# 3D Asset Pipeline — Robust Design

Free-first architecture. Every stage emits a GLB at a well-defined gate, so any free component can be swapped for a paid upgrade (and back) without redoing the chain.

Server: ComfyUI at `comfy.rt247a.ddns.me` (RTX 3090, 24 GB VRAM). All node names verified against live `/object_info`.

---

## 1. Architecture

```
     STAGE 0                     STAGE 1                 STAGE 2
  Text / concept art  ──▶  2D reference sheet   ──▶  Geometry (3D mesh)
                                                        │
                                                        ▼ GLB ◀── interchange gate
    STAGE 3                     STAGE 4                      │
  Clean / remesh  ──▶  Texture synth + bake   ──▶   PBR maps + single texture
                                                        │
                                                        ▼ GLB/FBX
    STAGE 5                     STAGE 6
  Rigging (optional) ──▶  Export  ──▶ game engine
```

**Compatibility rule:** pass GLB between stages. Stay behind any paid upgrade point until the free path is "good enough to know better." Then upgrade one stage at a time and re-validate at the next gate.

---

## 2. Recommended free path (nodes, verified)

| Stage | Task | Nodes |
|---|---|---|
| 0 | Concept | text → 2D (Flux.1 / HiDream / Gemini free tier) |
| 1 | Reference | generate clean front view; **improvement:** 3–6 view sheet (front/left/right/back) for multi-view conditioning |
| 2 | **Geometry** | `Hy3D_2_1SimpleMeshGen` (image→mesh, best free quality) — or `Hy3DGenerateMesh` + `Hy3DVAEDecode` for 2.1 full pipeline |
| 2a | Geometry alt | `MoGeInference` → `MoGePointMapToMesh` → `MESHToTrimesh` (fast props, lower fidelity) |
| 3 | Clean / remesh | `Hy3DPostprocessMesh` → `Hy3DIMRemesh` (target face count) |
| 4 | **Texture** | `Hy3DRenderMultiView` (nvdiffrast) → `Hy3DSampleMultiView` (paint model) → `Hy3DDelightImage` (remove baked shading) → `Hy3DBakeFromMultiview` (bake onto mesh) |
| 4b | PBR maps | `Hy3DGetMeshPBRTextures` (base_color / emissive / metallic_roughness / normal / occlusion) |
| 5 | Rigging (free) | `UniRigAutoRig` (+ `UniRigExportPosedFBX`) |
| 6 | Export | `Hy3DExportMesh` / `TrimeshSave` (GLB → engine) |

**One-liner pipeline** (image in → GLB out):
```
2D ref → Hy3D_2_1SimpleMeshGen → Hy3DPostprocessMesh → Hy3DRenderMultiView
      → Hy3DSampleMultiView → Hy3DDelightImage → Hy3DBakeFromMultiview
      → Hy3DGetMeshPBRTextures (or straight) → Hy3DExportMesh (GLB)
```

---

## 3. Upgrade paths (paid drop-ins, per stage)

Because GLB is the gate, each free stage has a direct paid substitute:

| Stage | Free (this doc) | Paid upgrade | Compatibility |
|---|---|---|---|
| 2 Geometry | Hy3D / MoGe | `TripoTextToModelNode` / `TripoP1TextToModelNode` | direct replacement; GLB unchanged |
| 3 Clean | Hy3DPostprocess + Remesh | `TripoRefineNode` (v1.4 only), `TripoConversionNode` (quad) | direct |
| 4 Texture | paint + delight + bake | `TripoTextureNode` | direct |
| 5 Rigging | UniRig | `TripoRigNode` | direct |
| 6 Export | Hy3DExportMesh | `TripoConversionNode` (FBX preset) | direct |

**The key bridge — reuse a free GLB in a paid stage:**

```
[free stage → GLB] → TripoImportModelNode → MODEL_TASK_ID → TripoTextureNode / TripoRigNode / TripoConversionNode
```

This is the "start free, keep compatible" loop: generate geometry free (Hy3D), then pay only for the texture/rig upgrade if quality demands it. Verify: `TripoImportModelNode` input `model_3d: FILE_3D_GLB` (present), output `model task_id: MODEL_TASK_ID` (present).

Reverse is also true: any paid Tripo GLB can be fed back to Hy3D for remesh/postprocess.

---

## 4. Setup requirements (free path)

| Item | Where | Notes |
|---|---|---|
| Hy3D 2.1 base checkpoint | server `models/diffusion_models/` | **not present** — must be uploaded (multi-GB). This is the one-time blocking item. |
| Hy3D 2.1 VAE | server `models/vae/` | same, required for `Hy3DVAEDecode` |
| Paint model (texture) | auto-downloaded by `DownloadAndLoadHy3DPaintModel` | `hunyuan3d-paint-v2-0` / `-turbo`, on first queue |
| Delight model | auto-downloaded by `DownloadAndLoadHy3DDelightModel` | `hunyuan3d-delight-v2-0` |
| MoGe weights | auto-downloaded by `LoadMoGeModel` | fast fallback for props |
| UniRig model | auto-downloaded by `UniRigLoadModel` | only if rigging needed free |

Node packages assumed present: ComfyUI-3D-Pack (Hy3D/Trimesh nodes), comfyui-unirig, ComfyUI-3D-Comfy (MoGe). Install missing ones in ComfyUI-Manager from the server.

---

## 5. Decisions / things to weigh

- **Hy3D vs MoGe for geometry:** Hy3D = higher fidelity, needs the big base checkpoint, slower. MoGe = fast, tileable, good for props/scan-like capture, auto-downloads. Start MoGe for experimentation, move to Hy3D for real assets.
- **Bake or export channel maps?** Bake = single textured GLB (fast, Blender-friendly). Export channels via `Hy3DGetMeshPBRTextures` = 5 maps for engine PBR. Decide by target engine.
- **Remesh before or after bake?** Remesh first (fewer faces = cheaper bake, cleaner topology); re-check vertex count vs texture resolution.
- **Seeds:** keep deterministic seeds per stage; a fixed seed makes each paid/free swap comparable.

---

## 7. Unity target — artifact conventions

End goal is Unity, so every export decision is made with Unity's importers in mind.

| Asset type | Format | Unity importer |
|---|---|---|
| Rigged / animated character | **FBX** (Mixamo skeleton preset) | FBX Importer (built-in) — best in-engine rigging, no add-on material work |
| Static prop / environment | **GLB** (binary glTF) | glTF importer (built-in) or runtime via glTFast / Trinio |
| Editor placement | OBJ/PLY/STL | built-in primitive importers |
| Collada | DAE | Collada importer only — avoid |
| USDZ | — | not supported by Unity; avoid |

**Unity-specific export flags (set on `TripoConversionNode` / Hy3D export):**
- `fbx_preset = "mixamo"` for characters (Unity's FBX importer rigs are Mixamo-skeleton compatible). `blender`/`3dsmax` presets are for other DCCs.
- `force_symmetry = true` when generating bipedal characters — rigging/proportions come out cleaner and import predictably.
- `flatten_bottom = true` + `pivot_to_center_bottom = true` for props/environment pieces — places the mesh at y=0 with sensible pivot in the Editor.
- `with_animation = true` when you want the generated idle/walk baked as an FBX animation clip for review in Unity.

**PBR maps → Unity Standard/URP shader:** the 5 channels from `Hy3DGetMeshPBRTextures` map directly:

| Hy3D channel | Unity Standard channel |
|---|---|
| base_color | Albedo |
| normal | Normal (RG) |
| metallic_roughness | Metallic (B) + Roughness (G) — split in Photoshop / imBatch |
| emissive | Emission |
| occlusion | optional — use as alpha/mask or bake into albedo |

glTF KHR2 (the material model Unity's glTF importer reads) uses the *same* channel set (baseColor/metallic/roughness/normal/occlusion/emissive), so a PBR-baked GLB lands almost 1:1; URP material import just needs a split of the metallic_roughness composite.

**Recommendation:** export characters as **FBX (mixamo, rigged)** and props/environments as **GLB with PBR baked or channel-mapped**. This keeps everything on Unity's happy path and avoids re-export loops.

---

## 8. Experiment log

See `EXPERIMENTS.md` — one table, one row per run, columns: `date · variant (free/paid) · stage under test · input · params · GLB path · verdict · next`

Seed experiments queued:
- E1: MoGe chain, single photo → GLB (validate setup, ~2 min)
- E2: Hy3D full chain text→6-view→texture→PBR (validate weights + texture quality)
- E3: free GLB → TripoImport → TripoTexture (validate the paid bridge, cost check)
- E4: UniRig on a free GLB → FBX (rigging fit)