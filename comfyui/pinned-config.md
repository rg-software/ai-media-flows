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

Then confirm: `venv/bin/python -c "import torch; print(torch.__version__)"` says `2.11.0+cu128`, and Hy3D loads (`import custom_rasterizer_kernel` works). The custom nodes are separate repos - restore any one of them the same way if the update moves it and something breaks.

## Notes left in the checkout at pin time

- `login/` is untracked by design (it holds `PASSWORD`) and `object_info.json` was a scratch dump from an earlier session. Neither blocks a fast-forward, but per this repo's own rule a scratch file inside a checkout is a liability; the dump was moved to the home directory before the update.
- Two custom-node repos are dirty, one file each (`ComfyUI-seamless-tiling`, `ComfyUI-TextureAlchemy`) - their state is whatever `pip freeze` and the revisions above describe, and they are not part of the ComfyUI update.
