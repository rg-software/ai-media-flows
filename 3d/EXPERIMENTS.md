# 3D Experiments Log

One row per run. Verdicts: `PASS` / `FAIL` / `MEH` / `BLOCKED`. Add experiments under "PENDING", move to table on run.

| Run | Date | Variant | Stage under test | Input | Key params | GLB path | Verdict | Notes / Next |
|---|---|---|---|---|---|---|---|---|
| E1 | 2026-09-08 | MoGe chain | geometry (free) | house png | decimation=1, res=6 | output/ | **PASS** | front-only (by design) — switched to Hy3D |
| E2a | 2026-09-08 | Hy3D shape | geometry (free) | house png | hy3dgen\model.fp16.ckpt, steps 50/5.5/384 | output/3D/Hy3D/ | **PASS** | complete 360° mesh. Next: texture |
| E2b | 2026-09-09 | Hy3D texture | texture (free) | house png | paint=2-0, delight=2-0 | output/3D/Hy3D_textured/ | **PASS** | 3 attempts: (A) comfy-env cp312 blocked (no torch 2.13 cp312 win wheel); (B) local compile vs MSVC2026 → cudafe++ crash; (C) compile vs **MSVC 2022** → OK → cp313 pyd uploaded to server. Fixed workflow by adding **Hy3DMeshUVWrap** (missing UV map → `NoneType` crash in bake). |
| E2c | 2026-09-09 | Hy3D retopology | retopology (free) | house png | Hy3DIMRemesh vc=10000, smooth=8, tri=true | output/3D/Hy3D_untextured/ | **PASS** | inserted `Hy3DIMRemesh` between postprocess & UVWrap in `hy3d-full`; untextured export now post-remesh (cleaner geometry for downstream). Note: needs `pip install pynanoinstantmeshes` on server. |
| E2d | 2026-09-09 | Hy3D multiview | shape (free) | 4 view imgs | mv checkpoint fast, resize 512+pad | output/3D/Hy3Dmv_*.glb | **PASS** | needed `.safetensors` (shapegen loader re-nests), `pip install pynanoinstantmeshes`, and forced 4 views to identical 512² via ImageResizeKJv2 (mv model emits non-uniform view sizes → torch.cat crash otherwise). |
| E2e | 2026-09-09 | texture inpaint | texture (free) | — | vertex inpaint + CV2 ns | — | **PASS (quality MEH)** | gridlike black seams were *unfilled bake UV seams*; fixed with Hy3DMeshVerticeInpaintTexture → CV2InpaintTexture before Apply. Quality acceptable, not perfect. |
| E3 | | Tripo bridge | paid upgrade | free GLB | import→texture | | | validate GLB bridge + cost |
| E4 | 2026-09-09 | UniRig | rigging (free) | humanoid GLB | AutoRig mixamo | — | **BLOCKED** | `UniRigAutoRig` → `from .unirig import direct` fails → `No module named 'comfy'` in isolated worker (worker env lacks comfy on sys.path). Disabling isolation (in-process) → `bpy` DLL load fails on Windows (`0xc0000139`, `DLL load failed while importing bpy: The specified procedure could not be found`). Root: UniRig needs **bpy (Blender-as-Python)** for mesh preprocessing; native DLL broken on this Windows host. Fix candidates: match Blender version / bpy wheel, or run rigging on Linux (bpy conda), or skip rigging for now. |
| E5 | 2026-09-09 | Unity import | end-to-end | Hy3D_textured.glb | glTF importer | — | **PASS** | textured GLB imports fine (glTF importer); scale/orientation sane. Unity-compatible artifacts confirmed. |
| L1 | 2026-09-11 | Linux migration smoke | all stages (free) | house.png (768²) | same hy3d-full / multiview workflows | output/3D/Hy3D_00001_.glb, Hy3Dmv_{un,}textured, Hy3D_{un,}textured, MoGe_smoke | **PASS** | first Linux run after migration. full single-image shape→textured-GLB worked, incl. **custom_rasterizer** rebuilt from source (nvcc 12.8 + gcc-13 + `math_functions.h noexcept` patch) — see HANDOFF. MoGe chain re-verified with current `MESHToTrimesh→Hy3DExportMesh` (scratch chain was stale: used old `TrimeshSave` / return types). |
| L2 | 2026-09-11 | SDXL base art (2D) | base (free) | prompt only | sd_xl_base_1.0.safetensors, 25 steps euler, 1024² | output/2D/sdxl_smoke_00001_.png | **PASS** | first Linux 2D run; SDXL checkpoint downloaded fresh (nothing carried over from Windows). |

---
## PENDING

- [x] E1 — MoGe chain. **PASS** (house → front-only GLB; expected — measurement tool).
- [x] E2a — Hy3D shape. **PASS** with `hy3dgen\model.fp16.ckpt` (2.1) after two wrong-weight attempts (v2-0 safetensors flat → `KeyError: 'model'`; v2-0 ckpt → state_dict mismatch). Summary in `setup-hy3d.md` Step 1.
- [x] E2b — texture stage (`hy3d-full-workflow.json`). **PASS** (2026-09-09).
  - Attempt A: comfy-env py3.12 isolation → pixi can't solve torch 2.13 (no cp312 Windows wheel).
  - Attempt B: local compile (py3.13.5 + torch2.13+cu130 + MSVC2026 + CUDA13) → `cudafe++` crash (ACCESS_VIOLATION).
  - Attempt C: local compile with **MSVC 2022 (17.14)** → OK → `custom_rasterizer_kernel.cp313-win_amd64.pyd` built, uploaded to server `site-packages` (loaded fine — driver-provided CUDA DLLs present).
  - **Workflow fix:** added `Hy3DMeshUVWrap` between Postprocess and RenderMultiView (missing UV map → `NoneType` crash in bake/back_project).
  - Artifacts: `C:\Projects-Git\cuda-compile\custom_rasterizer-src\` (pyd + build-rasterizer.bat), `3d\workflows\hy3d-full-workflow.json`, output `output/3D/Hy3D_textured/`.
- [x] E2c — retopology. **PASS** (2026-09-09). `Hy3DIMRemesh` inserted between Postprocess & UVWrap in `hy3d-full`; untextured mid-export now post-remesh. Requires `pip install pynanoinstantmeshes` on server (added to `setup-hy3d.md`).
- [x] E2d — multiview. **PASS** (2026-09-09). Workflow `hy3d-multiview-workflow.json`. Wall-mine: `Hy3DModelLoader` (shapegen loader) wants **`.safetensors`** (it re-nests flat itself), unlike `Hy3D_2_1SimpleMeshGen` which wants nested `.ckpt`. Also needed: uniform 4-view inputs (ImageResizeKJv2 512² pad) + `pynanoinstantmeshes`.
- [x] E2e — texture inpaint. **PASS (quality MEH)**. Added `Hy3DMeshVerticeInpaintTexture → CV2InpaintTexture` between Bake and Apply in BOTH workflows — fixes the gridlike black seams (unfilled UV atlas gaps). Quality acceptable, not perfect.
- [ ] E3 — needs Tripo API key on server. **Setup:** copy free `.glb` into `ComfyUI/models/3d/` (Load3D dropdown reads `models/3d/`), then `workflows/scratch/tripo-bridge-workflow.json`. See `hy3d-tripo-swap.md`.
- [x] E5 — Unity import. **PASS** (2026-09-09). `Hy3D_textured.glb` imports cleanly via Unity glTF importer; scale/orientation OK. The "strive for Unity-compatible artifacts" goal is met for props.
- [ ] E4 — UniRig rigging — **BLOCKED on bpy/Windows** (2026-09-09). `UniRigAutoRig` needs `bpy` (Blender-as-Python module) for mesh preprocessing; `DLL load failed while importing bpy` on this Windows host. Isolated worker also can't find `comfy` on its sys.path. Cleanest path: run UniRig when we migrate ComfyUI to Linux (bpy is a conda package there), or when Blender/bpy-in-Windows is sorted. Until then rigging is parked. Workflow retained at `workflows/unirig-humanoid-workflow.json`.
- [ ] **E3-on-Linux — UniRig retest.** E4 was Windows-blocked on `bpy`; Linux (bpy via conda) was the predicted fix. Not retested in L1 smoke (no humanoid input handy); park until rigging matters again.
- [x] **L1 — Linux migration smoke — PASS (2026-09-11).** Repo workflows ran on Linux after: (1) `omegaconf` `pyrootutils` `timm` `rembg[onnxruntime]` installed (not in wrapper requirements.txt — silent runtime deps); (2) **schema-drift fixes** in hand-built API prompts: `Attention_mode` now `['sdpa','sageattn']` (was positional), `Hy3DSampleMultiView.scheduler` is now link-only (widget removed → old `'fixed'` bubbles into `denoise_strength` → flatten), `Hy3DGenerateMeshMultiView.scheduler` now named (`FlowMatchEulerDiscreteScheduler`). The workflow JSONs still save/paste fine in the GUI (frontend fills defaults); drift only bit API-only submissions.
- [x] **custom_rasterizer on Linux — UNBLOCKED (2026-09-11).** Recipe that worked: patch `<conda128>/targets/x86_64-linux/include/crt/math_functions.h` adding `noexcept` to the 6 `cospi/sinpi/rsqrt[f]` double+float decls (glibc 2.41 in Ubuntu 26 declares them `noexcept(true)` in `bits/mathcalls.h`; nvcc 12.8 emitted `exception specification is incompatible`). Then `CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 CUDA_HOME=$HOME/miniconda3/envs/cuda128 PATH=.../cuda128/bin:$PATH TORCH_CUDA_ARCH_LIST='8.6' pip install . --no-build-isolation` → built+installed; nr.2 check (nvcc 13.2) still hard-fails (torch `_check_cuda_version` mismatch) — 12.8 is the right pairing for torch 2.11+cu128.

---
## Template (copy for each new experiment)

```
## EX-<n>: <short title>
- Date: 
- Variant: free | paid | hybrid
- Stage: geometry | remesh | texture | rig | export | bridge
- Workflow: <filename>
- Input: 
- Params: 
- GLB/FBX: 
- Verdict: 
- Observations: 
- Next: 
```

