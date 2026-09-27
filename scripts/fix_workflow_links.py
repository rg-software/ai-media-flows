#!/usr/bin/env python3
"""Check (and repair) the internal link consistency of ComfyUI GUI workflow files.

A GUI workflow stores its graph TWICE:

  * the `links` array - one entry per connection: [id, origin_node, origin_slot, target_node,
    target_slot, type]
  * each node's own `inputs[].link` and `outputs[].links` fields

ComfyUI wires from the `links` array, so the node fields are *derived*. When the two disagree, the
consequences differ by case - and conflating them is how `2d/workflows/inpaint.json` shipped with a
broken SaveImage:

  1. **Stale reference** - the declaration points at a link whose TYPE is incompatible with the input
     (SaveImage.images <- a MASK). Pure corruption, from a hand-edit that shifted ids. Safe to
     re-derive from the array: `inpaint.json` had every id from 9 up one too low, so the array was
     right and the fields were wrong.
  2. **Declared-but-unrouted** - the declaration points at a link whose type MATCHES but which the
     array routes to another node. The array-alone reading would leave that input *unconnected* -
     and where the input is required, that state cannot run, so the declaration carries real intent
     (the author wired it; the array lost the edge). Repairing this means ADDING a link, which is
     reported explicitly.
  3. **Out-of-range slot** - the array names a slot the node does not have (a node lost an input
     after the link was made). If exactly one input claims that link with a matching type, the slot
     is corrected.

The `links` array is authoritative for *connections*; the node fields are authoritative for
*intent* when the array is incomplete. Usage:

    uv run python scripts/fix_workflow_links.py                # check every curated workflow
    uv run python scripts/fix_workflow_links.py --write        # repair, reporting every change
    uv run python scripts/fix_workflow_links.py --write 2d/workflows/inpaint.json

`workflows/scratch/` is deliberately excluded: it is archive, not maintained.

ONE CHECK IS NOT ABOUT CONSISTENCY AT ALL. A file can be perfectly self-consistent and still be
semantically wrong, so `check_data` also reports a **CONDITIONING output that nothing consumes**. A node
that modifies conditioning - attaching a reference frame, a pose, a control hint, a face embedding - does
its work through its *return value*, so leaving that value unconnected silently drops everything it
attached, and no type check can notice because CONDITIONING -> CONDITIONING is always valid. Two shipped
flows had exactly this: the Wan flow ignored both its reference image and its driving video
(`animation/EXPERIMENTS.md` E2), and `instantid-character.json` ran its negative pass without the ID
embedding. Both were internally consistent, so every other check passed.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iter_curated():
    """Every maintained workflow (scratch excluded). Scenario-generic: the wildcard cannot cross a path
    separator, so `*/workflows/scratch/*.json` stays out."""
    for p in sorted(glob.glob(os.path.join(REPO, "*", "workflows", "*.json"))):
        yield p


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path: str, d: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, indent=1, ensure_ascii=False)


def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    return [] if v in (None, []) else [v]


def _nodes(d: dict) -> dict:
    return {n["id"]: n for n in (d.get("nodes") or [])}


def _type_ok(declared, ltype) -> bool:
    """Can a link of type `ltype` land on a slot declared as `declared`?

    A slot may declare a UNION - `MHR_POSE_DATA,KIMODO_POSE_DATA`, `FILE_3D_GLB,FILE_3D_GLTF,...` - and a link
    carrying any one member is valid. Comparing the strings literally reports every union as a problem, which
    is what the SAM3D-Body workflow did on three perfectly good edges.
    """
    if declared == ltype:
        return True
    if isinstance(declared, str) and "," in declared:
        return ltype in [t.strip() for t in declared.split(",")]
    return False


def check_data(d: dict, rel: str) -> list[str]:
    """Inconsistencies between a workflow's node link references and its `links` array."""
    problems: list[str] = []
    links = d.get("links") or []
    ids = [l[0] for l in links]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"{rel}: duplicate link id(s) {dupes}")

    nodes = _nodes(d)
    want_input: dict[tuple[int, int], list] = {}
    want_output: dict[tuple[int, int], list] = {}

    for l in links:
        lid, onode, oslot, tnode, tslot, ltype = l
        origin, target = nodes.get(onode), nodes.get(tnode)
        if origin is None or target is None:
            problems.append(f"{rel}: link {lid} references a missing node ({onode} -> {tnode})")
            continue
        outs, ins = origin.get("outputs") or [], target.get("inputs") or []
        if oslot >= len(outs):
            problems.append(f"{rel}: link {lid} origin slot {oslot} does not exist on node {onode} "
                            f"({origin.get('type')})")
        elif not _type_ok(outs[oslot].get("type"), ltype):
            problems.append(f"{rel}: link {lid} type {ltype} != origin output type "
                            f"{outs[oslot].get('type')} on node {onode}")
        if tslot >= len(ins):
            problems.append(f"{rel}: link {lid} target slot {tslot} does not exist on node {tnode} "
                            f"({target.get('type')})")
        elif not _type_ok(ins[tslot].get("type"), ltype):
            problems.append(f"{rel}: link {lid} type {ltype} != target input type "
                            f"{ins[tslot].get('type')} on node {tnode}")
        if (tnode, tslot) in want_input:
            problems.append(f"{rel}: two links target node {tnode} input slot {tslot}")
        want_input.setdefault((tnode, tslot), []).append(l)
        want_output.setdefault((onode, oslot), []).append(lid)

    for nid, n in sorted(nodes.items()):
        for i, inp in enumerate(n.get("inputs") or []):
            want = want_input.get((nid, i))
            expected = want[0][0] if want else None
            if inp.get("link") == expected:
                continue
            if want is None:
                # declared but nothing in the array targets it: stale, or load-bearing intent?
                claim = next((l for l in links if l[0] == inp.get("link")), None)
                if claim is not None and _type_ok(inp.get("type"), claim[5]):
                    problems.append(f"{rel}: node {nid} ({n.get('type')}) input {inp.get('name')!r} "
                                    f"routed to link {claim[0]} by declaration, but the array sends it "
                                    f"to node {claim[3]} - the array alone leaves this input "
                                    f"unconnected (declared-but-unrouted)")
                else:
                    problems.append(f"{rel}: node {nid} ({n.get('type')}) input "
                                    f"{inp.get('name')!r} declares link {inp.get('link')} but nothing "
                                    f"targets it")
            else:
                problems.append(f"{rel}: node {nid} ({n.get('type')}) input {inp.get('name')!r} "
                                f"declares link {inp.get('link')}, expected {expected} "
                                f"(which carries {want[0][5]})")
        for j, out in enumerate(n.get("outputs") or []):
            want_ids = sorted(want_output.get((nid, j), []))
            if sorted(_as_list(out.get("links"))) != want_ids:
                problems.append(f"{rel}: node {nid} ({n.get('type')}) output {out.get('name')!r} "
                                f"lists links {out.get('links')}, expected {want_ids}")
            # A CONDITIONING output that nothing consumes is almost never a style choice. A node that MODIFIES
            # conditioning - attaching a reference image, a pose, a control hint - does its work through its
            # return value, so leaving that value unconnected silently drops everything it attached while every
            # type check still passes: CONDITIONING -> CONDITIONING is always valid. That is exactly how the
            # Wan flow came to ignore both its reference image and its driving video (animation/EXPERIMENTS.md
            # E2), and the file was internally consistent throughout, so nothing else could have caught it.
            if out.get("type") == "CONDITIONING" and not want_ids:
                problems.append(
                    f"{rel}: node {nid} ({n.get('type')}) output {out.get('name')!r} is CONDITIONING and "
                    f"nothing consumes it - if this node modifies conditioning, whatever it attached is "
                    f"dropped (a sampler usually wants it)")
    return problems


def normalise_slots(d: dict) -> list[str]:
    """Correct link slots that name a slot the node does not have (case 3)."""
    fixes: list[str] = []
    nodes = _nodes(d)
    for l in (d.get("links") or []):
        lid, onode, oslot, tnode, tslot, ltype = l[0], l[1], l[2], l[3], l[4], l[5]
        origin, target = nodes.get(onode), nodes.get(tnode)
        if origin is None or target is None:
            continue
        outs, ins = origin.get("outputs") or [], target.get("inputs") or []
        if not (oslot < len(outs) and outs[oslot].get("type") == ltype):
            claims = [j for j, o in enumerate(outs)
                      if o.get("type") == ltype and lid in _as_list(o.get("links"))]
            if len(claims) == 1:
                fixes.append(f"link {lid}: origin_slot {oslot} -> {claims[0]}")
                l[2] = claims[0]
        if not (tslot < len(ins) and ins[tslot].get("type") == ltype):
            claims = [i for i, inp in enumerate(ins)
                      if inp.get("type") == ltype and inp.get("link") == lid]
            if len(claims) == 1:
                fixes.append(f"link {lid}: target_slot {tslot} -> {claims[0]}")
                l[4] = claims[0]
    return fixes


def realise_unrouted(d: dict) -> list[str]:
    """Turn declared-but-unrouted inputs into real links (case 2), reporting each added edge."""
    added: list[str] = []
    nodes = _nodes(d)
    links = d.get("links") or []
    routed = {(l[3], l[4]) for l in links}
    next_id = max([l[0] for l in links] + [d.get("last_link_id", 0)]) + 1
    for nid in sorted(nodes):
        n = nodes[nid]
        for i, inp in enumerate(n.get("inputs") or []):
            if (nid, i) in routed or inp.get("link") is None:
                continue
            src = next((l for l in links if l[0] == inp.get("link")), None)
            if src is None or src[5] != inp.get("type"):
                continue
            new = [next_id, src[1], src[2], nid, i, src[5]]
            links.append(new)
            routed.add((nid, i))
            added.append(f"added link {next_id}: node {src[1]}.{src[2]} -> node {nid} "
                         f"({n.get('type')}).{inp.get('name')} [{src[5]}]")
            next_id += 1
    d["links"] = links
    d["last_link_id"] = next_id - 1
    return added


def derive_fields(d: dict) -> int:
    """Rewrite every node's link references from the (now complete) `links` array."""
    want_input: dict[tuple[int, int], int] = {}
    want_output: dict[tuple[int, int], list] = {}
    for l in (d.get("links") or []):
        want_input[(l[3], l[4])] = l[0]
        want_output.setdefault((l[1], l[2]), []).append(l[0])

    changed = 0
    for n in (d.get("nodes") or []):
        nid = n["id"]
        for i, inp in enumerate(n.get("inputs") or []):
            want = want_input.get((nid, i))
            if inp.get("link") != want:
                inp["link"] = want
                changed += 1
        for j, out in enumerate(n.get("outputs") or []):
            want = sorted(want_output.get((nid, j), []))
            if sorted(_as_list(out.get("links"))) != want:
                out["links"] = want
                changed += 1
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Check/repair ComfyUI workflow link consistency.")
    ap.add_argument("--write", action="store_true", help="apply the repair (default: report only)")
    ap.add_argument("files", nargs="*", help="specific workflow file(s); default: all curated")
    a = ap.parse_args()

    paths = [f if os.path.isabs(f) else os.path.join(REPO, f) for f in a.files] or list(iter_curated())
    remaining = 0
    for p in paths:
        rel = os.path.relpath(p, REPO).replace(os.sep, "/")
        d = load(p)
        problems = check_data(d, rel)
        if not problems:
            print(f"  ok   {rel}")
            continue
        print(f"  FAIL {rel} ({len(problems)} problem(s))")
        for x in problems:
            print("        " + x)
        if not a.write:
            remaining += len(problems)
            continue

        ids_before = sorted(l[0] for l in (d.get("links") or []))
        for f in normalise_slots(d):
            print("        FIX  " + f)
        for f in realise_unrouted(d):
            print("        ADD  " + f)
        changed = derive_fields(d)
        ids_after = sorted(l[0] for l in (d.get("links") or []))
        if not set(ids_before) <= set(ids_after):
            print("        REFUSING to write: an existing link id disappeared")
            remaining += len(problems)
            continue
        left = check_data(d, rel)
        if left:
            print(f"        REFUSING to write: {len(left)} problem(s) remain")
            for x in left:
                print("          " + x)
            remaining += len(left)
            continue
        print(f"        rewrote {changed} link reference(s); "
              f"link ids {len(ids_before)} -> {len(d['links'])}")
        save(p, d)

    if remaining == 0:
        print("\nall workflows consistent" if a.write else "\nnothing to do")
    else:
        print(f"\n{remaining} problem(s)")
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(main())
