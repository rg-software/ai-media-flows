# Hardware: what fits, and what to upgrade (2026-09-16)

Written after Qwen-Image-Edit-2511 fp8 **hard-froze the machine** (see `README.md` → "Hardware ceiling"). Purpose: answer "does the model fit?" with measurements instead of guesses, and map the upgrade options to the work we actually want to do.

## The box

| | |
|---|---|
| Chassis / board | **AZW GTi14** (Beelink GTi14 Ultra), 158×158×56 mm |
| CPU | Intel **Core Ultra 9 185H** (Meteor Lake, 16C/22T) — *mobile* CPU |
| RAM | **32 GB** (2×16 GB DDR5-5600 SO-DIMM) — **2 slots, max 96 GB** |
| Swap | **512 MB** ← effectively none |
| GPU | **RTX 3090 24 GB**, Ampere sm_86, power limit 370 W |
| GPU link | **PCIe 5.0 x8** interface (bottom door) → Beelink **EX dock** with built-in **600 W PSU**, supports cards "up to 600 W" (4090-class and below) |
| Storage | NVMe, ~500 GB free |

Two consequences that are easy to miss:

- **The binding constraint is host RAM, not VRAM.** Anything larger than VRAM must be offloaded to system memory; with 32 GB RAM and 512 MB swap, an offload of ~20 GB thrashes the kernel and the *whole machine* hangs.
- **Ampere has no native fp8.** ComfyUI logs `emulated ops: float8_e4m3fn` / `manual cast: torch.bfloat16`. On this card an "fp8" size is a *storage* figure, and fp8 checkpoints bring no speed advantage the way they do on Ada/Blackwell.

## Measured model footprints (all verified on this box)

Model = diffusion weights; +enc = text encoder; the *peak* column is what has to be resident somewhere (VRAM ∪ RAM) at the worst moment.

| workload | model | weights | +enc | peak | verdict |
|---|---|---|---|---|---|
| Base art | SDXL (RealVisXL) | ~7 GB | 1.4 GB | ~9 GB | ✅ easy |
| Base art | **Z-Image Turbo** (6B, Apache-2.0) | 11.5 GB bf16 | 5.3 GB (Qwen3-4B fp8) | ~17 GB | ✅ **fits with room** |
| Control | ControlNet SDXL | 2.5 GB | — | ~3 GB | ✅ |
| Edit / relight | **Flux.1 Kontext dev** fp8 | 11.9 GB | 5.2 GB (T5 fp8) | ~17.6 GB | ✅ works, 69 s |
| Edit / relight | Qwen-Image-Edit-2511 **fp8** | **19.6 GB** | **7.9 GB** | **~27.5 GB** | ❌ **freezes the box** |
| Edit / relight | Qwen-Image-Edit-2511 **GGUF Q4_K_M** | 12.3 GB | 7.9 GB | ~20 GB | ⚠ fits, needs RAM headroom |
| Edit / relight | Qwen-Image-Edit-2511 **GGUF Q5_K_M** | 14.0 GB | 7.9 GB | ~22 GB | ⚠ tight |
| Upscale | **SeedVR2 7B** fp16 | 15.4 GB | 0.5 GB | ~16 GB | ✅ works, 39 s |
| Upscale | SeedVR2 3B fp16 | 6.3 GB | 0.5 GB | ~7 GB | ✅ easy |
| PBR intrinsics | Marigold (SD1.5-scale) | ~1.7 GB | 0.65 GB | ~2.5 GB | ✅ easy |
| Gen | FLUX.2 [dev] INT4 (32B) | ~18 GB | ~9 GB (24B enc) | ~27 GB+ | ❌ |
| Gen | FLUX.2 [dev] FP16 (32B) | ~70 GB | — | 70 GB+ | ❌ (needs 80 GB GPU) |

**Empirical ceiling on this box: ~18 GB of *total* footprint, i.e. ~14 GB of diffusion weights once a ~4-8 GB text encoder is in play.** Everything at or below that has run cleanly; everything above has not.

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

### 2. RAM 32 to 96 GB: **the best value upgrade**
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
2. **Next:** **RAM to 96 GB.** That is the single upgrade that changes what is possible; it turns the whole Apache-2.0 Qwen line from "freezes the box" into "runs, slower".
3. **Then, if throughput matters:** an **RTX 5090 32 GB** in the EX dock.
4. **Meanwhile:** for anything >18 GB, prefer **GGUF quants** (a 12 GB Q4 Qwen-Edit does fit) and **cloud** for the 32B+ tier — do not feed this box a 27 GB fp8 model.

## Licence note

The models that fit best are also the ones with clean licences: **Z-Image Turbo (Apache-2.0)**, **SeedVR2 (Apache-2.0)**, **Marigold (Apache-2.0)**, and the **Qwen GGUF** line (Apache-2.0). The non-commercial heavy hitters (Flux dev / Kontext dev, SUPIR, `4x-UltraSharp`) are the ones we should be replacing anyway — see `../2d/AUDIT-tooling-2026-09.md`.
