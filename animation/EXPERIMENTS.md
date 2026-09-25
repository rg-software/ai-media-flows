# Animation Experiments Log

One row per run. Verdicts: `PASS` / `FAIL` / `MEH` / `BLOCKED`. Add experiments under "PENDING", move to the table once run.

Context: this scenario began as an investigation, not an assumption. The question was whether the box could afford video-reference motion at all, so E1 is deliberately a **cost-and-capability probe** first - one short clip, measured - rather than a quality run.

| Run | Date | Variant | Stage under test | Input | Key params | Output | Verdict | Notes / Next |
|---|---|---|---|---|---|---|---|---|
| E1 | 2026-09-25 | Wan Animate 2 motion transfer | video reference (whole flow) | `pink_hair_mech_arms_ref.png` + `street_dance_drive.mp4` (both the upstream example assets) | Q5_K_M GGUF, 480x848, 33 frames, LCM, 6 steps, cfg 1.0, shift 5, lightx2v distill LoRA | `output/3D/wan_probe_00001_.mp4` (239 KB); sheet `wan_probe_sheet.png` | **PASS** | **Answers the affordability question: yes.** 91 s for one clip at a **peak of 20 844 MiB** VRAM (~3 GB headroom on the 24 GB 3090). The result is a coherent, identity-preserved animation - the reference character waves and its mouth moves with the driving clip, over a fresh plain background from the prompt. **Format finding:** exported as **GGUF Q5_K_M, not fp8** - the 3090 rejects `fp8e4nv`, so the official repo's `int8_convrot` is not the safe path here (same Ampere limitation `../comfyui/hardware.md` records for Qwen). Download 20.1 GB total, of which the 12.3 GB diffusion model took 121 s. **Graph findings:** (a) the upstream template ships as *subgraphs*, which cannot be POSTed to `/prompt`, so it had to be flattened to be scriptable at all; (b) the output size is taken from the *driving video* and snapped to a multiple of 16 (requested 854 → 848); (c) there are **two** CLIP-vision encodes (reference image *and* pose-video frame 0) and dropping the second degrades output without erroring. **Next:** longer clips need the upstream `ContextWindowsManual` chunking, since ~3 GB of headroom will not absorb a longer `length`; and the open parametric cell (motion → skeletal clips) is untouched by this run. |

---

## PENDING

- [ ] **E2 - longer clip / context windows.** 33 frames fit with ~3 GB spare. Measure where a single pass stops fitting and whether the upstream `ContextWindowsManual` chunking (context 21, overlap 8, `standard_static`, pyramid fuse) restores it, since that is the difference between a 1.4 s and a multi-second clip.
- [ ] **E3 - our own character, not the example asset.** E1 used the upstream example pair to maximise the chance of a valid first run. The informative run is one of our own characters (`assets/2d/char_knight.png`) against a clip we chose, which also tests identity preservation on art we actually made.
- [ ] **E4 - motion → parametric (the real target).** Everything above produces a *video*. The scenario's open cell is skeletal clips for an engine, and the honest question is whether motion can be recovered from this video (or from the same driving clip) onto the `unirig-humanoid` rig, rather than authored from scratch.
- [ ] **E5 - is the driving clip the right lever at all?** The Mixamo branch is free and the engine already retargets. Before investing further in generated motion, decide whether generated video actually adds anything over a free clip library for our use cases.
