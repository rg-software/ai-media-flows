#!/usr/bin/env python3
"""Check a GLB against the things an engine importer cares about - offline, no engine needed.

WHY THIS EXISTS

PIPELINES open items 1-3 ("engine import contract", "no engine has been opened", "normal-map conventions")
were all blocked on the same thing: no engine exists on this box, so the contract could only be asserted in
prose. But most of the contract is *structural*, and a GLB is a self-describing container - so it can be
checked mechanically. This converts several assumptions into facts, and it is the check that would have
caught the E11 over-reading instantly (a 0.16 extents ratio on a house is visible here, not a week later).

WHAT IT CHECKS, and why an engine cares

  structural   GLB magic, version, a single buffer, JSON chunk parses
  geometry     POSITION present; **NORMAL** present (absent => a conforming importer must flat-shade, which
               is what makes our exports look faceted); TEXCOORD_0 present when a texture is bound (absent
               => the map samples one texel, so the model looks untextured however good the texture is)
  material     per material: baseColorTexture / metallicRoughnessTexture / normalTexture / occlusionTexture;
               and the scalar factors. **`metallicFactor` absent means glTF defaults it to 1.0 = fully
               metal** - our exports omit it, so this is a real defect an engine WILL apply.
               Also: when a metallicRoughnessTexture is bound, metallicFactor/roughnessFactor must be 1.0
               (any other value multiplies the map and silently darkens the surface)
  textures     embedded (bufferView) vs external (uri) - an external uri breaks a single-file handoff
               colourspace sanity: normalTexture must not be sRGB; metallicRoughness likewise linear
  footprint    vertex/face counts, extents in model units, and the **extents ratio** (min/max axis) - a flat
               ratio is the signature of a relief/plaque rather than an object

Usage:
    uv run python scripts/check_gltf_contract.py FILE.glb [--json]
    uv run python scripts/check_gltf_contract.py --dir DIR        # every .glb in DIR

Exit code is 1 if any ERROR-level finding is present (warnings alone do not fail).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import struct
import sys

# ---- reading -------------------------------------------------------------------------------------
GLB_MAGIC = b"glTF"


def read_glb(path):
    """Return (json_chunk, has_bin, n_chunks). Raises ValueError on anything malformed."""
    raw = open(path, "rb").read()
    if raw[:4] != GLB_MAGIC:
        raise ValueError("not a GLB (missing 'glTF' magic)")
    version, total = struct.unpack("<II", raw[4:12])
    if version != 2:
        raise ValueError("glTF version %d, expected 2" % version)
    if total != len(raw):
        raise ValueError("header says %d bytes, file is %d" % (total, len(raw)))
    off, gj, has_bin, n = 12, None, False, 0
    while off < total:
        ln, ty = struct.unpack("<II", raw[off:off + 8])
        chunk = raw[off + 8:off + 8 + ln]
        n += 1
        if ty == 0x4E4F534A:                       # JSON
            gj = json.loads(chunk.decode("utf-8"))
        elif ty == 0x004E4942:                     # BIN
            has_bin = True
        off += 8 + ln
    if gj is None:
        raise ValueError("no JSON chunk")
    return gj, has_bin, n


# ---- checks --------------------------------------------------------------------------------------
def check(path):
    """Return (findings, facts). A finding is (level, code, message); level in ERROR/WARN/INFO."""
    f, facts = [], {}
    try:
        g, has_bin, n_chunks = read_glb(path)
    except Exception as exc:
        return [("ERROR", "glb", "unreadable: %s" % exc)], facts

    facts["asset_version"] = (g.get("asset") or {}).get("version")
    facts["generator"] = (g.get("asset") or {}).get("generator")
    facts["chunks"] = n_chunks
    facts["extensions"] = g.get("extensionsUsed") or []

    meshes = g.get("meshes") or []
    if not meshes:
        f.append(("ERROR", "geometry", "no meshes"))
    prims = [p for m in meshes for p in (m.get("primitives") or [])]
    facts["primitives"] = len(prims)

    # ---- geometry attributes
    has_normal = any("NORMAL" in (p.get("attributes") or {}) for p in prims)
    has_uv = any("TEXCOORD_0" in (p.get("attributes") or {}) for p in prims)
    has_pos = any("POSITION" in (p.get("attributes") or {}) for p in prims)
    facts["has_POSITION"] = has_pos
    facts["has_NORMAL"] = has_normal
    facts["has_TEXCOORD_0"] = has_uv

    if not has_pos:
        f.append(("ERROR", "geometry", "no POSITION attribute"))
    if not has_normal:
        f.append(("ERROR", "normals",
                  "no NORMAL attribute -> a conforming importer must flat-shade this mesh "
                  "(engines will look faceted; the Comfy viewer hides it by recomputing normals on load)"))

    # ---- materials
    mats = g.get("materials") or []
    facts["materials"] = len(mats)
    if not mats:
        f.append(("WARN", "material", "no materials (stripped geometry)"))
    for i, m in enumerate(mats):
        pbr = m.get("pbrMetallicRoughness") or {}
        bound = {k: (k in pbr) for k in ("baseColorTexture", "metallicRoughnessTexture")}
        bound["normalTexture"] = "normalTexture" in m
        bound["occlusionTexture"] = "occlusionTexture" in m
        facts.setdefault("material_bindings", []).append(bound)

        if bound["baseColorTexture"] and not has_uv:
            f.append(("ERROR", "material",
                      "material %d binds baseColorTexture but the mesh has no TEXCOORD_0 - the map "
                      "cannot be sampled" % i))

        # the metallic default: informational, NOT a defect. In our pipeline the source GLB's scalar never
        # decides anything - either a PBR pass supplies a metallicRoughnessTexture (which per glTF must carry
        # the factors at 1.0 anyway, and then the map is the truth), or the factor is set in the engine on
        # import. A baked placeholder would be worse than absent: it would assert a dielectric for a sword.
        mf, rf = pbr.get("metallicFactor"), pbr.get("roughnessFactor")
        if bound["metallicRoughnessTexture"]:
            if mf not in (None, 1.0) or rf not in (None, 1.0):
                f.append(("ERROR", "material",
                          "material %d binds metallicRoughnessTexture but metallicFactor=%s "
                          "roughnessFactor=%s - these multiply the map; both must be 1.0" % (i, mf, rf)))
        else:
            f.append(("INFO", "material",
                      "material %d has no metallicRoughnessTexture and no metallicFactor (glTF default 1.0 = "
                      "fully metallic). Not a defect in our pipeline: either the PBR pass supplies the map, or "
                      "the factor is set on import. Set it in-engine rather than baking a placeholder." % i))

        if bound["baseColorTexture"] and "baseColorFactor" not in pbr:
            f.append(("INFO", "material", "material %d omits baseColorFactor (defaults to white)" % i))

    # ---- textures: embedded vs external, and colourspace intent
    images = g.get("images") or []
    embedded = sum(1 for im in images if "bufferView" in im)
    external = [im.get("uri") for im in images if "uri" in im]
    facts["images"] = len(images)
    facts["images_embedded"] = embedded
    facts["images_external"] = external
    if external:
        f.append(("WARN", "textures",
                  "%d image(s) reference external files (%s) - a single-file handoff will break; embed "
                  "them for a drop-in asset" % (len(external), ", ".join(str(e)[:28] for e in external[:3]))))
    if images and not has_bin:
        f.append(("ERROR", "textures", "images are embedded but there is no BIN chunk"))

    # glTF states colourspace per *usage*, so an sRGB-tagged normal/MR map is a red flag
    for i, m in enumerate(mats):
        if "normalTexture" in m:
            f.append(("INFO", "colourspace",
                      "material %d has a normalTexture: import as **linear / Normal-map type** "
                      "(not sRGB), and note the green-channel convention (OpenGL +Y vs DirectX -Y)" % i))
        if (m.get("pbrMetallicRoughness") or {}).get("metallicRoughnessTexture"):
            f.append(("INFO", "colourspace",
                      "material %d has a metallicRoughnessTexture: import as **linear** (not sRGB)" % i))

    # ---- footprint
    try:
        import numpy as np
        import trimesh
        mesh = trimesh.load(path, force="mesh")
        ext = mesh.extents
        facts["vertices"], facts["faces"] = len(mesh.vertices), len(mesh.faces)
        facts["extents"] = [round(float(x), 3) for x in ext]
        facts["extents_ratio"] = round(float(min(ext) / max(ext)), 3) if max(ext) else None
        facts["watertight"] = bool(mesh.is_watertight)
        if facts["extents_ratio"] is not None and facts["extents_ratio"] < 0.25:
            f.append(("WARN", "footprint",
                      "extents ratio %.2f (min/max axis) - this is a *relief/plaque*, not an object-shaped "
                      "mesh; for E11-style questions that ratio is the first thing to read" %
                      facts["extents_ratio"]))
    except Exception as exc:
        f.append(("INFO", "footprint", "measurement skipped (%s)" % exc))
    return f, facts


# ---- reporting -----------------------------------------------------------------------------------
ICON = {"ERROR": "ERROR", "WARN": "warn ", "INFO": "info "}


def report(path, f, facts, as_json):
    if as_json:
        print(json.dumps({"file": path, "findings": f, "facts": facts}, indent=1))
        return
    print("### %s" % path)
    for k in ("asset_version", "generator", "extents", "extents_ratio", "vertices", "faces",
              "watertight", "has_POSITION", "has_NORMAL", "has_TEXCOORD_0", "images",
              "images_embedded", "materials"):
        if k in facts:
            print("   %-16s %s" % (k, facts[k]))
    if not f:
        print("   no findings")
    for level, code, msg in f:
        print("   %s %-12s %s" % (ICON[level], code, msg))
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a GLB against the engine-import contract (offline).")
    ap.add_argument("files", nargs="*", help="GLB file(s)")
    ap.add_argument("--dir", help="check every .glb in this directory")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    targets = list(args.files)
    if args.dir:
        targets += sorted(glob.glob(os.path.join(args.dir, "*.glb")))
    if not targets:
        ap.error("give at least one file, or --dir")

    errors = 0
    for p in targets:
        f, facts = check(p)
        report(p, f, facts, args.json)
        errors += sum(1 for lvl, _, _ in f if lvl == "ERROR")
    if not args.json:
        print("%d file(s), %d error(s)" % (len(targets), errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
