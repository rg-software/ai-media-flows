#!/usr/bin/env python3
"""Sweep ANY shipped workflow: point it at a flow, name widgets to vary, get a sheet.

WHY THIS EXISTS

`scripts/sweep.py` builds its own txt2img graph (CheckpointLoaderSimple + a prompt) and can only vary
`KSampler` widgets with two axes. That covered E16, but every later sweep has needed more, and each time we
wrote a throwaway script instead:

  * `sweep_outpaint.py` - image-conditioned: the flow kept its own graph, so a *separate* harness appeared
    (its own docstring says so)
  * this session: SV3D turnaround variants, pose-control (cn_end/cfg/strength), pose granularity (arm angle)

All of those wanted the same three things `sweep.py` cannot do:
  1. sweep a graph that CONDITIONS ON AN IMAGE, not just a prompt
  2. vary a widget on ANY node, not only the KSampler
  3. produce a set of frames per arm (a sprite run renders N frames, not 1)

So this harness is generic in the useful sense: it loads a workflow file, overrides named widget values, and
runs each cell. Nothing about the graph is hardcoded.

USAGE

    # two axes, on the shipped pixel-art flow
    uv run python scripts/sweep_workflow.py 2d/workflows/pixel-art.json \
        --set "6.cfg:4,7,10" --set "6.steps:15,25" --out 2D/sweeps/pixel_cfg_steps

    # one axis over a *node's* widget, with an image supplied to LoadImage
    uv run python scripts/sweep_workflow.py 2d/workflows/pose-skeleton.json \
        --image 2d/char_knight.png --set "8.strength:0.9,1.2,1.5" --out 2D/sweeps/pose_strength

AXIS SYNTAX: `<node_id>.<widget_name>` or `<node_id>.<widget_index>`, values comma-separated.
Named widgets are resolved against the live `/object_info` schema, so a name that does not exist on that node
is a hard error rather than a silent no-op (the failure mode that makes hand-written sweeps untrustworthy).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CO = os.path.expanduser("~/Projects-Git/ComfyUI")


def _load_check_workflows():
    spec = importlib.util.spec_from_file_location("cw", os.path.join(REPO, "scripts", "check_workflows.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def api(base, token, path):
    url = base.rstrip("/") + path
    if token:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"token": token})
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def post(base, token, path, payload):
    url = base.rstrip("/") + path + ("?" + urllib.parse.urlencode({"token": token}) if token else "")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def parse_axis(spec):
    """'6.cfg:3,5' -> (node_id, widget_ref, ['3','5']). Values are coerced per the schema later."""
    if ":" not in spec or "." not in spec.split(":", 1)[0]:
        raise SystemExit("axis must look like <node_id>.<widget>:v1,v2  (got %r)" % spec)
    where, vals = spec.split(":", 1)
    node, ref = where.split(".", 1)
    return node.strip(), ref.strip(), [v.strip() for v in vals.split(",")]


def widget_names(info, class_type):
    """Widget names in declaration order (the order widgets_values uses)."""
    cw = _load_check_workflows()
    return [n for n, _d in cw.widget_slots(info[class_type]) if n]


def coerce(value, decl):
    """Turn a CLI string into the type the schema expects."""
    t = decl[0] if isinstance(decl, list) and decl else decl
    o = decl[1] if isinstance(decl, list) and len(decl) > 1 and isinstance(decl[1], dict) else {}
    if isinstance(t, list) or t == "COMBO":
        if value not in (o.get("options") or t if isinstance(t, list) else []):
            # runtime-populated combos have no options; accept and let the server judge
            pass
        return value
    if t == "INT":
        return int(value)
    if t == "FLOAT":
        return float(value)
    if t == "BOOLEAN":
        return value.lower() in ("1", "true", "yes", "on")
    return value


def build_prompt(workflow, info, overrides, image=None):
    """API prompt from a shipped UI workflow; `overrides` is {node_id: {widget_name_or_index: value}}."""
    cw = _load_check_workflows()
    nodes = {n["id"]: n for n in workflow["nodes"]}
    prompt = {}
    for nid, n in nodes.items():
        if n["type"] in ("Note", "MarkdownNote"):
            continue
        inputs = {}
        slots = cw.widget_slots(info[n["type"]])
        values = list(n.get("widgets_values") or [])
        ov = overrides.get(nid, {})
        for idx, ref in ov.items():
            if isinstance(ref, int):
                if idx < len(values):
                    values[idx] = ref
            else:                                     # by name -> find its slot index
                names = [nm for nm, _ in slots]
                if idx not in names:
                    raise SystemExit("node %s (%s) has no widget %r; it has %s"
                                     % (nid, n["type"], idx, names))
                values[names.index(idx)] = ref
        for i, v in enumerate(values):
            if i >= len(slots):
                break
            name, _decl = slots[i]
            if name is None:
                continue
            inputs[name] = v
        for l in workflow["links"]:
            if l[3] != nid:
                continue
            dst = n["inputs"][l[4]] if l[4] < len(n.get("inputs") or []) else None
            if dst:
                inputs[dst["name"]] = [str(l[1]), l[2]]
        # defaults the saved flow does not carry (the UI fills these silently; the API will not)
        for grp in ("required", "optional"):
            for name, decl in (info[n["type"]]["input"].get(grp) or {}).items():
                if name in inputs:
                    continue
                o = decl[1] if len(decl) > 1 and isinstance(decl[1], dict) else {}
                if "default" in o:
                    inputs[name] = o["default"]
                elif isinstance(decl[0], list) and decl[0]:
                    inputs[name] = decl[0][0]
        if image and n["type"] == "LoadImage":
            inputs["image"] = image
        prompt[str(nid)] = {"class_type": n["type"], "inputs": inputs}
    return prompt


def main() -> int:
    ap = argparse.ArgumentParser(description="Sweep any shipped workflow over named widgets.")
    ap.add_argument("workflow", help="e.g. 2d/workflows/pixel-art.json")
    ap.add_argument("--set", action="append", default=[], metavar="NODE.WIDGET:V1,V2",
                    help="repeatable; one axis each (1-2 axes make a grid)")
    ap.add_argument("--image", help="override every LoadImage with this file (in ComfyUI input/)")
    ap.add_argument("--out", required=True, help="output prefix (subfolder/name)")
    ap.add_argument("--base", default=os.environ.get("COMFY_BASE", "http://127.0.0.1:8188"))
    ap.add_argument("--token", default=os.environ.get("COMFY_TOKEN"))
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve the axes and print the grid, run nothing")
    args = ap.parse_args()

    if not args.token:
        pw = os.path.join(CO, "login", "PASSWORD")
        if os.path.isfile(pw):
            args.token = open(pw).readline().strip()

    path = args.workflow if os.path.isabs(args.workflow) else os.path.join(REPO, args.workflow)
    workflow = json.load(open(path, encoding="utf-8"))
    info = api(args.base, args.token, "/object_info")
    nodes = {n["id"]: n for n in workflow["nodes"]}

    axes = [parse_axis(s) for s in args.set]
    if not axes:
        ap.error("give at least one --set axis")
    if len(axes) > 2:
        ap.error("at most two axes (a grid)")

    # resolve every axis against the schema FIRST, so a typo fails before any run
    grid = []
    for node_s, ref, vals in axes:
        nid = int(node_s)
        cls = nodes[nid]["type"]
        decls = dict((nm, d) for nm, d in
                     [(nm, d) for nm, d in
                      list((info[cls]["input"].get("required") or {}).items()) +
                      list((info[cls]["input"].get("optional") or {}).items())])
        if not ref.isdigit() and ref not in decls:
            raise SystemExit("node %s (%s) has no widget %r" % (nid, cls, ref))
        decl = decls[ref] if not ref.isdigit() else None
        grid.append((nid, ref, [coerce(v, decl) if decl else v for v in vals]))
        print("  axis: node %s (%s).%s = %s" % (nid, cls, ref, grid[-1][2]))

    cells = []
    if len(grid) == 1:
        cells = [(i, [g]) for i, g in enumerate(
            [(grid[0][0], grid[0][1], v) for v in grid[0][2]])]
    else:
        for a_i, a_v in enumerate(grid[0][2]):
            for b_i, b_v in enumerate(grid[1][2]):
                cells.append((len(cells), [(grid[0][0], grid[0][1], a_v),
                                           (grid[1][0], grid[1][1], b_v)]))

    print("\nrunning %d cell(s) of %s" % (len(cells), os.path.basename(path)))
    if args.dry_run:
        print("\ndry run: %d cell(s) of %s" % (len(cells), os.path.basename(path)))
        for idx, assignment in cells:
            print("  cell %-3d %s" % (idx, ", ".join("%s.%s=%s" % tuple(str(x) for x in a) for a in assignment)))
        return 0
    manifest = []
    for idx, assignment in cells:
        overrides = {}
        for nid, ref, val in assignment:
            key = int(ref) if isinstance(ref, str) and ref.isdigit() else ref
            overrides.setdefault(nid, {})[key] = val
        prompt = build_prompt(workflow, info, overrides, args.image)
        # every SaveImage gets a unique prefix so cells cannot overwrite each other
        for nid, n in prompt.items():
            if n["class_type"] == "SaveImage":
                n["inputs"]["filename_prefix"] = "%s_c%02d" % (args.out, idx)
        t0 = time.time()
        resp = post(args.base, args.token, "/prompt", {"prompt": prompt})
        if "prompt_id" not in resp:
            print("  cell %d SUBMIT FAILED: %s" % (idx, json.dumps(resp)[:180]))
            manifest.append({"cell": idx, "assignment": assignment, "files": []})
            continue
        pid = resp["prompt_id"]
        files = []
        for _ in range(args.timeout // 5):
            time.sleep(5)
            h = api(args.base, args.token, "/history/" + pid)
            if pid in h:
                e = h[pid]
                st = e["status"]["status_str"]
                for m in e["status"].get("messages", []):
                    if m[0] == "execution_error":
                        print("  cell %d ERROR: %s @ %s" % (idx, m[1].get("exception_message", "")[:120],
                                                            m[1].get("node_type")))
                for o in (e.get("outputs") or {}).values():
                    for im in o.get("images", []):
                        files.append(im.get("filename"))
                print("  cell %-3d %5.1fs  %s  %s" % (
                    idx, time.time() - t0, st, ", ".join(str(a[2]) for a in assignment)))
                break
        manifest.append({"cell": idx, "assignment": assignment, "files": files})

    md = os.path.join(CO, "output", os.path.dirname(args.out),
                      os.path.basename(args.out) + "_manifest.json")
    os.makedirs(os.path.dirname(md), exist_ok=True)
    json.dump({"workflow": args.workflow, "axes": args.set, "cells": manifest}, open(md, "w"), indent=1)
    print("\nmanifest -> %s" % md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
