#!/usr/bin/env python3
"""E21 - change a character's POSE while keeping the character, and measure whether it worked.

S7 covers appearance consistency (design/face) but had no answer for "same character, different pose".
The pose is a *structural* carrier, and we have the tools: `OpenposePreprocessor` extracts a skeleton
(`IMAGE` + `POSE_KEYPOINT`), the union ControlNet has an `openpose` mode, and ComfyUI core can draw
keypoints back to a skeleton. Identity has to be carried separately (the skeleton says nothing about who
the character is) - hence the optional PuLID arm.

Subcommands (all talk to the ComfyUI HTTP API; no third-party deps beyond numpy/PIL):

    template out.json [--preset standing|arms_spread|t_pose] [--arm DEG] [--rotate DEG]
             [--width W] [--height H]
             write an EDITABLE keypoints file (18 joints x [x, y, confidence]) - start here if you
             just want a pose without running anything else

    extract  <image in ComfyUI input/> [--prefix 2D/E21/pose] [--resolution 1024]
             keypoints of an image -> JSON in ComfyUI's output/ (prints the path + a summary)

    draw     <keypoints.json> <out.png> [--transform none|spread|roll:<deg>] [--labels]
             render an OpenPose-style body skeleton for the ControlNet, optionally posed; `--labels`
             prints each joint's index on the image (the way to learn or verify the joint order):
               spread      rotate each upper arm ~35 deg away from the body (a real pose change)
               roll:<deg>  rotate the whole figure in-plane (a lean/tilt - NOT a viewpoint change;
                           a 2D COCO skeleton cannot express yaw, which is what "camera angle" needs)

    run-cn   <skeleton in ComfyUI input/> [--strength 0.9] [--prompt ...] [--ipadapter <image>]
             RealVisXL + ControlNet-Union(`openpose`) + optional IPAdapter for the design ->
             output/2D/E21/   (this is what 2d/workflows/pose-skeleton.json does, via the API)

    run-qwen <image> --instruction "..."   the Qwen-Edit instruction arm (E21's best single shot)
    measure  <generated image> <target keypoints.json>
             re-extract the generated pose and compare -> mean/median joint error in px

## How to author a pose (three ways, cheapest first)

1. **Start from a preset** - the common case, no other tooling:
       uv run python scripts/pose_probe.py template /tmp/pose.json --preset t_pose
       # edit the numbers (e.g. move joints 4/7 - the wrists - to change the hands)
       uv run python scripts/pose_probe.py draw /tmp/pose.json output/pose_t.png --labels
       #   --labels prints every joint's index on the picture: draw once, see which number to move
   Then upload `output/pose_t.png` to the box's `input/_pose/` and set the flow's first LoadImage to it:
       uv run python scripts/comfy_io.py upload output/pose_t.png --subfolder _pose
   Presets: `standing` (arms ~8 deg), `arms_spread` (45), `t_pose` (90); `--arm` sets any angle and
   `--rotate` leans the figure in-plane.

2. **Take a pose from a PHOTO** (not stylised art - see the caveat below):
       uv run python scripts/pose_probe.py extract 2d/some_photo.png --prefix 2D/pose
       # the JSON lands in ComfyUI/output/2D/pose_00001.json - fetch it with a base64/ssh copy,
       # or edit it in place on the box; then `draw` it and upload as above.

3. **Take the pose from an existing picture of your character** - same as (2), but it needs the
   preprocessor to see a person: it returns `people: []` on our stylised/armoured assets (E21), so
   for those author the joints by hand with (1) instead.

Then run `2d/workflows/pose-skeleton.json` (or `run-cn` for the API equivalent) and judge by eye: the
pose CN follows the skeleton, the DESIGN drifts unless IPAdapter holds it at a LOW weight.

**The CN window (`--cn-end`) is what makes a pose cue do anything at all (E22).** Applied for all steps,
`openpose` is ignored at 0.9-1.2 and wrecks the image at 1.5 (E21c). End it early (`--strength 1.5
--cn-end 0.5`) and a T-pose cue beats a prompt that explicitly says the opposite - but only at the level of
the SILHOUETTE: a 45-deg cue still renders arms at the sides, an asymmetric cue is ignored, and a "both arms
up" cue comes back as shoulder horns. This is a coarse-stance tool ("arms out / wide / tall"); for a
specific pose use an instruction (`run-qwen`). Keep IPAdapter at ~0.15 (0.35 erased a 45-deg spread; >=0.6
freezes the reference's own stance).

Combo options (ApplyPulid.method, PulidInsightFaceLoader.provider) are read from /object_info before
submitting, because a bad combo value fails SILENTLY in ComfyUI (the `SetUnionControlNetType` lesson).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

COMFY = Path.home() / "Projects-Git" / "ComfyUI"
COMFY_IN = COMFY / "input"
COMFY_OUT = COMFY / "output"
CKPT = "RealVisXL_V5.0_fp16.safetensors"
UNION_CN = "controlnet-union-sdxl.safetensors"
PULID_FILE = "ip-adapter_pulid_sdxl_fp16.safetensors"

# OpenPose COCO-18 body layout
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10),
         (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
          (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
          (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]
L_SHOULDER, L_ELBOW, L_WRIST = 5, 6, 7
R_SHOULDER, R_ELBOW, R_WRIST = 2, 3, 4

# joints: 0 nose, 1 neck, 2/3/4 R shoulder/elbow/wrist, 5/6/7 L shoulder/elbow/wrist,
#         8/9/10 R hip/knee/ankle, 11/12/13 L hip/knee/ankle, 14/15 R/L eye, 16/17 R/L ear
# "R" is the SUBJECT's right = image LEFT (OpenPose convention).
PRESETS = {"standing": 8, "arms_spread": 45, "t_pose": 90}
JOINT_NAMES = ["nose", "neck", "Rshoulder", "Relbow", "Rwrist", "Lshoulder", "Lelbow", "Lwrist",
               "Rhip", "Rknee", "Rankle", "Lhip", "Lknee", "Lankle", "Reye", "Leye", "Rear", "Lear"]


def build_figure(w: int, h: int, arm_deg: float, rotate: float = 0.0):
    """A centred standing figure on a w x h canvas; `arm_deg` swings the arms out from vertical."""
    import math
    cx = w / 2
    nose, neck = h * 0.13, h * 0.28
    hip, knee, ankle = h * 0.55, h * 0.72, h * 0.93
    shx, hipx = w * 0.085, w * 0.048
    upper, fore = h * 0.13, h * 0.12
    pt = {
        0: (cx, nose), 1: (cx, neck),
        2: (cx - shx, neck), 3: None, 4: None, 5: (cx + shx, neck), 6: None, 7: None,
        8: (cx - hipx, hip), 9: (cx - hipx * 0.9, knee), 10: (cx - hipx * 0.8, ankle),
        11: (cx + hipx, hip), 12: (cx + hipx * 0.9, knee), 13: (cx + hipx * 0.8, ankle),
        14: (cx - w * 0.02, nose - h * 0.015), 15: (cx + w * 0.02, nose - h * 0.015),
        16: (cx - w * 0.035, nose - h * 0.01), 17: (cx + w * 0.035, nose - h * 0.01),
    }
    for side, (sh, el, wr) in (("L", (5, 6, 7)), ("R", (2, 3, 4))):
        sx, sy = pt[sh]
        s = 1.0 if side == "L" else -1.0
        a = math.radians(90 - arm_deg)          # 90 = straight out (T-pose)
        ex, ey = sx + s * upper * math.cos(a), sy + upper * math.sin(a)
        a2 = math.radians(90 - arm_deg * 0.7)
        wx, wy = ex + s * fore * math.cos(a2), ey + fore * math.sin(a2)
        pt[el], pt[wr] = (ex, ey), (wx, wy)
    if rotate:
        cx0, cy0 = w / 2, h / 2
        pt = {k: rotate_about((v[0], v[1], 1.0), (cx0, cy0), rotate)[:2] for k, v in pt.items()}
    return [c for i in range(18) for c in (pt[i][0], pt[i][1], 1.0)]


# --------------------------------------------------------------------------- HTTP
def _api(base, token):
    def url(path, **params):
        if token:
            params["token"] = token
        return f"{base}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")

    def post(obj):
        req = urllib.request.Request(url("/prompt"), data=json.dumps(obj).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)

    def get(path, **params):
        with urllib.request.urlopen(url(path, **params), timeout=120) as r:
            return json.load(r)

    def wait(pid, timeout=900):
        for _ in range(timeout // 3):
            entry = get("/history", prompt_id=pid).get(pid)
            if entry:
                st = entry.get("status", {})
                if st.get("completed") or st.get("status_str") == "error":
                    if st.get("status_str") == "error":
                        raise SystemExit("run errored - check the journal (comfyui/README.md)")
                    return entry
            time.sleep(3)
        raise SystemExit("timed out")

    return url, post, get, wait


def check_graph(graph):
    """Every ["id", slot] reference must point at a node that exists in the graph.

    ComfyUI reports a dangling reference as an opaque `400 prompt_outputs_failed_validation` (the detail
    names only the *dependent* node), so a renamed node turned into a stack trace instead of a message.
    Renumbering the ControlNet node while the KSampler still pointed at the old id did exactly this.
    """
    bad = []
    for nid, node in graph.items():
        for name, val in node["inputs"].items():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] not in graph:
                bad.append(f"  node {nid} ({node['class_type']}).{name} -> node {val[0]} (missing)")
    if bad:
        raise SystemExit("graph has dangling references:\n" + "\n".join(bad))


def run_graph(a, graph, label):
    check_graph(graph)
    base = a.base.rstrip("/")
    url, post, get, wait = _api(base, a.token)
    resp = post({"prompt": graph, "client_id": "pose_probe"})
    pid = resp.get("prompt_id")
    if not pid:
        raise SystemExit(f"{label}: submit failed: {json.dumps(resp)[:300]}")
    entry = wait(pid)
    files = []
    for o in entry.get("outputs", {}).values():
        files += o.get("images", [])
        for v in o.values():
            if isinstance(v, list):
                for it in v:
                    if isinstance(it, dict) and "filename" in it:
                        files.append(it)
    return pid, files


def combo_options(a, node, name):
    _, _, get, _ = _api(a.base.rstrip("/"), a.token)
    spec = get("/object_info/" + node)[node]["input"]
    for group in ("required", "optional"):
        s = (spec.get(group) or {}).get(name)
        if s and isinstance(s[0], list):
            return s[0]
    return None


# --------------------------------------------------------------------------- extract / measure
def graph_extract(image, prefix, resolution):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image}},
        "2": {"class_type": "OpenposePreprocessor",
              "inputs": {"image": ["1", 0], "detect_hand": "enable", "detect_body": "enable",
                         "detect_face": "enable", "resolution": resolution,
                         "scale_stick_for_xinsr_cn": "enable"}},
        "3": {"class_type": "SavePoseKpsAsJsonFile",
              "inputs": {"pose_kps": ["2", 1], "filename_prefix": prefix}},
        # keep the rendered skeleton too - it shows what the preprocessor saw
        "4": {"class_type": "SaveImage",
              "inputs": {"images": ["2", 0], "filename_prefix": prefix + "_skeleton"}},
    }


def pose_of(payload):
    """First person's body keypoints from a controlnet_aux pose JSON payload."""
    data = payload[0] if isinstance(payload, list) else payload
    people = data.get("people") or []
    if not people:
        return [], data
    p = dict(people[0])
    for k in ("pose_keypoints_2d",):
        v = p.get(k) or []
        if v and isinstance(v[0], (list, tuple)):
            v = [c for t in v for c in t]          # [[x, y, conf], ...] -> flat
        pts = [(v[i], v[i + 1], v[i + 2] if i + 2 < len(v) else 1.0) for i in range(0, len(v) - 2, 3)]
        if len(pts) >= 18:
            return pts, data
        pts = [(v[i], v[i + 1], 1.0) for i in range(0, min(len(v), 36), 2)]
        if len(pts) >= 18:
            return pts, data
    return [], data


def latest_json(prefix):
    """SavePoseKpsAsJsonFile writes into output/ and reports nothing in history, so glob for it."""
    parent = COMFY_OUT / Path(prefix).parent
    stem = Path(prefix).name
    hits = sorted(parent.glob(stem + "*.json"), key=lambda p: p.stat().st_mtime)
    if not hits:
        raise SystemExit(f"no POSE json matching {parent / (stem + '*.json')}")
    return hits[-1]


def cmd_extract(a):
    pid, files = run_graph(a, graph_extract(a.image, a.prefix, a.resolution), "extract")
    jp = latest_json(a.prefix)
    payload = json.loads(jp.read_text(encoding="utf-8"))
    pts, data = pose_of(payload)
    if not pts:
        raise SystemExit(f"no person detected in {a.image}")
    det = sum(1 for _, _, s in pts if s > 0.1)
    pngs = [f for f in files if f["filename"].endswith(".png")]
    print(f"  json   : {jp}")
    if pngs:
        print(f"  skeleton: {COMFY_OUT / (pngs[-1].get('subfolder') or '') / pngs[-1]['filename']}")
    print(f"  canvas : {data.get('canvas_width')}x{data.get('canvas_height')}")
    print(f"  joints : {det}/18 above confidence 0.1")
    return 0


def arm_geometry(pts):
    """Scale-free description of the arms - the thing 'did the pose take?' actually means.

    Pixel error is only comparable between renders of the SAME size (and a 512px SD1.5 run vs a 1024px
    SDXL run share no coordinate system at all), so measure everything in units of the figure's own
    torso length. `spread` is how far the wrist sits out to the side of the hip, `drop` how far the
    wrist sits below the shoulder: a T-pose is spread >> 1 with drop ~ 0, arms-down is spread < 0.5 with
    drop > 1. Returns None when the detector did not see the joints.
    """
    R_SH, R_WR, R_HP = 2, 4, 8
    L_SH, L_WR, L_HP = 5, 7, 11
    if max(pts[i][2] for i in (R_SH, R_WR, R_HP, L_SH, L_WR, L_HP)) <= 0.1:
        return None
    sh_y = (pts[R_SH][1] + pts[L_SH][1]) / 2
    hp_y = (pts[R_HP][1] + pts[L_HP][1]) / 2
    torso = abs(hp_y - sh_y)
    if torso < 1e-6:
        return None
    out = {"torso_px": torso}
    for side, (sh, wr, hp) in (("R", (R_SH, R_WR, R_HP)), ("L", (L_SH, L_WR, L_HP))):
        if min(pts[sh][2], pts[wr][2], pts[hp][2]) <= 0.1:
            out[side] = None
            continue
        out[side] = {"spread": abs(pts[wr][0] - pts[hp][0]) / torso,
                     "drop": (pts[wr][1] - sh_y) / torso}
    return out


def _fmt_geom(g):
    if g is None:
        return "no person detected"
    parts = []
    for side in ("R", "L"):
        s = g[side]
        parts.append(f"{side} spread {s['spread']:.2f} drop {s['drop']:+.2f}" if s else f"{side} no joints")
    return "   ".join(parts)


def cmd_measure(a):
    target = json.loads(Path(a.target).read_text(encoding="utf-8"))
    tpts, _ = pose_of(target)
    pid, files = run_graph(a, graph_extract(a.image, "2D/E21/measure", 1024), "measure")
    payload = json.loads(latest_json("2D/E21/measure").read_text(encoding="utf-8"))
    gpts, _ = pose_of(payload)
    print(f"  target pose: {_fmt_geom(arm_geometry(tpts))}")
    if not gpts:
        print("  no person detected (pose NOT followed)")
        return 1
    g = arm_geometry(gpts)
    print(f"  got         : {_fmt_geom(g)}")
    errs = []
    for (tx, ty, ts), (gx, gy, gs) in zip(tpts, gpts):
        if ts > 0.1 and gs > 0.1:
            errs.append(((tx - gx) ** 2 + (ty - gy) ** 2) ** 0.5)
    if not errs:
        print("  no joints comparable")
        return 1
    errs.sort()
    mean = sum(errs) / len(errs)
    print(f"  comparable joints: {len(errs)}/18")
    unit = f"{mean / g['torso_px']:.2f} torso lengths" if g else "torso not measurable"
    print(f"  joint error: mean {mean:.1f} px = {unit}"
          f", median {errs[len(errs) // 2]:.1f} px")
    return 0


# --------------------------------------------------------------------------- author a pose
def rotate_about(p, c, deg):
    import math
    th = math.radians(deg)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * math.cos(th) - dy * math.sin(th),
            c[1] + dx * math.sin(th) + dy * math.cos(th), p[2])


def cmd_draw(a):
    payload = json.loads(Path(a.keypoints).read_text(encoding="utf-8"))
    pts, data = pose_of(payload)
    if not pts:
        raise SystemExit(f"no person in {a.keypoints}")
    W = int(data.get("canvas_width") or 1024)
    H = int(data.get("canvas_height") or 1024)
    pts = list(pts)
    if a.transform == "spread":
        for sh, el, wr, sign in ((L_SHOULDER, L_ELBOW, L_WRIST, 1), (R_SHOULDER, R_ELBOW, R_WRIST, -1)):
            if pts[sh][2] > 0.1 and pts[el][2] > 0.1:
                c = (pts[sh][0], pts[sh][1])
                pts[el] = rotate_about(pts[el], c, sign * 35)
                if pts[wr][2] > 0.1:
                    pts[wr] = rotate_about(pts[wr], c, sign * 35)
    elif a.transform.startswith("roll:"):
        deg = float(a.transform.split(":", 1)[1])
        xs = [p[0] for p in pts if p[2] > 0.1]
        ys = [p[1] for p in pts if p[2] > 0.1]
        c = (sum(xs) / len(xs), sum(ys) / len(ys))
        pts = [rotate_about(p, c, deg) if p[2] > 0.1 else p for p in pts]

    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (i1, i2) in enumerate(LIMBS):
        if pts[i1][2] > 0.1 and pts[i2][2] > 0.1:
            d.line([pts[i1][:2], pts[i2][:2]], fill=COLORS[i % len(COLORS)], width=max(4, W // 200))
    for p in pts:
        if p[2] > 0.1:
            r = max(4, W // 150)
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=(255, 255, 255))
    if a.labels:
        from PIL import ImageFont
        fnt = ImageFont.load_default(size=max(12, W // 40))
        for i, p in enumerate(pts):
            if p[2] > 0.1:
                d.text((p[0] + max(6, W // 90), p[1] - max(8, W // 70)), str(i),
                       fill=(255, 255, 0), font=fnt)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    im.save(a.out)
    print(f"  wrote {a.out} ({W}x{H}, transform={a.transform})")
    return 0


# --------------------------------------------------------------------------- run-cn
def graph_cn(a, prompt, neg, seed, pulid_options):
    # ControlNet-Union needs the mode-selector node; a plain SD1.5/SDXL CN (e.g. the official
    # openpose or a dedicated xinsir file) is loaded and applied directly.
    cn_from = ["5", 0]
    g = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": a.ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": a.skeleton}},
        "5": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": a.cn_file}},
        "6": {"class_type": "ControlNetApplyAdvanced",
              "inputs": {"positive": ["2", 0], "negative": ["3", 0], "control_net": cn_from,
                         "image": ["4", 0], "strength": a.strength,
                         "start_percent": a.cn_start, "end_percent": a.cn_end}},
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": a.width, "height": a.height,
                                                           "batch_size": 1}},
    }
    if a.cn_file == UNION_CN:
        g["21"] = {"class_type": "SetUnionControlNetType",
                   "inputs": {"control_net": ["5", 0], "type": a.cn_type}}
        g["6"]["inputs"]["control_net"] = ["21", 0]
    model_from = ["1", 0]
    if a.ipadapter:
        # a helmeted character has no face to embed, so carry the DESIGN (IPAdapter), not a face (PuLID)
        g["17"] = {"class_type": "CLIPVisionLoader",
                   "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}}
        g["18"] = {"class_type": "IPAdapterModelLoader",
                   "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}}
        g["19"] = {"class_type": "LoadImage", "inputs": {"image": a.ipadapter}}
        g["20"] = {"class_type": "IPAdapterAdvanced",
                   "inputs": {"model": ["1", 0], "ipadapter": ["18", 0], "image": ["19", 0],
                              "weight": a.ipadapter_weight, "weight_type": "linear",
                              "combine_embeds": "concat", "start_at": 0.0, "end_at": 1.0,
                              "embeds_scaling": "V only", "clip_vision": ["17", 0]}}
        model_from = ["20", 0]
    if a.pulid:
        method, provider = pulid_options
        g["9"] = {"class_type": "LoadImage", "inputs": {"image": a.pulid}}
        g["10"] = {"class_type": "PulidModelLoader", "inputs": {"pulid_file": PULID_FILE}}
        g["11"] = {"class_type": "PulidInsightFaceLoader", "inputs": {"provider": provider}}
        g["12"] = {"class_type": "PulidEvaClipLoader", "inputs": {}}
        g["13"] = {"class_type": "ApplyPulid",
                   "inputs": {"model": ["1", 0], "pulid": ["10", 0], "eva_clip": ["12", 0],
                              "face_analysis": ["11", 0], "image": ["9", 0], "method": method,
                              "weight": a.pulid_weight, "start_at": 0.0, "end_at": 1.0}}
        model_from = ["13", 0]
    g["14"] = {"class_type": "KSampler",
               "inputs": {"seed": seed, "steps": a.steps, "cfg": a.cfg, "sampler_name": a.sampler,
                          "scheduler": "normal", "denoise": 1.0, "model": model_from,
                          "positive": ["6", 0], "negative": ["6", 1], "latent_image": ["8", 0]}}
    g["15"] = {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["1", 2]}}
    g["16"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": a.out, "images": ["15", 0]}}
    return g


def cmd_run_cn(a):
    pulid_options = (None, None)
    if a.pulid:
        method = a.pulid_method
        if method == "auto":
            opts = combo_options(a, "ApplyPulid", "method") or []
            method = "fidelity" if "fidelity" in opts else (opts[0] if opts else None)
        if method is None:
            raise SystemExit("could not determine ApplyPulid.method from /object_info")
        provider_opts = combo_options(a, "PulidInsightFaceLoader", "provider") or []
        provider = "gpu" if "gpu" in provider_opts else (provider_opts[0] if provider_opts else None)
        pulid_options = (method, provider)
        print(f"  pulid: method={method} face_provider={provider} weight={a.pulid_weight}")
    pid, files = run_graph(a, graph_cn(a, a.prompt, a.negative, a.seed, pulid_options), "run-cn")
    print(f"  strength={a.strength} type={a.cn_type} ipadapter={'yes' if a.ipadapter else 'no'} "
          f"pulid={'yes' if a.pulid else 'no'} -> {[f['filename'] for f in files]}")
    return 0


# --------------------------------------------------------------------------- qwen-edit arm
def graph_qwen(a):
    """Instruction-based arm: the cheap 'just ask for the new pose' path (qwen-edit-gguf.json)."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": a.image}},
        "2": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": "qwen-image-edit-2511-Q4_K_M.gguf"}},
        "3": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                         "type": "qwen_image", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        # the shipped flow loads the RELIGHT LoRA; off here so the pose test is clean
        "5": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["2", 0], "lora_name": "Qwen-Image-Edit-2509-Relight.safetensors",
                         "strength_model": a.lora_strength}},
        "6": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["5", 0], "shift": 3.1}},
        "7": {"class_type": "CFGNorm", "inputs": {"model": ["6", 0], "strength": 1.0}},
        "8": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["1", 0]}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["4", 0]}},
        "10": {"class_type": "TextEncodeQwenImageEditPlus",
               "inputs": {"clip": ["3", 0], "vae": ["4", 0], "image1": ["1", 0], "prompt": a.instruction}},
        "11": {"class_type": "TextEncodeQwenImageEditPlus",
               "inputs": {"clip": ["3", 0], "vae": ["4", 0], "image1": ["1", 0], "prompt": ""}},
        "12": {"class_type": "FluxKontextMultiReferenceLatentMethod",
               "inputs": {"conditioning": ["10", 0], "reference_latents_method": "index_timestep_zero"}},
        "13": {"class_type": "FluxKontextMultiReferenceLatentMethod",
               "inputs": {"conditioning": ["11", 0], "reference_latents_method": "index_timestep_zero"}},
        "14": {"class_type": "KSampler",
               "inputs": {"seed": a.seed, "steps": 40, "cfg": 3.0, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": 1.0, "model": ["7", 0],
                          "positive": ["12", 0], "negative": ["13", 0], "latent_image": ["9", 0]}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["4", 0]}},
        "16": {"class_type": "SaveImage", "inputs": {"filename_prefix": a.out, "images": ["15", 0]}},
    }


def cmd_run_qwen(a):
    pid, files = run_graph(a, graph_qwen(a), "run-qwen")
    print(f"  '{a.instruction[:60]}...' -> {[f['filename'] for f in files]}")
    return 0


def write_pose_json(path, triples, width: int, height: int):
    """Emit a keypoints file that is actually editable: one joint per line, named, flat-array shape.

    Plain `json.dumps` puts each of the 54 numbers on its own line, which defeats the purpose of a
    file whose only job is to be hand-edited (`%g` keeps it compact: 512, 133.12, 1). The result is
    re-parsed and compared against the joints it was built from, so this formatting can never drift.
    """
    body = ",\n".join("      [%s]" % ", ".join(f"{c:g}" for c in t) for t in triples)
    text = ('[\n {\n  "people": [\n   {\n    "pose_keypoints_2d": [\n' + body + "\n    ],\n"
            '    "joint_names": [' + ", ".join(f'"{n}"' for n in JOINT_NAMES) + "]\n"
            "   }\n  ],\n"
            f'  "canvas_width": {width},\n  "canvas_height": {height}\n }}\n]\n')
    pts, _ = pose_of(json.loads(text))
    if len(pts) != len(triples) or max(abs(p[i] - t[i]) for p, t in zip(pts, triples) for i in range(2)) > 0.01:
        raise SystemExit("write_pose_json: the formatted file does not round-trip - refusing to write")
    Path(path).write_text(text, encoding="utf-8")


def cmd_template(a):
    """Emit a keypoints JSON you can edit, so nobody has to hand-write 54 numbers."""
    arm = a.arm if a.arm is not None else PRESETS[a.preset]
    flat = build_figure(a.width, a.height, arm, a.rotate)
    triples = [flat[i:i + 3] for i in range(0, len(flat), 3)]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_pose_json(out, triples, a.width, a.height)
    print(f"  wrote {out}   preset={a.preset}  arm={arm:+g} deg  rotate={a.rotate:+g}  "
          f"canvas {a.width}x{a.height}")
    print("  18 joints in order (x, y, confidence each):")
    print("   0 nose   1 neck   2 Rsh  3 Rel  4 Rwr  5 Lsh  6 Lel  7 Lwr")
    print("   8 Rhp    9 Rkn   10 Ran  11 Lhp 12 Lkn 13 Lan  14 Rey 15 Ley 16 Rear 17 Lear")
    print("  ('R' is the SUBJECT's right = image LEFT, OpenPose convention)")
    print("  edit the numbers, then draw and use it:")
    print(f"    uv run python scripts/pose_probe.py draw {out} input/_pose/mypose.png")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="E21: pose change + adherence measurement.")
    ap.add_argument("--base", default="http://127.0.0.1:8188")
    ap.add_argument("--token", default="")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract")
    e.add_argument("image")
    e.add_argument("--prefix", default="2D/E21/pose")
    e.add_argument("--resolution", type=int, default=1024)
    e.set_defaults(fn=cmd_extract)

    d = sub.add_parser("draw")
    d.add_argument("keypoints")
    d.add_argument("out")
    d.add_argument("--transform", default="none")
    d.add_argument("--labels", action="store_true",
                   help="print each joint's index on the image (for hand-editing the JSON)")
    d.set_defaults(fn=cmd_draw)

    t = sub.add_parser("template", help="emit an editable keypoints JSON from a preset")
    t.add_argument("out")
    t.add_argument("--preset", choices=sorted(PRESETS), default="standing")
    t.add_argument("--arm", type=float, default=None,
                   help="arm angle in degrees from vertical (overrides the preset's)")
    t.add_argument("--rotate", type=float, default=0.0,
                   help="rotate the whole figure in-plane (a lean/tilt - NOT a camera yaw)")
    t.add_argument("--width", type=int, default=1024)
    t.add_argument("--height", type=int, default=1024)
    t.set_defaults(fn=cmd_template)

    r = sub.add_parser("run-cn")
    r.add_argument("skeleton")
    r.add_argument("--strength", type=float, default=0.9)
    r.add_argument("--cn-type", default="openpose")
    r.add_argument("--prompt", default=("full body game character concept art of a single heroic fantasy knight "
                                        "in ornate plate armor, standing with both arms outstretched to the sides, "
                                        "solo, arms and legs fully visible, plain light gray background, "
                                        "clean silhouette, highly detailed digital painting, neutral studio lighting"))
    r.add_argument("--negative", default="blurry, lowres, text, watermark, extra limbs, cropped, "
                                         "character sheet, multiple views, multiple figures, border, frame, "
                                         "deformed, arms at sides, hands on hips")
    r.add_argument("--ckpt", default=CKPT)
    r.add_argument("--seed", type=int, default=1101)
    r.add_argument("--cfg", type=float, default=7.0,
                   help="keep 7.0 for the shipped look; LOWER (4-5) gives the ControlNet relatively more say")
    r.add_argument("--steps", type=int, default=25)
    r.add_argument("--sampler", default="euler")
    r.add_argument("--cn-start", type=float, default=0.0)
    r.add_argument("--cn-end", type=float, default=1.0,
                   help="apply the CN only early (e.g. 0.5): pose set in the first steps, model free later")
    r.add_argument("--cn-file", default=UNION_CN,
                   help="any models/controlnet file; a NON-union file skips the union mode-selector node "
                        "(e.g. control_v11p_sd15_openpose_fp16.safetensors with --ckpt v1-5-pruned-emaonly.safetensors)")
    r.add_argument("--width", type=int, default=1024)
    r.add_argument("--height", type=int, default=1024)
    r.add_argument("--ipadapter", default=None,
                   help="design/identity image (in ComfyUI input/) - carries the CHARACTER via IPAdapter")
    r.add_argument("--ipadapter-weight", type=float, default=0.6)
    r.add_argument("--pulid", default=None, help="face image - PuLID arm (needs a visible face; no good on a helmet)")
    r.add_argument("--pulid-method", default="auto")
    r.add_argument("--pulid-weight", type=float, default=0.9)
    r.add_argument("--out", default="2D/E21/pose_cn")
    r.set_defaults(fn=cmd_run_cn)

    q = sub.add_parser("run-qwen")
    q.add_argument("image")
    q.add_argument("--instruction", required=True)
    q.add_argument("--lora-strength", type=float, default=0.0)
    q.add_argument("--seed", type=int, default=20001)
    q.add_argument("--out", default="2D/E21/pose_qwen")
    q.set_defaults(fn=cmd_run_qwen)

    m = sub.add_parser("measure")
    m.add_argument("image")
    m.add_argument("target")
    m.set_defaults(fn=cmd_measure)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
