#!/usr/bin/env python3
"""Speak audio longer than one pass: chain InfiniteTalk segments in a single graph.

WHY THIS EXISTS

`WanInfiniteTalkToVideo` speaks the FIRST `length` frames' worth of audio
(`audio_start = 0, audio_end = length` - 81 frames = 3.24 s at 25 fps as shipped)
and never reads past it. Raising `length` raises VRAM, so longer audio chains:
segment k > 0 takes the previous segment's decoded frames as `previous_frames`,
which advances the audio window by `length - motion_frame_count` (72 = 2.88 s at
defaults), while the first `motion_frame_count` (9) decoded frames reproduce the
overlap. The node's `trim_image` output (9 in extend mode) says how many leading
frames to drop - and the assembly below does exactly that, in latent space.

The bookkeeping is why this is a script and not a manual recipe:

  * chunk lengths: full 81-frame chunks, then a last chunk trimmed to fit the
    audio (`L' = F - 72 * (N - 1)` rounded to 4n+1, so the clip ends where the
    audio ends instead of idling through padding);
  * the overlap is 9 IMAGE frames = 2.25 latents, which no integer cut can split -
    so assembly drops whole *sampled* latents instead: the extend wrapper prepends
    the 3 motion latents and drops 3 sampled ones, hence each continuation
    contributes exactly `latent_t - 3` new latent frames (`LatentCut` t/3/amount +
    `LatentConcat` t, the same pair S33 uses for its first-frame hack);
  * one final `VAEDecode` + the last segment's `CreateVideo` (which muxes the whole
    original audio, cut to the clip), so there is exactly one output file;
  * the shipped flow's seconds-knob helpers are replaced by direct `length`
    widgets - a script can do its own arithmetic.

Everything is HTTP: the audio duration is probed locally (ffprobe), the chained
graph is built from the shipped workflow and submitted once, and the result is
fetched here. No shell on the box. Audio cannot be uploaded over the API (this
build exposes no /upload/audio), so a missing file is an error with scp
instructions, not a silent substitution.

Usage:
    uv run python scripts/talk_chain.py long_line.mp3 --ref portrait_heroine.png --out from-box/long_line.mp4
    uv run python scripts/talk_chain.py line.mp3 --dry-run          # show the plan, run nothing

The audio must exist locally AND in the server's input/ root. The reference
portrait must already be in input/.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_io  # noqa: E402
import sweep_workflow as sw  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WORKFLOW = os.path.join(REPO, "video", "workflows", "wan-infinitetalk.json")
FPS = 25
FULL = 81          # frames per full chunk (the shipped length)
ADVANCE = 72       # FULL - motion_frame_count; audio frames each continuation advances
OVERLAP_LATENT = 3  # (motion_frame_count - 1) // 4 + 1: motion latents the wrapper prepends


def round4n1(n: int) -> int:
    return max(1, math.floor((n - 1) / 4 + 0.5) * 4 + 1)


def probe_audio(path: str) -> float:
    if shutil.which("ffprobe") is None:
        raise SystemExit("ffprobe is required to read the audio duration and was not found on PATH")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise SystemExit("could not read the duration of %r (ffprobe said %r)" % (path, r.stdout.strip()))


def plan(total: int) -> list[int]:
    """Chunk lengths (4n+1) whose stitched output is `total` frames, +-2."""
    if total <= FULL:
        return [round4n1(total)]
    n = math.ceil((total - FULL) / ADVANCE) + 1
    last = round4n1(total - ADVANCE * (n - 1))
    # A last chunk under 13 frames would leave LatentCut with amount 0 (schema
    # minimum is 1) - clamp, and let the mux absorb the <=4-frame overshoot.
    out = [FULL] * (n - 1) + [max(13, last)]
    return out


def stitched(lengths: list[int]) -> int:
    return lengths[0] + sum(l - 9 for l in lengths[1:])


def ensure_audio(base, token, name, timeout):
    data = comfy_io._get_optional(
        comfy_io._url(base, "/view", token, filename=name, type="input"), timeout)
    if data is None:
        raise SystemExit(
            "%r is not in the server's input/ - this build has no /upload/audio, so copy it over:\n"
            "  scp <file> <box>:Projects-Git/ComfyUI/input/" % name)


def build(base, token, info, workflow, audio, ref, lengths):
    nodes = {n["id"]: copy.deepcopy(n) for n in workflow["nodes"]}
    links = [list(l) for l in workflow["links"]]
    lid = max(l[0] for l in links)
    nid = max(nodes)

    def new_id():
        nonlocal nid
        nid += 1
        return nid

    def add_link(src, ss, dst, ds, typ):
        nonlocal lid
        lid += 1
        links.append([lid, src, ss, dst, ds, typ])
        nodes[src]["outputs"][ss].setdefault("links", []).append(lid)
        while len(nodes[dst]["inputs"]) <= ds:
            nodes[dst]["inputs"].append({})
        # The slot keeps its own name (cloned from the template); only the link
        # is new. Writing typ.lower() as the name here misaligned every widget
        # after it in build_prompt's positional pass - names are load-bearing.
        nodes[dst]["inputs"][ds]["type"] = typ
        nodes[dst]["inputs"][ds]["link"] = lid
        nodes[dst]["inputs"][ds].setdefault("name", typ.lower())
        return lid

    # The seconds-knob helpers are dead weight in a scripted graph: length is set
    # directly per chunk below. Drop them (and their links) so nothing dangles.
    dead = [i for i, n in nodes.items() if n["type"] in ("PrimitiveFloat", "ComfyMathExpression")]
    dead_links = {l[0] for l in links if l[1] in dead or l[3] in dead}
    links = [l for l in links if l[0] not in dead_links]
    for i in dead:
        del nodes[i]
    for n in nodes.values():
        for o in n.get("outputs") or []:
            o["links"] = [l for l in (o.get("links") or []) if l not in dead_links]
        for i in n.get("inputs") or []:
            if i.get("link") in dead_links:
                del i["link"]

    # The shipped terminal chain (decode/assemble/mux) is rebuilt per plan below.
    for i in (14, 15, 16):
        doomed = {l[0] for l in links if l[1] == i or l[3] == i}
        links = [l for l in links if l[0] not in doomed]
        del nodes[i]
    for n in nodes.values():
        for o in n.get("outputs") or []:
            o["links"] = [l for l in (o.get("links") or []) if l in {l[0] for l in links}]
        for idx, i in enumerate(list(n.get("inputs") or [])):
            if i.get("link") not in {l[0] for l in links}:
                n["inputs"][idx] = {k: v for k, v in i.items() if k != "link"}

    base_wan = nodes[11]
    base_ks = nodes[13]
    acc = None       # (node id, slot) of the assembled latent so far
    prev_decode = None
    for k, lk in enumerate(lengths):
        w = copy.deepcopy(base_wan)
        w["id"] = new_id()
        w["widgets_values"] = ["single_speaker", 480, 832, lk, 9, 1.0]
        w["inputs"] = [dict(i) for i in base_wan["inputs"]]
        for i in w["inputs"]:
            i.pop("link", None)
        nodes[w["id"]] = w
        for l in [l for l in links if l[3] == 11]:
            add_link(l[1], l[2], w["id"], l[4], l[5])
        if k > 0:
            # continuation: the previous segment's decoded frames pin the motion
            # and advance the audio window by ADVANCE frames inside the node.
            w["inputs"].append({})
            add_link(prev_decode, 0, w["id"], len(w["inputs"]) - 1, "IMAGE")
            nodes[w["id"]]["inputs"][-1]["name"] = "previous_frames"
        ks = copy.deepcopy(base_ks)
        ks["id"] = new_id()
        nodes[ks["id"]] = ks
        # The sampler runs on the Wan node's OUTPUTS (patched model + carried
        # conditioning + latent) - not on the shared loaders. The original links
        # point at the deleted template Wan (11), so they are rewired here to
        # this segment's own Wan clone, never copied.
        add_link(w["id"], 0, ks["id"], 0, "MODEL")
        add_link(w["id"], 1, ks["id"], 1, "CONDITIONING")
        add_link(w["id"], 2, ks["id"], 2, "CONDITIONING")
        add_link(w["id"], 3, ks["id"], 3, "LATENT")
        latent_t = (lk - 1) // 4 + 1
        if k == 0:
            acc = (ks["id"], 0)
        else:
            cut = {"id": new_id(), "type": "LatentCut", "pos": [100, 520],
                   "size": [220, 100], "flags": {}, "mode": 0,
                   "widgets_values": ["t", OVERLAP_LATENT, latent_t - OVERLAP_LATENT],
                   "inputs": [{"name": "samples", "type": "LATENT"}],
                   "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}],
                   "properties": {"Node name for S&R": "LatentCut"}}
            nodes[cut["id"]] = cut
            add_link(ks["id"], 0, cut["id"], 0, "LATENT")
            cat = {"id": new_id(), "type": "LatentConcat", "pos": [100, 660],
                   "size": [220, 80], "flags": {}, "mode": 0,
                   "widgets_values": ["t"],
                   "inputs": [{"name": "samples1", "type": "LATENT"},
                              {"name": "samples2", "type": "LATENT"}],
                   "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}],
                   "properties": {"Node name for S&R": "LatentConcat"}}
            nodes[cat["id"]] = cat
            add_link(acc[0], acc[1], cat["id"], 0, "LATENT")
            add_link(cut["id"], 0, cat["id"], 1, "LATENT")
            acc = (cat["id"], 0)
        if k < len(lengths) - 1:
            dec = {"id": new_id(), "type": "VAEDecode", "pos": [100, 300],
                   "size": [220, 80], "flags": {}, "mode": 0,
                   "widgets_values": [],
                   "inputs": [{"name": "samples", "type": "LATENT"},
                              {"name": "vae", "type": "VAE"}],
                   "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}],
                   "properties": {"Node name for S&R": "VAEDecode"}}
            nodes[dec["id"]] = dec
            add_link(ks["id"], 0, dec["id"], 0, "LATENT")
            add_link(7, 0, dec["id"], 1, "VAE")
            prev_decode = dec["id"]
    del nodes[11]
    del nodes[13]
    live = set(nodes)
    links = [l for l in links if l[1] in live and l[3] in live]

    vae_out = {"id": new_id(), "type": "VAEDecode", "pos": [100, 300],
               "size": [220, 80], "flags": {}, "mode": 0,
               "widgets_values": [],
               "inputs": [{"name": "samples", "type": "LATENT"},
                          {"name": "vae", "type": "VAE"}],
               "outputs": [{"name": "IMAGE", "type": "IMAGE", "slot_index": 0}],
               "properties": {"Node name for S&R": "VAEDecode"}}
    nodes[vae_out["id"]] = vae_out
    add_link(acc[0], acc[1], vae_out["id"], 0, "LATENT")
    add_link(7, 0, vae_out["id"], 1, "VAE")
    cv = {"id": new_id(), "type": "CreateVideo", "pos": [380, 220],
          "size": [260, 100], "flags": {}, "mode": 0,
          "widgets_values": [25, 8],
          "inputs": [{"name": "images", "type": "IMAGE"},
                     {"name": "audio", "type": "AUDIO"}],
          "outputs": [{"name": "VIDEO", "type": "VIDEO", "slot_index": 0}],
          "properties": {"Node name for S&R": "CreateVideo"}}
    nodes[cv["id"]] = cv
    add_link(vae_out["id"], 0, cv["id"], 0, "IMAGE")
    add_link(9, 0, cv["id"], 1, "AUDIO")
    sv = {"id": new_id(), "type": "SaveVideo", "pos": [680, 220],
          "size": [340, 300], "flags": {}, "mode": 0,
          "widgets_values": ["talk_chain/out", "auto", "auto"],
          "inputs": [{"name": "video", "type": "VIDEO"}],
          "outputs": [],
          "properties": {"Node name for S&R": "SaveVideo"}}
    nodes[sv["id"]] = sv
    add_link(cv["id"], 0, sv["id"], 0, "VIDEO")

    graph = {"nodes": list(nodes.values()), "links": links}
    return sw.build_prompt(graph, info, {9: {"audio": audio}}, image=ref)


def main() -> int:
    ap = argparse.ArgumentParser(description="Speak audio longer than one InfiniteTalk pass.")
    ap.add_argument("audio", help="local audio file (duration probed with ffprobe)")
    ap.add_argument("--duration", type=float, default=None,
                    help="audio seconds, to skip the ffprobe probe (e.g. when running on the box)")
    ap.add_argument("--ref", default="portrait_heroine.png", help="portrait in the server's input/")
    ap.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    ap.add_argument("--out", help="local path for the chained result")
    ap.add_argument("--base", default=os.environ.get("COMFY_BASE"))
    ap.add_argument("--token", default=os.environ.get("COMFY_TOKEN"))
    ap.add_argument("--timeout", type=float, default=7200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.audio):
        raise SystemExit("no such audio file: %s" % args.audio)
    dur = args.duration if args.duration else probe_audio(args.audio)
    total = round(dur * FPS)
    lengths = plan(total)
    print("audio: %s  %.2f s  ~%d frames @ %d fps" % (args.audio, dur, total, FPS))
    print("plan: %d segment(s) of %s; stitched %d frames (%.2f s)%s"
          % (len(lengths), lengths, stitched(lengths), stitched(lengths) / FPS,
             "" if len(lengths) == 1 else "; joins at %s"
             % ", ".join(str(81 + 72 * k) for k in range(len(lengths) - 1))))

    base = comfy_io.resolve_base(args.base)
    token = comfy_io.resolve_token(args.token, base)
    name = os.path.basename(args.audio)
    ensure_audio(base, token, name, 300)

    workflow = json.load(open(args.workflow, encoding="utf-8"))
    info = sw.api(base, token, "/object_info")
    prompt = build(base, token, info, workflow, name, args.ref, lengths)
    if args.dry_run:
        print("dry run: prompt built (%d nodes), nothing submitted" % len(prompt))
        return 0

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
        if time.time() - t0 > args.timeout:
            raise SystemExit("chained run timed out after %.0fs" % args.timeout)
    if not entry[pid].get("status", {}).get("completed"):
        raise SystemExit(json.dumps(entry[pid].get("status", {}))[:600])
    files = [f for f in comfy_io.collect_files(entry[pid])
             if f["filename"].endswith((".mp4", ".webm")) and f["type"] == "output"]
    if not files:
        raise SystemExit("chained run produced no output video (history listed: %s)"
                         % [f["filename"] for f in comfy_io.collect_files(entry[pid])])
    mp4 = comfy_io._get(comfy_io._url(base, "/view", token, filename=files[0]["filename"],
                                      subfolder=files[0]["subfolder"] or None,
                                      type=files[0]["type"]), args.timeout)
    if not args.out:
        raise SystemExit("--out is required for a real run")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "wb").write(mp4)
    print("\nwrote %s  %d frames planned, %d bytes  %.0fs wall"
          % (args.out, stitched(lengths), len(mp4), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
