#!/usr/bin/env python3
"""Measure whether a recovered motion is SENSIBLE: not jittery, not broken.

An experiment probe, not a user tool: it reproduces the measurement behind E5 (`animation/EXPERIMENTS.md`)
rather than producing an asset. Use it before trusting a recovered clip, and after changing any knob.

WHAT IT READS

The animation out of a GLB - specifically the SAM 3D Body / motion-recovery export, whose rotation channels
are named `openpose_limb_*`. For each such channel it takes the per-frame angular step (the angle between
consecutive quaternions, sign-invariant so a quaternion `q` vs `-q` is not mistaken for a flip) and the
frame-to-frame *change* in that step.

  * **jitter** is high-frequency noise on a smooth signal: a large change relative to the step. `jerk` is
    `p99(change) / median(step)` - scale-free, so it compares across clips and settings.
  * **a break** is a single-frame step above `--break-deg`. Far beyond what a human joint does in 1/fps of a
    second, and - unlike jitter - a low-pass filter cannot remove it. This is the check that matters.

Exit code 1 when a break or a non-finite value is found, so it can gate a run.

MEASURED FINDINGS (E6, 2026-09-27, RTX 3090)

  * Moderate motion is clean: the E4 clip showed no breaks, jerk median 2.1.
  * A fast dance clip **breaks**: 8 joints with single-frame steps over 45 deg, up to 174, visible as the
    mesh's orientation snapping between frames.
  * **Neither smoothing method removes them**, because `SAM3DBody_Smooth.rotation_threshold_degrees`
    *disables* smoothing above a root rotation rate ("to preserve fast spins") and the stock template ships
    **15** - below the schema's own default of 30 - so smoothing switches itself off exactly when the motion
    gets fast. Raising it is the lever:

        rotation_threshold_degrees   jerk median   jerk p90   joints with breaks
        15  (template)                   16.60       35.15        8
        89                                6.84       14.43        5
        0   (always smooth)               2.75        6.44        4

    So the template's value is the worst of the three. Setting 0 cuts jitter ~6x and halves the breaks, but a
    genuinely fast or spinning clip can still flip: two ~173 deg pops remained.
  * Separately, `BuildPoseFile.camera_translation` = `off` keeps the root at its bind position, so the render
    does not sit on the performer; `centered`/`absolute` bake the camera translation in instead.

Usage:
    python scripts/motion_quality.py <file.glb> [--break-deg 45] [--top 12]
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys

import numpy as np


def read_glb(path):
    b = open(path, "rb").read()
    magic, _ver, _ln = struct.unpack("<4sII", b[:12])
    if magic != b"glTF":
        raise SystemExit(f"{path}: not a GLB")
    off, js, bin_ = 12, None, b""
    while off < len(b):
        clen, ctype = struct.unpack("<I4s", b[off:off + 8])
        chunk = b[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(chunk.decode("utf-8"))
        elif ctype.startswith(b"BIN"):
            bin_ = chunk
        off += 8 + clen + ((4 - clen % 4) % 4)
    return js, bin_


_CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
       5125: ("I", 4), 5126: ("f", 4)}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def accessor(js, bin_, idx):
    a = js["accessors"][idx]
    fmt, size = _CT[a["componentType"]]
    n = _NC[a["type"]]
    bv = js["bufferViews"][a["bufferView"]]
    base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or (size * n)
    out = np.empty((a["count"], n), dtype=np.float32 if fmt == "f" else np.int64)
    for i in range(a["count"]):
        out[i] = struct.unpack_from("<" + fmt * n, bin_, base + i * stride)
    return out


def quat_angle_deg(q1, q2):
    """Angle between two unit quaternions. `abs` makes it sign-invariant, so a q/-q pair reads as 0."""
    d = min(1.0, max(-1.0, abs(float(np.dot(q1, q2)))))
    return math.degrees(2.0 * math.acos(d))


def analyse(path, break_deg, top):
    js, bin_ = read_glb(path)
    anims = js.get("animations") or []
    if not anims:
        raise SystemExit(f"{path}: no animation in the GLB")
    nodes = js.get("nodes", [])

    print(f"file: {path}")
    print(f"animations: {len(anims)}  nodes: {len(nodes)}  skins: {len(js.get('skins', []))} "
          f"joints: {[len(s.get('joints', [])) for s in js.get('skins', [])]}")

    rows, breaks, nonfinite, t_all = [], [], 0, None
    for anim in anims:
        for ch in anim["channels"]:
            if ch["target"]["path"] != "rotation":
                continue
            s = anim["samplers"][ch["sampler"]]
            t = accessor(js, bin_, s["input"]).ravel()
            q = accessor(js, bin_, s["output"])
            t_all = t
            if not np.isfinite(q).all():
                nonfinite += 1
            steps = np.array([quat_angle_deg(q[i - 1], q[i]) for i in range(1, len(q))])
            change = np.abs(np.diff(steps)) if len(steps) > 1 else np.zeros(1)
            name = nodes[ch["target"]["node"]].get("name") or f"node{ch['target']['node']}"
            med_step = float(np.median(steps))
            p99_change = float(np.percentile(change, 99)) if len(change) else 0.0
            rows.append((name, med_step, float(np.percentile(steps, 99)), p99_change,
                         p99_change / med_step if med_step > 1e-6 else float("inf"), float(steps.max())))
            if steps.max() > break_deg:
                breaks.append((name, float(steps.max()), int(np.argmax(steps)) + 1))

    n = len(t_all) if t_all is not None else 0
    dur = float(t_all[-1] - t_all[0]) if n else 0.0
    print(f"rotation channels: {len(rows)}  frames: {n}  duration: {dur:.2f}s  "
          f"fps: {(n - 1) / dur if dur > 0 else 0:.1f}")
    print(f"non-finite channel(s): {nonfinite}")

    print(f"\n{'joint':<30}{'step_med':>9}{'step_p99':>9}{'chg_p99':>9}{'jerk':>8}{'step_max':>9}")
    for name, ms, ps, pc, j, mx in sorted(rows, key=lambda r: -r[4])[:top]:
        print(f"{name:<30}{ms:9.2f}{ps:9.2f}{pc:9.2f}{j:8.2f}{mx:9.1f}")

    if rows:
        jerks = np.array([r[4] for r in rows if np.isfinite(r[4])])
        print(f"\nwhole clip: median step {np.median([r[1] for r in rows]):.2f} deg/frame; "
              f"jerk median {np.median(jerks):.2f}, p90 {np.percentile(jerks, 90):.2f}")
    if breaks:
        print(f"\nBREAKS (single-frame step > {break_deg} deg) in {len(breaks)} joint(s):")
        for name, mx, fr in sorted(breaks, key=lambda b: -b[1])[:5]:
            print(f"   {name}: {mx:.1f} deg at frame {fr}")
    else:
        print(f"\nno single-frame step above {break_deg} deg (no obvious pops)")
    return 1 if (breaks or nonfinite) else 0


def main():
    ap = argparse.ArgumentParser(description="Measure jitter/breaks in a GLB animation.")
    ap.add_argument("glb")
    ap.add_argument("--break-deg", type=float, default=45.0,
                    help="a single-frame step above this counts as a pop (default 45)")
    ap.add_argument("--top", type=int, default=12, help="worst joints to list")
    a = ap.parse_args()
    return analyse(a.glb, a.break_deg, a.top)


if __name__ == "__main__":
    sys.exit(main())
