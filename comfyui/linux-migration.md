# ComfyUI → Linux migration checklist

Purpose: when we move the ComfyUI server to Linux, get it back to today's capability **fast** and *without* repeating the Windows pain (MSVC compile, `.pyd` shipping, bpy DLL hell).

Guiding principle: **carry the knowledge, re-provision the environment.** Workflows, weights, and docs are portable; the Windows env is not (and shouldn't be transplanted).

## Carries over 100% (no work)

| Thing | Where | Notes |
|---|---|---|
| Workflow JSONs | `3d/workflows/*.json` (+ scratch) | platform-agnostic; same `models/` relative paths |
| Knowledge base | this repo (`comfyui/`, `3d/`, `2d/`) | schemas, knobs, verdicts, experiment log |
| `/object_info` workflow | — | same on any ComfyUI |
| Model weights | `models/diffusion_models/hy3dgen/*` (7.4GB Hy3D ckpt, mv ckpt+safetensors), `models/checkpoints/*` (SDXL etc.) | re-download/replace into same layout; commands in `3d/setup-hy3d.md` unchanged |

## Carries over but needs re-environmenting (expected work)

| Item | Windows (today) | Linux (target) |
|---|---|---|
| torch + CUDA | embedded py 3.13, torch 2.13+cu130 | `pip install torch --index-url https://download.pytorch.org/whl/cu128` (or cu130) |
| ComfyUI | `C:\Projects-Git\ComfyUI` | `git clone` + install from source |
| ComfyUI-Manager | v3.40 | same, cross-platform |
| `custom_rasterizer` | **local MSVC 2022 compile → ship `.pyd`** (E2b saga) | **prebuilt manylinux wheel upstream** → `pip install custom_rasterizer...whl`, no compile |
| comfy-env isolation | `%LOCALAPPDATA%\Programs\comfy-env` | `~/.ce`; packs (unirig etc.) re-provision |
| **UniRig rigging (E4 blocker)** | blocked: `bpy` DLL load fails on Windows | **bpy is a conda package on Linux** → E4 likely *works* — re-test here |
| `pynanoinstantmeshes` (retopo) | pip (works) | same pip |

## Do NOT transplant from Windows

- `python_embeded` venv / any `.pixi`/comfy-env env dirs — rebuild clean.
- Hardcoded `C:\Projects-Git\ComfyUI\...` paths in shell commands (they're in our notes, not workflows — workflows use relative `models/...`).
- The compiled `.pyd` files — replace with wheels/Linux builds.

## What to do now (cheap) to make migration faster later

- Keep `comfyui/setup.md` updated with the server runtime facts (versions) so we can match them.
- When migration happens: follow `3d/setup-hy3d.md` for weights + workflows, `comfyui/environments.md` for comfy-env, this file for the deltas.
- First Linux steps to verify: Hy3D shape → texture (custom_rasterizer via wheel), then **retest UniRig rigging** (the bpy wall should be gone).

## First-run smoke checklist on Linux

1. ComfyUI boots, `/object_info` shows Hy3D + MoGe nodes.
2. `hy3d-shape` (scratch) produces a GLB (weights + pipeline OK).
3. `hy3d-full` produces textured GLB (custom_rasterizer wheel OK).
4. `hy3d-multiview` runs (mv weights OK).
5. UniRig rigging — attempt again (E4 was Windows-blocked, not a code bug).
6. SDXL 2D base art (server already has the checkpoints to carry over).