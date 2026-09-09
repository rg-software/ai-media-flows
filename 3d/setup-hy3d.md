# Hy3D (Hunyuan 2) via kijai/ComfyUI-Hunyuan3DWrapper — install & run

**No ComfyUI-3D-Pack needed.** The wrapper (`comfyui-hunyuan3dwrapper`) is already loaded on the server (`C:\Projects-Git\ComfyUI\ComfyUI\custom_nodes\comfyui-hunyuan3dwrapper`), so this is the low-friction path.

The main workflow (verified against wrapper source + official example `hy3d_example_01.json`), in `workflows/`:
- `workflows/hy3d-full-workflow.json` — shape **+ AI texture + delight + bake** → textured GLB (paint & delight model weights auto-download on first run). Emits **two** GLBs per run: `3D/Hy3D_untextured.glb` (right after shape postprocess, i.e. the "raw" 3D) and `3D/Hy3D_textured.glb` (final) — so you can inspect the source → untextured → textured progression.

A shape-only quick-check workflow (image → mesh → GLB, no texture) exists in `workflows/scratch/hy3d-shape-workflow.json` for validating the model/checkpoint in isolation — it's superseded by the full workflow's mid-export but kept for debugging.

---

## Step 1 — Place the base checkpoint (the ONLY manual download)

> **CRITICAL — use the 2.1 combined `.ckpt`, not 2.0 and not the flat `.safetensors`.**
> - `Hy3D_2_1SimpleMeshGen` builds the **2.1** model from `dit_config_2_1.yaml` (`HunYuanDiTPlain` with `x_embedder`/`t_embedder`/`blocks.*`/`moe`). A v2-0 checkpoint fails with a state_dict size mismatch (`final_layer.linear` `[64,1024]` vs `[64,2048]`).
> - The loaded file must be **nested** (`ckpt['model']`/`ckpt['vae']`/`ckpt['conditioner']`). ComfyUI `load_torch_file` returns a *flat* dict for `.safetensors`, but a *nested* one for `.ckpt`. Use the Tencent original `.ckpt`.

Wrapper reads from `ComfyUI/models/diffusion_models/`. The official workflow uses a `hy3dgen/` subfolder. Use this exact file (7.4 GB):

```
ComfyUI/models/diffusion_models/hy3dgen/model.fp16.ckpt   (from tencent/Hunyuan3D-2.1, 7,366,389,768 bytes)
```

Download (verified 200):
```
https://huggingface.co/tencent/Hunyuan3D-2.1/resolve/main/hunyuan3d-dit-v2-1/model.fp16.ckpt
```
Server shell:
```
cd C:\Projects-Git\ComfyUI\ComfyUI\models\diffusion_models
mkdir hy3dgen && cd hy3dgen
curl -L -O "https://huggingface.co/tencent/Hunyuan3D-2.1/resolve/main/hunyuan3d-dit-v2-1/model.fp16.ckpt"
```
Then pick `hy3dgen\model.fp16.ckpt` in the `Hy3D_2_1SimpleMeshGen` model dropdown (default in the shipped workflows). You can delete the old v2-0 `model.ckpt` / `hunyuan3d-dit-v2-0-fp16.safetensors` files in this folder to reclaim ~11 GB.

## Step 2 — Import & run

1. Import `workflows/hy3d-full-workflow.json` (or the shape-only `workflows/scratch/hy3d-shape-workflow.json` to validate just the model).
2. Point `LoadImage` at your house image (e.g. `assets/house-reference.png`, upload to server `input/` first).
3. On `Hy3D_2_1SimpleMeshGen`, confirm the model dropdown shows `hy3dgen\model.fp16.ckpt`.
4. Queue. Shape gen ~1–2 min on the 3090; GLB lands in `output/3D/Hy3D/`.

**What "works" looks like:** rotate the `Preview3D`/imported GLB and the **back of the house is present** — Hy3D is generative, so it completes the full 360° form from the single image. That's the whole point vs MoGe.

## Step 3 — Full texture (once shape passes)

Import `workflows/hy3d-full-workflow.json` instead. Same first three steps, then:
- `DownloadAndLoadHy3DPaintModel` → auto-downloads `hunyuan3d-paint-v2-0` (diffusers) on first run.
- `DownloadAndLoadHy3DDelightModel` → auto-downloads `hunyuan3d-delight-v2-0`.
- Output: `output/3D/Hy3D_textured/*.glb` (PBR-baked, Unity-ready).

### Texture-stage widgets (sensible defaults from the official example)
| Node | Widgets (in order) |
|---|---|
| Hy3DRenderMultiView | `1024, 2048, world` |
| Hy3DSampleMultiView | `view_size=512, steps=30, seed(123/fixed)` |
| Hy3DDelightImage | `steps=50, width=512, height=512, cfg=1.0, seed=42` |
| Hy3DExportMesh (textured) | `3D/Hy3D_textured, glb, save` |

---

## Tuning notes
- **steps** (SimpleMeshGen/GenerateMesh): 30 = fast, 50 = quality.
- **octree_resolution**: 384 default; raise to 512 for finer meshes (slower).
- **Reduce faces** (`Hy3DPostprocessMesh` max_facenum=50000) keeps GLB sizes sane for Unity.
- Background level in the source image affects **delight** quality a lot (README note): pure-black or fully-white backgrounds can tint results — mid-gray is safest.

## Server dependencies (pip)

The wrapper itself loads already, but the **retopology** stage (`Hy3DIMRemesh`) needs an extra pip package not in the wrapper's requirements:

```
C:\Projects-Git\ComfyUI\python_embeded\python.exe -m pip install pynanoinstantmeshes
```

(Remesh imports this at run time; without it, `Hy3DIMRemesh` throws `ImportError: pynanoinstantmeshes not found`.)

## If shape works but the texture stage errors
Paste the console error. Most likely causes: first-run model download interrupted, or the seed/`normal_space` widget values need a manual confirm in the UI (I marked the ones I derived from source in Step-3 table).
