# ComfyUI — index & server map

The ComfyUI server is the workhorse behind every scenario in this repo. Server is **remote** (Windows), accessed over https.

- Server URL / password: ask the user (not stored here).
- The remote instance has **1,759 nodes** registered at last count — most of the "studio" providers (Tripo, Hy3D, Meshy, Rodin, MoGe) are available as nodes, not just an API.

## Docs in this folder (general = not scenario-specific)

| Doc | What it answers |
|---|---|
| `setup.md` | How the server is installed/run, known caveats, and what to change when migrating to Linux. |
| `environments.md` | `comfy-env` / pixi per-node environments — how to isolate nodes that need a different Python/torch/CUDA than the host. |
| `workflow-file-format.md` | The `.json` workflow schema: nodes, links, widgets, `order`/`mode`, import rules, and how to hand-edit safely. |
| `linux-migration.md` | What carries to a Linux server, what to re-provision, and how to avoid the Windows-specific pain (MSVC, `.pyd`, bpy). |

## Server runtime facts (reproducibility)

- Path: `C:\Projects-Git\ComfyUI\` on the server; embedded Python at `C:\Projects-Git\ComfyUI\python_embeded\python.exe`.
- Python **3.13.12**, torch **2.13.0+cu130**, RTX 3090 (24 GB).
- ComfyUI v0.27.0; frontend package 1.45.20.
- Login: ComfyUI-Login plugin (POST `/login`, cookie `AIOHTTP_SESSION`), user `rg_software`.
- Several custom node packs already installed — most relevant to 3D listed in `../3d/README.md`.

## How to talk to it programmatically

- POST `/login` with password → capture `AIOHTTP_SESSION` cookie.
- `GET /system_stats`, `GET /object_info` (node schemas — the ground truth for inputs/outputs/widget names), `POST /prompt` (queue a workflow).
- Node schema is the source of truth: whenever in doubt about a node's inputs/option values, read `/object_info` rather than trusting memory.

## Convention

Scenario-specific installs (e.g. Hy3D wrapper + weights) go in the scenario folder, not here. This folder holds only what applies to ComfyUI regardless of task.