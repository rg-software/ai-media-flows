# ComfyUI — index & server map

The ComfyUI server is the workhorse behind every scenario in this repo. Server is **remote** (Linux box — see `linux-setup.md`), accessed over HTTPS.

- Server URL / password: ask the user (not stored here).
- The remote instance has **1,034 nodes** registered at last count (Linux box, 2026-09-15); the "studio" providers (Tripo, Hy3D, Meshy, Rodin, MoGe) are nodes, not just an API.

## Docs in this folder (general = not scenario-specific)

| Doc | What it answers |
|---|---|
| `setup.md` | How the server is installed/run, known caveats, and what to change when migrating to Linux. |
| `environments.md` | `comfy-env` / pixi per-node environments — how to isolate nodes that need a different Python/torch/CUDA than the host. |
| `workflow-file-format.md` | The `.json` workflow schema: nodes, links, widgets, `order`/`mode`, import rules, and how to hand-edit safely. |
| `linux-migration.md` | What carries to a Linux server, what to re-provision, and how to avoid the Windows-specific pain (MSVC, `.pyd`, bpy). |

## Server runtime facts (reproducibility)

- Path: `~/Projects-Git/ComfyUI` on the Linux box; venv `./venv/bin/python` (**Python 3.11.16**).
- torch **2.11.0+cu128**, RTX 3090 (24 GB), Ubuntu 26.04 / driver 595.91.07.
- systemd **user** unit `comfyui` (`systemctl --user restart comfyui`; no sudo).
- Login: ComfyUI-Login plugin; API calls need `?token=<first line of login/PASSWORD>`.
- Custom node packs: ACN (`comfyui_controlnet_aux`), KJNodes, Hy3D wrapper, UniRig, ComfyUI-Login, ComfyUI-Manager, CameraPack.

## Node gotchas

- **MASK convention is "1 = transparent/selected"**, not "1 = keep". Concretely:
  - core `JoinImageWithAlpha` → `alpha = 1.0 - mask`
  - KJNodes `SaveImageWithAlpha` → `a = 255 * (1.0 - mask)`
  - core `SplitImageWithAlpha` → returns `1.0 - alpha`
  - So to turn a **foreground** mask (e.g. `RemoveBackground`, which sets 1 on the subject)
    into cutout alpha, you must insert **`InvertMask`** first. Skipping it yields a perfectly
    inverted cutout (background kept, subject transparent) — verified in E3.
- `SaveImageWithAlpha` is **KJNodes**, not core; core has `SplitImageWithAlpha`/`JoinImageWithAlpha`.
- **`ComfyUI-seamless-tiling` stability**: `SeamlessTile` (patches the *MODEL*) **segfaults in
  `libcuda.so.1`** on this box and takes ComfyUI down. Use the **VAE-side** route instead
  (`MakeCircularVAE` + `CircularVAEDecode`). Even that path crashes on a *second* run in the same
  session — `systemctl --user restart comfyui` between runs. Externally this looks like a dropped
  connection mid-prompt; `Restart=on-failure` silently brings the server back (masking the crash).

## How to talk to it programmatically

- `GET /system_stats`, `GET /object_info` (node schemas — the ground truth for inputs/outputs/widget names), `POST /prompt` (queue a workflow).
- **Auth**: append `?token=<token>` where token = first line of `~/Projects-Git/ComfyUI/login/PASSWORD`. (`POST /login` expects **form** data; sending JSON returns 500.)
- `POST /prompt` takes **API format** (`{node_id: {class_type, inputs}}`), not the GUI graph JSON.
- Node schema is the source of truth: whenever in doubt about a node's inputs/option values, read `/object_info` rather than trusting memory.

## Convention

Scenario-specific installs (e.g. Hy3D wrapper + weights) go in the scenario folder, not here. This folder holds only what applies to ComfyUI regardless of task.