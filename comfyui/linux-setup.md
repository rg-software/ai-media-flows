# ComfyUI Linux setup: Ubuntu 26.04 and RTX 3090

Target box: `rg_software@Beelink`, Ubuntu 26.04.1 LTS, RTX 3090, driver 595.91.07 / CUDA 13.2, 850 GB free. Python 3.14.4 is default (too new); we install **Python 3.11** (best-compatible for torch + ComfyUI nodes).

Status: **installed and running** (2026-09-15). This file started as the plan; where it disagrees with reality, trust the working notes below. Actual deviations: torch is **2.11.0+cu128** (not cu130) because comfy-kitchen 0.2.33 needs it; `custom_rasterizer` was **built from source** (nvcc 12.8 header-patch, §9), not installed from a wheel.

## 1. Python 3.11

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

## 2. NVIDIA driver (already present: 595.91.07): verify and persist

Driver + CUDA 13.2 already working. Confirm:
```bash
nvidia-smi | head -4
```
(no driver install needed; only add cuda libs if torch needs them — it ships its own).

## 3. ComfyUI from git and venv

```bash
mkdir -p ~/Projects-Git/ComfyUI && cd ~/Projects-Git/ComfyUI
python3.11 -m venv venv
source venv/bin/activate
git clone https://github.com/comfyanonymous/ComfyUI.git .
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```
> `cu128` because comfy-kitchen 0.2.33 needs torch 2.11.0+cu128 (not cu130).
> ComfyUI also ships default custom-node manager; install `ComfyUI-Manager` per its repo if not bundled.

## 4. custom_rasterizer (built from source)

Needed by Hy3D texture bake. There is no usable wheel for this torch/CUDA combo, so it is compiled on the box — full recipe in §9. (An early plan to pull a manylinux wheel from the wrapper repo did not survive contact with torch 2.11+cu128.)

## 5. Repeat the rest of the node list (via ComfyUI-Manager on first GUI boot)

- comfyui-hunyuan3dwrapper (above)
- ComfyUI-3D-Pack (if needed; includes BPT TrimeshSave etc.)
- comfyui-unirig (rigging — **bpy works on Linux**, re-test E4)
- comfyui-marigold, comfyui-controlnet-aux, was-node-suite, KJNodes, Impact-Pack
- ComfyUI-Login (restores the password login screen)

## 6. Verify (smoke checklist)

1. ComfyUI boots; `/object_info` shows Hy3D + MoGe.
2. `hy3d-shape` (scratch) → GLB.
3. `hy3d-full` → textured GLB (custom_rasterizer wheel OK).
4. `hy3d-multiview`.
5. UniRig rigging — installed and passing (E4-L).
6. SDXL 2D base art.

## 7. Service and remote access

### ComfyUI runs as a systemd *user* service
Deployed unit: `~/.config/systemd/user/comfyui.service` (versioned copy: `comfyui/comfyui.service`). It is `enabled` and `active`; the process is `venv/bin/python main.py --listen --disable-api-nodes` on `0.0.0.0:8188`.

```bash
systemctl --user status comfyui        # active (running)
systemctl --user restart comfyui       # NO sudo
journalctl --user -u comfyui -f
```
`sudo systemctl restart comfyui` reports **not-found** — that's system scope; the unit is user scope. Do not add a sudoers rule for this; none is needed.

**Linger is OFF** (`loginctl show-user rg_software` → `Linger=no`), so the service does not start at boot until someone logs in. Fix once:
```bash
sudo loginctl enable-linger rg_software
```

### Network topology (why SSH is indirect)
- Front router forwards all HTTPS to **Synology `192.168.1.40`**; nginx there (in Docker) routes by hostname to the **Beelink `192.168.1.46`** (`:8188`).
- The Synology runs sshd on **port 5022** (public). Its `AllowTcpForwarding no` blocks `-J`/ProxyJump.
- The Beelink's sshd listens on `:22` but is not forwarded to the internet.

Agent access therefore chains: **Windows → Synology:5022 → nested SSH → Beelink:22.**
```bash
# from the Windows dev box (key authorized on the Synology)
ssh -p 5022 rg_software@rt247a.ddns.me \
  "ssh -i ~/.ssh/beelink rg_software@192.168.1.46 '<command>'"
```
A dedicated ed25519 key (`~/.ssh/beelink` on the Synology, comment `synology-to-beelink`) is authorized on the Beelink. For non-trivial remote scripts, base64-encode to avoid quoting issues:
```bash
# powershell
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
# then: ssh ... "ssh -i ~/.ssh/beelink rg_software@192.168.1.46 'echo $b64 | base64 -d | bash'"
```

**Two traps in that command, both of which look like the box being down.** Write it exactly as above: `-J rt247a.ddns.me:5022` silently uses the *local* username for the jump host (so it authenticates as your Windows user, not `rg_software`, and falls back to a password prompt that hangs a non-interactive shell), and `AllowTcpForwarding no` means ProxyJump could never work there anyway — the nested `ssh` is the mechanism, not a convenience. And a non-interactive ssh does not source the profile, so `uv` is not on `PATH`: run the tooling as `~/.local/bin/uv run python …` or the repo venv's `.venv/bin/python scripts/…`.

### File transfer, the same way round

A single file comes back over the same two hops - **box -> NAS -> Windows** - because the file has to land on the NAS before Windows can see it. From Windows (the inner command runs on the NAS):

```bash
# 1. NAS pulls it off the Beelink into its own home
ssh -i ~/.ssh/id_rsa -p 5022 rg_software@rt247a.ddns.me \
  "scp -i ~/.ssh/beelink rg_software@192.168.1.46:/path/on/beelink ~/x.flac"
# 2. Windows pulls it off the NAS
scp -O -i $env:USERPROFILE\.ssh\id_rsa -P 5022 rg_software@rt247a.ddns.me:~/x.flac ./x.flac
```

**`-O` is not optional.** The Synology's sshd does not run the SFTP **subsystem**, and a modern `scp` asks for it by default, so the plain form fails with `subsystem request failed on channel 0`. `-O` selects the legacy protocol, which needs no subsystem. That is the third thing on this page that looks like a broken box and is a flag.

**Verify the copy**, because a truncated transfer is otherwise silent: `md5sum` on the far side against `Get-FileHash -Algorithm MD5` on this one. The ComfyUI `/view` route (`scripts/comfy_io.py`, see S14 in `HOWTO.md`) is usually simpler - it needs the token but no SSH - so this route is for when you have no token, or the file is large, or it sits somewhere `/view` does not serve.

### API access with ComfyUI-Login
The login plugin (ComfyUI-Login) blocks `/object_info`, `/prompt`, etc. with 401. It accepts a **token query param**; the token is the first line of `~/Projects-Git/ComfyUI/login/PASSWORD`:

```bash
TOKEN=$(head -1 ~/Projects-Git/ComfyUI/login/PASSWORD)
curl -s "http://127.0.0.1:8188/object_info?token=$TOKEN"
```
Then POST an **API-format** prompt (`{node_id: {class_type, inputs}}`, not the GUI graph):
```python
urllib.request.Request(f"{BASE}/prompt?token={quote(TOKEN)}", data=json.dumps({'prompt': api}).encode(),
                       headers={'Content-Type': 'application/json'})
```
`POST /login` expects **form data** (`username`, `password`) — sending JSON yields a 500. Prefer the token. The `workflows/*.json` files are the GUI format; API submissions need the node->inputs form (generate it with `GET /object_info` for signatures).

## Repo docs to consult
- `3d/setup-hy3d.md` (weights + Hy3D node specifics)
- `3d/hy3d-knobs.md`, `3d/EXPERIMENTS.md`

## 8. Rebuild notes (migrated from retired HANDOFF.md)

Rebuild `custom_rasterizer` (nvcc 12.8 header patch — glibc 2.41 redeclares `cospi/cospif/rsqrt/rsqrtf/sinpi/sinpif` `noexcept(true)` in `bits/mathcalls.h`, and nvcc 12.8 emits "exception specification is incompatible" unless its own header matches; add `noexcept` to those decls in `<conda128>/targets/x86_64-linux/include/crt/math_functions.h`):
```
cd ~/Projects-Git/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/hy3dgen/texgen/custom_rasterizer
pip uninstall -y custom_rasterizer; rm -rf build dist
export CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13
export CUDA_HOME=$HOME/miniconda3/envs/cuda128
export PATH=$HOME/miniconda3/envs/cuda128/bin:$PATH
export TORCH_CUDA_ARCH_LIST='8.6'
pip install . --no-build-isolation
```
Do NOT use nvcc 13.2 (torch 2.11+cu128 hard-errors on the major mismatch). Result: `custom_rasterizer-0.1.0+torch2110.cuda128` wheel, `import custom_rasterizer_kernel` OK.

Runtime deps the wrapper needs beyond its requirements.txt (install before running):
```
pip install omegaconf pyrootutils timm rembg onnxruntime pynanoinstantmeshes
```
(`rembg` without `onnxruntime` first hangs silently downloading `bria-rmbg-2.0.onnx` — install onnxruntime first.) For the textured render check (`Hy3DNvdiffrastRenderer`, E7):
```
pip install ninja nvdiffrast
pip install "utils3d @ git+https://github.com/EasternJournalist/utils3d.git@580474822b0a72098f687dbe820c38f1214edfec"
```
Pin `utils3d`: upstream master renamed `intrinsics_from_fov_xy` → `intrinsics_from_fov`; commit `5804748` (2025-08-31) still defines it. Restart `comfyui` after installing (stale `sys.modules` otherwise).

API-only submissions need current node signatures (Linux wrapper is newer than some saved workflows): `Hy3DModelLoader.attention_mode` is now a combo; `Hy3DGenerateMeshMultiView.scheduler` is named; `Hy3DSampleMultiView.scheduler` is link-only (drop stale `'fixed'` widget values); keep model paths forward-slash.

Weights (on disk; re-download sources if ever needed): `tencent/Hunyuan3D-2.1` → `hy3dgen/model.fp16.ckpt`; `tencent/Hunyuan3D-2mv` → `hy3dgen/hunyuan3d-dit-v2-mv-fast/model.fp16.safetensors`; `Comfy-Org/MoGe` → `moge_2_vitl_normal_fp16.safetensors`. Paint/delight diffusers auto-download on first texture run (~14 GB).