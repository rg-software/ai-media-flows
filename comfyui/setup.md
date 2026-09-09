# ComfyUI — server install, run, caveats, Linux migration

Target audience: someone (a future me) rebuilding this ComfyUI from scratch, possibly on Linux. Facts current as of the initial exploration.

## What runs where

- **Server** (RTX 3090, Windows): `https://comfy.rt247a.ddns.me` — the GPU host. Owns `C:\Projects-Git\ComfyUI\` (embedded Python, `custom_nodes\`).
- **Client** (this machine, laptop 6 GB): just the browser. No local inference for 3D.

## Server facts (verified 2026-09)

| Item | Value |
|---|---|
| ComfyUI path | `C:\Projects-Git\ComfyUI\ComfyUI` |
| Python | `C:\Projects-Git\ComfyUI\python_embeded\python.exe` — **3.13.12** |
| Torch | **2.13.0+cu130** |
| GPU | RTX 3090, 24 GB |
| ComfyUI version | v0.27.0 |
| Login | ComfyUI-Login plugin — `POST /login`, cookie `AIOHTTP_SESSION` |
| Extra search paths | `c:\Projects-Git\sd.webui\webui\models\...` (checkpoints/controlnet) |

## Installing / updating custom nodes

- ComfyUI-Manager (v3.40) is installed on the server.
- **Caveat:** several big packs use aggressive `install.py` that assume CUDA toolkit / a C toolchain on PATH. On this server (no CUDA toolkit), those fail at import — see `environments.md`.
- Update pitfall: a pack update may change node class names. The server's own `object_info` is the ground truth for what's actually registered.

## Model weights: where they live

(`comfyui` general note — scenario-specific exact files in each scenario's setup doc.)

- Diffusion checkpoints: `ComfyUI\models\diffusion_models\`
- VAE: `ComfyUI\models\vae\`
- Folders are often empty until you drop weights in; several nodes **auto-download** from HuggingFace on first run (see `environments.md`).

## Known environment constraints (Windows-specific)

1. **No CUDA toolkit / nvcc on the server.** Native wheel-compiling nodes (`PyMCubes`, `install.py` CUDA checks) fail. Workaround: ship prebuilt wheels/`.pyd`, or isolate via `comfy-env` (see `environments.md`).
2. **Python 3.13 host** — cp312 wheels do not load. Extensions must be built for cp313 (or nodes isolated into a 3.12 pixi env).
3. **Torch 2.13.0+cu130 has no cp312 Windows wheels** — a 3.12 isolated env can't mirror host torch; it must use a torch that exists for cp312 on Windows (the wall that blocked the Hy3D texture node, see `3d/EXPERIMENTS.md` E2b).

## Linux migration notes

Migration should simplify most of the above. Planned facts to preserve:

- Install torch with CUDA via `pip install torch --index-url https://download.pytorch.org/whl/cu{ver}`.
- `custom_rasterizer` prebuilt wheels exist for Linux in the upstream repo (`custom_rasterizer-0.1-cp312-...-manylinux*.whl`) → no `.pyd` shipping needed.
- `comfy-env` targets `~/.ce` (see `environments.md`); pixi is cross-platform.
- ComfyUI-Manager works the same; `install.py`-based packs more likely to succeed on Linux (proper toolchain available).
- Autodownload of weights is platform-independent.

## Random operational notes

- `distutils.use_network`-style warnings and `object_info` 302s are normal (login-stage). 
- When a node shows red / "missing", first check it against `/object_info` before assuming the file is wrong.
- The server occasionally restarts itself (ComfyUI-Manager "legacy mode" restarts); refresh the browser after.