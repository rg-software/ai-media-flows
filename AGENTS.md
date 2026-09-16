# AI Gamedev Tasks

Working notes + a growing knowledge base for using generative-AI in game development. Goals: **get pipelines working, AND understand them deeply** (nodes, args, knobs, reproducibility, environment setup).

## Goals (priority)

1. **Get things done** — iterate on real assets through working pipelines (ComfyUI on the server: `https://comfy.rt247a.ddns.me`).
2. **Learn** — genuinely understand each pipeline: what each node does, its inputs/outputs, tunable parameters (knobs), failure modes, and how to recreate a reproducible environment.
3. **Reproducibility** — document environments (Python/torch/CUDA versions, comfy-env isolation, model weights+where they live) so the setup can be rebuilt or ported (e.g. to Linux).
4. Keep the sparse cheatsheet in `C:\Vault\Notes\Generative AI solutions.md` as the high-level landscape; this repo holds the operational detail.

## How to work here

- **Scenario folders** first, tooling knowledge second. New task → new scenario folder + README index.
- Every experiment/run gets a row in the scenario's `EXPERIMENTS.md`.
- Record **verdicts** (`PASS` / `BLOCKED` / `MEH`) with the *why*, not just the result.
- When you hit a wall, write down the attempted fix and the real blocker — those notes are the education.

## Repository layout

```
ai-gamedev-tasks/
├── AGENTS.md                    ← this file
├── HANDOFF.md                   ← Linux box handoff: env, blockers, next steps
├── PIPELINES.md                 ← CAPABILITY MAP: every flow by operation × subject × status
├── assets/                      ← shared test inputs; assets/2d/ = curated concept art (tracked)
├── scripts/                     ← helper scripts (find-pythons.bat, ...)
├── comfyui/                     ← general ComfyUI knowledge (not scenario-specific)
│   ├── README.md                ← index + server map
│   ├── setup.md                 ← install/run, caveats, Linux migration notes
│   ├── environments.md          ← comfy-env / pixi isolation, per-node envs
│   ├── linux-setup.md           ← Ubuntu 26.04 + 3090 install/restore commands
│   ├── linux-migration.md       ← what carries over vs re-provision
│   └── workflow-file-format.md  ← the ComfyUI .json workflow schema (nodes/links/widgets)
├── 3d/                          ← 3D asset generation scenario (complete)
│   ├── README.md                ← scenario index + workflow map
│   ├── cookbook-3d-assets.md    ← reference: models per 3D task (superseded by pipeline-design)
│   ├── pipeline-design.md       ← architecture: free-first + pay-per-stage, GLB gate
│   ├── EXPERIMENTS.md           ← run log (E1 ... En)
│   ├── setup-hy3d.md            ← Hy3D wrapper + weights install (3d-specific)
│   └── workflows/               ← *valuable* workflow .json files here
│       └── scratch/             ← one-off/scaffolding workflows (archive, don't maintain)
├── 2d/                          ← 2D asset generation scenario (active)
│   ├── README.md                ← scenario index + workflow map + server model inventory
│   └── EXPERIMENTS-2D.md        ← run log (E1 ... En)
└── <future scenario folders>    ← animation, audio, text, ... as we get there
```

## Conventions

- Workflow JSON files live in the scenario's `workflows/` folder. Name by pipeline (`hy3d-full`, `moge-free`, `tripo-bridge`, ...). Only **valuable/curated** workflows stay in `workflows/`; scaffolding (one-off validation, superseded, unmaintained) goes to `workflows/scratch/` and is not cleaned up on refactors.
- **Categories are by operation, not just scenario.** Scenario folders (`2d/`, `3d/`) hold assets/experiments; the cross-cutting capability map lives in `PIPELINES.md` (family × subject × domain). Add a row there for every new flow, and prefer the `<family>-<detail>` filename convention for new ones.
- A pipeline that used to be a separate standalone workflow should instead be represented as **mid-node outputs** inside one valuable workflow when the checkpoint is meaningful (e.g. `hy3d-full` exports both the untextured and textured GLB in a single run).
- References to workflow files inside markdown use `workflows/<name>.json`.
- Server specifics: ComfyUI server has migrated to Linux (Ubuntu 26.04, RTX 3090, systemd user service `comfyui`). See `comfyui/README.md`.
- Do not commit model weights or API keys; note *where* weights should live, not ship them.
- **Asset policy — location decides, not file type.** `assets/` is the curated, tracked set; a
  valuable artefact belongs in the repo whether it is a `.png`, `.glb`, `.fbx` or `.json`. There are
  deliberately **no per-extension ignore rules for asset formats** (`*.glb`/`*.fbx`/`*.obj` were
  removed in 2026-09 for exactly this reason). `output/`, `temp/` and `assets-temp/` are ignored
  wholesale and are where generated/scratch files live. Promotion into `assets/` is always a
  deliberate step (`2d` via `scripts/publish_assets.sh`), never an ad-hoc dump.

## Status (2026-09-11)

**Current phase: 3D done → switching to 2D.** The 3D scenario reached "working + understood" (shape, multiview, texture bake, retopo, rigging, Unity import all PASS on Linux), so effort moves to the 2D asset scenario. 3D stays maintained, not extended, unless a task needs it.

- **3d/** — complete: E1–E5 PASS + **E4 rigging UNBLOCKED on Linux** (2026-09-11, E4-L): `ComfyUI-UniRig` provides bpy 4.2 LTS via conda/pixi; rigs humanoid GLB → Mixamo FBX in ~90s. Rasterizer texture bake **works on Linux** (nvcc 12.8 header-patch build). All smoke (shape/multiview/texture/MoGe/2D) green.
  - Open (low priority): rig a *generated* humanoid + `UniRigApplyAnimation` templates; package `custom_rasterizer` as a manylinux wheel; E3 Tripo bridge (needs API key).
- **2d/** — **active scenario**. E1 SDXL base art PASS on Linux. Next: E2 ControlNet (weights to pull) → E3–E7 per `2d/README.md`.

URL/password live with the user. Runtime facts that matter for reproducibility:

- Host: **Linux** — Ubuntu 26.04.1 LTS, `rg_software@Beelink`, RTX 3090 (24 GB), driver 595.91.07 / CUDA 13.2.
- ComfyUI: `~/Projects-Git/ComfyUI`; venv `./venv/bin/python` (**Python 3.11.16**), torch **2.11.0+cu128**, comfy-kitchen 0.2.33.
- Launch: `./venv/bin/python main.py --listen --disable-api-nodes`; systemd unit `comfyui.service` (see `HANDOFF.md`).
- Custom nodes live under `custom_nodes/`; installed: Hy3D wrapper, MoGe, UniRig (own pixi env, bpy 4.2 LTS), KJNodes, ComfyUI-Manager v3.41.
- `custom_rasterizer` is built **from source on this box** (nvcc 12.8 header-patch in conda env `cuda128`, gcc-13, `TORCH_CUDA_ARCH_LIST=8.6`); recipe in `HANDOFF.md` + `3d/EXPERIMENTS.md`. Do NOT use nvcc 13.2 (torch 2.11+cu128 hard-errors on the major mismatch).
- Old Windows host (retired): embedded Python 3.13.12, torch 2.13.0+cu130, MSVC-compiled `.pyd`. Kept only as history; see `comfyui/environments.md` + E2b.