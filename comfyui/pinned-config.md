# Pinned config: the rollback point before the 2026-09-28 ComfyUI upgrade

A snapshot of the box's working state, taken **before** updating ComfyUI so the update is reversible. The raw package list is beside this file: `pinned-config-freeze-2026-09-28.txt` (337 packages, from `venv/bin/pip freeze`).

## What is pinned

| what | state |
|---|---|
| ComfyUI | `a7b1d39d342d102f305797fb5ba12dc304d9c1f5` on `master` (`a7b1d39d`, 2026-09-09, "Update instructions for manual install on windows AMD") |
| python | 3.11.16 |
| **torch** | **2.11.0+cu128** (CUDA 12.8) — against a driver reporting CUDA 13.2 |
| torchaudio / torchvision | 2.11.0+cu128 / 0.26.0+cu128 |
| transformers / diffusers | 5.17.0 / 0.40.0 |
| numpy / onnxruntime / safetensors | 2.4.6 / 1.30.0 / 0.8.0 |
| models | 105 files over 10 MB, **322 GB** total |
| custom nodes | 18, each its own repo, at the revisions below |

```
ComfyUI-CameraPack               a58268f      ComfyUI-KJNodes                 5710537
comfyui_controlnet_aux           59b1fc4      ComfyUI-Login                   5fce303
ComfyUI-GGUF                     6ea2651      ComfyUI-Manager                 6c120969
ComfyUI-Hunyuan3DWrapper         2609efa      ComfyUI-Marigold                2adfec7
ComfyUI-Inpaint-CropAndStitch    00d4776      ComfyUI-PixelArt-Detector       d5ed602
ComfyUI_InstantID                72495e8      ComfyUI-QFX-PBRGenerator        a565b16
ComfyUI_IPAdapter_plus           a0f451a      ComfyUI-seamless-tiling         9225ed5
ComfyUI-TextureAlchemy           0afda45      ComfyUI-UniRig                   69ee59d
PuLID_ComfyUI                    93e0c4c      seedvr2_videoupscaler           4490bd1
```

## After the update (2026-09-28)

**The update was clean.** ComfyUI went `a7b1d39d` -> **`8d534945`** (2026-09-27) and **torch did not move** - it was pinned on the install command line precisely so it could not, since `requirements.txt` lists torch unpinned and the freeze alone cannot restore `custom_rasterizer`. Eight packages changed: `comfyui_frontend_package` 1.52.6 -> **1.53.6**, `comfy-kitchen` 0.2.33 -> 0.2.35, `comfy-aimdo` 0.5.3 -> 0.5.5, `comfyui-embedded-docs` 0.5.11 -> 0.5.12, `comfyui_workflow_templates` 0.11.57 -> 0.11.70 and the workflow-templates core/json/media packages. The raw list is `pinned-config-freeze-after-2026-09-28.txt` (338 packages).

Verified afterwards: `torch 2.11.0+cu128`; **`custom_rasterizer_kernel` imports** - but import **torch first**, since the extension needs torch's `libc10.so` already loaded, which is exactly what a one-line test of mine got wrong and briefly reported as a failure; a real generation runs; the node types went 1247 -> **1264**; and **all 35 of our workflows still validate** with 0 contradictions.

**What arrived:** the YuE 2 nodes (`YuE2GenerateMusic`, `SheetSage2AudioToABC`) - music *and* the cover/restyle route ACE-Step does not expose. The Mel-Band RoFormer and Chatterbox TTS nodes are **still absent**, and their templates carry no pack id, so those two are a *node-pack install* rather than something the update brings.

**The frontend bump fired the Load3D texture re-check, and it is answered.** User visual check on 1.53.6 (2026-09-28): the `Load3D` viewport renders the mesh but not its texture (grey, material mode `original`) - so the verdict is unchanged and the `Textured turntable` workaround stays - and the recorded diagnosis did not survive reading the source. See the open items.

## The real risk, named

**`custom_rasterizer` was built from source against exactly this torch and CUDA.** It is the one component the freeze alone cannot restore: it needs nvcc **12.8** (not 13.2, which hard-errors on the major mismatch), gcc-13, `TORCH_CUDA_ARCH_LIST=8.6`, and the header patch recorded in `HANDOFF.md` and `3d/EXPERIMENTS.md`. So an upgrade that **moves torch off 2.11.0+cu128** means rebuilding it, and an upgrade that leaves torch alone does not. Everything Hy3D does depends on it, so check that first after any update.

The **UniRig** rigger runs in its own pixi environment (bpy 4.2 LTS) and is unaffected by the venv.

## What to expect to change

- `comfyui-frontend-package` will bump, which is the **trigger** for the Load3D/Preview3D texture re-check (`3d/workflows/scratch/load3d-texture-probe.json`, recorded on that flow's note and in the open items).
- New nodes arrive with the update: see `audio/EXPERIMENTS.md` PENDING for the audio models this unblocks (Mel-Band RoFormer separation, Chatterbox TTS, YuE 2 - and the templates package is already ahead of the code).

## How to restore this pin

```bash
cd ~/Projects-Git/ComfyUI
git checkout a7b1d39d342d102f305797fb5ba12dc304d9c1f5
venv/bin/pip install -r ~/Projects-Git/ai-gamedev-tasks/comfyui/pinned-config-freeze-2026-09-28.txt \
  --extra-index-url https://download.pytorch.org/whl/cu128      # +cu128 wheels need that index
systemctl --user restart comfyui
```

Then confirm: `venv/bin/python -c "import torch; print(torch.__version__)"` says `2.11.0+cu128`, and Hy3D loads (and it must be imported **after** torch: `import torch, custom_rasterizer_kernel`). The custom nodes are separate repos - restore any one of them the same way if the update moves it and something breaks.

## Local components on the box (2026-10-05, E19) - not in any pin

**`custom_nodes/audio_latent_mask/`** - `SetAudioLatentNoiseMask`, a ~10-line node that is a required component, not a convenience. **Regenerating an audio region (masked-latent repaint) does not run without it**, because the core `SetLatentNoiseMask` reshapes every mask to 4-D, which is right for image latents and wrong for a 3-D audio latent (its `reshape_mask` path then needs a 3-D mask and errors). The node stores the mask unchanged so the 1-D path works. Source is mirrored in this repo at `audio/custom_nodes/audio_latent_mask/__init__.py` - **if the node directory is lost from the box, restore it from there** (a custom node has no `pip freeze` entry, so nothing else records it). Measured: E19.

## Local patches on the box (2026-10-05, E18d) - not in any pin

`ComfyUI-kaola-ace-step` (ACE-Step's own nodes: text2music, **cover**, **repaint**, understand) is installed on the box and **carries four hand-applied patches plus two installed packages**, none of them upstream. They are the difference between the pack working and the node existing without an engine. Record them here because a `git pull` on that pack, a `pip install -U`, or a venv rebuild silently undoes them.

| what | where | why |
|---|---|---|
| `acestep_repo` re-cloned from **`ace-step/ACE-Step-1.5`** at the pinned commit `45d9783b` | `custom_nodes/ComfyUI-kaola-ace-step/acestep_repo` | **`.gitmodules` says `ACE-Step-1.5` but it had been cloned from `ACE-Step`** - a different repository, so the pin did not exist and the checkout fell back to that repo's `main`, which has no `handler.py` / `inference.py` / `llm_inference.py`. The tell is `checkpoint_dir` reading `[[""]]` in `/object_info`: the node registered, but `ACESTEP_AVAILABLE` was False. |
| `pip install loguru vector_quantize_pytorch` | venv | both are hard imports of the vendored engine |
| `levels_tensor` / `_levels` / `_basis` / `implicit_codebook` forced to `device='cpu'` | `residual_fsq.py` + `finite_scalar_quantization.py`, in the `vector_quantize_pytorch` package (`.orig`, `.orig2` kept) | **transformers 5.17 builds `trust_remote_code` models under a meta device**, so these *non-persistent* buffers - never restored from the checkpoint, so they must be real at init - landed on meta (`Tensor.item() cannot be called on meta tensors`). This is the pattern transformers itself documents in `initialization.py::meta_device_safe_creation_ops`. |
| `_get_attention_implementation()` returns `eager` | `acestep_wrapper.py`, in the pack (`.orig` kept) | transformers 5.x now **rejects** rather than warns about `flash_attention_2` on a model declaring no `_supports_flash_attn`, and the wrapper's own fallback only covered `sdpa -> eager`. |
| `ACESTEP_DTYPE` env override on `self.dtype` | same file | a knob, not a fix: fp32 does **not** cure the NaNs below |

**Known open defect (E18d):** the **first** generation after a `systemctl --user restart comfyui` succeeds and **every later one in the same process returns all-NaN latents** - 1 success in 10, bf16 and fp32 alike. Not diagnosed; it is handler state, not dtype.

**Also in this pack, unmeasured:** `ACE_STEP_Cover` (`audio_cover_strength`, "use LOWER 0.1-0.3 for more style change") and `ACE_STEP_Understand`. The first bears on E5/E5b, which concluded ACE-Step's restyle was out of reach in-graph.

## Notes left in the checkout at pin time

- `login/` is untracked by design (it holds `PASSWORD`) and `object_info.json` was a scratch dump from an earlier session. Neither blocks a fast-forward, but per this repo's own rule a scratch file inside a checkout is a liability; the dump was moved to the home directory before the update.
- Two custom-node repos are dirty, one file each (`ComfyUI-seamless-tiling`, `ComfyUI-TextureAlchemy`) - their state is whatever `pip freeze` and the revisions above describe, and they are not part of the ComfyUI update.

## Added 2026-10-07: the voice cell (Chatterbox TTS)

- `custom_nodes/ComfyUI_Fill-ChatterBox` @ **f7d7a16** (`git clone --depth 1`, github.com/filliptm). Nodes: `FL_ChatterboxTTS`, `FL_ChatterboxTurboTTS`, `FL_ChatterboxMultilingualTTS`, `FL_ChatterboxVC`, `FL_ChatterboxDialogTTS`.
- Deps added to the venv: `resampy`, `s3tokenizer`, `conformer` (the rest of its `requirements.txt` was already satisfied). **Verified unmoved:** numpy 2.4.6, torch 2.11.0+cu128, transformers 5.17.0 - so `custom_rasterizer` is untouched.
- Weights download on first use to `models/chatterbox/` (not committed, as usual).
- Service restarted clean; the pack imports in 0.2 s, and the first take checked out (**E25**).
- **Declined the same day:** Mel-Band RoFormer - in-graph separation was never needed, and our own separation was never clean enough to build on (E15/E16).
