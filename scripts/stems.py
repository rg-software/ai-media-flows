#!/usr/bin/env python3
"""Split a take into stems (vocals / instrumental) with the measured MDX recipe.

A repo tool, not an experiment: it ships audio E10's recipe (E15 made it explicit,
E16 ranked MDX best of three) as one command. The counterpart of
scripts/audio_check.py - that one verifies a take, this one takes it apart for
mixing or salvage. See `audio/README.md` -> "Composition, mixing and repair" for
which route to pick: generate parts first; separate only what already exists.

WHAT IT RUNS

`audio-separator` with `UVR-MDX-NET-Voc_FT.onnx` (MDX-ONNX vocal/instrumental),
about 81 s per two-minute take on CPU (E15). The packages come the E10 way -
ephemeral, not repo deps:

    uv run --no-project --with audio-separator[cpu] --with audioread --with soundfile --with librosa \
        python scripts/stems.py <take> [--out dir] [--model other.onnx]

Refusing to guess is a feature here: without those wheels the script stops and
prints the line above instead of running a different separator. Output is
`<name>_(Vocals|Instrumental)_*.flac` in --out, plus a levels table per stem
(reused from audio_check, so a stem that clips is as visible as a take that clips).

MEASURED ANCHORS (audio E31, 2026-10-16)

    take                              vocals RMS   instrumental RMS   wall
    e11 4 s take                      (see E31)    (see E31)          (see E31)
    120 s XL song                     (see E31)    (see E31)          (see E31)
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NEED = "uv run --no-project --with audio-separator[cpu] --with audioread --with soundfile --with librosa"
DEFAULT_MODEL = "UVR-MDX-NET-Voc_FT.onnx"


def main() -> int:
    ap = argparse.ArgumentParser(description="Split a take into vocal/instrumental stems (MDX).")
    ap.add_argument("take", help="audio file (wav/flac/mp3/ogg - whatever audio-separator reads)")
    ap.add_argument("--out", default=None, help="output dir (default <take>_stems/)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="separator model (default the measured MDX vocal/instrumental)")
    ap.add_argument("--format", default="FLAC", help="output container for the stems")
    args = ap.parse_args()

    if not os.path.isfile(args.take):
        raise SystemExit(f"no such take: {args.take}")
    try:
        import audio_separator  # noqa: F401
    except ImportError:
        raise SystemExit("audio-separator is not installed - run it the E10 way:\n"
                         f"  {NEED} python scripts/stems.py ...")
    out = args.out or (os.path.splitext(args.take)[0] + "_stems")
    os.makedirs(out, exist_ok=True)
    before = set(glob.glob(os.path.join(out, "*")))
    exe = shutil.which("audio-separator")
    if exe is None:
        raise SystemExit("the audio-separator entry point is missing - reinstall the E10 wheels")
    cmd = [exe, "-m", args.model,
           "--output_dir", out, "--output_format", args.format,
           "--use_soundfile", args.take]
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"audio-separator failed (exit {r.returncode})")
    made = sorted(set(glob.glob(os.path.join(out, "*"))) - before)
    if not made:
        raise SystemExit("audio-separator ran but left no new files in " + out)
    for f in made:
        print("made", f)
    try:
        from audio_check import analyse
        print(f"\n{'stem':44} {'dur':>8} {'sr':>7} {'peak':>14} {'rms':>13}")
        bad = 0

        class A:
            clip_run = 16
            spec = None
            asr = False
        for f in made:
            clipped, _line = analyse(f, A())
            bad += bool(clipped)
        return 1 if bad else 0
    except ImportError:
        print("(soundfile missing, skipping stem levels - uv add soundfile for the table)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
