# Audio: scenario index

Goal: audio as **content** - the consumer is a player's ears, not an engine's sprite/rig pipeline. The sibling question to `video/`'s ("a viewer's file, not an engine asset"): here it is a *listener's* file.

First model: **ACE-Step 1.5** (MIT, commercial-ready by its own card, trained on licensed/royalty-free/synthetic data). It is the licence-cleanest thing in this repo - cleaner than the 2D stack's `insightface`, the 3D scenario's Hunyuan licence, or the Retro Diffusion pixel-art models.

## What runs today

| what                                                         | how                                                                                                                                                                                                                  | cost                                                                        | status                                                                                                                                    |
|--------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| **text -> a sound effect or ambience**                       | `audio/workflows/stable-audio.json` - Stable Audio Open 1.0, core nodes only: a 4.5 GB checkpoint plus a 0.83 GB t5 in `text_encoders/` (the checkpoint carries no CLIP)                                             | 5.4 GB, **Stability AI Community** licence                                  | **PASS** (E11: 4 s effects in ~5 s each; the transients verify in a spectrogram)                                                          |
| **text -> a song or instrumental**                           | the official ComfyUI template `audio_ace_step_1_5_checkpoint.json`: `CheckpointLoaderSimple` -> `TextEncodeAceStepAudio1.5` -> `EmptyAceStep1.5LatentAudio` -> `KSampler` -> `VAEDecodeAudio` -> `SaveAudioAdvanced` | `ace_step_1.5_turbo_aio.safetensors` **9.3 GB** (one file, all-in-one), MIT | **PASS** (E1: a 120 s instrumental in **25 s**, including the checkpoint load)                                                            |
| **restyle a track: keep the tune, change the idiom (cover)** | `audio/workflows/yue2-cover.json` - YuE 2 with SheetSage2: the reference's **melody** is transcribed into ABC notation and re-rendered with a new style + new lyrics                                                 | 3.9 GB + 1.3 GB, **`cc-by-nc-4.0`** (non-commercial, research only)         | **PASS** (E12d: the user's ears confirm the cover is recognisably the reference's tune; a 30 s cover in 65 s)                             |
| **text -> a song, sung properly (4B)**                       | `audio/workflows/ace-step-xl-sft.json` - ACE-Step 1.5 **XL SFT** (4B): 50 steps, `DualCLIPLoader` (Qwen 0.6B + 4B), `ModelSamplingAuraFlow` shift 3                                                                  | ~19 GB, **MIT**                                                             | **PASS** (E13/E13b: 124 of 188 lyric words sung cleanly on a clear-lead style, where the 8-step turbo sang nothing; ~50 s per 120 s song) |

## Knobs

- **Simultaneous voices depend on how hard you ask (E10 -> E14).** A *duet* request alone comes back **traded, not together** (E10). But when both the style text and the lyric markers demand overlap - "a male and a female lead sing the SAME words at the SAME time ... never trading lines and never solo", with `[Bridge] One breath, two voices` in the lyric - the user's ears confirm **two voices at once** (E14). The prompt is the lever; the recipe's own texts are in `workflows/scratch/duet-{style,lyric}.txt`. **How much** overlap you get still varies by model and style (E14): ACE-Step turbo and XL SFT both have simultaneous sections, YuE "sort of", and MiniMax - the best word-coverage arm - trades instead, so coverage and simultaneity do not rank the same. Some of it is a **choir doubling in unison** rather than two harmony leads.
- **YuE 2 (the cover flow) is `cc-by-nc-4.0` - non-commercial.** It is the only *restyle* route we have (ACE-Step keeps a reference but cannot restyle it, E5), so it is worth the licence for research, but nothing it makes can ship; the shippable form of the same capability is ACE-Step's own Cover mode (MIT, upstream's app). Its **duration is the model's own** - `YuE2GenerateMusic` returns a FLOAT that drives the latent, bounded by `max_duration` - and its two-stage `YuE2GenerateABC` -> `abc` route is optional (dropping the link prunes the stage and makes the run ~30% faster, E12b).
- **Which music model to use (E13)?** On identical text: ACE-Step 1.5 **turbo** (the shipped flow) sings 52 words in **15 s**; ACE-Step **XL SFT** (4B, 50 steps) sings 53 in **~50 s of sampling** and is **MIT**; **MiniMax Music 3** sings 90 in **~18 min**, outputs 44.1 kHz, and needs a 'MiniMax-Music3' display term; **YuE 2** sings sparsely and is **non-commercial**. So: the turbo stays the default for iteration, MiniMax is the lyric-heavy option, and XL SFT is the licence-clean candidate that *reads as higher-quality* but delivered a **hushed vocal** on a style asking for a shouted lead (E13) - the second-prompt check (E13b) is what decides it.
- **Every model here generates at full scale (E11).** Five takes across two unrelated models and two unrelated graphs peaked at **0.0 dBFS**, so normalise before shipping anything - it is not one model's quirk.
- **`tags`** - what the music *is*: genre, mood, instrumentation, production, as prose (the template ships a paragraph of Neo-Soul tags). This is the prompt.
- **`lyrics`** - empty means instrumental; **size it to the duration** (E7): the model sings about **60%** of the words it is given, i.e. 1.5-3 words per second, so a 120 s track wants **250-350 words**; markers alone change nothing, but verse/chorus/bridge with a repeated chorus does; the template ships a complete demo song's lyrics, with `[Verse]` / `[Chorus]` / `[Intro - …]` section markers.
- **`duration`** (seconds, drives the latent) - **and it gates the vocals**: at 30 s the flow is a music-only generator even with a full lyric, while 120 s sings (E6), **`bpm`**, **`keyscale`**, **`timesignature`**, **`language`** (50+), **`seed`**.
- The sampler side: the template uses `cfg_scale` **2**, `temperature` **0.85**, `top_p` **0.9**, `min_p` 0, 8 steps (`KSampler` with `ModelSamplingAuraFlow`), and `generate_audio_codes` on.

## Lyric section markup - what `[Verse]` and `[Chorus]` actually are

**A convention the model learned, not a keyword list, and nothing in the pipeline parses it.** The node hands the lyric straight to the tokenizer (`clip.tokenize(tags, lyrics=lyrics, ...)` in the ACE-Step node module, `nodes_ace.py`, inside ComfyUI's core `comfy_extras`) - no vocabulary, no validation, and no error for an unknown name. The evidence is what the ten shipped ACE-Step templates actually write: **21 distinct bracketed tokens**, in two kinds.

| kind | examples from the shipped templates |
|---|---|
| **structural** - what shapes the arrangement | `[Intro]` `[Verse]` `[Verse 1]` `[Verse 2]` `[Pre-Chorus]` `[Chorus]` `[Post-Chorus]` `[Final Chorus]` `[Bridge]` `[Outro]` |
| **free-form** - a hint, never validated | `[Intro - Rhodes piano and brushed drums]`, `[Chorus - Pop Explosion]`, `[Verse 1 - Trap Rap]`, `[instrumental]`, `[break down]`, `[drum fill]`, `[chopped samples]` |

Use the standard names for structure and a dash plus a phrase for arrangement hints. An invented name is not an error - it may simply mean nothing - and **we cannot measure which**, because a section label changes the arrangement rather than the words, so neither the transcript nor the spectrogram settles it. That is what ears are for. (The v1 node exposes `lyrics_strength`, a weight on how hard the lyric is followed; v1.5 has no such knob and carries the structured parameters - `bpm`, `keyscale`, `timesignature`, `duration` - instead.)

## Composition, mixing and repair - the next topic (protocol)

The 2D scenario composes rather than hoping one prompt carries three characters: mask, move, paste, inpaint. Audio has the same machinery, and most of it is already in core - checked on this build:

| job | nodes / tools |
|---|---|
| **separate a take into stems** | `audio-separator[cpu]` (E10's recipe; ephemeral through `uv run --with`) - the first thing to ship as a `scripts` tool |
| **mix and blend** | `AudioMerge`, `AudioAdjustVolume`, `AudioEqualizer3Band`, `SplitAudioChannels` / `JoinAudioChannels`, `TrimAudioDuration` - an in-graph mixer |
| **repair a region** (a mispronounced word, a deliberately deleted piece) | `VAEEncodeAudio` -> `CreateAudioMask` -> `SetLatentNoiseMask` -> `KSampler` at partial denoise -> `VAEDecodeAudio` - the inpainting analogue, on an audio latent |
| **a target timbre** | `ReferenceTimbreAudio`; for new *words* on an existing tune, YuE's cover (S22) |

**Match the route to the job - what this pipeline is actually for.** Source separation is an ill-posed inverse problem, so "generate a song, split it, recombine" will never be clean. Pick the route by goal:

| the goal | the route, in order of preference |
|---|---|
| **an instrumental bed** | ask for an instrumental directly (`lyrics` empty) - guaranteed clean. Only separate when the mix already exists, and then MDX (`UVR-MDX-NET-Voc_FT`) is the best of the three measured (BS-Roformer and Mel-Band Roformer both leave audible vocal), optionally followed by a **debleed/denoise** pass |
| **a reusable voice track** | generate the voice *as a part* (a cappella prompt, or YuE's cover for a melody plus new words); separation is a *salvage* tool, not a source |
| **restyle / keep only the melody** | a **symbolic** reference - YuE's cover (S22) turns the reference into ABC, so the original's vocals cannot survive it (ACE-Step's m2m is latent/denoise-based and *retains* instead) |
| **repair a word or a region** | the mask/inpaint route (`CreateAudioMask` + `SetLatentNoiseMask`), not separation - E18 |
| **two genuine voices** | **deprioritised** - what the models deliver is a *unison choir*, which is a legitimate sound but not two leads (E14/E15), so it is only worth pushing if harmony itself is the goal |

**Planned order, revised after E15's ears:** **The gap this topic exists to close:** *"cut a piece and generate a blended replacement"* is masked-latent inpainting, and ComfyUI cannot mask an audio latent (E18) - so the parts-first route above is the salvage pipeline, and closing the gap is one small custom node or upstream's app. **E15** stems (done - the vocal stem is clean) -> **E16** **separation quality first**: the user's ears say the *instrumental* stems still carry vocals (and a 0-word transcript does not contradict that), so the ladder of stronger models (BS-Roformer, Mel-Band Roformer, MDX23-class) plus a **second pass** comes before any mixing, and the measure to trust is the ear, with ASR only as a hint -> **E17** mixing and voice blending, including a *controlled* two-voice blend (the thing E14 could only ask for in a prompt - and the ears say prompting gives *one voice or a unison backing*, not two leads) -> **E18** region repair, with splice-plus-crossfade comping as the fallback.

**Repair verdict (E18-E18c):** there is no clean in-graph repair. The mask route is blocked by the latent geometry, the latent splice rewrites the untouched audio, a one-word edit re-performs the whole take, and a waveform comp preserves the surroundings exactly but the seams are prominent (E4's crossfade mechanism - two takes are uncorrelated in phase and timing). The practical answer is **re-render and take the new master**, or a comped seam you can hear. **Discipline carried over:** every model here lands at **0.0 dBFS**, so a mix needs explicit normalisation; E4's join rule *inverts* for edits (a hard join was right for a *loop*, a crossfade is the tool for music edits); and a transcript is a **lower bound** on vocal presence, never a presence test.

## Traps (measured, not read)

- **The official template uses `PrimitiveNode`s** (frontend-only nodes that feed widget inputs). A UI->API converter must substitute their *value* into the consumer **and must collect them in a pre-pass** - a consumer can be visited before its primitive (nodes 98 and 99 here), and the resulting prompt otherwise links to a node that is not in it, which the server rejects outright. Fixed in `scripts/sweep_workflow.py` (E1).
- **A flac *file* md5 is not a determinism test (E13).** Two runs of ACE-Step XL SFT produced different file md5s but **sample-identical audio** (`max|diff| 0.000000` over 5,760,000 samples) - the container carries metadata that moves. Compare decoded samples (E2's bit-exactness test used file md5, which happened to work on that model).
- **There is no `soundfile` in either venv, and `torchaudio.load` now wants `torchcodec`** - so measurement uses `uv run --with soundfile` (the ephemeral-dependency pattern), with the STFT and stats in numpy.
- **For a loop, cut from the middle of a longer bed and join it hard** (E4): measured on an ambient bed, an 8 s segment cut from 4 s in wraps at **1.2x** the track's median adjacent sample step - seamless - while adding a 50 ms self-crossfade made the worst step near the wrap **31x** the median and put a visible broadband click in the spectrogram, because a crossfade *sums two uncorrelated passages* and their percussion lines up. So the usual advice is inverted here, and the thing to do is measure the wrap rather than assume.
- **`SaveAudioAdvanced` output prefixes are not rewritten by a sweep's `--out`** (only `SaveImage`/`SaveVideo` are), so an audio file lands under whatever prefix the workflow carries.
- **We cannot listen, but we can verify two of the three things listening would tell us** (E3): (1) **is it music** - a **spectrogram**, the audio analogue of this repo's "look at the image": harmonics are horizontal lines, a beat is regular vertical transients, noise is a featureless wash, and sections are visible as texture changes; (2) **are the words right** - **transcription** (`faster-whisper`), which on the demo song put **83%** of the sung words back into the input lyrics and recovered **74%** of them. Taste is what remains out of scope, and it is the only thing that is. **(Corrected in E12c: transcription is a lower bound on vocal presence, not a presence test - the user's ears hear a vocal in YuE takes where Whisper read 0-19 words of a dense or shouted mix, so a transcript of "nothing" means unreadable, not absent.)**

## Docs

| Doc | What it answers |
|---|---|
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Run log with verdicts and the measurements behind them. |
| [`../HOWTO.md`](../HOWTO.md) | User stories S19-S22 (music, style reference, sound effects, restyle/cover). |
| `../comfyui/README.md` | Node gotchas. |
| `../comfyui/hardware.md` | What fits on this card, measured. |
