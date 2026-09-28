# ComfyUI Linux setup: Ubuntu 26.04 and RTX 3090

Target box: `rg_software@Beelink`, Ubuntu 26.04.1 LTS, RTX 3090, driver 595.91.07 / CUDA 13.2, 850 GB free. Python 3.14.4 is default (too new); we install **Python 3.11** (best-compatible for torch + ComfyUI nodes).

Status: **installed and running** (2026-09-15). This file started as the plan; where it disagrees with reality, trust the working notes below (and `HANDOFF.md`). Actual deviations: torch is **2.11.0+cu128** (not cu130) because comfy-kitchen 0.2.33 needs it; `custom_rasterizer` was **built from source** (nvcc 12.8 header-patch), not installed from a wheel.

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
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
```
> `cu130` matches the driver; torch 2.10.0+cu130 has cp311 manylinux wheels (verified).
> ComfyUI also ships default custom-node manager; install `ComfyUI-Manager` per its repo if not bundled.

## 4. custom_rasterizer (the one-time Windows pain: now a wheel on Linux)

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

## 7. Verify (smoke checklist)

1. ComfyUI boots; `/object_info` shows Hy3D + MoGe.
2. `hy3d-shape` (scratch) → GLB.
3. `hy3d-full` → textured GLB (custom_rasterizer wheel OK).
4. `hy3d-multiview`.
5. UniRig rigging — re-attempt (was Windows-bpy-blocked).
6. SDXL 2D base art.

## 8. Service and remote access

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
- `HANDOFF.md` (the box handoff: environment, blockers, next steps)
- `3d/setup-hy3d.md` (weights + Hy3D node specifics)
- `3d/hy3d-knobs.md`, `3d/EXPERIMENTS.md`