# HANDOFF — AI Gamedev Tasks / ComfyUI Linux Migration

Author: Maxim's AI agent (this is a handoff for a coding agent running on the new Linux box).
Date: 2026-09-11. Read this first; then `AGENTS.md`, `comfyui/linux-migration.md`, `comfyui/linux-setup.md`.

## Repo
- GitHub private: `github.com/rg-software/ai-gamedev-tasks` (branch `master`).
- On this box: `~/Projects-Git/ai-gamedev-tasks` (clone if not present: `git clone https://github.com/rg-software/ai-gamedev-tasks.git`).
- Docs that matter: `3d/EXPERIMENTS.md` (verdicts+why), `3d/hy3d-knobs.md`, `3d/setup-hy3d.md`, `comfyui/workflow-file-format.md`.

## Environment (current known state on this box)
- Ubuntu 26.04.1 LTS, `rg_software@Beelink`, RTX 3090, driver 595.91.07 / CUDA 13.2.
- ComfyUI: `~/Projects-Git/ComfyUI`; venv `./venv/bin/python`; launch `./venv/bin/python main.py --listen --disable-api-nodes`.
- Python 3.11 venv; torch **2.11.0+cu128**; comfy-kitchen 0.2.33.
- ComfyUI-Login installed (login screen works). ComfyUI-Manager NOT installed yet.
- Access: `https://comfy.rt247a.ddns.me` (HTTP API; login cookie).
- Reachable node packs: Hy3D (30 nodes), MoGe (6). UniRig NOT installed.

## What the free 3D pipeline is (validated on Windows)
- **Shape:** `Hy3D_2_1SimpleMeshGen` + `hy3dgen/model.fp16.ckpt` (2.1, **nested .ckpt**). Flat `.safetensors` → `KeyError: 'model'`.
- **Multiview:** `Hy3DModelLoader` + `Hy3DGenerateMeshMultiView` + `hy3dgen/hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors` (**.safetensors** — shapegen loader re-nests it). Inputs must be uniform 512² (pad).
- **Retopology:** `Hy3DIMRemesh` (needs `pynanoinstantmeshes`).
- **Texture:** paint→delight→bake→apply. **Requires `custom_rasterizer`** (no CPU fallback in this wrapper).
- **Inpaint** after bake: `Hy3DMeshVerticeInpaintTexture → CV2InpaintTexture` (removes black-grid seams).
- Workflows: `3d/workflows/hy3d-full-workflow.json`, `hy3d-multiview-workflow.json` (+ scratch/).

## ⚠️ THE OPEN BLOCKER — `custom_rasterizer` won't compile on this box
Gates the **texture bake** only. Shape + multiview work WITHOUT it. Park it if it resists; 2D needs no kernel.

### The exact problem (all other build issues already solved)
- Upstream ships **Windows-only wheels**; no Linux wheel exists (checked PyPI — none).
- Coherent toolchain reached: **gcc-13** (`CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13`), nvcc via conda, torch 2.11+cu128.
- **nvcc 12.8** → glibc header clash: `cospi/sinpi/rsqrt` exception-spec incompatible with Ubuntu 26 glibc (`mathcalls.h`).
- **nvcc 13.2** → compiles past glibc, but torch `_check_cuda_version` hard-errors: `detected CUDA 13.2 vs PyTorch 12.8` (major mismatch → raise, no env-var bypass).

### Best next move (try in this order)
1. **Patch nvcc 12.8's `crt/math_functions.h`** to drop/guard the `noexcept` on `cospi/sinpi/rsqrt` — community fix for "cuda-12.8-on-new-glibc". Then 12.8 matches torch 12.8. Build with:
   ```
   cd ~/Projects-Git/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/hy3dgen/texgen/custom_rasterizer
   pip uninstall -y custom_rasterizer; rm -rf build dist
   export CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13
   export CUDA_HOME=$HOME/miniconda3/envs/cuda128   # nvcc 12.8
   export PATH=$HOME/miniconda3/envs/cuda128/bin:$PATH
   export TORCH_CUDA_ARCH_LIST='8.6'   # RTX 3090 = sm86
   pip install . --no-build-isolation
   ```
2. If that fails: **park texture**; run shape+multiview+2D. Revisit later (prebuilt wheel, or Ubuntu 22.04).
3. Avoid Arch for this — Ubuntu/Debian is the safer ML base (see `linux-migration.md`).

### After kernel (or if parked)
- Drop Hy3D weights (dropdowns currently empty):
  - `models/diffusion_models/hy3dgen/model.fp16.ckpt` (7.4GB) — `https://huggingface.co/tencent/Hunyuan3D-2.1/resolve/main/hunyuan3d-dit-v2-1/model.fp16.ckpt`
  - `models/geometry_estimation/moge_2_vitl_normal_fp16.safetensors` (630MB) — `https://huggingface.co/Comfy-Org/MoGe/resolve/main/geometry_estimation/moge_2_vitl_normal_fp16.safetensors`
  - `models/diffusion_models/hy3dgen/hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors` (4.9GB) — `https://huggingface.co/tencent/Hunyuan3D-2mv/resolve/main/hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors`
- Install `pynanoinstantmeshes` (retopo): `pip install pynanoinstantmeshes`.
- Install ComfyUI-Manager (custom_nodes clone).
- Run smoke checklist (`comfyui/linux-migration.md`): shape → (texture) → multiview → SDXL 2D.

## Priority for the agent
1. Verify current state (ComfyUI boots, node count, model dropdowns).
2. Try the rasterizer header-patch (one shot). If it works, texture is unblocked.
3. Regardless: drop in weights, install Manager + pynanoinstantmeshes, run shape + multiview smoke.
4. Set up 2D scenario (fully works, high value) — `2d/README.md` has the experiment plan.
5. If texture stays blocked, document clearly (E2b-on-Linux BLOCKED, why) and continue with 2D.
