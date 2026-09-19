#!/usr/bin/env python3
"""Match one image's palette to another's - for a **global** cast, not a seam.

    !! MEASURED WARNING (E20) !!
    This does NOT fix the usual complaint - "the same tree looks a different colour either side of an
    outpaint seam". That is a CONTENT difference (the model painted its own foliage), and on our test
    frame a statistical match left the seam step unchanged or worse (global: 8.2 -> 9.1 mean_std / 10.6
    histogram), and a local match (extension vs the adjacent original band) not only failed (8.2 -> 10.3)
    but BROKE an already-good seam (2.4 -> 23.9), darkening the extension to blue-grey - because the
    reference band's *content* (a shaded wall, dark foliage) dominates its statistics.

    What it IS good for: a global cast, e.g. the whole extension reading too cool or too warm. Then pick
    the reference for its PALETTE, not its content, and dial `--strength` down. For a seam, fix it at
    generation instead: denoise, prompt hygiene, the controlled-fill route (E18b), or a local repaint.

    uv run python scripts/color_match.py output.png --reference source.png --mode mean_std \
        --strength 0.5 --out matched.png --seam 512 --seam 1536

Modes:
    mean_std   per-channel mean/standard-deviation transfer (gentle; preserves detail)
    histogram  per-channel percentile matching (stronger; can shift hue more)

`--strength` blends between the original and the fully matched image (0 = untouched, 1 = fully
matched). `--mask` restricts the correction (and the statistics) to the masked area.

`--seam X` reports the colour step at column X (the statistic our outpaint sweeps use) before and
after, so the effect is visible as a number as well as an image.

No third-party deps beyond numpy/PIL (already in the repo env).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load(p: str) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB"), np.float32)


def match_mean_std(target: np.ndarray, ref: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Per-channel mean/std transfer. With a mask, the STATISTICS come from the masked pixels only
    (zeroing the rest instead would compute them over mostly-zeros and blow the correction up)."""
    out = np.empty_like(target)
    for c in range(3):
        t_all, r = target[..., c], ref[..., c]
        t = t_all[mask] if mask is not None else t_all.ravel()
        ts = t.std() if t.std() > 1e-6 else 1.0
        out[..., c] = (t_all - t.mean()) / ts * r.std() + r.mean()
    return out


def match_histogram(target: np.ndarray, ref: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    levels = np.linspace(0, 255, 256)
    out = np.empty_like(target)
    for c in range(3):
        t_all, r = target[..., c], ref[..., c]
        t = t_all[mask] if mask is not None else t_all.ravel()
        tq = np.percentile(t, levels / 255 * 100)
        rq = np.percentile(r, levels / 255 * 100)
        out[..., c] = np.interp(t_all, tq, rq)
    return out


def tone_step(a: np.ndarray, x: int) -> float:
    """The same colour-step statistic the outpaint sweeps report (mean |left band - right band|)."""
    left = a[:, max(0, x - 16):x - 4].reshape(-1, 3).mean(0)
    right = a[:, x + 4:x + 16].reshape(-1, 3).mean(0)
    return float(np.abs(left - right).mean())


def main() -> int:
    ap = argparse.ArgumentParser(description="Match a target image's palette to a reference.")
    ap.add_argument("target", help="the image to correct (e.g. an outpainted result)")
    ap.add_argument("--reference", required=True, help="the image whose colours to adopt (the source)")
    ap.add_argument("--mode", choices=["mean_std", "histogram"], default="mean_std")
    ap.add_argument("--strength", type=float, default=1.0, help="0 = untouched, 1 = fully matched")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seam", type=int, action="append", default=[],
                    help="column to report the colour step at (repeatable), before and after")
    ap.add_argument("--mask", default=None,
                    help="optional mask: match using only the masked (generated) area's statistics")
    a = ap.parse_args()

    tgt, ref = load(a.target), load(a.reference)
    if tgt.shape != ref.shape and not a.mask:
        pass  # different sizes are fine: only statistics are taken from the reference

    mask = None
    if a.mask:
        mask = np.asarray(Image.open(a.mask).convert("L"), np.float32) > 0
        if mask.shape != tgt.shape[:2]:
            raise SystemExit("mask size must match the target")

    fn = match_mean_std if a.mode == "mean_std" else match_histogram
    matched = fn(tgt, ref, mask)
    if mask is not None:
        matched = np.where(mask[..., None], matched, tgt)   # only the masked area is corrected

    out = tgt + float(np.clip(a.strength, 0.0, 1.0)) * (matched - tgt)
    out = np.clip(out, 0, 255).astype(np.uint8)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(a.out)
    print(f"  mode={a.mode} strength={a.strength}  {a.target} + palette of {a.reference}")
    print(f"  wrote {a.out}  {out.shape[1]}x{out.shape[0]}")
    for x in a.seam:
        print(f"  seam x={x}: colour step {tone_step(tgt, x):5.1f} -> {tone_step(out.astype(np.float32), x):5.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
