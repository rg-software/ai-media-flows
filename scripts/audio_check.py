#!/usr/bin/env python3
"""Check whether a generated take is shippable: levels, clipping, spectrogram, words.

An experiment probe and checker, not a user tool: it reproduces the verification
behind audio E1-E3 (level stats, a spectrogram, 16 kHz ASR) as one command, so
"we have no ears" is a stated limit rather than a hole. The counterpart of
scripts/motion_quality.py: it measures an artefact rather than producing one.
Run it on every take before auditioning, and after changing any knob.

WHAT IT REPORTS (all facts about the samples, no taste)

  * peak dBFS and RMS dBFS (mono mixdown when the take is stereo);
  * full-scale runs: the longest run of consecutive samples at digital full scale,
    and how many samples sit at full scale at all. A hot master *touches* 0.0;
    runs of flat-topped samples *are* clipping. The gate is --clip-run.
  * DC offset (mean), which a VAE decoder sometimes leaves behind;
  * an optional log-magnitude spectrogram PNG (--spec), the audio analogue of an
    evidence sheet;
  * optional words (--asr, faster-whisper, 16 kHz mono): printed transcript plus
    word count, for coverage arithmetic against the lyric, not for quality.

MEASURED ANCHORS (audio E29, 2026-10-16, takes below)

    take                                    peak     rms    longest FS run
    e13b XL song (120 s)                   -0.1   -14.5    0
    Chatterbox standard dialogue (9.7 s)    -0.1   -21.0    0
    E26b Turbo dialogue, THIS file         -0.7   -22.0    0   (E28's -8 dB take was a different file)
    e11 take (4 s)                           0.0   -21.3    1 (a touch, not a clip)
    SFX explosion (4 s)                     -6.0   -14.0    0
    + 5 more songs/covers (worst -1.9); E24_take is ace_iron by md5, so 10 unique takes.
    (audio E29: no take breaches; the gate default stays provisional.)

  * The gate default (--clip-run 16) is provisional: a sine at 0 dB touches one
    or two samples per crest, so 16 consecutive full-scale samples has no musical
    reading. The E29 sweep sets the real number.

Usage:
    uv run python scripts/audio_check.py <take.wav> [more takes...] [--spec out.png]
    uv run --with faster-whisper python scripts/audio_check.py song.flac --asr

faster-whisper is deliberately NOT a repo dependency (ctranlate2 is heavy for a
checker most runs do not need): --asr fails loudly with the --with line when it
is missing. soundfile IS declared (pyproject): it reads wav/flac/ogg; anything
else arrives as already-decoded takes, the way the box saves them (flac).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import wave

import numpy as np


def read_audio(path: str) -> tuple[np.ndarray, int]:
    """Mono float32 samples in [-1, 1] + sample rate. soundfile first, stdlib wave fallback."""
    try:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        return data.mean(axis=1), int(sr)
    except ImportError:
        pass
    except Exception as e:
        raise SystemExit(f"{path}: soundfile could not read it ({e})")
    try:
        with wave.open(path, "rb") as w:
            n, ch, sr, sw = w.getnframes(), w.getnchannels(), w.getframerate(), w.getsampwidth()
            raw = w.readframes(n)
        if sw == 1:
            x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
        elif sw == 2:
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 4:
            x = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise SystemExit(f"{path}: {sw * 8}-bit wav is not supported by the stdlib fallback")
        return x.reshape(-1, ch).mean(axis=1), sr
    except wave.Error:
        raise SystemExit(f"{path}: needs soundfile (uv add soundfile) - not a plain wav")


def dbfs(x: float) -> float:
    return 20.0 * math.log10(x) if x > 0 else float("-inf")


def longest_run(mask: np.ndarray) -> int:
    best, cur = 0, 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def analyse(path: str, args) -> tuple[bool, str]:
    if not os.path.isfile(path):
        raise SystemExit(f"no such file: {path}")
    x, sr = read_audio(path)
    dur = len(x) / sr
    peak = float(np.abs(x).max())
    rms = float(np.sqrt(np.mean(x ** 2)))
    full = np.abs(x) >= 1.0 - 1e-9
    run = longest_run(full) if full.any() else 0
    dc = float(x.mean())
    clipped = run >= args.clip_run
    line = (f"{os.path.basename(path):44} {dur:7.1f}s {sr/1000:5.1f}kHz "
            f"peak {dbfs(peak):6.1f} dBFS  rms {dbfs(rms):6.1f} dBFS  "
            f"FS-samples {int(full.sum()):6d}  longest-run {run:5d}  dc {dc:+.4f}"
            + ("  CLIPPED" if clipped else ""))
    print(line)
    if args.spec:
        write_spec(x, sr, args.spec, os.path.basename(path))
    if args.asr:
        print("    words: " + transcribe(path, args))
    return clipped, line


def stft(x: np.ndarray, n_fft: int = 2048, hop: int = 512) -> np.ndarray:
    win = np.hanning(n_fft)
    frames = 1 + (len(x) - n_fft) // hop
    out = np.empty((n_fft // 2 + 1, frames), dtype=np.float32)
    for i in range(frames):
        seg = x[i * hop:i * hop + n_fft] * win
        out[:, i] = np.abs(np.fft.rfft(seg))
    return out


def write_spec(x: np.ndarray, sr: int, path: str, title: str) -> None:
    from PIL import Image, ImageDraw
    s = stft(x)
    lo = np.log10(s + 1e-6)
    lo -= lo.min()
    lo *= 255.0 / max(lo.max(), 1e-9)
    img = Image.fromarray(lo[::-1].astype(np.uint8), mode="L").convert("RGB")
    img = img.resize((min(1600, img.width), 256))
    d = ImageDraw.Draw(img)
    d.text((8, 6), f"{title}  {len(x) / sr:.1f}s @ {sr} Hz", fill=(255, 255, 0))
    d.text((8, 20), "log-magnitude STFT (Hann 2048/512); bright = energy", fill=(255, 255, 0))
    img.save(path)
    print(f"    spectrogram -> {path}")


def transcribe(path: str, args) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper is not installed: "
                         "uv run --with faster-whisper python scripts/audio_check.py ... --asr")
    import soundfile as sf
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    x = data.mean(axis=1)
    if sr != 16000:
        idx = np.linspace(0, len(x), int(len(x) * 16000 / sr) + 1).astype(np.int64)[:-1]
        x = x[np.clip(idx, 0, len(x) - 1)].astype(np.float32)
    model = WhisperModel(args.asr_model, device="cpu", compute_type="int8")
    segs, _info = model.transcribe(x, beam_size=5, language=args.asr_lang or None)
    text = " ".join(s.text.strip() for s in segs).strip()
    return f"{len(text.split())} words: {text[:400]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a generated take: levels, clipping, spectrogram, words.")
    ap.add_argument("takes", nargs="+")
    ap.add_argument("--spec", default=None, help="write a log-magnitude spectrogram PNG (single-take runs)")
    ap.add_argument("--asr", action="store_true", help="transcribe with faster-whisper (needs --with)")
    ap.add_argument("--asr-model", default="small")
    ap.add_argument("--asr-lang", default="en")
    ap.add_argument("--clip-run", type=int, default=16,
                    help="a full-scale run this long or longer fails the take (default 16)")
    args = ap.parse_args()
    if args.spec and len(args.takes) != 1:
        raise SystemExit("--spec takes exactly one take (one sheet per take)")
    bad = 0
    print(f"{'take':44} {'dur':>8} {'sr':>7} {'peak':>14} {'rms':>13} {'FS':>11} {'run':>12}")
    for t in args.takes:
        clipped, _line = analyse(t, args)
        bad += bool(clipped)
    if bad:
        print(f"\n{bad} take(s) breach the full-scale-run gate (--clip-run {args.clip_run})")
    else:
        print("\nno take breaches the full-scale-run gate")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
