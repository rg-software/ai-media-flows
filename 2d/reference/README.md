# 2d/reference — legacy workflow archive

**Loose, unorganized, partially broken. Reference only — not maintained.**
These are workflows recovered from the previous (Windows) machine's
`user/default/workflows/`. The curated, maintained pipelines live in `../workflows/`.

Use them as **design references** (node choices, wiring, prompts) and as a shopping list of
node packs / weights. Expect schema drift: they were saved against an older ComfyUI
(e.g. `Checkpoint Loader (Simple)` is WAS-NS, one node has a UUID class name).

## Inventory

| File | Purpose | Node packs it needs | Weights it expects | Repo track |
|---|---|---|---|---|
| `SDXL Texture Clay.json` | seamless texture + PBR | `comfyui-seamless-tiling`, `qornflex/ComfyUI-QFX-PBRGenerator` | `RealVisXL_V5.0_fp16` | E7 |
| `SDXL Texture Wear.json` | seamless texture (wear) + PBR | **`texturealchemy`** (`SeamlessTiling`), `qornflex/ComfyUI-QFX-PBRGenerator` | `RealVisXL_V5.0_fp16` | E7 |
| `Upscale & PBR.json` | upscale + depth→PBR | `comfyui-marigold`, `qornflex/ComfyUI-QFX-PBRGenerator`, `comfyui-image-compare` | `4x-UltraSharp`, `prs-eth/marigold-iid-{lighting,appearance}-v1-1` | E4 |
| `SUPIR Upscale.json` | SUPIR restoration upscale | `comfyui-supir` | `realvisxlV50_v40LightningBakedvae`, `SUPIR/SUPIR-v0Q_fp16` | E4 alt |
| `SDXL Inpaint.json` | masked inpaint (all **core** nodes) | — (core) | `AnythingXL_xl` | **E8** |
| `IPAdapter Icons.json` | icon set from a reference image | `comfyui_ipadapter_plus` | `RealVisXL_V5.0_fp16`, `ip-adapter-plus_sdxl_vit-h`, `CLIP-ViT-H-14-laion2B-s32B-b79K` | **E11** |
| `RR House.json` | Retro Diffusion pixel house | — (core + RR ckpt) | `RetroDiffusion24x-64xModel` | **E5** |
| `RR Controlnet.json` | pixel art + scribble CN | core CN, `comfyui-pixelart-detector` | `RetroDiffusion24x-64xModel`, `control_v11p_sd15_scribble_fp16` | E5 |
| `RR Depth Ctrlnet.json` | pixel art + depth CN | core CN | `RetroDiffusion24x-64xModel`, `control_v11f1p_sd15_depth_fp16` | E5 |
| `RR Pose-Controlnet.json` | pixel art + scribble/depth CN | `comfyui_controlnet_aux` | `RetroDiffusion24x-64xModel`, CN SD1.5 | E5 |
| `RR Products.json` | pixel props, auto-cutout | `comfyui-inspyrenet-rembg`, `comfyui-pixelart-detector` | `RetroDiffusion16xModel` | E5 / E3 alt |
| `RR Paltest.json` | palette extraction test | `comfyui-pixelart-detector` | — | E5 |
| `MIA AutoRig.json` | mesh auto-rig (3D) | `comfyui-unirig` | — | 3D E4 alt |

**"RR" = Retro Diffusion.** Pixel-art checkpoints (all three now hardlinked into
`models/checkpoints/`):
- `RetroDiffusion16xModel.safetensors` — v2.0, 256² canvas → 16×16 pixel art (range 128–512)
- `RetroDiffusion24x-64xModel.safetensors` — v1.0, 512² canvas → 64×64 pixel art (range 192–512)
- `RetroDiffusion128xModel.safetensors` — v5.0, 1024² canvas → 128×128 pixel art (range 768–1280)
Prompt convention: include **"pixel art"**.

## Node packs referenced

Installed on the box: `comfyui-seamless-tiling`, `comfyui-hunyuan3dwrapper`, `comfyui-unirig`,
`comfyui_controlnet_aux`, `comfyui-kjnodes`, **`texturealchemy`**, **`qornflex/ComfyUI-QFX-PBRGenerator`**.

Still missing (install when the matching track starts): `comfyui-pixelart-detector`,
`comfyui_ipadapter_plus`, `comfyui-supir`, `comfyui-inspyrenet-rembg`, `comfyui-marigold`,
`comfyui-image-compare`.
