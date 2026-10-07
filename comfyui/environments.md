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
Build once: `python_embeded\python.exe <node_dir>\install.py`. Env lands in `%LOCALAPPDATA%\Programs\comfy-env\.pixi\envs\<plugin>-<dir>`, named like `<pack>-<subdir>` (lowercased).

## Critical gotchas (hard-won)

1. **Config must be at the node pack ROOT** (`discover_config` reads `<node_dir>/comfy-env-root.toml` then `<node_dir>/comfy-env.toml`). `nodes/` subdir config only for *sub-node* isolation.
2. **`python = "3.12"` must be quoted** — unquoted TOML parses as float `3.1`.
3. **Torch family is pinned workspace-wide to the host** (`==2.13.*` for host 2.13.0) and mirrored into every env; the tool **strips** node torch entries (see `_strip_torch_family`). You cannot independently pick torch version in a single node config.
4. **CUDA index** derived from host torch (`whl/cu130`). If that index lacks a wheel for your env's python ABI, the whole env fails to solve. Concretely: **torch 2.13.0+cu130 has no cp312 Windows wheels** → any `python="3.12"` env requested with host torch cannot be built on this server. This is an upstream packaging gap, not fixable from config.
5. **Local wheels / URL deps**: pixi wants `[pypi-dependencies.X]` as a **table with a `url` key**; plain `file://` URLs and `@`-version specs both rejected. Even then `file://` fails ("URL scheme is not allowed") → use `find-links` (`[pypi-options] find-links = [{ path = "<abs dir>" }]`) with a plain `name = "*"` dep — but see gotcha 3 about torch.
6. Envs are **reproducible via `pixi.lock`** — a future Linux port just re-runs `install.py` there.
7. `cuda-wheels` (prebuilt repo) can serve CUDA packages *only* if the node declares them in `[cuda] packages` (then comfy-env uses a cuda-only override combo). A custom node like `custom_rasterizer` is not in that index.

## Case study: Hy3D texture node (`custom_rasterizer`)

### The problem
`custom_rasterizer` ships only **cp312** wheels; host is **3.13**. Texture nodes crash `ModuleNotFoundError: No module named 'custom_rasterizer'`.

### The two escape hatches
1. **Isolate the pack into a 3.12 env** (this file's config). Works only if torch family solves for cp312 — here it does NOT (torch 2.13 has no cp312 Windows wheel) → **blocked**.
2. **Compile the extension for host (3.13)** — done successfully; see `3d/EXPERIMENTS.md` E2b. Result `custom_rasterizer_kernel.cp313-win_amd64.pyd` shipped into server `python_embeded\Lib\site-packages\` (plus the `custom_rasterizer\` package folder). No comfy-env needed after that.

### Verdict
comfy-env is the **correct general tool** but cannot fix a missing host-ABI wheel for a *non-cuda-index* package. Use it for packs with coherent wheel availability; compile locally for gaps. Expect Linux to be far easier (prebuilt manylinux wheels exist upstream).

> **Housekeeping:** the Hy3D isolate config (`comfyui-hunyuan3dwrapper/comfy-env.toml`, `python="3.12"`) was **deleted** after the cp313-compile path won — a stale env config in the tree poisons every `comfy-env install` (any failing env aborts the whole workspace install, including UniRig's deferred cuda-wheels). Keep only *live* comfy-env configs on the server.

## Reference commands
```
# build envs for all packs with config
python_embeded\python.exe <node>\install.py
# check envs on boot (comfy-env prints status)
[comfy-env] <pack>: 1 isolation env(s) ... [OK|MISSING -- run install.py]
```

## A repo tool's own env: the bpy pose renderer

`scripts/render_glb_poses.py` needs `bpy` (Blender as a Python module) - ~1.6 GB, and nothing else wants it, so it gets **its own env rather than the ComfyUI venv**:

```bash
python3.11 -m venv ~/bpyenv && ~/bpyenv/bin/pip install bpy==4.2.0   # verified: bpy 4.2.0
~/bpyenv/bin/python scripts/render_glb_poses.py --glb ~/Projects-Git/ComfyUI/input/Knight.glb \
    --out ~/Projects-Git/ComfyUI/output/3d/poses --clip Idle_Rig:0.5 --yaws 0,90,180 --gear 1H_Sword,Round_Shield
```

It lives in **`~/bpyenv`, not the repo** (it is big and rebuildable), and it is *not* in the ComfyUI venv's freeze. Renders are headless (no `--background` needed with the bpy module) on **Cycles + CUDA**, and a GPU-context failure falls back to CPU by itself. The same pattern applies to any future repo tool with a heavy module: its own env, and the rebuild line written down here.
