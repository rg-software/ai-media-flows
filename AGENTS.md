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
├── README.md                    ← FRONT DOOR: mission, mental model, "I want to…" index, known gaps
├── HOWTO.md                     ← USER STORIES: how to actually run each job (prereqs, steps, knobs, traps)
├── AGENTS.md                    ← this file
├── HANDOFF.md                   ← Linux box handoff: env, blockers, next steps
├── PIPELINES.md                 ← CAPABILITY MAP: every flow by operation × subject × status
├── assets/                      ← curated, tracked artefacts (2d/, 3d/); location decides, not file type
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
- **Flows are classified by operation, not by folder.** The taxonomy lives in `PIPELINES.md`
  (Axis 1 family × Axis 2 subject/domain). Two conventions to keep: a harness that does nothing to an
  asset is `tooling`, not an operation; and a flow that **moves data between domains** writes its
  domain explicitly as `from->to` (e.g. `texture->3D model`) rather than inventing a string.
- **Lint the docs before committing:** `python scripts/lint_docs.py`. It catches the two failure modes
  that silently waste a reviewer's time — a table whose separator has the wrong column count (strict
  renderers then drop the *whole* table), and a cell containing a literal newline (which splits the
  row and leaves an orphan paragraph). Both have happened while hand-merging tables with scripts.

## Status (2026-09-16)

**Both scenarios are complete; the repo is consolidating rather than expanding.** The 2D ladder
**E1–E16** is done, the upgrade track **U1–U7** is done, and the 3D scenario is complete including
Linux rigging. The live list of open items is **`PIPELINES.md` → "Status — what is actually left"**.

- **2d/** — ladder + upgrades complete. Licence posture is clean except one item: `insightface`
  (used by the InstantID and PuLID flows) is non-commercial research-only.
- **3d/** — complete (shape, multiview, texture bake, retopo, rigging on Linux).
- **Next candidates, in order:** (1) the **engine import contract** — assets are Unity-*compatible*
  but not drop-in (no `.meta`/`.mat`, wrong importer defaults for pixel art and PBR maps, no
  PPU/pivot convention, and glTF-vs-Unity channel packing differs); (2) **animation** as a new
  scenario folder, partly gated on more RAM; (3) hardware — the box is **RAM-bound, not
  VRAM-bound** (`comfyui/hardware.md`, `comfyui/UPGRADE-TODO.md`).

URL/password live with the user. Runtime facts that matter for reproducibility:

- Host: **Linux** — Ubuntu 26.04.1 LTS, `rg_software@Beelink`, RTX 3090 (24 GB), driver 595.91.07 / CUDA 13.2.
- ComfyUI: `~/Projects-Git/ComfyUI`; venv `./venv/bin/python` (**Python 3.11.16**), torch **2.11.0+cu128**, comfy-kitchen 0.2.33.
- Launch: `./venv/bin/python main.py --listen --disable-api-nodes`; systemd unit `comfyui.service` (see `HANDOFF.md`).
- Custom nodes live under `custom_nodes/`; installed: Hy3D wrapper, MoGe, UniRig (own pixi env, bpy 4.2 LTS), KJNodes, ComfyUI-Manager v3.41.
- `custom_rasterizer` is built **from source on this box** (nvcc 12.8 header-patch in conda env `cuda128`, gcc-13, `TORCH_CUDA_ARCH_LIST=8.6`); recipe in `HANDOFF.md` + `3d/EXPERIMENTS.md`. Do NOT use nvcc 13.2 (torch 2.11+cu128 hard-errors on the major mismatch).
- Old Windows host (retired): embedded Python 3.13.12, torch 2.13.0+cu130, MSVC-compiled `.pyd`. Kept only as history; see `comfyui/environments.md` + E2b.