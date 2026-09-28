# Audio: scenario index

Goal: audio as **content** - the consumer is a player's ears, not an engine's sprite/rig pipeline. The sibling question to `video/`'s ("a viewer's file, not an engine asset"): here it is a *listener's* file.

First model: **ACE-Step 1.5** (MIT, commercial-ready by its own card, trained on licensed/royalty-free/synthetic data). It is the licence-cleanest thing in this repo - cleaner than the 2D stack's `insightface`, the 3D scenario's Hunyuan licence, or the Retro Diffusion pixel-art models.

## What runs today

| what | how | cost | status |
|---|---|---|---|
| **text -> a song or instrumental** | the official ComfyUI template `audio_ace_step_1_5_checkpoint.json`: `CheckpointLoaderSimple` -> `TextEncodeAceStepAudio1.5` -> `EmptyAceStep1.5LatentAudio` -> `KSampler` -> `VAEDecodeAudio` -> `SaveAudioAdvanced` | `ace_step_1.5_turbo_aio.safetensors` **9.3 GB** (one file, all-in-one), MIT | **PASS** (E1: a 120 s instrumental in **25 s**, including the checkpoint load) |

## Knobs

- **`tags`** - what the music *is*: genre, mood, instrumentation, production, as prose (the template ships a paragraph of Neo-Soul tags). This is the prompt.
- **`lyrics`** - empty means instrumental; **size it to the duration** (E7): the model sings about **60%** of the words it is given, i.e. 1.5-3 words per second, so a 120 s track wants **250-350 words**; markers alone change nothing, but verse/chorus/bridge with a repeated chorus does; the template ships a complete demo song's lyrics, with `[Verse]` / `[Chorus]` / `[Intro - …]` section markers.
- **`duration`** (seconds, drives the latent) - **and it gates the vocals**: at 30 s the flow is a music-only generator even with a full lyric, while 120 s sings (E6), **`bpm`**, **`keyscale`**, **`timesignature`**, **`language`** (50+), **`seed`**.
- The sampler side: the template uses `cfg_scale` **2**, `temperature` **0.85**, `top_p` **0.9**, `min_p` 0, 8 steps (`KSampler` with `ModelSamplingAuraFlow`), and `generate_audio_codes` on.

## Traps (measured, not read)

- **The official template uses `PrimitiveNode`s** (frontend-only nodes that feed widget inputs). A UI->API converter must substitute their *value* into the consumer **and must collect them in a pre-pass** - a consumer can be visited before its primitive (nodes 98 and 99 here), and the resulting prompt otherwise links to a node that is not in it, which the server rejects outright. Fixed in `scripts/sweep_workflow.py` (E1).
- **There is no `soundfile` in either venv, and `torchaudio.load` now wants `torchcodec`** - so measurement uses `uv run --with soundfile` (the ephemeral-dependency pattern), with the STFT and stats in numpy.
- **For a loop, cut from the middle of a longer bed and join it hard** (E4): measured on an ambient bed, an 8 s segment cut from 4 s in wraps at **1.2x** the track's median adjacent sample step - seamless - while adding a 50 ms self-crossfade made the worst step near the wrap **31x** the median and put a visible broadband click in the spectrogram, because a crossfade *sums two uncorrelated passages* and their percussion lines up. So the usual advice is inverted here, and the thing to do is measure the wrap rather than assume.
- **`SaveAudioAdvanced` output prefixes are not rewritten by a sweep's `--out`** (only `SaveImage`/`SaveVideo` are), so an audio file lands under whatever prefix the workflow carries.
- **We cannot listen, but we can verify two of the three things listening would tell us** (E3): (1) **is it music** - a **spectrogram**, the audio analogue of this repo's "look at the image": harmonics are horizontal lines, a beat is regular vertical transients, noise is a featureless wash, and sections are visible as texture changes; (2) **are the words right** - **transcription** (`faster-whisper`), which on the demo song put **83%** of the sung words back into the input lyrics and recovered **74%** of them. Taste is what remains out of scope, and it is the only thing that is.

## Docs

| Doc | What it answers |
|---|---|
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log with verdicts and the measurements behind them. |
| `../HOWTO.md` | (no user story yet - the flow ships as a story once it is curated into `workflows/`) |
| `../comfyui/README.md` | Node gotchas. |
| `../comfyui/hardware.md` | What fits on this card, measured. |
