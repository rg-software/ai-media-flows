# 3D Asset Generation: scenario index

Goal: generate game-ready 3D assets (props, characters) with a mix of free and paid tools on ComfyUI. Everything here operates against the remote ComfyUI server (`comfyui/README.md`).

## How AI 3D actually looks in practice (the ladder)

The repo mirrors the realistic tiers, not a toy pipeline. Most real work is **Tier 1**; tiers add cost/accuracy only when the asset justifies it.

- **Tier 1 — workhorse (props/env, greybox, iteration):** single prompt or single image → 3D. The model *hallucinates* the back/sides. Cheap, fast, "good enough for a placeholder." (→ `hy3d-full`)
- **Tier 2 — accuracy-critical (characters, product):** start from a **2D turnaround (front/side/back)** → multiview 3D gen. *Practice detail:* the turnaround is usually **AI-generated** (concept art → multi-view diffusion: SV3D / Zero123++ / MV-Adapter / Hunyuan mv), not hand-drawn — hand-drawing 4 clean ortho views is reserved for hero assets. The multiview 3D generator is the "use the views" half. (→ `hy3d-multiview`)
- **Tier 3 — studio/production loop:** concept → turnaround → base gen → **retopology** → **PBR texture** (Substance or AI) → **rig** → engine. AI does base + often texture; humans do cleanup/rig/final. This is the *free-first + pay-per-stage* design's whole point. (→ `hy3d-tripo-swap`)

**Game-relevant rule of thumb:** env props = high-volume, cheap → single image/prompt. Characters = low-volume, high-value → turnaround + retopo + rig justifies the cost.

## The design in one breath

**Free-first, GLB-compatible.** Architecture doc: [`pipeline-design.md`](pipeline-design.md). The core idea:
- Every pipeline stage emits a **GLB** → any free component can be swapped for a paid upgrade (and back) without redoing the chain.
- **Free path (Hy3D):** shape → UV-wrap → paint → delight → bake → textured GLB.
- **Paid bridge (Tripo):** take a free GLB → `TripoImportModelNode` → texture/rig/export when you want paid polish on the same geometry.

## Workflow map

Only the **valuable** pipelines live in `workflows/`. Scaffolding/one-off experiments moved to `workflows/scratch/` (see below).

| Workflow (`workflows/`) | What it does | Cost | Status |
|---|---|---|---|
| `hy3d-full-workflow.json` | image → shape → postprocess → **IMRemesh (retopology)** → UV-wrap → paint → delight → bake. **Dual output:** `Hy3D_untextured.glb` (remeshed geometry checkpoint) + `Hy3D_textured.glb` (final) — you see the source→untextured→textured progression in one run | free | **PASS (E2a/E2b/E2c)** |
| `hy3d-multiview-workflow.json` | 4 view images (front/left/right/back) → **mv checkpoint** → multi-view shape → retopology → texture tail → dual GLB | free | **ready to run; needs mv checkpoint** (`hy3dgen\hunyuan3d-dit-v2-mv-fast\model.fp16.safetensors` from `tencent/Hunyuan3D-2mv`) |

**Viewing a run:** every 3D flow ends in a viewer node — `Preview3D` on both Hy3D exports, `UniRigPreviewRiggedMesh` on the rig — so the mesh is orbited **inside the ComfyUI canvas**; a dedicated 3D app is not needed to check a run (the GLB/FBX is still written to `output/` for Blender/Unity). The viewers load from `output/`, which is why they take the export node's own path output; `Load3D`, the node that feeds a model *into* a graph, reads `input/3d/` instead. The 3D viewer is a frontend **Beta** feature, enabled by default (*Settings → 3D → Enable 3D Viewer*). Node-level detail: `../comfyui/README.md`.

### `workflows/scratch/` (one-off scaffolding: archive, don't maintain)

| File | Why it existed | Worth keeping? |
|---|---|---|
| `hy3d-shape-workflow.json` | shape-only test (E2a) — **superseded**: the full workflow's untextured mid-export does this now | no |
| `moge-free-chain.json` | MoGe measurement (E1) — established "front-only by design" then we switched to generative Hy3D | no |
| `moge-unirig-free-chain.json` | MoGe + UniRig rigging experiment | no (rigging via E4 later, on Hy3D mesh) |
| `tripo-chain-workflow.json` | paid Tripo pipeline from text | yes — re-enable when Tripo API key available (E3) |
| `tripo-bridge-workflow.json` | paid GLB→Tripo bridge (validated schema) | yes — same as above |
| `hunyuan21-full-example.json` | upstream official Hy3D 2.1 example (reference) | keep as reference when debugging new pre/post stages |

## Docs

| Doc | What it answers |
|---|---|
| [`pipeline-design.md`](pipeline-design.md) | Architecture: free path per stage, paid drop-ins, the GLB gate, Unity export conventions. |
| [`setup-hy3d.md`](setup-hy3d.md) | Hy3D-specific install: which checkpoint, where, the two official workflows' widget values, tuning knobs. |
| [`hy3d-knobs.md`](hy3d-knobs.md) | Every Hy3D node's knobs + defaults + "symptom → knob" table. |
| [`hy3d-tripo-swap.md`](hy3d-tripo-swap.md) | **Hy3D ↔ Tripo swap guide** — where the swap points are, how to bridge a Hy3D GLB into Tripo texturing/rigging, cost notes, gotchas. |
| [`cookbook-3d-assets.md`](cookbook-3d-assets.md) | Node signatures reference (superseded by pipeline-design; kept for raw node details). |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log E1–En with verdicts + the *why*. |

## Key server-side requirements (this scenario only)

- **Hy3D base checkpoint** (7.4 GB, one-time): `ComfyUI\models\diffusion_models\hy3dgen\model.fp16.ckpt` (see `setup-hy3d.md`).
- **Multi-view checkpoint** (mv, for `hy3d-multiview`): `ComfyUI\models\diffusion_models\hy3dgen\hunyuan3d-dit-v2-mv-fast\model.fp16.safetensors` from `tencent/Hunyuan3D-2mv` (4.9 GB).
- **`custom_rasterizer`** compiled cp313 `.pyd` in `python_embeded\Lib\site-packages\` (texture bake) — see `../comfyui/environments.md` E2b case study + `EXPERIMENTS.md` E2b.
- **`pynanoinstantmeshes`** pip package (retopology; see `setup-hy3d.md`).
- Paint/delight models auto-download on first use (HuggingFace).
- Tripo requires an API key on the server for the paid workflows.

## Next candidates (from pipeline-design.md)

- **E2d** — multiview (`workflows/hy3d-multiview-workflow.json`) — needs the mv checkpoint downloaded.
- **E3** Tripo bridge on a free Hy3D GLB (paid texture/rig comparison). See `hy3d-tripo-swap.md`.
- **E4** UniRig on a free GLB → FBX.
- **E5** Import the textured GLB into Unity (glTF importer) — the "strive for Unity-compatible artifacts" goal.

