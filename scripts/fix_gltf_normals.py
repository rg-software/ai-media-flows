#!/usr/bin/env python3
"""Add the vertex normals a GLB should have but Hy3D's texture stage drops.

WHY THIS IS NOT COSMETIC

Our PBR route produces **tangent-space** normal maps (measured: all four QFX/Marigold maps we had on the box
are centred on (127,127,255), the encoding of a flat surface's (0,0,1) in tangent space). A tangent-space
map is a *perturbation* of the mesh's own normals, and the TBN basis that applies it is built from the UVs
**and the vertex normals**. A mesh exported without a `NORMAL` attribute therefore cannot use the normal map
we generate for it: there is no basis to perturb.

We ship such meshes. `check_gltf_contract.py` reports `no NORMAL attribute` on **24 of 24** exports, because
the Hy3D texture stage reconstructs the mesh from positions + faces + UVs only
(`MeshRender.set_mesh(vtx_pos, pos_idx, vtx_uv, uv_idx)` takes no normals), so nothing upstream can carry
them through. `Hy3DPostprocessMesh.smooth_normals` runs too early - `Hy3DIMRemesh` and the xatlas UV-wrap
rebuild the mesh afterwards - and core's `MeshSmoothNormals` fails on our meshes
(`'MESH' object has no attribute 'vertex_colors'`).

What works, and is what this does: compute them on the final textured mesh and re-export. Verified on a real
export - the result keeps `TEXCOORD_0`, the material, and the embedded image, and gains `NORMAL`.

Usage:
    uv run python scripts/fix_gltf_normals.py FILE.glb [FILE.glb ...]
    uv run python scripts/fix_gltf_normals.py --dir DIR [--out-dir DIR2] [--dry-run]

In place by default (the file is rewritten); `--out-dir` writes copies instead. Run
`scripts/check_gltf_contract.py` afterwards to confirm.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys


def has_normals(path) -> bool:
    """True if any primitive already carries a NORMAL attribute."""
    import json
    import struct
    raw = open(path, "rb").read()
    if raw[:4] != b"glTF":
        return False
    total = struct.unpack("<I", raw[8:12])[0]
    off = 12
    while off < total:
        ln, ty = struct.unpack("<II", raw[off:off + 8])
        if ty == 0x4E4F534A:
            g = json.loads(raw[off + 8:off + 8 + ln].decode("utf-8"))
            return any("NORMAL" in (p.get("attributes") or {})
                       for m in (g.get("meshes") or []) for p in (m.get("primitives") or []))
        off += 8 + ln
    return False


def fix(path, out_path=None, dry_run=False):
    """Return (changed, message). Computes vertex normals and re-exports, preserving everything else."""
    import trimesh
    if not has_normals(path):
        pass                                   # still needs the work; this is the normal case
    else:
        return False, "already has NORMAL"
    try:
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:
        return False, "unreadable: %s" % exc
    if len(mesh.faces) == 0:
        return False, "no faces"
    before = {"uv": getattr(mesh.visual, "uv", None) is not None,
              "mat": getattr(mesh.visual, "material", None) is not None,
              "verts": len(mesh.vertices), "faces": len(mesh.faces)}
    if dry_run:
        return True, "would add NORMAL (uv=%s material=%s, %d verts)" % (
            before["uv"], before["mat"], before["verts"])
    mesh.vertex_normals = trimesh.smoothing.get_vertices_normals(mesh)
    dst = out_path or path
    mesh.export(dst, file_type="glb")
    # verify rather than assume
    ok = has_normals(dst)
    kept_uv = getattr(trimesh.load(dst, force="mesh").visual, "uv", None) is not None
    return ok, "NORMAL written (uv kept=%s, material kept=%s, %d faces) -> %s" % (
        kept_uv, before["mat"], before["faces"], os.path.basename(dst)) if ok else "FAILED to write NORMAL"


def main() -> int:
    ap = argparse.ArgumentParser(description="Add vertex normals to GLB(s) whose texture stage dropped them.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--out-dir", help="write fixed copies here instead of rewriting in place")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = list(args.files)
    if args.dir:
        targets += sorted(glob.glob(os.path.join(args.dir, "*.glb")))
    if not targets:
        ap.error("give at least one file, or --dir")

    changed = failed = 0
    for p in targets:
        out = None
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            out = os.path.join(args.out_dir, os.path.basename(p))
        ok, msg = fix(p, out, args.dry_run)
        if ok:
            changed += 1
        elif "FAILED" in msg or "unreadable" in msg:
            failed += 1
        print("  %-38s %s" % (os.path.basename(p), msg))
    print("\n%d file(s): %d changed, %d failed%s" % (len(targets), changed, failed,
                                                    " (dry run)" if args.dry_run else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
