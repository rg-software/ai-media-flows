# ComfyUI Linux setup — Ubuntu 26.04 + RTX 3090

Target box: `rg_software@Beelink`, Ubuntu 26.04.1 LTS, RTX 3090, driver 595.91.07 / CUDA 13.2, 850 GB free.
Python 3.14.4 is default (too new); we install **Python 3.11** (best-compatible for torch + ComfyUI nodes).

Status: ComfyUI NOT installed yet. This is a fresh, clean setup.

## 1. Python 3.11

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

## 2. NVIDIA driver (already present: 595.91.07) — verify + persist

Driver + CUDA 13.2 already working. Confirm:
```bash
nvidia-smi | head -4
```
(no driver install needed; only add cuda libs if torch needs them — it ships its own).

## 3. ComfyUI from git + venv

```bash
mkdir -p ~/Projects-Git/ComfyUI && cd ~/Projects-Git/ComfyUI
python3.11 -m venv venv
source venv/bin/activate
git clone https://github.com/comfyanonymous/ComfyUI.git .
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
```
> `cu130` matches the driver; torch 2.10.0+cu130 has cp311 manylinux wheels (verified).
> ComfyUI also ships default custom-node manager; install `ComfyUI-Manager` per its repo if not bundled.

## 4. custom_rasterizer (the one-time Windows pain — now a wheel on Linux)

Needed by Hy3D texture bake. Pull from the wrapper's manylinux wheel:
```bash
cd ~/Projects-Git/ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-Hunyuan3DWrapper.git
cd ComfyUI-Hunyuan3DWrapper
pip install -r requirements.txt
pip install wheels/custom_rasterizer-0.1-*.whl   # manylinux wheel
```

## 5. Repeat the rest of the node list (via ComfyUI-Manager on first GUI boot)

- comfyui-hunyuan3dwrapper (above)
- ComfyUI-3D-Pack (if needed; includes BPT TrimeshSave etc.)
- comfyui-unirig (rigging — **bpy works on Linux**, re-test E4)
- comfyui-marigold, comfyui-controlnet-aux, was-node-suite, KJNodes, Impact-Pack
- ComfyUI-Login (restores the password login screen)

## 6. Restore bits from the Windows backup

```bash
# your workflows + settings + API keys
cp -r <backup>/user/* ~/Projects-Git/ComfyUI/user/
# test/input images
cp -r <backup>/input/* ~/Projects-Git/ComfyUI/input/
# weights (optional — else re-download, identical files)
cp -r <backup>/models/* ~/Projects-Git/ComfyUI/models/
```
Rest of the repo (workflows, docs) is already on GitHub:
```bash
git clone https://github.com/rg-software/ai-gamedev-tasks.git
```

## 7. Verify (smoke checklist from `linux-migration.md`)

1. ComfyUI boots; `/object_info` shows Hy3D + MoGe.
2. `hy3d-shape` (scratch) → GLB.
3. `hy3d-full` → textured GLB (custom_rasterizer wheel OK).
4. `hy3d-multiview`.
5. UniRig rigging — re-attempt (was Windows-bpy-blocked).
6. SDXL 2D base art.

## Repo docs to consult
- `comfyui/linux-migration.md` (carry vs re-provision)
- `3d/setup-hy3d.md` (weights + Hy3D node specifics)
- `3d/hy3d-knobs.md`, `3d/EXPERIMENTS.md`