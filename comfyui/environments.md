# ComfyUI environments: comfy-env and pixi isolation

The root problem it solves: **ComfyUI shares one Python for all custom nodes, but real-world node packs need conflicting Pythons/torchs/CUDA.**

Repo tool: [`comfy-env`](https://github.com/PozzettiAndrea/comfy-env) — already installed on the server (v0.4.3+) and used by `comfyui-unirig`. It provides:
- **Per-node isolated Python environments** (pixi + uv under the hood) running as persistent subprocesses.
- **CUDA wheel resolution** (flash-attn, spconv, ...) from prebuilt wheels — no CUDA toolkit/compiler needed on the box.

## The "standard" landscape (2026-09 snapshot)

Two distinct efforts — don't conflate:

1. **Per-node isolation TODAY = comfy-env** (third-party, this doc). Chronically unchanged; many heavy packs ship as comfy-env pack (UniRig, TRELLIS2, SAM3, GeometryPack...).
2. **Provisioning / fresh-install = Comfy-Org/ComfyUI-Standalone-Environments** — prebuilt per-OS/Python/torch/CUDA environment archives consumed by **ComfyUI Desktop 2.0** (beta; repo desc "standalone environment definitions consumed by ComfyUI Desktop 2.0 to provision Python environments"). Active & shipping since mid-2026 (`env1` release). Serves from R2, driven by `torch-index-stacks.json`. **Does not** (yet) do per-*node* isolation within one install — a ComfyUI install gets one env. So for a mixed-node remote server like ours, comfy-env remains the per-node answer; the standalone-envs project is the thing that will make a *fresh* server trivial and the natural Linux-migration path (prebuilt Linux envs → no compile, no `.pyd` shipping).

## Core model

Two config files:

| Config | Role |
|---|---|
| `comfy-env-root.toml` (pack root) | node dependency mgmt, `[node_packs]`, `[types]`. **Never touches Python env.** |
| `comfy-env.toml` (a node dir) | isolation config: `python`, `[cuda]`, `[dependencies]`, `[pypi-dependencies]`, `[pypi-options]`. One pixi env per such file. |

Plus the standard triplet in the pack:
```python
# __init__.py
from comfy_env import register_nodes
NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = register_nodes()
WEB_DIRECTORY = "./web"
```
```python
# install.py
from comfy_env import install; install()
```
```python
# prestartup_script.py
from comfy_env import setup_env; setup_env()
```
Build once: run the pack's `install.py` with the server Python. Envs land in comfy-env's pixi dir, named like `<pack>-<subdir>` (lowercased).

## Critical gotchas (hard-won)

1. **Config must be at the node pack ROOT** (`discover_config` reads `<node_dir>/comfy-env-root.toml` then `<node_dir>/comfy-env.toml`). `nodes/` subdir config only for *sub-node* isolation.
2. **`python = "3.12"` must be quoted** — unquoted TOML parses as float `3.1`.
3. **Torch family is pinned workspace-wide to the host** (`==2.11.*` for host 2.11.0+cu128) and mirrored into every env; the tool **strips** node torch entries (see `_strip_torch_family`). You cannot independently pick torch version in a single node config.
4. **Local wheels / URL deps**: pixi wants `[pypi-dependencies.X]` as a **table with a `url` key**; plain `file://` URLs and `@`-version specs both rejected. Even then `file://` fails ("URL scheme is not allowed") → use `find-links` (`[pypi-options] find-links = [{ path = "<abs dir>" }]`) with a plain `name = "*"` dep — but see gotcha 3 about torch.
5. Envs are **reproducible via `pixi.lock`** — re-run `install.py` to rebuild.
6. `cuda-wheels` (prebuilt repo) can serve CUDA packages *only* if the node declares them in `[cuda] packages` (then comfy-env uses a cuda-only override combo). A custom node like `custom_rasterizer` is not in that index.

## Reference commands **[Windows-era paths; Linux uses `venv/bin/python`]**
```
# build envs for all packs with config
python_embeded\python.exe <node>\install.py
# check envs on boot (comfy-env prints status)
[comfy-env] <pack>: 1 isolation env(s) ... [OK|MISSING -- run install.py]
```

## A repo tool's own env: the bpy pose renderer

`scripts/render_glb_poses.py` needs `bpy` (Blender as a Python module) - ~1.6 GB installed. It is an **opt-in repo dependency**, so it does not burden the normal tooling environment or ComfyUI's torch environment. `bpy==4.2.0` only publishes Python 3.11 wheels, so select Python 3.11 and give the pose renderer a separate uv environment (do not replace the repo's default `.venv`):

```bash
UV_PROJECT_ENVIRONMENT="$HOME/.cache/ai-gamedev-tasks/pose-render" uv run --extra pose-render --python 3.11 \
    scripts/render_glb_poses.py --glb ~/Projects-Git/ComfyUI/input/Knight.glb \
    --out ~/Projects-Git/ComfyUI/input/poses --clip Idle_Rig:0.5 --yaws 0,90,180 --gear 1H_Sword,Round_Shield
```

On Windows PowerShell, set `$env:UV_PROJECT_ENVIRONMENT` to a separate path (for example `$env:LOCALAPPDATA\ai-gamedev-tasks\pose-render`) before the same `uv run --extra pose-render --python 3.11 ...` command. The wheel exists for Linux, Windows, and macOS; the renderer is not tied to the box, but only its renders saved under ComfyUI's `input/` can be used by the next ComfyUI pixelation step without uploading them first. **Run-verified on Windows (2026-10-10):** `uv sync --extra pose-render --python 3.11` plus a 3-yaw 1024 render of the KayKit knight ran end-to-end locally (Cycles, ~15 s/frame, transparent RGBA PNGs exactly as documented); the PNGs were then uploaded to `input/poses/` (recreated - it had been cleaned) for the E24f sweep. Renders are headless (no `--background` needed with the bpy module) on **Cycles + CUDA**, and a GPU-context failure falls back to CPU by itself. The same pattern applies to any future repo tool with a heavy module: its own env, and the rebuild line written down here.
