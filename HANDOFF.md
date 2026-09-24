# HANDOFF: AI Gamedev Tasks (ComfyUI Linux Migration)

> **UPDATE 2026-09-11 (second agent pass):** The rasterizer blocker is **resolved** and the full smoke checklist **PASSES on Linux** — shape, multiview, full single-image texture, MoGe, and SDXL 2D all verified (see `3d/EXPERIMENTS.md` L1/L2 + PENDING). Head to **"After the build"** below for the current state; the original blocker notes follow for the record.

Author: Maxim's AI agent (this is a handoff for a coding agent running on the new Linux box). Date: 2026-09-11. Read this first; then `AGENTS.md`, `comfyui/linux-setup.md`.

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

## ⚠️ ORIGINAL OPEN BLOCKER: `custom_rasterizer` won't compile: **RESOLVED 2026-09-11**

**The texturing blocker is UNBLOCKED.** The exact "best next move" in the original doc worked. Texture bake is verified end-to-end (textured GLBs from both `hy3d-full` and `hy3d-multiview`, see `3d/EXPERIMENTS.md` L1).

### What actually worked (record for rebuilding)
1. Patch **nvcc 12.8**'s `<conda128>/targets/x86_64-linux/include/crt/math_functions.h`: add `noexcept` to the 6 decls that glibc 2.41 (`bits/mathcalls.h`) redeclares `noexcept(true)` — `cospi/cospif/rsqrt/rsqrtf/sinpi/sinpif` (lines ~597/621/2556/2579/2601/2623). nvcc 12.8 emits `exception specification is incompatible` otherwise.
   - Note: the original note says "drop/guard the noexcept" — the class of fix was right; what works on this glibc is **adding** `noexcept` to the CUDA header to match glibc, not removing it.
2. Build (all linux-forward env on purpose):
   ```
   cd ~/Projects-Git/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/hy3dgen/texgen/custom_rasterizer
   pip uninstall -y custom_rasterizer; rm -rf build dist
   export CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13
   export CUDA_HOME=$HOME/miniconda3/envs/cuda128
   export PATH=$HOME/miniconda3/envs/cuda128/bin:$PATH
   export TORCH_CUDA_ARCH_LIST='8.6'
   pip install . --no-build-isolation
   ```
   → built `custom_rasterizer-0.1.0+torch2110.cuda128-cp311-cp311-linux_x86_64.whl` and installed cleanly; `import custom_rasterizer_kernel` OK.
3. **Do NOT use nvcc 13.2** even though the driver is CUDA 13.2 — torch 2.11+cu128 hard-errors on the major-version mismatch at import. 12.8 matches torch's 12.8.

### Runtime deps for the wrapper that were NOT in its requirements.txt (install before running)
```
pip install omegaconf pyrootutils timm rembg onnxruntime pynanoinstantmeshes
```
(`rembg` without `onnxruntime` first use downloads `bria-rmbg-2.0.onnx` ~1GB to `~/.rembg/` and **hangs silently** if the backend import fails — the original "ComfyUI won't stop" symptom was exactly this. Install onnxruntime first.)

For the **textured render** (`Hy3DNvdiffrastRenderer`, the reliable texture check — E7):
```
pip install ninja nvdiffrast                       # nvdiffrast from PyPI builds the CUDA plugin at install time
pip install "utils3d @ git+https://github.com/EasternJournalist/utils3d.git@580474822b0a72098f687dbe820c38f1214edfec"
```
- Pin `utils3d`: upstream **master renamed `intrinsics_from_fov_xy` → `intrinsics_from_fov`**, so `Hy3DNvdiffrastRenderer` dies with `module 'utils3d.torch' has no attribute 'intrinsics_from_fov_xy'`. Commit `5804748` (2025-08-31) is the last one that still defines it.
- Build env for nvdiffrast = the `custom_rasterizer` recipe (`CUDA_HOME=~/miniconda3/envs/cuda128`, `CC=gcc-13`, `TORCH_CUDA_ARCH_LIST=8.6`); it is a `CUDAExtension` compiled **at install time**, so no nvcc is needed at runtime.
- **Restart `comfyui` after installing any of these**: a module imported earlier in the running process stays in `sys.modules`, so the new code is not picked up (`No module named` → `has no attribute` → correct, in that order, if you install while it runs).

### Weights and nodes (current state: all present)
- 3 weights already on disk (dropdowns populated): `hy3dgen/model.fp16.ckpt`, `hy3dgen/hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors`, `moge_2_vitl_normal_fp16.safetensors`.
  - (Re-download sources, if ever needed: `tencent/Hunyuan3D-2.1` → `hunyuan3d-dit-v2-1/model.fp16.ckpt`; `tencent/Hunyuan3D-2mv` → `hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors`; `Comfy-Org/MoGe` → `geometry_estimation/moge_2_vitl_normal_fp16.safetensors`.)
- Paint/delight diffusers models **auto-download on first texture run** → `models/diffusers/hunyuan3d-{paint,delight}-v2-0/` (~14GB total).
- `pynanoinstantmeshes` installed. **ComfyUI-Manager v3.41 installed** (contrary to this doc's "NOT installed"). KJNodes (`ImageResizeKJv2`) installed for multiview.
- Play checkpoints: **2D checkpoints were empty** (not carried from Windows); **SDXL base 1.0 downloaded 2026-09-11** into `models/checkpoints/`.

### Schema drift to know (Linux wrapper is newer than the saved workflows)
The workflow JSONs are fine in the GUI (frontend fills defaults), but **API-only submissions** need these fixes:
- `Hy3DModelLoader`: `attention_mode` is now `['sdpa','sageattn']` combo (was extra widget).
- `Hy3DGenerateMeshMultiView.scheduler` → named now (`FlowMatchEulerDiscreteScheduler`), not `'fixed'`.
- `Hy3DSampleMultiView.scheduler` is now **link-only**; old `widgets_values` `'fixed'` shifts sideways → ends up as `denoise_strength='fixed'` (float cast error). Drop the stale scheduler widget value.
- Keep model paths forward-slash (workflow files have `\\`).

### Original doc (kept for context)
- Upstream ships **Windows-only wheels**; no Linux wheel existed on PyPI (checked).
- `nvcc 13.2` compiles past glibc but torch rejects it (#35) — still true, use 12.8.

## Priority for the agent
1. ✅ Verify current state (ComfyUI boots, node count, model dropdowns) — **done L1**.
2. ✅ Try the rasterizer header-patch (one shot). If it works, texture is unblocked — **it worked, texture UNBLOCKED**.
3. ✅ Drop in weights, install Manager + pynanoinstantmeshes, run shape + multiview smoke — **all PASS on Linux**.
4. ✅ Set up 2D scenario (fully works, high value) — **SDXL base art PASS (E1)**; ControlNet weights still need pulling.
5. ✅ **UniRig rigging retest — PASS (2026-09-11, E4-L).** `ComfyUI-UniRig` (PozzettiAndrea) installed via `python install.py`; self-contained pixi env `~/.ce/envs/unirig-nodes` with **bpy 4.2 LTS (conda)** — the Windows `bpy` DLL blocker is fully gone. Rigged `realistic_male_character.glb` → Mixamo-normalized FBX (Kaydara FBX v7400) in ~90s incl. weight download. `unirig-humanoid-workflow.json` updated to current node names. Caveat: spconv warns sm86 (3090) not in its prebuilt set — non-fatal.
6. ⬜ **Next open items:**
   - Rig a **Hy3D/MoGe-generated humanoid** (not just the pack test asset); try `UniRigApplyAnimation` with the bundled Mixamo animation templates (e.g. `Hip_Hop_Dancing.fbx`, `Breakdance.fbx`).
   - 2D E2 (ControlNet) + E3–E7 per `2d/README.md`.
   - E3 Tripo bridge still needs an API key.
   - Consider packaging the patched `custom_rasterizer` as a manylinux wheel so no recompile is needed on the next box (the successful build produced a cp311 wheel in the build dir).
