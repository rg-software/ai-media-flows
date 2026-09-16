# Upgrade TODO — Beelink GTi14 (owner: user)

Actionable checklist derived from `hardware.md`. Ordered by value. Each task has a
**Do → Verify** pair so a change can be confirmed rather than assumed.

Context: the box has **32 GB RAM / 512 MB swap**, and that — not the 24 GB RTX 3090 — is what
stopped Qwen-Image-Edit (27.5 GB of model) from running. Measured ceiling today is ~18 GB of total
model footprint.

---

## Task 1 — Swapfile (free, ~5 min, do first)

Turns "machine hangs" into "slow but alive" and gives the kernel somewhere to put cold pages.

```bash
sudo swapoff /swapfile
sudo fallocate -l 32G /swapfile          # 64G is fine too; NVMe has ~500 GB free
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# keep swap a safety net, not a crutch
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf
sudo sysctl -w vm.swappiness=10

# persist across reboots (a swapfile entry usually already exists)
grep -i swap /etc/fstab
```

**Verify**
```bash
free -h                      # Swap: should show ~32Gi
swapon --show                # /swapfile, 32G
cat /proc/sys/vm/swappiness  # 10
```
Then reboot once and re-check `free -h` to confirm it comes back automatically.

---

## Task 2 — RAM 32 GB → 96 GB ⭐ highest value

The single change that alters what is possible: offloading becomes safe, **Qwen-Image 20B fp8
(27.5 GB) becomes runnable**, FLUX.2 dev INT4 becomes plausible, and the freeze class disappears.

### What is in there now — **confirmed via `sudo dmidecode -t memory` (2026-09-16)**

| | |
|---|---|
| Configuration | **2 × 16 GB DDR5-5600 SO-DIMM, BOTH SLOTS OCCUPIED** (1 DIMM per channel) |
| Part number | **Crucial `CT16G56C46S5.C8D`** (both slots, matched pair — serials `E93D3AEE` / `E93D3AE1`) |
| Speed | 5600 MT/s rated, **5600 MT/s *configured*** — i.e. running at full rated speed |
| Rank | **1 (single-rank)** |
| Locators | `Controller0-ChannelA-DIMM0`, `Controller1-ChannelA-DIMM0` |

Two things follow from this that matter for the upgrade:

1. **No free slot** — reaching 64/96 GB means **replacing both sticks**.
2. The current modules are **single-rank**, and they comfortably hold 5600. The 48 GB modules are
   **dual-rank (`2Rx8`)**. Dual-rank is the usual reason a SODIMM kit lands below its rated speed.
   Offsetting that: we run **one DIMM per channel** (not 2 DPC), which is the configuration Intel's
   "speed may be lower when populating multiple DIMMs per channel" footnote is about — so 2×48 GB
   has a good chance of holding 5600, but **verify the configured speed after installing**.

*Earlier this was read without root from EDAC (`/sys/devices/system/edac/mc/mc*/dimm*/size` →
four entries of 8192 MB; DDR5 SO-DIMMs carry two 32-bit sub-channels each, so 2 physical sticks
appear as 4 EDAC entries — which is also why Meteor Lake reports as "quad channel"). EDAC mislabels
DDR5 as `Unbuffered-DDR3`; ignore that.*

### What to buy

The Core Ultra 9 185H officially supports **96 GB max, DDR5-5600** (Intel spec), and the GTi14 has
**2 SO-DIMM slots, max 48 GB per slot**.

| target | kit | part number | note |
|---|---|---|---|
| **96 GB** ⭐ | 2× 48 GB DDR5-5600 SODIMM | **Crucial `CT2K48G56C46S5`** | Intel's documented maximum; CL46, 1.10 V, 262-pin, non-ECC |
| 64 GB | 2× 32 GB DDR5-5600 SODIMM | Crucial `CT2K32G56C46S5` | cheaper, still clears Qwen fp8 comfortably |
| — | alternatives | Kingston `KVR56S46BD8K2-96` / Corsair `CMSX96GX5M2B5600C44` | same class |

**Caveat, and why it doesn't matter for us:** 48 GB modules are **dual-rank (`2Rx8`)** while the
current 16 GB sticks are single-rank — dual-rank is the usual reason a kit lands below its rated
speed. Because we run one DIMM per channel, 2×48 GB has a good chance of holding 5600 anyway.
Even if it downclocks to 5200/4800, **it is irrelevant to our workload**: we are buying *capacity*
to hold offloaded model weights, not bandwidth, and diffusion inference is not
memory-bandwidth-bound. Capacity is the whole point.

Prices vary a lot by region — check locally before ordering.

**Fit:** GTi14 Ultra, 158×158×56 mm; the two SO-DIMM slots are behind the bottom panel.

**Verify after install**
```bash
free -h                              # Mem: should total ~94Gi
sudo dmidecode -t memory | grep -Ei 'size|configured memory speed|part number'
#   expect 2x 48GB; note the *Configured* speed (5200/4800 is fine and expected)
```

### Task 2b — ⚠ raise the ComfyUI memory guard to match (do NOT skip)

The service is deliberately capped so an oversized model kills ComfyUI instead of the machine.
Those values assume 32 GB. **After** the RAM upgrade, edit
`~/.config/systemd/user/comfyui.service` (repo copy: `comfyui/comfyui.service`):

```ini
MemoryHigh=72G      # was 20G
MemoryMax=88G       # was 24G
MemorySwapMax=8G    # unchanged
```

Rule of thumb: keep every value at least ~6 GB below installed RAM (96 → High 72, Max 88).

```bash
systemctl --user daemon-reload
systemctl --user restart comfyui
systemctl --user show comfyui -p MemoryHigh -p MemoryMax   # confirm new values
```

**Then re-test the model that failed:** it should run, slowly, without hanging.

---

## Task 3 — GPU (optional; only after Task 2)

The GTi14 exposes **PCIe 5.0 x8** through the bottom door into the Beelink **EX dock** (built-in
600 W PSU, rated for cards up to 600 W). x8 at gen 5 ≈ x16 at gen 4, so bandwidth is not the
limiting factor for diffusion inference.

**The meaningful step is VRAM, not speed:**

| card | VRAM | unlocks | note |
|---|---|---|---|
| RTX 3090 (current) | 24 GB | today's stack | 370 W |
| **RTX 5090** | **32 GB** | Qwen fp8 + encoder resident; FLUX.2 dev INT4/INT8; video models | 575 W — fits the 600 W dock; ~$2k |
| RTX 4090 | 24 GB | same capacity as now, just faster | **poor value for us** — no VRAM gain |
| RTX 6000 Ada / RTX PRO 6000 | 48 / 96 GB | FLUX.2 dev at INT8/FP8; LoRA training | workstation money |
| Cloud A100 80 GB | 80 GB | everything | ~$1.4/hr — better for one-off top-tier jobs |

**Verify after install**
```bash
nvidia-smi --query-gpu=name,memory.total,pcie.link.gen.current,pcie.link.width.current --format=csv
# expect: <card>, ~32760 MiB (5090), link gen 5 x8 under load (idle reports gen 1)
```
Also confirm the dock's PSU headroom before buying anything above 600 W.

---

## Task 4 — Keep learning honest (no hardware)

- **Before pulling any model over ~10 GB**, check its expected footprint against the ceiling in
  `hardware.md`. The failure mode is a machine-wide hang, not a tidy error.
- Prefer **GGUF quants** locally above ~14 GB of weights, and **cloud** for the 32B+ tier.
- The models that fit are also the **licence-clean** ones (Z-Image Turbo, SeedVR2, Marigold, Qwen
  GGUF — all Apache-2.0), so the fit constraint and the licence goal point the same way.

---

## Status

- [x] Swapfile — *(commands above; pending you)*
- [ ] RAM 96 GB — *(purchase + install)*
- [ ] Raise the memory guard to match — **required with RAM, easy to forget**
- [ ] GPU (optional)
