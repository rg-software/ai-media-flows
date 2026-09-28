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
- Use Github CLI (`gh` tool) to access Github.

## Repository layout

```
ai-gamedev-tasks/
├── README.md                    ← FRONT DOOR (cookbook): mission + "I want to make…" index
├── HOWTO.md                     ← USER STORIES: how to actually run each job (prereqs, steps, knobs, traps)
├── AGENTS.md                    ← this file
├── HANDOFF.md                   ← Linux box handoff: env, blockers, next steps
├── PIPELINES.md                 ← CAPABILITY MAP: every flow by operation × subject × status
├── assets/                      ← curated, tracked artefacts (2d/, 3d/); location decides, not file type
├── scripts/                     ← helper scripts + the repo-local tooling env (uv; see pyproject.toml)
│   ├── mdtable.py               ← AST-based markdown table parse/render (`--self-test` round-trips all)
│   └── lint_docs.py             ← the doc gate: NULs, table shape, links, flow coverage, per-flow docs
├── comfyui/                     ← general ComfyUI knowledge (not scenario-specific)
│   ├── README.md                ← index + server map
│   ├── environments.md          ← comfy-env / pixi isolation, per-node envs
│   ├── linux-setup.md           ← Ubuntu 26.04 + 3090 install/restore, remote access
│   ├── hardware.md              ← what fits: measured footprints, RAM ceiling, upgrade order
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
├── animation/                   ← animation scenario: engine assets that move (sprite / parametric) × motion source.
│   ├── README.md                ← scenario index + the form/source map
│   ├── EXPERIMENTS.md           ← run log (E1 ... En)
│   ├── motion-sourcing.md       ← where motion comes from: the free path vs the video route's cost
│   └── workflows/               ← `sam3d-motion.json` (footage → an animated skeletal GLB; ships two
│                                   corrected upstream defaults)
├── video/                       ← video scenario: motion as *content* (the consumer is a viewer, not an engine).
│   ├── README.md                ← scenario index + the metadata trap (a GGUF loses the model type)
│   ├── EXPERIMENTS.md           ← run log (E1 ... En) + the deferred video-model backlog
│   └── workflows/               ← `wan-animate-motion.json` (video reference; the flat rebuild of an
│                                   upstream *subgraph* template, which cannot be scripted as shipped)
├── audio/                       ← audio scenario: audio as *content* (a listener's file). ACE-Step 1.5 (MIT).
│   ├── README.md                ← scenario index + knobs + the "we have no ears" traps
│   ├── EXPERIMENTS.md           ← run log (E1 ... En) + the short-form/loop backlog
│   └── evidence/                ← spectrograms (the audio analogue of an evidence sheet)
└── <future scenario folders>    ← text, ... as we get there
```

## Conventions

- Workflow JSON files live in the scenario's `workflows/` folder. Name by pipeline (`hy3d-full`, `moge-free`, `tripo-bridge`, ...). Only **valuable/curated** workflows stay in `workflows/`; scaffolding (one-off validation, superseded, unmaintained) goes to `workflows/scratch/` and is not cleaned up on refactors.
- **The job → flow → story mapping is data, not prose: `workflows/jobs.json`.** It holds the README job rows (26), each workflow's story claim (39 flows) and the story titles, and is the only place any of that should be edited. `scripts/gen_job_docs.py --write` renders it into the README job table, every `PIPELINES.md` story cell and each workflow's note footer; `scripts/check_job_docs.py` (wired into the lint) fails if any of those surfaces stops equalling the registry. Before this, the same mapping was hand-maintained in four places — ~45 references — which is why renumbering the stories had to be done as one regex pass (any half-applied edit would have gone unnoticed). Adding a job, or moving one between stories, is now a one-file edit.
- **Categories are by operation, not just scenario.** Scenario folders (`2d/`, `3d/`) hold assets/experiments; the cross-cutting capability map lives in `PIPELINES.md` (family × subject × domain). Add a row there for every new flow, and prefer the `<family>-<detail>` filename convention for new ones.
- A pipeline that used to be a separate standalone workflow should instead be represented as **mid-node outputs** inside one valuable workflow when the checkpoint is meaningful (e.g. `hy3d-full` exports both the untextured and textured GLB in a single run).
- References to workflow files inside markdown use `workflows/<name>.json`.
- Server specifics: ComfyUI server has migrated to Linux (Ubuntu 26.04, RTX 3090, systemd user service `comfyui`). See `comfyui/README.md`.
- Do not commit model weights or API keys; note *where* weights should live, not ship them.
- **Asset policy — location decides, not file type.** `assets/` is the curated, tracked set; a valuable artefact belongs in the repo whether it is a `.png`, `.glb`, `.fbx` or `.json`. There are deliberately **no per-extension ignore rules for asset formats** (`*.glb`/`*.fbx`/`*.obj` were removed in 2026-09 for exactly this reason). `output/`, `temp/` and `assets-temp/` are ignored wholesale and are where generated/scratch files live. Promotion into `assets/` is always a deliberate step (`2d` via `scripts/publish_assets.sh`), never an ad-hoc dump.
- **Flows are classified by operation, not by folder.** The taxonomy lives in `PIPELINES.md` (Axis 1 family × Axis 2 subject/domain). Two conventions to keep: a harness that does nothing to an asset is `tooling`, not an operation; and a flow that **moves data between domains** writes its domain explicitly as `from->to` (e.g. `texture->3D model`) rather than inventing a string.
- **Audience split: `HOWTO.md` is for *users*, `AGENTS.md`/`2d/PROTOCOL.md` for *contributors*.** A user story answers "I want to make X" — prerequisites, steps, knobs, traps — and never mentions staging, promotion, md5 publishing, `EXPERIMENTS` rows, or `E`/`U` ids; that internal loop lives in `2d/PROTOCOL.md`. A tool that maintains the repo rather than producing a user asset is listed in `CONTRIBUTOR_TOOLS` (`scripts/lint_docs.py`) and is deliberately exempt from the README job table. `scripts/pose_probe.py` and `scripts/motion_quality.py` are the worked examples - a probe and a checker respectively, neither of which produces an asset; `scripts/pose_probe.py`: it is an **experiment probe** - it scripts poses, runs the ControlNet arms and measures adherence (E21-E23) - so it carries no user story, and the user-facing pose path is `2d/workflows/pose-extract.json` (S16) feeding `2d/workflows/pose-skeleton.json` (S7).
- **Lint the docs before committing:** `uv run python scripts/lint_docs.py`. It checks, in order of what has actually bitten us: **NUL bytes** (which make git treat a file as *binary*, so its diff silently becomes invisible — `git diff --numstat` shows `- -`), table shape via **markdown-it-py** (`scripts/mdtable.py`) rather than string splitting (a malformed separator, a row whose cell count differs from the header — which markdown-it *silently pads or truncates*, i.e. data loss), a table that interrupts a paragraph, dead internal links/paths, **flow coverage** (every flow reachable from the README table and present in `PIPELINES.md`), and **per-flow docs** (every workflow carries a `MarkdownNote`; every story cited must exist in `HOWTO.md`, and every story must be referenced), **prose wrapping**, and **workflow link integrity** (each workflow's node link references must agree with its authoritative `links` array — ComfyUI wires from the array, so a stale reference only errors when its type is wrong; `inpaint.json` shipped with SaveImage fed by a MASK that way. Fix with `scripts/fix_workflow_links.py --write`). **Contributors only — none of this is user-facing:** `scripts/add_workflow_notes.py` writes the per-flow `MarkdownNote` that the per-flow-docs check then enforces, and tables are always edited through `scripts/mdtable.py`, never by hand.
- **Prose is one line per paragraph — never hard-wrap.** Line width is not a thing in Markdown: GitHub *reflows* a single newline, but Obsidian only ignores it when `Strict line breaks` is on (**its default is off**), so a wrapped sentence shows a visible mid-phrase break there — and a sentence split across lines cannot be grepped. Same principle as the anchor/plugin note above: content must not render differently depending on a per-user toggle. Lint flags re-wrapped prose (it shares the exact predicate with the fixer, so they cannot drift); fix it with `uv run python scripts/lint_docs.py --fix-wrapping`, which is idempotent and only ever joins prose — never tables, fenced code, headings, blockquotes or list structure. Verified on adoption by rendering every changed file through markdown-it before and after: **the HTML was identical**, i.e. only source line breaks moved.
- **Repo-local tooling env (uv).** Python scripts are run from the repo's own environment, not from whatever interpreter happens to be around: `uv sync` then `uv run python scripts/<x>.py`. Dependencies are declared in `pyproject.toml` and pinned in `uv.lock` (committed). The one exception is `scripts/marigold_pbr.py`, which needs torch/diffusers and therefore runs in the ComfyUI venv.
- **Never park scratch files inside the box's repo checkout.** An untracked file blocks `git pull --ff-only` on that path: git prints `Updating a..b` and then **aborts**, so the tree stays on the old commit and the resulting lint failure looks like a content bug rather than a stale checkout. It happened twice while testing new scripts (each time because the file was base64'd straight into `scripts/`). Copy test files to `/tmp` instead, and if a pull looks suspiciously uneventful, check `git status --short` before believing the lint output.
- **Never hand-parse or hand-pad markdown tables.** Use `scripts/mdtable.py` (AST-based: `parse`, `find`, `render`, `replace`, `add_column`). Five separate documentation bugs came from treating tables as text — see that module's docstring. It has a `--self-test` that round-trips every table in the repo (currently 50) and fails loudly if our content stops surviving a parse->render->parse cycle.
- **Cross-references must work in both GitHub and Obsidian.** The two tools disagree on heading anchors and it is *not* covered by CommonMark: GitHub generates **kebab-case slugs** (`#s5-edit-a-picture…`), while Obsidian uses the **URL-encoded heading text** (`#S5.%20Edit…`) and natively resolves **neither GFM slugs nor HTML anchors** (GitHub also prefixes user-supplied `id=` with `user-content-`, and custom anchors aren't officially supported there). We therefore write GFM slugs, and Obsidian needs the community plugin **`gfm-compatibility`** (BRAT: `MMadder/Obsidian-GFM-Compatibility`) to resolve them. Lint validates every fragment against the real heading anchors, so renaming a story fails the lint rather than rotting links. *Known cosmetic limitation:* in Obsidian's **live-preview** editor the plugin centres the target line instead of pinning it to the top, so it lands "nearby"; reading view takes a different code path and is closer. Only fixable by forking the plugin. If exactness ever matters more than the single-file layout, the escape hatch is **one file per story** (file links carry no fragment, so they work everywhere and cannot rot).
- **A heading must slugify identically on GitHub and in Obsidian — so no space-surrounded punctuation.** The two algorithms differ *only* there: GitHub turns each space into a hyphen (`picture--remove`), while the plugin collapses the whitespace run (`picture-remove`). A heading containing ` — `, ` / `, ` & `, ` + `, ` = `, an arrow or an interior emoji therefore resolves in one tool and silently breaks in the other — those links looked fine in Obsidian and were dead on GitHub for exactly this reason. Use `: ` or parentheses instead. Lint enforces it (`check_heading_anchors`) and models GitHub's algorithm *exactly* (each space → one hyphen, plus the `-1`/`-2` dedup suffixes), skipping fenced code so a shell `#` comment is not mistaken for a heading.

## Vocabulary and doc map (for working *on* the repo)

**Four kinds of file**

| kind          | where                         | what it is                                                                 |
|---------------|-------------------------------|----------------------------------------------------------------------------|
| **assets**    | `assets/`                     | the curated, tracked artefacts; value decides inclusion, not file type     |
| **workflows** | `<scenario>/workflows/*.json` | ComfyUI graphs ready to run (one-off scaffolding in `workflows/scratch/`)  |
| **scripts**   | `scripts/`                    | non-graph scripts: sweeps, generators, format packing, publishing, linting |
| **docs**      | the `.md` files               | the *why*: verdicts, gotchas, measurements, decisions                      |

**Numbering is a log, not a version**

- **E-numbers** (`E1`…`E16`) are **experiments** — one capability each, run in order, each with a verdict and the reasoning. `E1c`, `E4b`, `E13f` refine the same experiment.
- **U-numbers** (`U1`…`U7`) are **upgrades** — swapping a working-but-suboptimal tool for a better or licence-cleaner one, decided by the audit.
- Both live in `2d/EXPERIMENTS-2D.md` and `3d/EXPERIMENTS.md`. **Read the verdicts, not just the results** — several entries are explicit corrections of earlier ones.

**Glossary** — *asset* (curated artefact in `assets/`) · *flow/workflow* (a ComfyUI graph) · *knob* (a parameter worth tuning; each flow's `PIPELINES.md` row names its most important one) · *evidence* (a labelled comparison sheet in `2d/evidence/`) · *promotion* (the deliberate move from a staging dir into `assets/`) · *verdict* (`PASS`/`MEH`/`BLOCKED` **plus the reason**) · *gateway* (a licence or hardware constraint deciding whether output is shippable).

**Doc map**

| doc                                               | answers                                                          |
|---------------------------------------------------|------------------------------------------------------------------|
| `README.md`                                       | the cookbook gateway — "I want to make X"                        |
| `HOWTO.md`                                        | user stories — what to actually do, per job                      |
| `PIPELINES.md`                                    | the capability index, the taxonomy, and what is still open       |
| `2d/PROTOCOL.md`                                  | the canonical asset set and the run/sweep/promotion contract     |
| `2d/AUDIT-tooling-2026-09.md`                     | are we using the best tool? (quality + licence + cost to switch) |
| `2d/ROADMAP-2D.md`                                | tracks A–J and the E/U backlog                                   |
| `comfyui/README.md`                               | **node gotchas** — the highest-density page in the repo          |
| `comfyui/hardware.md` · `comfyui/UPGRADE-TODO.md` | what fits / what to buy                                          |
| `comfyui/workflow-file-format.md`                 | how to hand-edit a workflow `.json` safely                       |
| `HANDOFF.md`                                      | the Linux box: environment, remote access, blockers              |

## Status (2026-09-16)

**Agenda (2026-09-28).** The asset scenarios are built, and the last three gaps are closed: 2d track I by **E34** (text/UI), the 3D-to-facing-set question by **E24/E24b/E24c**, and the facial half of the parametric cell by **E20/E20b**. What is left, in the order we intend to take it:

1. **`audio/` - the next modality, in progress.** ACE-Step 1.5 (**MIT**, commercial-ready by its own card, ~10 s per song on this card, <4 GB VRAM) is the first model; the nodes are installed and **only the weights are missing**. Plan: the official ComfyUI template -> the all-in-one checkpoint -> the `audio/` scenario -> one measured flow. Taxonomy entry: `generate / scene / audio`, with the `subject` vocabulary question (`clip`, `cue`) already recorded in `PIPELINES.md`.
2. **E24 Phase 2 - posed facings.** Phase 1 (yaw) and the stylisation arms are done and the recipe is fixed (Hy3D turnaround -> pick facings -> `pixel-art-restyle` -> one shared palette). Poses need char_knight rigged with UniRig (`3d/workflows/unirig-humanoid-workflow.json`).
3. **The `video/` backlog** - deliberately deferred. Interpolation shipped (E17/E17b/S18); the rest (~100 unused node types: LTXV, MiniMax, camera control, motion tracking, combinations, audio-driven talking heads) needs weights and licence reads.
4. **Small open items**, each in its scenario log's PENDING: **E9** (does the SAM 3D Body recipe hold on other fast clips), **E20c** (how much skeleton has to be visible for a partial-source clip), **E20b's residue** (arm/bone quality on more content), and **E34's tool follow-up** (`svg_trace.py`, so raster to vector is a pipeline rather than a recipe). One item is a **trigger**, not work: the Load3D/Preview3D texture re-check fires when `comfyui-frontend-package` is bumped.
5. **Hardware** - RAM and swap are done; the only meaningful upgrade left is VRAM, and it is optional.

**The asset scenarios are complete; the repo is consolidating rather than expanding.** The 2D ladder **E1–E16** is done, the upgrade track **U1–U7** is done, the 3D scenario is complete including Linux rigging, and both motion scenarios are built — **`animation/`** (engine assets: sprite sheets, skeletal clips) and **`video/`** (motion as content: a clip a viewer plays). The live list of open items is **`PIPELINES.md` → "Status — what is actually left"**.

- **2d/** — ladder + upgrades complete. Licence posture: clean except `insightface` (InstantID/PuLID, non-commercial research-only) and the Retro Diffusion pixel-art models (non-commercial). Kontext and `4x-UltraSharp` are non-commercial but superseded.
- **3d/** — complete (shape, multiview, texture bake, retopo, rigging on Linux). Licence posture is **not** clean: Hy3D is under the Tencent Hunyuan 3D Community License (excludes EU/UK/South Korea; >1M MAU needs a licence); UniRig is MIT.
- **animation/** — complete for engine assets: sprites (`2d/workflows/pose-extract.json` → `pose-skeleton.json` → `scripts/atlas.py`) and skeletal clips (`sam3d-motion.json`, SAM 3D Body). The recovered skin is Meta MHR, so retargeting onto our rig is engine-side by decision.
- **video/** — new scenario, split out of `animation/` on the repo's own rule (**the consumer decides**: a viewer's file is not an engine's). Holds the driving-video route (`wan-animate-motion.json`, Wan Animate 2) and the deferred video-model backlog.
- **Inventory:** 38 2D assets · 5 3D assets · **33 workflows** (26 in `2d/`, 3 in `3d/`, 1 in `animation/`, 2 in `video/`, 1 in `audio/`; plus scaffolding   in `workflows/scratch/`) · 46 evidence sheets · 25 scripts · 26 docs.
- **Working rules** (full version in `2d/PROTOCOL.md` and `HOWTO.md` Part 1): prefer **scripts over GUI clicks** so every run is replayable; change **one knob at a time**; and remember **a metric is a hint, the image is the truth** (it has misled us three times — E7, E15, U6b).
- **Next candidates, in order:** (1) the **video scenario's own backlog** — it is where most of the unused video-model surface belongs (~100 node types: frame interpolation, camera control, motion tracking, combinations, LTXV/MiniMax/Hunyuan); (2) **hardware** — the box is **RAM-bound, not VRAM-bound** (`comfyui/hardware.md`, `comfyui/UPGRADE-TODO.md`). The animation forms themselves are built (sprite, skeletal clip, driving-video); the **engine import contract** is done (E12: `scripts/check_gltf_contract.py`, `scripts/fix_gltf_normals.py`), and the engine's own side is a stated boundary, not a backlog item.

URL/password live with the user. Runtime facts that matter for reproducibility:

- Host: **Linux** — Ubuntu 26.04.1 LTS, `rg_software@Beelink`, RTX 3090 (24 GB), driver 595.91.07 / CUDA 13.2.
- ComfyUI: `~/Projects-Git/ComfyUI`; venv `./venv/bin/python` (**Python 3.11.16**), torch **2.11.0+cu128**, comfy-kitchen 0.2.33.
- Launch: `./venv/bin/python main.py --listen --disable-api-nodes`; systemd unit `comfyui.service` (see `HANDOFF.md`).
- Custom nodes live under `custom_nodes/`; installed: Hy3D wrapper, MoGe, UniRig (own pixi env, bpy 4.2 LTS), KJNodes, ComfyUI-Manager v3.41.
- `custom_rasterizer` is built **from source on this box** (nvcc 12.8 header-patch in conda env `cuda128`, gcc-13, `TORCH_CUDA_ARCH_LIST=8.6`); recipe in `HANDOFF.md` + `3d/EXPERIMENTS.md`. Do NOT use nvcc 13.2 (torch 2.11+cu128 hard-errors on the major mismatch).
- Old Windows host (retired): embedded Python 3.13.12, torch 2.13.0+cu130, MSVC-compiled `.pyd`. Kept only as history; see `comfyui/environments.md` + E2b. The Windows-era docs (setup.md, linux-migration.md, both under `comfyui/`) were **deleted** once the migration completed — recover them from git history if the Windows path is ever revived.