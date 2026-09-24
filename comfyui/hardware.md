# Hardware: what fits, and what to upgrade (2026-09-16)

Written after Qwen-Image-Edit-2511 fp8 **hard-froze the machine** (see `README.md` → "Hardware ceiling"). Purpose: answer "does the model fit?" with measurements instead of guesses, and map the upgrade options to the work we actually want to do.

## The box

| | |
|---|---|
| Chassis / board | **AZW GTi14** (Beelink GTi14 Ultra), 158×158×56 mm |
| CPU | Intel **Core Ultra 9 185H** (Meteor Lake, 16C/22T) — *mobile* CPU |
| RAM | **64 GB** (2×32 GB DDR5-5600 SO-DIMM, installed 2026-09-24) — **62 GiB usable** after firmware reserve; 2 slots, max 96 GB |
| Swap | **32 GB swapfile** (`/swapfile`, persisted in `/etc/fstab`, `vm.swappiness=10`); the unit caps its own swap at `MemorySwapMax=8G` |
| GPU | **RTX 3090 24 GB**, Ampere sm_86, power limit 370 W |
| GPU link | **PCIe 5.0 x8** interface (bottom door) → Beelink **EX dock** with built-in **600 W PSU**, supports cards "up to 600 W" (4090-class and below) |
| Storage | NVMe, ~500 GB free |

Two consequences that are easy to miss:

- **The binding constraint *was* host RAM, not VRAM.** Anything larger than VRAM is offloaded to system memory; at 32 GB with 512 MB swap a ~20 GB offload thrashed the kernel and froze the box. **Since 2026-09-24: 64 GB (62 GiB usable) + a 32 GB swapfile**, so that class is gone — Qwen-Image-Edit fp8 (27.5 GB of weights) now completes, measured at a **29.9 GB cgroup peak** under a 48G soft / 56G hard guard. The current limit is *speed*, and VRAM for the 32B+ tier.
- **Ampere has no native fp8.** ComfyUI logs `emulated ops: float8_e4m3fn` / `manual cast: torch.bfloat16`. On this card an "fp8" size is a *storage* figure, and fp8 checkpoints bring no speed advantage the way they do on Ada/Blackwell.

## Measured model footprints (all verified on this box)

Model = diffusion weights; +enc = text encoder; the *peak* column is what has to be resident somewhere (VRAM ∪ RAM) at the worst moment.

| workload | model | weights | +enc | peak | verdict |
|---|---|---|---|---|---|
| Base art | SDXL (RealVisXL) | ~7 GB | 1.4 GB | ~9 GB | ✅ easy |
| Base art | **Z-Image Turbo** (6B, Apache-2.0) | 11.5 GB bf16 | 5.3 GB (Qwen3-4B fp8) | ~17 GB | ✅ **fits with room** |
| Control | ControlNet SDXL | 2.5 GB | — | ~3 GB | ✅ |
| Edit / relight | **Flux.1 Kontext dev** fp8 | 11.9 GB | 5.2 GB (T5 fp8) | ~17.6 GB | ✅ works, 69 s |
| Edit / relight | Qwen-Image-Edit-2511 **fp8** | **19.6 GB** | **7.9 GB** | **~27.5 GB** | ✅ **runs since 64 GB** (peak 29.9 GB, ~5 min) — ❌ hard-froze at 32 GB |
| Edit / relight | Qwen-Image-Edit-2511 **GGUF Q4_K_M** | 12.3 GB | 7.9 GB | ~20 GB | ⚠ fits, needs RAM headroom |
| Edit / relight | Qwen-Image-Edit-2511 **GGUF Q5_K_M** | 14.0 GB | 7.9 GB | ~22 GB | ⚠ tight |
| Upscale | **SeedVR2 7B** fp16 | 15.4 GB | 0.5 GB | ~16 GB | ✅ works, 39 s |
| Upscale | SeedVR2 3B fp16 | 6.3 GB | 0.5 GB | ~7 GB | ✅ easy |
| PBR intrinsics | Marigold (SD1.5-scale) | ~1.7 GB | 0.65 GB | ~2.5 GB | ✅ easy |
| Gen | FLUX.2 [dev] INT4 (32B) | ~18 GB | ~9 GB (24B enc) | ~27 GB+ | ❌ |
| Gen | FLUX.2 [dev] FP16 (32B) | ~70 GB | — | 70 GB+ | ❌ (needs 80 GB GPU) |

**Empirical ceiling (2026-09-24): ~30 GB of *total* footprint.** The fp8 Qwen run peaked at 29.9 GB with the 48/56 GB guard and never touched the soft limit. The ~18 GB figure below/above was the 32 GB-era ceiling, where offload thrashed. Above ~30-40 GB, GGUF quants or cloud are still the honest answer.

## Upgrade options, by value

### 1. A real swapfile: free, do it first
32–64 GB on the ~500 GB free NVMe. Turns "machine hangs" into "slow but alive", and gives the kernel somewhere to put cold pages. Safe for every future run, not just Qwen.

```
sudo swapoff /swapfile
sudo fallocate -l 32G /swapfile      # or 64G
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
free -h
# persist (already referenced by the existing swapfile unit/fstab):
grep -i swap /etc/fstab
# keep swap as a safety net rather than a crutch:
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf
sudo sysctl -w vm.swappiness=10
```
Note: the `comfyui` unit caps *its own* swap at `MemorySwapMax=8G`, so this swapfile protects the desktop/OS and lets ComfyUI offload, without letting it thrash the SSD.

### 2. RAM: **DONE 2026-09-24, 64 GB installed** (was 32 GB; 96 GB is the slot maximum)
2× 48 GB DDR5-5600 SO-DIMM (~the price of a mid-range GPU). It:
- removes the freeze class entirely (offload becomes safe);
- makes **Qwen-Image fp8 (27.5 GB)** runnable, at reduced speed;
- makes **FLUX.2 dev INT4** and video models plausible;
- is required before any 20B+ model is worth attempting.

### 3. GPU: only once RAM is sorted
The GTi14 has a **PCIe 5.0 x8** interface into the EX dock (600 W PSU). x8 at gen 5 ≈ x16 at gen 4, so bandwidth is not the problem; power/budget are.

| card | VRAM | unlocks | note |
|---|---|---|---|
| RTX 3090 (have) | 24 GB | the ✅ rows above | 370 W |
| **RTX 5090** | **32 GB** | Qwen fp8 + encoder resident; FLUX.2 dev INT4/INT8; video | 575 W — inside the dock's 600 W; ~$2k |
| RTX 4090 | 24 GB | same capacity, more speed than the 3090 | no VRAM gain — poor value for us |
| RTX 6000 Ada / RTX PRO 6000 | 48 / 96 GB | FLUX.2 dev at INT8/FP8, LoRA training, multi-model residency | workstation money |
| Cloud (A100 80 GB) | 80 GB | everything | ~$1.4/hr — sensible for one-off top-tier work |

**A 32 GB card is the meaningful step, not a faster 24 GB one.**

## Recommendation

1. **Now:** swapfile (free) + keep the cgroup guard. Use the stack that fits — SDXL, **Z-Image Turbo**, **Flux Kontext**, **SeedVR2**, **Marigold**.
2. **Done:** RAM → **64 GB** (2026-09-24). This is the upgrade that turned the Apache-2.0 Qwen line from "freezes the box" into "runs": Qwen fp8 completes at a 29.9 GB peak. **96 GB** stays documented if the video tier ever needs it.
3. **Then, if throughput matters:** an **RTX 5090 32 GB** in the EX dock.
4. **Meanwhile:** the fp8 tier runs now; keep **GGUF quants** for the >30 GB tier and **cloud** for 32B+ — and remember the 3090 *emulates* fp8, so a GGUF quant is often the more predictable path.

## Licence note

The models that fit best are also the ones with clean licences: **Z-Image Turbo (Apache-2.0)**, **SeedVR2 (Apache-2.0)**, **Marigold (OpenRAIL++, not Apache as once assumed)**, and the **Qwen GGUF** line (Apache-2.0). The non-commercial heavy hitters (Flux dev / Kontext dev, SUPIR, `4x-UltraSharp`) are the ones we should be replacing anyway — see `../2d/AUDIT-tooling-2026-09.md`.
