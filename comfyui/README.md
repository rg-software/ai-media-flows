# ComfyUI: index and server map

The ComfyUI server is the workhorse behind every scenario in this repo. Server is **remote** (Linux box — see `linux-setup.md`), accessed over HTTPS.

- Server URL / password: ask the user (not stored here).
- **API auth:** direct calls (scripts, `curl`) need the token — the first line of `~/Projects-Git/ComfyUI/login/PASSWORD` — passed as `?token=…` or `Authorization: Bearer …` (ComfyUI-Login accepts either). A 401 usually means the token is **stale**: re-read that file, it changes when the password is reset.
- **A run reports success in ~2 s but saves nothing** — the API says `success` regardless; the journal says why: `journalctl --user -u comfyui` (a bad `SetUnionControlNetType` value is the classic cause).
- The remote instance has **1,034 nodes** registered at last count (Linux box, 2026-09-15); the "studio" providers (Tripo, Hy3D, Meshy, Rodin, MoGe) are nodes, not just an API.

## Docs in this folder (general: not scenario-specific)

| Doc | What it answers |
|---|---|
| `linux-setup.md` | How to install/restore the box from scratch — Ubuntu 26.04 + 3090 (driver/CUDA, torch, custom nodes), remote access, and the topology. |
| `environments.md` | `comfy-env` / pixi per-node environments — how to isolate nodes that need a different Python/torch/CUDA than the host. |
| `workflow-file-format.md` | The `.json` workflow schema: nodes, links, widgets, `order`/`mode`, import rules, and how to hand-edit safely. |
| `hardware.md` | **What fits and what doesn't** — measured model footprints (SDXL → Qwen 20B → FLUX.2 32B), the RAM/VRAM ceiling, and upgrade options in value order (swapfile → RAM → GPU). Read before pulling a large model. |

## Model stack (reproducibility: where weights live, not the weights)

**2D generation/edit stack.** Before 2026-09-16 the box was **SD1.5/SDXL-only** (`unet/`, `diffusion_models/`, `text_encoders/` were empty placeholders). Flux.1 Kontext dev (fp8) was added for instruction-based editing:

| role | file | dir | source (ungated) |
|---|---|---|---|
| Flux edit UNET | `flux1-dev-kontext_fp8_scaled.safetensors` (11.9 GB) | `models/diffusion_models/` | `Comfy-Org/flux1-kontext-dev_ComfyUI` → `split_files/diffusion_models/` |
| T5 encoder | `t5xxl_fp8_e4m3fn_scaled.safetensors` (5.16 GB) | `models/text_encoders/` | `comfyanonymous/flux_text_encoders` |
| CLIP-L | `clip_l.safetensors` (246 MB) | `models/text_encoders/` | `comfyanonymous/flux_text_encoders` |
| Flux VAE | `ae.safetensors` (320 MB) | `models/vae/` | `camenduru/FLUX.1-dev` — **the BFL repos are gated (HTTP 401)** |

**Identity stack** (added 2026-09-16, E14): `insightface` 2.0 + `onnxruntime-gpu` (pip, builds with system gcc/g++ — no cmake needed), `antelopev2` in `models/insightface/models/`, `ip-adapter.bin` (1.69 GB) in `models/instantid/`, `instantid_controlnet.safetensors` (2.5 GB) in `models/controlnet/`, node pack `cubiq/ComfyUI_InstantID`. `InstantIDFaceAnalysis(provider="CUDA")` works on the 3090.

Plus `models/checkpoints/`: SDXL (RealVisXL_V5.0_fp16 default, juggernautXL, ponyDiffusionV6XL, AnythingXL, sd_xl_refiner, 512-inpainting-ema), SD1.5 (v1-5-pruned, dreamshaper, Deliberate, protogen, chilloutmix, realisticVision, architecturerealmix), RetroDiffusion ×3. ControlNets: SD1.5 depth/openpose/scribble + `xinsir-canny-sdxl-v2`. Upscalers: `4x-UltraSharp`, `RealESRGAN_x4plus`.

**Upscale stack** (added 2026-09-16, U1): **SeedVR2** — node pack `numz/ComfyUI-SeedVR2_VideoUpscaler` (Apache 2.0; 4+ nodes, main = `SeedVR2VideoUpscaler`), weights auto-download to `models/SEEDVR2/`. On disk: `ema_vae_fp16` (0.47 GB), `seedvr2_ema_3b_fp16` (6.32 GB), `seedvr2_ema_7b_fp16` (15.35 GB). Extra pip deps: `rotary_embedding_torch`, `gguf`, `peft`. **`resolution` is the SHORT EDGE, not a multiplier** (1024 input + `resolution=2048` → 2048). **`batch_size` must follow 4n+1** (1 for a single still). `color_correction="lab"` is the highest-fidelity mode. 24 GB → 7B fp16 with no memory tricks; drop to 3B fp16 or 7B fp8 + `blocks_to_swap`/offloading if it OOMs. Still on disk and **non-commercial**: `4x-UltraSharp`.

## Hardware ceiling: what will and won't run on this box

Host is an **AZW GTi14 mini-PC**: Intel Core Ultra 9 185H (Meteor Lake), **31 GB RAM**, **512 MB swap**, RTX 3090 **24 GB** on a PCIe **x8** link, power limit 370 W. The binding constraint is **not** VRAM — it is **host RAM + swap**, because any model larger than VRAM must be offloaded to RAM.

Measured model footprints (fp8 checkpoints, as staged by ComfyUI):

| model | UNet | text encoder | total | outcome |
|---|---|---|---|---|
| Flux.1 Kontext dev | 11.9 GB | 5.2 GB (T5 fp8) | **~17.6 GB** | ✅ works (69 s) |
| Qwen-Image-Edit-2511 | **19.6 GB** | **7.9 GB** (Qwen2.5-VL-7B fp8) | **~27.5 GB** | ❌ **hard-freezes the machine** |

**The Qwen-Image-Edit freeze (2026-09-16).** 19.6 GB + 7.9 GB = 27.5 GB against a 24 GB card forces CPU offload, and 31 GB RAM with 512 MB swap cannot absorb the offload plus the page cache for a 19.6 GB file → kernel thrash → **the whole system hangs and needs a manual reboot**. The journal of that boot ends dead on the line `Model QwenImage prepared for dynamic VRAM loading. 19582MB Staged` with **no OOM-killer entry** — the kernel never got far enough to log, which is the signature of memory-thrash lockup rather than a clean allocation failure. Practical ceiling on this box: **~18 GB of total model footprint.**

Why fp8 is not a free win here: the 3090 is **Ampere (sm_86) and has no native fp8**; ComfyUI logs `emulated ops: float8_e4m3fn` / `manual cast: torch.bfloat16`. Treat "fp8" sizes as a storage figure only on this card.

**Mitigations, cheapest first:** full analysis with measured numbers and upgrade options is in **`hardware.md`**. Short version:
1. **Cap the service so it dies instead of the machine** — add `MemoryHigh=20G` / `MemoryMax=26G` to the `comfyui` user unit. The cgroup OOM-killer then kills ComfyUI on runaway allocation; the system stays up and SSH-reachable. No sudo, no hardware.
2. **A real swapfile** (32–64 GB on the ~500 GB free NVMe) — turns a hard freeze into slow-but-alive. Needs sudo once.
3. **Use GGUF quants** for anything ≥ ~18 GB (e.g. `unsloth/Qwen-Image-Edit-2511-GGUF` Q4/Q5 ≈ 12 GB)
   + the `ComfyUI-GGUF` node pack (not installed). The only local route to Qwen on this box.
4. **Add RAM** — the GTi14 has 2× DDR5 SO-DIMM slots (up to 96 GB). Going to 64 GB makes Qwen viable (still slow: mobile CPU + x8 PCIe).
5. **Don't run it locally** — keep Kontext as the edit model, or use a cloud GPU for Qwen.

**Z-Image Turbo (U3) — the modern base model that fits:** `models/diffusion_models/z_image_turbo_bf16.safetensors` (11.46 GB) + `models/text_encoders/qwen_3_4b_fp8_mixed.safetensors` (5.25 GB) + the Flux `ae.safetensors` VAE (reused). **Apache 2.0.** Load with `CLIPLoader type="lumina2"` — *not* `qwen_image`. Turbo recipe: 8 steps, cfg 1.0, `res_multistep`/`simple`, `ModelSamplingAuraFlow(3)`, negative via `ConditioningZeroOut`. Measured 25 s @1024², **19.3 GB cgroup peak, zero OOM** — it fits where Qwen 20B fp8 does not.

**GGUF (for anything that doesn't fit at fp8):** node pack `city96/ComfyUI-GGUF` (`UnetLoaderGGUF`); quants live in `models/unet/`. Installed: `qwen-image-edit-2511-Q4_K_M.gguf` (12.34 GB, Apache 2.0) — the replacement for the fp8 Qwen that froze the box.

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
  - So to turn a **foreground** mask (e.g. `RemoveBackground`, which sets 1 on the subject) into cutout alpha, you must insert **`InvertMask`** first. Skipping it yields a perfectly inverted cutout (background kept, subject transparent) — verified in E3.
- `SaveImageWithAlpha` is **KJNodes**, not core; core has `SplitImageWithAlpha`/`JoinImageWithAlpha`.
- **Inpaint/outpaint: prefer `ComfyUI-Inpaint-CropAndStitch`** (`InpaintCropImproved` + `InpaintStitchImproved`) over the core `ImagePadForOutpaint` → inpaint → `ImageCompositeMasked` path. `InpaintStitchImproved` never VAE round-trips unmasked pixels, so the original region returns **pixel-identical** (measured mean|diff| **0.041/255** vs **6.477/255** for the core path — verified E9). `extend_for_outpainting` + `extend_*_factor` >1 does the outpaint (1.5 = +50% per side of the source size; 2 = +100%). `device_mode="gpu (much faster)"` is 30-100x over CPU; `output_resize_to_target_size=False` for non-square targets (forcing 1024² squashes a wide crop). `mask` is an *optional* input — omit it for pure canvas extension.
- **The outpaint crop must be SAMPLED at ~1 MP, not at its raw size.** The crop for a 1024² source extended 1.5× each side is 2048×1024 = **2.1 MP**, and SDXL is ~1 MP native, so at full size the invented area comes out mushy (blurry foliage, smeared wall). `output_resize_to_target_size=True` with a target matching the crop's aspect (**1536×768** here) fixes it: crisper *and* ~33% faster (12 s vs 18 s, E19). **`preresize` cannot do this** — the node runs `preresize_imm` (line ~1631) *before* `extend_imm` (~1659), so it never sees the padded canvas; `output_resize_to_target_size` is applied to the crop afterwards (~1684) and is the knob that counts. Keep the target's aspect equal to the crop's or the stitcher distorts.
- **`InpaintCropImproved`: the mask knobs run BEFORE the outpaint extension.** With `extend_for_outpainting` on and **no mask wired in**, it expands/blurs an *empty* mask, so **`mask_expand_pixels` and `context_from_mask_extend_factor` are inert** — verified in E17, where `mask_expand_pixels` 0/32/64 and context 1.2/1.5/2.0 produced *byte-identical* images. Only **`mask_blend_pixels`** still bites, because it is also handed to the stitcher as the blend width — and it is the seam knob: 8/32/64 → local seam step **19.6 / 13.4 / 11.7** (0-255 luminance, at 64 the boundary no longer stands out from its own surroundings) and colour step 16.3 → 14.8. `denoise` ≈ **0.9** then matches the colour best. At ~0.8 and below the model stops refining and starts **inventing** — on the cottage it painted a second, different cottage. The fill itself is an **edge-clamp smear** (verified in the source: the node repeats the border row/column outward — it is *not* a mirror), so that addition is prompt-driven extra content on fresh canvas, not a mirrored source surviving. A clipped object (half a tree) is **not** continued by any blend width: the extension is invented, not continued.
- **`LoadImage` reads only from `input/`.** A file in `output/` cannot be loaded — copy it into `input/` first. Corollary: stage working/intermediate images in a **subdirectory** (e.g. `input/2d/_work/`), never directly in `input/2d/`, because `scripts/publish_assets.sh` sweeps `input/2d/*.png` into `assets/` (verified: a staging file got published as an "asset").
- **Flux.1 Kontext works at ~1 MP.** `FluxKontextImageScale` snapped 2048×1024 → **1456×720**. Anything bigger must be restored afterwards (4x-UltraSharp → downscale), so an edit + upscale pair is the normal recipe, not an optional extra. Flux is distilled: **`cfg` is unused, keep 1.0**; use `FluxGuidance` (2.5 here) for prompt adherence, 20 steps, `euler`/`simple`, ~69 s on the 3090.
- **Design consistency ≠ identity.** Flux Kontext with reference images reproduces hair/outfit/silhouette convincingly and is *not* the same face — measured with insightface/antelopev2, cosine **0.187** vs InstantID's **0.823**. **Always measure identity with an embedding, never by eye** — the two results look equally "right" to a human. Face embedders need a face **≥ ~112 px** in the reference; a 1024² full-body gives ~60 px, so keep a large-face portrait as the identity source.
- **InstantID transfers the face only** and **biases composition toward a close-up bust** — prompting it for a full scene still returns a portrait, because the face embedding wants a large face. Design/clothing must come from the prompt. For full-scene character placement, use Kontext reference instead (accepting the identity trade-off) or run InstantID then composite.
- **Marigold intrinsic (U4) is a diffusers script, not a node pack.** `kijai/ComfyUI-Marigold` is depth-only. Use `scripts/marigold_pbr.py` with `MarigoldIntrinsicsPipeline` (diffusers 0.40.0). Two traps: the checkpoints ship **only fp16 variants**, so `variant="fp16"` is **mandatory** (else `no file named model.safetensors ... in text_encoder`); and the pipeline returns **one stacked array, not a dict** — appearance → `(2,H,W,3)` = [albedo, material] with material channels `(roughness, metallicity, unused)`; lighting → `(3,H,W,3)` = [albedo, shading, residual]. Runs ~768 px.
- **`SetUnionControlNetType` fails SILENTLY.** Its `type` values are *grouped by family*, not per-model: `auto, openpose, depth, hed/pidi/scribble/ted, canny/lineart/anime_lineart/mlsd, normal, segment, tile, repaint`. Passing `"canny"` is invalid, and the failure mode is nasty: **`POST /prompt` returns a `prompt_id` and the run reports `status: success` in 3 s having produced no image** — the only message (`Output will be ignored`) goes to the journal. **Any run that succeeds suspiciously fast with no output: check `journalctl --user -u comfyui`.**
- **Tiling**: `SeamlessTile` (comfyui-seamless-tiling, patches the **MODEL**) **segfaults in `libcuda.so.1`** and takes ComfyUI down — avoid. Use **`SeamlessTiling`** (TextureAlchemy, an **image-space** op: `method` = mirror/blend_edges/offset) instead; it is stable and instant. The circular-VAE route (`MakeCircularVAE` + `CircularVAEDecode`) also works but crashes on a *second* run in one session — `systemctl --user restart comfyui` between runs. Externally a crash looks like a dropped connection mid-prompt; `Restart=on-failure` silently restarts.
- **The OpenPose extractor does not see our stylised characters.** `OpenposePreprocessor` returns `people: []` on `char_knight` — a rendered figure in armour — because it is the classic COCO detector, which fails on stylised art; `DensePosePreprocessor` maps the same figure cleanly. It is worse than one asset: across 15 stylised character renders the detector found **no person in 13** (E22), so `pose_probe.py measure` cannot score our output and pose work cannot be swept or re-verified the way every other operation can. It *does* read photorealistic output (18/18 joints off one render), which is how the authored skeletons got validated. Consequence: pose verdicts are **visual**, and the metrics in `measure` are only a hint. **DensePose cannot drive the union CN** (its `type` list has no `densepose`), and the core `SDPose` keypoint nodes (ComfyUI's `comfy_extras/`) would need a checkpoint we have not fetched.
- **A ControlNet hint is only as strong as its share of the frame (E23).** A hint that occupies ~5% of the picture is worth **nothing**: a potion rotated 90° and pasted small was ignored at `depth` 0.9 *and* at `1.5/end 0.5`, and both rendered a canonical **upright** bottle. The same rotation at **50% of frame height** was followed at both settings (the bottle stays on its side, neck to the left). So scale the hint to the object's real size in the frame before blaming the model, the mode or the strength — and when a hint "does nothing", check its scale before its weight.
- **A ControlNet's `end_percent` can matter more than its `strength` (E22).** `strength` 1.5 with `end_percent` 1.0 traces the hint through the picture and destroys the render (E21c), but the *same* 1.5 with `end_percent` 0.5 imposes the hint and still renders cleanly — a T-pose cue beat a prompt that explicitly said "both arms lowered, hanging straight down at his sides", where 0.9 with a full window was ignored. Raising `strength` is the wrong reflex while the window is open; end the window early instead. What it buys is the **silhouette**, not fine configuration: with `openpose`, a 45-deg cue still renders arms at the sides, an asymmetric cue (one arm up) is ignored, and a "both arms up" cue comes back as **shoulder horns** rather than arms. `cfg` (4.0 vs 7.0) made no difference.
- **Orientation of a 2D object: rotate the pixels, then re-render.** A geometric transform survives a low/moderate-denoise img2img pass (denoise 0.5 and 0.65 both kept a bottle lying on its side and produced a clean product shot; 0.2 is near-copy; 0.5 forgot it when the cue was the tiny version), and the *image* then carries properties the text cannot override — the prompt asked for a **red** bottle and the render came back **green**, from the cue's colour. This is more reliable than any ControlNet for orientation, because a rigid rotation is a transform, not a semantic edit (E23).
- **Metric ≠ quality**: edge-continuity metrics rated `mirror`/`blend_edges` as perfect (0.00) while they looked visibly awful (symmetric kaleidoscope / blurry cross). Always confirm with eyes.
- **A colour step across a seam is CONTENT, not palette — don't reach for a colour matcher.** The same tree looking a different colour either side of an outpaint boundary is the model having painted its own foliage, and E20 measured that statistical palette matching does **not** fix it: global match left the step at 8.2 → 9.1/10.6, a local match (extension vs the adjacent original band) 8.2 → 10.3, and it *broke* a good seam (2.4 → 23.9); at strength 1.0 the extension darkened to blue-grey because the reference band's **content** (shaded wall, dark foliage) dominates its statistics. Levers that do work are generation-side: `denoise`, prompt hygiene, the controlled-fill route (E18b), or repainting the area. Palette matching is only for a **global** cast — the whole extension reading too cool/warm — and then pick the reference for its palette, not its content: `ColorMatch` (KJNodes: `image_ref`/`image_target`, `method` = mkl/hm/reinhard/mvgd, `strength`) or `ColorMatchTransfer` (TextureAlchemy: `mean_std`/`histogram`), or offline with `scripts/color_match.py`.

## How to talk to it programmatically

- `GET /system_stats`, `GET /object_info` (node schemas — the ground truth for inputs/outputs/widget names), `POST /prompt` (queue a workflow).
- **Auth**: append `?token=<token>` where token = first line of `~/Projects-Git/ComfyUI/login/PASSWORD`. (`POST /login` expects **form** data; sending JSON returns 500.)
- `POST /prompt` takes **API format** (`{node_id: {class_type, inputs}}`), not the GUI graph JSON.
- Node schema is the source of truth: whenever in doubt about a node's inputs/option values, read `/object_info` rather than trusting memory.

## Convention

Scenario-specific installs (e.g. Hy3D wrapper + weights) go in the scenario folder, not here. This folder holds only what applies to ComfyUI regardless of task.