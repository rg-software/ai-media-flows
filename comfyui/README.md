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

## Model stack (reproducibility — where weights live, not the weights)

**2D generation/edit stack.** Before 2026-09-16 the box was **SD1.5/SDXL-only** (`unet/`, `diffusion_models/`, `text_encoders/` were empty placeholders). Flux.1 Kontext dev (fp8) was added for instruction-based editing:

| role | file | dir | source (ungated) |
|---|---|---|---|
| Flux edit UNET | `flux1-dev-kontext_fp8_scaled.safetensors` (11.9 GB) | `models/diffusion_models/` | `Comfy-Org/flux1-kontext-dev_ComfyUI` → `split_files/diffusion_models/` |
| T5 encoder | `t5xxl_fp8_e4m3fn_scaled.safetensors` (5.16 GB) | `models/text_encoders/` | `comfyanonymous/flux_text_encoders` |
| CLIP-L | `clip_l.safetensors` (246 MB) | `models/text_encoders/` | `comfyanonymous/flux_text_encoders` |
| Flux VAE | `ae.safetensors` (320 MB) | `models/vae/` | `camenduru/FLUX.1-dev` — **the BFL repos are gated (HTTP 401)** |

Plus `models/checkpoints/`: SDXL (RealVisXL_V5.0_fp16 default, juggernautXL, ponyDiffusionV6XL, AnythingXL, sd_xl_refiner, 512-inpainting-ema), SD1.5 (v1-5-pruned, dreamshaper, Deliberate, protogen, chilloutmix, realisticVision, architecturerealmix), RetroDiffusion ×3. ControlNets: SD1.5 depth/openpose/scribble + `xinsir-canny-sdxl-v2`. Upscalers: `4x-UltraSharp`, `RealESRGAN_x4plus`.

## Server runtime facts (reproducibility)

- Path: `~/Projects-Git/ComfyUI` on the Linux box; venv `./venv/bin/python` (**Python 3.11.16**).
- torch **2.11.0+cu128**, RTX 3090 (24 GB), Ubuntu 26.04 / driver 595.91.07.
- systemd **user** unit `comfyui` (`systemctl --user restart comfyui`; no sudo).
- Login: ComfyUI-Login plugin; API calls need `?token=<first line of login/PASSWORD>`.
- Custom node packs: ACN (`comfyui_controlnet_aux`), KJNodes, Hy3D wrapper, UniRig, ComfyUI-Login, ComfyUI-Manager, CameraPack, TextureAlchemy, QFX-PBRGenerator, PixelArt-Detector, `ComfyUI-IPAdapter_plus`, **`ComfyUI-Inpaint-CropAndStitch`** (lquesada).

## Node gotchas

- **MASK convention is "1 = transparent/selected"**, not "1 = keep". Concretely:
  - core `JoinImageWithAlpha` → `alpha = 1.0 - mask`
  - KJNodes `SaveImageWithAlpha` → `a = 255 * (1.0 - mask)`
  - core `SplitImageWithAlpha` → returns `1.0 - alpha`
  - So to turn a **foreground** mask (e.g. `RemoveBackground`, which sets 1 on the subject)
    into cutout alpha, you must insert **`InvertMask`** first. Skipping it yields a perfectly
    inverted cutout (background kept, subject transparent) — verified in E3.
- `SaveImageWithAlpha` is **KJNodes**, not core; core has `SplitImageWithAlpha`/`JoinImageWithAlpha`.
- **Inpaint/outpaint: prefer `ComfyUI-Inpaint-CropAndStitch`** (`InpaintCropImproved` + `InpaintStitchImproved`) over the core `ImagePadForOutpaint` → inpaint → `ImageCompositeMasked` path. `InpaintStitchImproved` never VAE round-trips unmasked pixels, so the original region returns **pixel-identical** (measured mean|diff| **0.041/255** vs **6.477/255** for the core path — verified E9). `extend_for_outpainting` + `extend_*_factor` >1 does the outpaint (1.5 = +50% per side of the source size; 2 = +100%). `device_mode="gpu (much faster)"` is 30-100x over CPU; `output_resize_to_target_size=False` for non-square targets (forcing 1024² squashes a wide crop). `mask` is an *optional* input — omit it for pure canvas extension.
- **`LoadImage` reads only from `input/`.** A file in `output/` cannot be loaded — copy it into `input/` first. Corollary: stage working/intermediate images in a **subdirectory** (e.g. `input/2d/_work/`), never directly in `input/2d/`, because `scripts/publish_assets.sh` sweeps `input/2d/*.png` into `assets/` (verified: a staging file got published as an "asset").
- **Flux.1 Kontext works at ~1 MP.** `FluxKontextImageScale` snapped 2048×1024 → **1456×720**. Anything bigger must be restored afterwards (4x-UltraSharp → downscale), so an edit + upscale pair is the normal recipe, not an optional extra. Flux is distilled: **`cfg` is unused, keep 1.0**; use `FluxGuidance` (2.5 here) for prompt adherence, 20 steps, `euler`/`simple`, ~69 s on the 3090.
- **Tiling**: `SeamlessTile` (comfyui-seamless-tiling, patches the **MODEL**) **segfaults in
  `libcuda.so.1`** and takes ComfyUI down — avoid. Use **`SeamlessTiling`** (TextureAlchemy, an
  **image-space** op: `method` = mirror/blend_edges/offset) instead; it is stable and instant.
  The circular-VAE route (`MakeCircularVAE` + `CircularVAEDecode`) also works but crashes on a
  *second* run in one session — `systemctl --user restart comfyui` between runs. Externally a
  crash looks like a dropped connection mid-prompt; `Restart=on-failure` silently restarts.
- **Metric ≠ quality**: edge-continuity metrics rated `mirror`/`blend_edges` as perfect (0.00)
  while they looked visibly awful (symmetric kaleidoscope / blurry cross). Always confirm with eyes.

## How to talk to it programmatically

- `GET /system_stats`, `GET /object_info` (node schemas — the ground truth for inputs/outputs/widget names), `POST /prompt` (queue a workflow).
- **Auth**: append `?token=<token>` where token = first line of `~/Projects-Git/ComfyUI/login/PASSWORD`. (`POST /login` expects **form** data; sending JSON returns 500.)
- `POST /prompt` takes **API format** (`{node_id: {class_type, inputs}}`), not the GUI graph JSON.
- Node schema is the source of truth: whenever in doubt about a node's inputs/option values, read `/object_info` rather than trusting memory.

## Convention

Scenario-specific installs (e.g. Hy3D wrapper + weights) go in the scenario folder, not here. This folder holds only what applies to ComfyUI regardless of task.