#!/usr/bin/env python3
"""Move files to and from a running ComfyUI over its HTTP API - no SSH, no sync daemon.

Everything here uses the same routes the web UI uses, so it needs nothing beyond the access
you already have for generation (the ComfyUI URL + token). That matters when the instance is
shared: a collaborator can move files without ever being given a shell.

  upload   PUT files INTO input/      (POST /upload/image - the GUI's drag-and-drop is a wrapper)
  outputs  list what a run produced   (GET  /history/<prompt_id>)
  fetch    pull those files down      (GET  /view?...) + a manifest recording the run
  get      pull ANY file under ComfyUI's output/, input/ or temp/ (GET /view)
           - for files written by scripts (PBR materials, sheets), which never appear in history

Usage:
    # on the box (token defaults to the login/PASSWORD first line, base to localhost):
    python comfy_io.py upload art/*.png --subfolder 2d/_work/refs
    python comfy_io.py outputs latest
    python comfy_io.py fetch latest --dest output/fetched
    python comfy_io.py get 2D/pbr_set/tex_stone/material/normal.png --dest from-box

    # from anywhere the server is reachable:
    python comfy_io.py fetch latest --base https://comfy.example.ddns.me --token "$COMFY_TOKEN"

Why 'fetch <prompt_id>' instead of syncing the output dir: the run tells you exactly which files
it made, so you get a precise, replayable set + manifest rather than a mirror of everything
(including scratch and temp). Load*FromFolder nodes cover bulk *input* by reading a folder once.
'get' exists because script-written artefacts (scripts/marigold_pbr.py, scripts/pbr_set.py) are
not runs and therefore have no history entry - but they are still servable if they live under
ComfyUI's own output/ (a file elsewhere on the box cannot be fetched at all, over any route
except SSH).

No third-party deps: stdlib urllib only (same as scripts/gen_assets.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_BASE = "http://127.0.0.1:8188"
DEFAULT_TOKEN_FILE = Path.home() / "Projects-Git" / "ComfyUI" / "login" / "PASSWORD"


def resolve_base(arg: str | None) -> str:
    return (arg or os.environ.get("COMFY_BASE") or DEFAULT_BASE).rstrip("/")


def resolve_token(arg: str | None, base: str) -> str | None:
    if arg:
        return arg
    if os.environ.get("COMFY_TOKEN"):
        return os.environ["COMFY_TOKEN"]
    if DEFAULT_TOKEN_FILE.is_file():
        first = DEFAULT_TOKEN_FILE.read_text(encoding="utf-8").splitlines()
        if first:
            return first[0].strip()
    if base.startswith(("http://127.0.0.1", "http://localhost")):
        return None  # local instance without auth is fine
    raise SystemExit("no token: pass --token, set COMFY_TOKEN, or run where "
                     "~/Projects-Git/ComfyUI/login/PASSWORD exists")


def _url(base: str, path: str, token: str | None, **params) -> str:
    query = {k: v for k, v in params.items() if v is not None}
    if token:
        query["token"] = token
    url = f"{base}{path}"
    return f"{url}?{urllib.parse.urlencode(query)}" if query else url


def _get(url: str, timeout: float) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{url.split('?')[0]} -> HTTP {e.code} {e.reason}"
                         + (" (check the token)" if e.code in (401, 403) else "")) from None
    except urllib.error.URLError as e:
        raise SystemExit(f"cannot reach {url.split('?')[0]}: {e.reason}") from None


def _multipart(fields: dict[str, str], name: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = "----comfyio" + secrets.token_hex(8)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    buf = bytearray()
    for k, v in fields.items():
        buf += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                f"{v}\r\n").encode()
    buf += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
    buf += content + b"\r\n"
    buf += f"--{boundary}--\r\n".encode()
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


def _post_multipart(url: str, body: bytes, ctype: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, data=body, method="POST",
                                headers={"Content-Type": ctype, "Content-Length": str(len(body))})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"upload -> HTTP {e.code} {e.reason}") from None


def cmd_upload(a: argparse.Namespace) -> int:
    base, token = resolve_base(a.base), resolve_token(a.token, resolve_base(a.base))
    ok = 0
    for f in a.files:
        p = Path(f)
        if not p.is_file():
            print(f"  SKIP {f} (not a file)")
            continue
        fields = {"type": "input", "overwrite": "true" if a.overwrite else "false"}
        if a.subfolder:
            fields["subfolder"] = a.subfolder
        body, ctype = _multipart(fields, "image", p.name, p.read_bytes())
        if a.dry_run:
            print(f"  DRY  {f} -> input/{a.subfolder + '/' if a.subfolder else ''}{p.name}")
            continue
        resp = json.loads(_post_multipart(_url(base, "/upload/image", token), body, ctype, a.timeout))
        where = f"{resp.get('subfolder', '')}/{resp['name']}".lstrip("/")
        print(f"  OK   {f} -> {resp.get('type', 'input')}/{where}")
        ok += 1
    print(f"uploaded {ok} file(s)")
    return 0 if ok or a.dry_run else 1


def history_entry(base: str, token: str | None, prompt_id: str, timeout: float) -> tuple[str, dict]:
    if prompt_id == "latest":
        hist = json.loads(_get(_url(base, "/history", token), timeout))
        if not hist:
            raise SystemExit("history is empty - nothing has run yet")
        prompt_id = next(reversed(hist))  # newest is appended last
    item = json.loads(_get(_url(base, "/history", token, prompt_id=prompt_id), timeout))
    if prompt_id not in item:
        raise SystemExit(f"no history entry for {prompt_id!r} (still running, or reaped by --max-history)")
    return prompt_id, item[prompt_id]


def collect_files(entry: dict) -> list[dict]:
    """Every downloadable artefact in a history entry (images, gifs, video, audio - any list of
    file descriptors), tagged with the node that produced it."""
    out = []
    for node_id, node_out in (entry.get("outputs") or {}).items():
        if not isinstance(node_out, dict):
            continue
        for kind, items in node_out.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and "filename" in it:
                    out.append({"node": node_id, "kind": kind, "filename": it["filename"],
                                "subfolder": it.get("subfolder", ""), "type": it.get("type", "output")})
    return out


def _get_optional(url: str, timeout: float) -> bytes | None:
    """Like _get, but returns None instead of raising (for 'try this file' lookups)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def cmd_get(a: argparse.Namespace) -> int:
    """Download arbitrary files from ComfyUI's served roots (output/, input/, temp/)."""
    base, token = resolve_base(a.base), resolve_token(a.token, resolve_base(a.base))
    got = 0
    for spec in a.paths:
        spec = spec.strip("/")
        subfolder, _, filename = spec.rpartition("/")
        if not filename:
            print(f"  SKIP {spec!r} (needs a filename)")
            continue
        url = _url(base, "/view", token, filename=filename, subfolder=subfolder or None, type=a.type)
        data = _get_optional(url, a.timeout)
        if data is None:
            print(f"  FAIL {spec} - not in ComfyUI's {a.type}/ (only that tree is served)")
            continue
        target = Path(a.dest) / spec
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"  OK   {spec} -> {target}  ({len(data):,} B)")
        got += 1
    print(f"fetched {got} file(s) into {a.dest}")
    return 0 if got else 1


def cmd_outputs(a: argparse.Namespace) -> int:
    base, token = resolve_base(a.base), resolve_token(a.token, resolve_base(a.base))
    pid, entry = history_entry(base, token, a.prompt_id, a.timeout)
    files = collect_files(entry)
    status = (entry.get("status") or {}).get("status_str", "?")
    print(f"{pid}  status={status}  files={len(files)}")
    for f in files:
        sub = (f["subfolder"] + "/") if f["subfolder"] else ""
        print(f"  {f['kind']:8} {f['type']:6} {sub}{f['filename']}  (node {f['node']})")
    return 0


def cmd_fetch(a: argparse.Namespace) -> int:
    base, token = resolve_base(a.base), resolve_token(a.token, resolve_base(a.base))
    pid, entry = history_entry(base, token, a.prompt_id, a.timeout)
    files = collect_files(entry)
    if not files:
        raise SystemExit(f"{pid} produced no files")
    dest = Path(a.dest) / pid
    dest.mkdir(parents=True, exist_ok=True)

    manifest = {"prompt_id": pid, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "base": base, "status": (entry.get("status") or {}).get("status_str"),
                "files": [], "prompt": entry.get("prompt")}
    for f in files:
        rel = Path(f["subfolder"]) / f["filename"] if f["subfolder"] else Path(f["filename"])
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        url = _url(base, "/view", token, filename=f["filename"], subfolder=f["subfolder"] or None,
                   type=f["type"])
        if a.dry_run:
            print(f"  DRY  {rel}")
            continue
        data = _get(url, a.timeout)
        target.write_bytes(data)
        manifest["files"].append({"file": rel.as_posix(), "node": f["node"], "kind": f["kind"],
                                  "type": f["type"], "bytes": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest()})
        print(f"  OK   {rel}  ({len(data):,} B)")

    if not a.no_manifest and not a.dry_run:
        (dest / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"  manifest -> {dest / 'manifest.json'}")
    print(f"fetched {len(manifest['files'])} file(s) into {dest}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ComfyUI file I/O over HTTP (no SSH).")
    p.add_argument("--base", help=f"server URL (default ${DEFAULT_BASE} or COMFY_BASE)")
    p.add_argument("--token", help="API token (default COMFY_TOKEN, else the box's login/PASSWORD)")
    p.add_argument("--timeout", type=float, default=120.0, help="per-request timeout in seconds")
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload", help="upload files into input/")
    up.add_argument("files", nargs="+")
    up.add_argument("--subfolder", help="upload into input/<subfolder> (e.g. 2d/_work/refs)")
    up.add_argument("--overwrite", action="store_true")
    up.add_argument("--dry-run", action="store_true")
    up.set_defaults(fn=cmd_upload)

    o = sub.add_parser("outputs", help="list a run's files (prompt id, or 'latest')")
    o.add_argument("prompt_id")
    o.set_defaults(fn=cmd_outputs)

    f = sub.add_parser("fetch", help="download a run's files + manifest (prompt id, or 'latest')")
    f.add_argument("prompt_id")
    f.add_argument("--dest", default="output/fetched", help="parent dir (default output/fetched)")
    f.add_argument("--no-manifest", action="store_true")
    f.add_argument("--dry-run", action="store_true")
    f.set_defaults(fn=cmd_fetch)

    g = sub.add_parser("get", help="download any file under ComfyUI's output/ input/ temp/")
    g.add_argument("paths", nargs="+", help="e.g. 2D/pbr_set/tex_stone/material/normal.png")
    g.add_argument("--type", default="output", choices=["output", "input", "temp"])
    g.add_argument("--dest", default="output/fetched", help="parent dir (default output/fetched)")
    g.set_defaults(fn=cmd_get)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
