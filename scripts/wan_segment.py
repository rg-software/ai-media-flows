#!/usr/bin/env python3
"""Generate a clip longer than one pass: segment it, and continue each segment from the last frame.

WHY THIS EXISTS

A single run generates `length` frames and stops - `WanAnimate2ToVideo` slices `pose_video[offset:][:length]`,
so a 121-frame clip with the default `length: 33` animates the first 27% and nothing after it. Raising `length`
is not the answer either: cost is super-linear, 81 frames measured 1000 s at 23.7 GB against 91 s and 20.8 GB
for 33 (`animation/EXPERIMENTS.md` E3).

Segmentation is the answer, and the node supports it: pass the previous segment's **last decoded frame** as
`continue_motion`, and the node pins it as the new segment's first frame and marks it *known* in the concat
mask. Measured join difference 40.76 -> 3.58, with the framing continuous where naive concatenation jumps the
camera (`animation/EXPERIMENTS.md` E12/E14).

The bookkeeping is the hard part, which is why it is a script and not a manual recipe:

  * the offset is DECREMENTED by the continue frames, so segment k takes `last pose + 1`, and the poses advance
    by `length - 1` per segment (0, 33, 65, 97 for 33-frame segments - *not* offset + length, which drifts a
    pose from the third segment on);
  * only the LAST frame of `continue_motion` is used;
  * each continuation's first output frame is the pinned one, so it is dropped when stitching;
  * the last tile usually overshoots the clip and is trimmed at the end.

Everything is HTTP: the clip is fetched and split locally, each segment is submitted to the remote ComfyUI
(with the previous frame uploaded into input/), and the result is stitched here. No shell on the box, and the
shipped workflow is used unchanged - the continue_motion LoadImage is injected into the API prompt, not the
file.

Usage:
    uv run python scripts/wan_segment.py street_dance_drive.mp4 --ref pink_hair_mech_arms_ref.png \
        --seed 33 --out from-box/dance_full.mp4
    uv run python scripts/wan_segment.py clip.mp4 --dry-run          # show the plan, run nothing

Both the clip and the reference image must already be in the server's `input/`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_io  # noqa: E402
import sweep_workflow as sw  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WORKFLOW = os.path.join(REPO, "animation", "workflows", "wan-animate-motion.json")
CONT_NODE = "9000"          # the LoadImage this script injects for continue_motion


def fetch(base, token, path, type_, timeout):
    subfolder, _, filename = path.strip("/").rpartition("/")
    url = comfy_io._url(base, "/view", token, filename=filename, subfolder=subfolder or None, type=type_)
    data = comfy_io._get_optional(url, timeout)
    if data is None:
        raise SystemExit(f"{path!r} is not in ComfyUI's {type_}/ - upload it first")
    return data


def probe(data: bytes) -> tuple[int, float, int, int]:
    import cv2
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
        fh.write(data)
        tmp = fh.name
    cap = cv2.VideoCapture(tmp)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    os.unlink(tmp)
    return n, fps, w, h


def decode(data: bytes) -> list:
    import cv2
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
        fh.write(data)
        tmp = fh.name
    cap = cv2.VideoCapture(tmp)
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        out.append(f)
    cap.release()
    os.unlink(tmp)
    return out


def upload_png(base, token, png_bytes, name, timeout):
    fields = {"type": "input", "overwrite": "true", "subfolder": "_wan_seg"}
    body, ctype = comfy_io._multipart(fields, "image", name, png_bytes)
    comfy_io._post_multipart(comfy_io._url(base, "/upload/image", token), body, ctype, timeout)


def plan(frames: int, length: int) -> list[tuple[int, int]]:
    if length < 5 or (length - 1) % 4:
        raise SystemExit(f"--segment must be 4n+1 (33, 49, 81...), got {length}")
    if frames <= length:
        return [(0, 0)]
    step = length - 1
    segments, start = [], 0
    while start < frames - 1:
        segments.append((len(segments), start))
        start += step
    return segments


def run_segment(base, token, info, workflow, wau_id, ref_node, ref, offset, cont_path, length, timeout, args):
    over = {wau_id: {"video_frame_offset": offset, "length": length}}
    if ref_node:
        over[ref_node] = {"image": ref}
    prompt = sw.build_prompt(workflow, info, over, None)
    if cont_path:
        prompt[CONT_NODE] = {"class_type": "LoadImage",
                             "inputs": {"image": cont_path, "upload": "image"}}
        prompt[str(wau_id)]["inputs"]["continue_motion"] = [CONT_NODE, 0]
    if args.dry_run:
        return None
    resp = sw.post(base, token, "/prompt", {"prompt": prompt})
    pid = resp["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(5)
        entry = json.loads(comfy_io._get(comfy_io._url(base, "/history", token, prompt_id=pid), 60))
        if pid in entry:
            st = entry[pid].get("status", {})
            if st.get("completed") or st.get("status_str") == "error":
                break
        if time.time() - t0 > timeout:
            raise SystemExit(f"segment timed out after {timeout:.0f}s")
    if not entry[pid].get("status", {}).get("completed"):
        raise SystemExit(json.dumps(entry[pid].get("status", {}))[:600])
    files = [f for f in comfy_io.collect_files(entry[pid])
             if f["filename"].endswith((".mp4", ".webm")) and f["type"] == "output"]
    if not files:
        raise SystemExit("segment produced no output video (history listed: %s)"
                         % [f["filename"] for f in comfy_io.collect_files(entry[pid])])
    mp4 = fetch(base, token, f'{files[0]["subfolder"]}/{files[0]["filename"]}'.strip("/"),
                files[0]["type"], timeout)
    print("    %.0fs, %s" % (time.time() - t0, files[0]["filename"]))
    return decode(mp4)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a clip longer than one pass, by segmenting it.")
    ap.add_argument("video", help="source clip, already in the server's input/")
    ap.add_argument("--ref", required=True, help="reference image, already in input/")
    ap.add_argument("--segment", type=int, default=33, help="frames per segment, 4n+1 (default 33)")
    ap.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    ap.add_argument("--out", help="local path for the stitched result")
    ap.add_argument("--base", default=os.environ.get("COMFY_BASE"))
    ap.add_argument("--token", default=os.environ.get("COMFY_TOKEN"))
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = comfy_io.resolve_base(args.base)
    token = comfy_io.resolve_token(args.token, base)

    data = fetch(base, token, args.video, "input", 300)
    frames, fps, w, h = probe(data)
    print("source: %s  %d frames  %.2f fps  %dx%d  %.1f s" % (args.video, frames, fps, w, h, frames / fps))

    workflow = json.load(open(args.workflow, encoding="utf-8"))
    info = sw.api(base, token, "/object_info")
    wau = next(n for n in workflow["nodes"] if n["type"] == "WanAnimate2ToVideo")
    ref_node = next((n["id"] for n in workflow["nodes"] if n["type"] == "LoadImage"), None)

    segments = plan(frames, args.segment)
    print("plan: %d segment(s) of %d frames; joins at %s"
          % (len(segments), args.segment,
             ", ".join(str(1 + k * (args.segment - 1)) for k in range(1, len(segments))) or "none"))

    import cv2
    import numpy as np
    collected = []
    step = args.segment - 1
    for k, start in segments:
        offset = 0 if k == 0 else 1 + k * step
        cont = None
        if k > 0 and not args.dry_run:
            prev = collected[-1]
            ok, buf = cv2.imencode(".png", prev)
            if not ok:
                raise SystemExit("could not encode the continuation frame")
            cont = f"_wan_seg/cont_{k}.png"
            upload_png(base, token, buf.tobytes(), f"cont_{k}.png", 300)
        print("  segment %d/%d  offset %d  pose %d  %s"
              % (k + 1, len(segments), offset, offset - 1 if k else 0,
                 "continue from the previous frame" if k else "no continuation"))
        if args.dry_run:
            continue
        got = run_segment(base, token, info, workflow, wau["id"], ref_node, args.ref,
                          offset, cont, args.segment, args.timeout, args)
        if k > 0:
            pin = float(np.abs(got[0].astype(np.float32) - collected[-1].astype(np.float32)).mean())
            print("    join: pinned frame differs by %.2f from the previous last frame" % pin)
            got = got[1:]
        collected.extend(got)

    if args.dry_run:
        print("dry run: nothing submitted")
        return 0

    collected = collected[:frames]
    if not args.out:
        raise SystemExit("--out is required for a real run")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    oh, ow = collected[0].shape[:2]      # the GENERATED size, which is not the source's
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (ow, oh))
    if not vw.isOpened():
        raise SystemExit("could not open %s for writing" % args.out)
    for f in collected:
        if f.shape[:2] != (oh, ow):
            f = cv2.resize(f, (ow, oh))
        vw.write(f)
    vw.release()
    print("\nwrote %s  %d frames  %.2f s  %.2f fps  %dx%d  %d bytes"
          % (args.out, len(collected), len(collected) / fps, fps, ow, oh, os.path.getsize(args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
