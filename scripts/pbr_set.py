#!/usr/bin/env python3
"""One command for a complete, licence-clean PBR material from a single texture.

Texture -> packed glTF material, using two models because neither is complete alone:

  Marigold IID (OpenRAIL++)  albedo, roughness, metallic   <- metallic is plausible
  QFX PBR (Apache-2.0)       normal, AO, displacement      <- metallic is inverted

Why the split (measured, E12b/U4/U7b): QFX's metallic is not merely inverted - its own
`metallic_min/max` knobs do invert it linearly (0.855 -> 0.145), but the distribution stays
wrong (14.6% of pixels >0.5, vs Marigold's 0.02% on the same stone). So QFX contributes no
metallic, and Marigold contributes no normal/AO.

"Plausible" is not "ground truth": Marigold's metallic is an estimate too. On our stone test it
sits at a flat ~0.36 everywhere (p5 0.31, p95 0.42) where a dielectric should be ~0, so an engine
can show a faint metallic sheen. The packing is right; the value may want a remap or a
per-material override. Deferred: a proper look at the metallic channel on real dielectrics.

Steps run by this script:
  1. upload the texture into ComfyUI's input/        (POST /upload/image)
  2. Marigold IID -> albedo / roughness / metallic   (scripts/marigold_pbr.py, needs the ComfyUI venv)
  3. QFX -> normal / AO / displacement               (the pbr-from-texture graph, over the HTTP API)
  4. pack a glTF 2.0 material                        (scripts/make_gltf_material.py)

Usage (on the box, from the repo root):
    uv run python scripts/pbr_set.py input/2d/tex_stone_seamless.png --outdir output/2D/pbr_set
    uv run python scripts/pbr_set.py tex.png --mesh assets/3d/stone_statue.glb --glb-out /tmp/out.glb

Token/URL resolve exactly as in scripts/comfy_io.py (--token/COMFY_TOKEN, else the box's
login/PASSWORD first line; --base/COMFY_BASE, else localhost).

CAVEAT, still open: QFX defaults to `normal_invert_y=True` while glTF expects OpenGL (+Y up).
A flat sheet cannot show a Y-convention error - it looks "engraved" instead of "raised" only in
a lit renderer. Verify on a mesh; `--no-invert-normal-y` flips it if the relief is inverted.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy_io  # noqa: E402  (shares the upload/view/token helpers; no third-party deps)

HERE = Path(__file__).resolve().parent
DEFAULT_MARIGOLD_PYTHON = Path.home() / "Projects-Git" / "ComfyUI" / "venv" / "bin" / "python"

# QFXPBRGenerator output slots (from /object_info): BaseColor, Normal, Roughness,
# Displacement, AO, Metallic, ORM
QFX_OUT = {"normal": 1, "displacement": 3, "ao": 4}


def run(cmd: "list[str | Path]", label: str, cwd: "str | Path | None" = None) -> None:
    print(f"  $ {' '.join(str(c) for c in cmd)}" + (f"   (cwd={cwd})" if cwd else ""))
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        raise SystemExit(f"{label} failed (exit {r.returncode})")


def upload(base: str, token: str | None, path: Path, subfolder: str, timeout: float) -> str:
    """Put the texture in ComfyUI's input/ and return the name LoadImage should use."""
    body, ctype = comfy_io._multipart({"type": "input", "overwrite": "true", "subfolder": subfolder},
                                      "image", path.name, path.read_bytes())
    resp = json.loads(comfy_io._post_multipart(comfy_io._url(base, "/upload/image", token), body,
                                               ctype, timeout))
    name = (f"{resp.get('subfolder', '')}/{resp['name']}").lstrip("/")
    print(f"  uploaded -> input/{name}")
    return name


def submit_qfx(base: str, token: str | None, image_name: str, texture_name: str,
               invert_y: bool, strength: float, timeout: float) -> dict:
    prompt = {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "QFXPBRGenerator", "inputs": {
            "image": ["1", 0], "texture_name": texture_name, "seamless_mode": "seamless",
            "normal_strength": strength, "normal_invert_y": invert_y,
            "roughness_min": 0.0, "roughness_max": 1.0,
            "metallic_min": 0.0, "metallic_max": 1.0, "metallic_threshold": 0.15,
            "ao_blur": 2, "ao_strength": 1.0, "save_textures": True}},
    }
    for i, (kind, slot) in enumerate(QFX_OUT.items(), start=10):
        prompt[str(i)] = {"class_type": "SaveImage",
                          "inputs": {"images": ["2", slot], "filename_prefix": f"pbrset/{texture_name}_{kind}"}}
    data = json.dumps({"prompt": prompt, "client_id": "pbr_set"}).encode()
    req = urllib.request.Request(comfy_io._url(base, "/prompt", token), data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        pid = json.load(urllib.request.urlopen(req, timeout=timeout))["prompt_id"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"QFX submit failed: HTTP {e.code} - {e.read()[:300]!r}") from None
    print(f"  queued QFX as {pid}; waiting")
    return wait_for(base, token, pid, timeout)


def wait_for(base: str, token: str | None, pid: str, timeout: float) -> dict:
    deadline = time.time() + max(timeout, 600)
    while time.time() < deadline:
        time.sleep(3)
        hist = json.loads(comfy_io._get(comfy_io._url(base, "/history", token, prompt_id=pid), timeout))
        if pid in hist:
            entry = hist[pid]
            status = (entry.get("status") or {}).get("status_str", "?")
            if status not in ("success", "error"):
                time.sleep(3)
                continue
            if status == "error":
                raise SystemExit("QFX run errored - check the journal (see comfyui/README.md)")
            return entry
    raise SystemExit("timed out waiting for the QFX run")


def fetch_qfx(base: str, token: str | None, entry: dict, outdir: Path, timeout: float) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    wanted = {v: k for k, v in QFX_OUT.items()}
    got = 0
    for node, node_out in (entry.get("outputs") or {}).items():
        for name, items in node_out.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict) or "filename" not in it:
                    continue
                # only the three savers we created
                fname = it["filename"]
                for kind in QFX_OUT:
                    if f"_{kind}" in fname:
                        data = comfy_io._get(comfy_io._url(
                            base, "/view", token, filename=fname,
                            subfolder=it.get("subfolder") or None, type=it.get("type", "output")), timeout)
                        (outdir / f"{kind}.png").write_bytes(data)
                        print(f"  qfx/{kind}.png  ({len(data):,} B)")
                        got += 1
    if got < 3:
        raise SystemExit(f"expected 3 QFX maps, fetched {got}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Texture -> complete glTF PBR material (Marigold + QFX).")
    ap.add_argument("texture", help="source texture (seamless albedo)")
    ap.add_argument("--outdir", default=None,
                    help="output dir; gets marigold/, qfx/, material/ (default: "
                         "<ComfyUI>/output/2D/pbr_set/<texture>, which stays fetchable over HTTP)")
    ap.add_argument("--base", help="ComfyUI URL (default localhost or COMFY_BASE)")
    ap.add_argument("--token", help="API token (default COMFY_TOKEN or the box's login/PASSWORD)")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--normal-strength", type=float, default=1.2)
    ap.add_argument("--no-invert-normal-y", action="store_true",
                    help="pass normal_invert_y=False to QFX (see the CAVEAT in the docstring)")
    ap.add_argument("--flip-normal-green", action="store_true",
                    help="flip the normal's green channel when packing for glTF")
    ap.add_argument("--marigold-python", default=str(DEFAULT_MARIGOLD_PYTHON),
                    help="interpreter with torch+diffusers (default: the ComfyUI venv)")
    ap.add_argument("--marigold-cwd", default=None,
                    help="working dir for marigold_pbr.py; it loads models/diffusers relatively, "
                         "so this must be the ComfyUI dir (default: derived from --marigold-python)")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--mesh", default=None, help="optional GLB to apply the material to")
    ap.add_argument("--glb-out", default=None)
    a = ap.parse_args()

    tex = Path(a.texture).resolve()
    if not tex.is_file():
        raise SystemExit(f"no such texture: {tex}")
    base = comfy_io.resolve_base(a.base)
    token = comfy_io.resolve_token(a.token, base)
    # NB: do NOT resolve() the interpreter path - a venv's bin/python is usually a symlink to the
    # system interpreter, and following it would collapse the ComfyUI dir to /usr.
    mpy = Path(os.path.abspath(a.marigold_python))
    if not mpy.is_file():
        raise SystemExit(f"marigold interpreter not found: {mpy} (pass --marigold-python)")
    # marigold_pbr.py loads `models/diffusers/...` relative to its CWD, so run it from the ComfyUI
    # root - the grandparent of <comfyui>/venv/bin/python.
    mcwd = Path(os.path.abspath(a.marigold_cwd)) if a.marigold_cwd else mpy.parents[2]
    if not (mcwd / "models" / "diffusers").is_dir():
        raise SystemExit(f"marigold cwd {mcwd} has no models/diffusers - pass --marigold-cwd")
    # Default under ComfyUI's own output/: only that tree is served by /view, so anywhere else
    # makes the result unreachable except over SSH (fetch it back with `comfy_io.py get`).
    outdir = Path(a.outdir).resolve() if a.outdir else (mcwd / "output" / "2D" / "pbr_set" / tex.stem)

    print(f"texture : {tex}")
    print(f"outdir  : {outdir.resolve()}")
    print(f"server  : {base}\n")

    print("[1/4] upload texture")
    image_name = upload(base, token, tex, "_pbr_set", a.timeout)

    print("\n[2/4] Marigold IID (albedo/roughness/metallic)")
    run([mpy, HERE / "marigold_pbr.py", tex, outdir / "marigold"], "marigold", cwd=mcwd)

    print("\n[3/4] QFX (normal/AO/displacement)")
    entry = submit_qfx(base, token, image_name, tex.stem, not a.no_invert_normal_y,
                       a.normal_strength, a.timeout)
    fetch_qfx(base, token, entry, outdir / "qfx", a.timeout)

    print("\n[4/4] pack the glTF material")
    pack_cmd = [sys.executable, HERE / "make_gltf_material.py",
                "--basecolor", outdir / "marigold" / "albedo.png",
                "--roughness", outdir / "marigold" / "roughness.png",
                "--metallic", outdir / "marigold" / "metallic.png",
                "--normal", outdir / "qfx" / "normal.png",
                "--occlusion", outdir / "qfx" / "ao.png",
                "--size", a.size, "--outdir", outdir / "material"]
    if a.flip_normal_green:
        pack_cmd.append("--flip-normal-green")
    if a.mesh:
        pack_cmd += ["--mesh", a.mesh, "--glb-out", a.glb_out or (outdir / "material.glb")]
    run(pack_cmd, "pack")

    print(f"\nDone. Material in {outdir / 'material'}/")
    try:
        rel = (outdir / "material").relative_to(mcwd / "output")
        print(f"  fetch it back: uv run python scripts/comfy_io.py get "
              f"{rel.as_posix()}/normal.png --dest from-box")
    except ValueError:
        print("  NB: that dir is outside ComfyUI's output/, so it is reachable over SSH only - "
              "drop --outdir to keep results fetchable over HTTP.")
    print("  basecolor.png, metallicRoughness.png (G=rough, B=metal), normal.png, occlusion.png, material.json")
    if a.mesh:
        print(f"  mesh with the material applied -> {a.glb_out or (outdir / 'material.glb')}")
    print("\nVerify the normal's Y convention on a lit mesh before shipping (see the docstring caveat).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
