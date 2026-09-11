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
├── assets/                      ← shared test inputs (images, refs)
├── scripts/                     ← helper scripts (find-pythons.bat, ...)
├── comfyui/                     ← general ComfyUI knowledge (not scenario-specific)
│   ├── README.md                ← index + server map
│   ├── setup.md                 ← install/run, caveats, Linux migration notes
│   ├── environments.md          ← comfy-env / pixi isolation, per-node envs
│   └── workflow-file-format.md  ← the ComfyUI .json workflow schema (nodes/links/widgets)
├── 3d/                          ← 3D asset generation scenario
│   ├── README.md                ← scenario index + workflow map
│   ├── cookbook-3d-assets.md    ← reference: models per 3D task (superseded by pipeline-design)
│   ├── pipeline-design.md       ← architecture: free-first + pay-per-stage, GLB gate
│   ├── EXPLORATION.md             ← run log (E1 ... En)
│   ├── setup-hy3d.md              ← Hy3D wrapper + weights install (3d-specific)
│   └── workflows/                 ← *valuable* workflow .json files here
│       └── scratch/               ← one-off/scaffolding workflows (archive, don't maintain)
├── 2d/                            ← 2D asset generation scenario
│   ├── README.md                  ← scenario index + workflow map + server model inventory
│   └── EXPERIMENTS-2D.md          ← run log (E1 ... En)
└── <future scenario folders>    ← animation, audio, text, ... as we get there
```

## Conventions

- Workflow JSON files live in the scenario's `workflows/` folder. Name by pipeline (`hy3d-full`, `moge-free`, `tripo-bridge`, ...). Only **valuable/curated** workflows stay in `workflows/`; scaffolding (one-off validation, superseded, unmaintained) goes to `workflows/scratch/` and is not cleaned up on refactors.
- A pipeline that used to be a separate standalone workflow should instead be represented as **mid-node outputs** inside one valuable workflow when the checkpoint is meaningful (e.g. `hy3d-full` exports both the untextured and textured GLB in a single run).
- References to workflow files inside markdown use `workflows/<name>.json`.
- Server specifics: ComfyUI server has migrated to Linux (Ubuntu 26.04, RTX 3090, systemd user service `comfyui`). See `comfyui/README.md`.
- Do not commit model weights or API keys; note *where* weights should live, not ship them.

## Status (2026-09-11)

- **3d/** — complete: E1–E5 PASS + **E4 rigging UNBLOCKED on Linux** (2026-09-11, E4-L): `ComfyUI-UniRig` provides bpy 4.2 LTS via conda/pixi; rigs humanoid GLB → Mixamo FBX in ~90s. Rasterizer texture bake **works on Linux** (nvcc 12.8 header-patch build). All smoke (shape/multiview/texture/MoGe/2D) green.
- **2d/** — scenario started; E1 SDXL base art PASS on Linux. ControlNet + E2–E7 pending.

URL/password live with the user. Runtime facts that matter for reproducibility:

- Host: Windows (`C:\Projects-Git\ComfyUI\...`), embedded Python **3.13.12**, torch **2.13.0+cu130**, RTX 3090 (24 GB).
- Custom nodes live under `custom_nodes\` on the server; several are already installed (see `comfyui/README.md`).
- The `custom_rasterizer` extension was compiled locally (MSVC 2022, CUDA 13.0) and shipped as a `.pyd`; see `comfyui/environments.md` + `3d/EXPERIMENTS.md` E2b.