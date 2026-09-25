#!/usr/bin/env python3
"""Validate every shipped workflow's stored widget values against the live ComfyUI schema.

Why this exists: a UI workflow stores a node's settings as a positional `widgets_values` array. If that
array is out of step with the node's widget list, values land in the WRONG fields, and the failure appears
at run time as nonsense that looks nothing like a file problem:

    [ERROR] * SeedVR2VideoUpscaler 4:
    [ERROR]   - Value 0 smaller than min of 16: resolution
    [ERROR]   - Value not in list: color_correction: 0 not in ['lab', 'wavelet', ...]
    [ERROR]   - Failed to convert an input value to a FLOAT value: latent_noise_scale, cpu

`upscale-seedvr2.json` shipped exactly that: the frontend inserts a `control_after_generate` string after a
`seed` widget (the pack's own example workflow has 13 values for that node; ours had 12), so every value
after `seed` shifted one place left and `resolution` received `max_resolution`'s 0.

So this checks each stored value against the schema slot it actually lands in - combo membership, numeric
range, boolean-ness - and reports only real contradictions. Trailing values that are simply absent (a node
that grew a widget) are not reported: they fall back to defaults and do not shift anything.

Run on the box (needs the server's /object_info; the schema can't be checked offline):
    uv run python scripts/check_workflows.py [--base URL] [--token TOKEN]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import urllib.parse
import urllib.request

# A widget is a scalar the UI edits inline; anything else is a socket wired between nodes.
WIDGET_TYPES = ("INT", "FLOAT", "STRING", "BOOLEAN")
# ComfyUI's v3 dynamic combos are widgets too: they hold a string and the UI writes them into
# widgets_values exactly like a classic combo. Missing this made `SaveVideo.format` invisible to both the
# validator and `sweep_workflow`'s prompt builder, which then dropped the value and the run died with
# `SaveVideo.execute() missing 1 required positional argument: 'format'`.
DYNAMIC_WIDGET_TYPES = ("COMFY_DYNAMICCOMBO_V3",)
COMFY_INPUT = os.path.expanduser("~/Projects-Git/ComfyUI/input")
CONTROL_AFTER_GENERATE = ("fixed", "randomize", "increment", "decrement")


def find_repo():
    """The repo root, whether this runs from scripts/ or from a copy elsewhere (e.g. /tmp on the box)."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.environ.get("REPO"), here, os.getcwd()):
        if cand and os.path.isdir(os.path.join(cand, "2d", "workflows")):
            return os.path.abspath(cand)
    raise SystemExit("could not locate the repo (no 2d/workflows in $REPO, script dir or cwd)")


def api(base, token, path):
    url = base.rstrip("/") + path
    if token:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"token": token})
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def choices_of(decl):
    """The allowed values of a combo, whichever way this ComfyUI version serialises them.

    Older builds inline the list (`[["a","b"], {...}]`); this one also uses `["COMBO", {"options": [...]}]`,
    and some combos are populated at runtime with no options at all (a model that auto-downloads) - then
    there is nothing to validate against.
    """
    t = decl[0] if isinstance(decl, list) and decl else decl
    if isinstance(t, list):
        return t
    if t == "COMBO" and len(decl) > 1 and isinstance(decl[1], dict):
        return decl[1].get("options")
    return None


def is_widget(decl):
    t = decl[0] if isinstance(decl, list) and decl else decl
    if isinstance(t, list) or t == "COMBO" or t in WIDGET_TYPES or t in DYNAMIC_WIDGET_TYPES:
        return True
    # "socketless" inputs are frontend widgets that are not wired between nodes (ImageCompare's
    # compare_view is one) - they still occupy a slot in the stored value list.
    return (isinstance(decl, list) and len(decl) > 1 and isinstance(decl[1], dict)
            and decl[1].get("socketless") is True)


def widget_slots(spec):
    """[(name, decl)] for each widget in declaration order, with a None slot for control_after_generate.

    An INT named `seed` gets a following control slot, which stores a string like 'fixed' - the UI writes
    it and the schema has no field for it, so it must be skipped when mapping values to slots.
    """
    slots = []
    inp = spec.get("input", {})
    for group in ("required", "optional"):
        for name, decl in (inp.get(group) or {}).items():
            if is_widget(decl):
                slots.append((name, decl))
                if name == "seed":
                    slots.append((None, None))
    return slots


def violation(name, decl, value):
    """Why `value` is not acceptable for widget `name`, or None if it is."""
    t = decl[0] if isinstance(decl, list) and decl else decl
    opts = decl[1] if isinstance(decl, list) and len(decl) > 1 and isinstance(decl[1], dict) else {}

    if isinstance(t, list) or t == "COMBO":                     # combo
        allowed = choices_of(decl)
        if allowed is None:
            return None                                        # runtime-populated: nothing to check
        if value in allowed:
            return None
        # File-like combos (LoadImage and friends): object_info caps the list, and a value may name a
        # subfolder entry that the truncated list does not show. What matters is that the file is where the
        # node will look for it - so accept an existing file, and say so when it is missing.
        if isinstance(value, str):
            if os.path.basename(value) in allowed:
                return None
            candidate = os.path.join(COMFY_INPUT, value.replace("\\", "/"))
            if os.path.exists(candidate):
                return None
            return (f"value {value!r} not among {list(allowed)[:4]}... and no such file under input/ "
                    f"({candidate})")
        return f"value {value!r} not among {list(allowed)[:6]}{'...' if len(allowed) > 6 else ''}"
    if t == "INT":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"expected an integer, found {value!r}"
        lo, hi = opts.get("min"), opts.get("max")
        if lo is not None and value < lo:
            return f"value {value} below min {lo}"
        if hi is not None and value > hi:
            return f"value {value} above max {hi}"
        return None
    if t == "FLOAT":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"expected a number, found {value!r}"
        lo, hi = opts.get("min"), opts.get("max")
        if lo is not None and value < lo:
            return f"value {value} below min {lo}"
        if hi is not None and value > hi:
            return f"value {value} above max {hi}"
        return None
    if t == "BOOLEAN":
        if not isinstance(value, bool):
            return f"expected true/false, found {value!r}"
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Check workflow widget values against the live schema.")
    ap.add_argument("--base", default=os.environ.get("COMFY_BASE", "http://127.0.0.1:8188"))
    ap.add_argument("--token", default=os.environ.get("COMFY_TOKEN"))
    ap.add_argument("--comfy", default=os.environ.get("COMFY_ROOT", os.path.expanduser("~/Projects-Git/ComfyUI")),
                    help="ComfyUI root, to confirm file-like values exist under input/")
    args = ap.parse_args()
    repo = find_repo()
    if not args.token:
        pw = os.path.expanduser("~/Projects-Git/ComfyUI/login/PASSWORD")
        if os.path.exists(pw):
            args.token = open(pw).readline().strip()

    global COMFY_INPUT
    COMFY_INPUT = os.path.join(args.comfy, "input")
    info = api(args.base, args.token, "/object_info")
    print(f"schema: {len(info)} node types")

    files = sorted(glob.glob(os.path.join(repo, "*", "workflows", "*.json")))
    problems = 0
    for path in files:
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        w = json.load(open(path, encoding="utf-8"))
        for n in w.get("nodes", []):
            t = n.get("type")
            if t in ("MarkdownNote", "Note"):
                continue
            spec = info.get(t)
            if spec is None:
                print(f"  {rel}: node {n.get('id')} {t}: NOT REGISTERED on this server")
                problems += 1
                continue
            slots = widget_slots(spec)
            values = n.get("widgets_values") or []
            # An EMPTY widgets_values is worth flagging when - and only when - a setting would be genuinely
            # UNSPECIFIED. The UI always writes the values, so an empty array means the file was generated
            # or hand-edited without them, and the loop below has nothing to contradict: a workflow with no
            # model names, no prompt and no size passes every other gate (build_workflow.py's spec-key typo
            # produced exactly that across 25 nodes). But an empty array is *not* by itself a defect, which
            # is the stance the docstring already takes for trailing values - so a widget is exempt when it
            # is well-defined without a stored value:
            #   * it is *wired* (converting an input to a link removes its widget - TrimVideoLatent.trim_amount
            #     is normally fed by a link and must not be flagged);
            #   * it declares an explicit schema `default` (DepthAnythingV2Preprocessor.ckpt_name is exactly
            #     its default, so its empty array changes nothing);
            #   * it is a socketless display toggle (ImageCompare.compare_view - not a result-affecting setting).
            # What remains is a combo with no default at all (UnetLoaderGGUF.unet_name and friends), where
            # there is no way to know which entry was meant.
            wired = {i.get("name") for i in (n.get("inputs") or []) if i.get("link") is not None}

            def _opts(d):
                return d[1] if isinstance(d, list) and len(d) > 1 and isinstance(d[1], dict) else {}

            unspecified = [s for s, d in slots
                           if s and s not in wired
                           and not _opts(d).get("socketless")
                           and "default" not in _opts(d)]
            if unspecified and not values:
                problems += 1
                print(f"  {rel}: node {n.get('id')} {t}: widgets_values is EMPTY and these widgets have no "
                      f"schema default, so nothing says what they are ({', '.join(unspecified)[:70]})")
                continue
            bad = []
            for i, v in enumerate(values):
                if i >= len(slots):
                    break                      # extra trailing value (e.g. LoadImage's upload) - harmless
                name, decl = slots[i]
                if name is None:
                    continue                   # control_after_generate slot
                why = violation(name, decl, v)
                if why:
                    bad.append(f"{name}: {why}")
            if bad:
                problems += len(bad)
                print(f"  {rel}: node {n.get('id')} {t}")
                for b in bad:
                    print(f"      {b}")
    print(f"\n{len(files)} workflow file(s), {problems} value(s) that contradict the schema")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
