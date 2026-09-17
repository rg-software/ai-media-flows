#!/usr/bin/env python3
"""Lint the repo's Markdown and its cross-references.

Run it before committing docs:  uv run python scripts/lint_docs.py

Checks, in the order of what has actually bitten us:

  1. **No NUL bytes.** A stray NUL makes git treat a file as *binary*, so its diff silently
     becomes invisible (`git diff --numstat` shows `-  -` instead of line counts). This really
     happened, and cost a review pass.
  2. **Tables parse, and nothing is silently lost.** Tables are parsed with markdown-it
     (`scripts/mdtable.py`), not by splitting strings. Two failure modes are caught:
       - a row-looking line that is *not* inside a parseable table -> a malformed table
         (usually a separator with the wrong column count, which makes strict renderers drop the
         WHOLE table);
       - a row whose raw cell count differs from the header -> markdown-it *normalises* this
         silently (padding short rows, truncating long ones = data loss), so it is checked
         against the raw line.
  3. **A table must not interrupt a paragraph** (GFM cannot start a table mid-paragraph).
  4. **Links resolve.** Markdown links are file-relative; backticked paths resolve against
     the file dir, the scenario dir, or the repo root (this repo uses all three).
  5. **Flow coverage:** every flow is reachable from the README's job table and has a
     `PIPELINES.md` row.
  6. **Per-flow docs:** every workflow carries a `MarkdownNote` (a group title renders as a
     clipped label in the canvas), and every story cited in the index exists in `HOWTO.md`.
  7. **Story mapping:** every README job row names a story that exists, and every story is
     referenced by at least one row.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdtable  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BLOCK_MARKER = re.compile(r"^(#{1,6}\s|\||>\s?|[-*+]\s|\d+[.)]\s|-{3,}|_{3,})")


def unescaped_pipes(line: str) -> int:
    """Count pipes that are not escaped by an odd number of preceding backslashes."""
    n, i = 0, 0
    while i < len(line):
        if line[i] == "|":
            bs = 0
            j = i - 1
            while j >= 0 and line[j] == "\\":
                bs += 1
                j -= 1
            if bs % 2 == 0:
                n += 1
        i += 1
    return n


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


_ANCHOR_CACHE: dict[str, set[str]] = {}


def anchors_of(path: str) -> set[str]:
    """The set of anchors a file's headings produce (GitHub's algorithm)."""
    if path not in _ANCHOR_CACHE:
        txt = open(path, encoding="utf-8", errors="replace").read()
        got = set()
        for h in re.findall(r"^#{1,6}\s+(.*)$", txt, re.M):
            s = h.strip().lower()
            s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
            s = re.sub(r"\s+", "-", s)
            got.add(s)
        _ANCHOR_CACHE[path] = got
    return _ANCHOR_CACHE[path]


# --------------------------------------------------------------------------- per-file checks
def lint_file(path: str, rel: str) -> list[str]:
    problems: list[str] = []
    raw = open(path, "rb").read()
    n_nul = raw.count(b"\x00")
    if n_nul:
        problems.append(
            f"{rel} contains {n_nul} NUL byte(s) -> git treats it as BINARY, so its diff is "
            f"invisible. Something wrote a placeholder instead of real text."
        )
        return problems  # everything else is meaningless on a corrupt file

    text = raw.decode("utf-8", "replace")
    lines = text.split("\n")
    tables = mdtable.parse(text)
    spans = [(t.start, t.end) for t in tables]

    def inside_table(i: int) -> bool:
        return any(s <= i < e for s, e in spans)

    # (2)+(3) tables
    for t in tables:
        ncol = len(t.header)
        for i in range(t.start, t.end):
            line = lines[i]
            if not line.strip().startswith("|") or is_separator(line):
                continue
            # -1 because a row of N cells has N+1 unescaped pipes (leading + separators)
            cells = unescaped_pipes(line) - 1
            if cells != ncol:
                problems.append(
                    f"{rel}:{i+1} row has {cells} cells, header has {ncol} -> markdown-it will "
                    f"silently {'pad' if cells < ncol else 'TRUNCATE (data loss)'} this row"
                )
        if t.start > 0:
            prev = lines[t.start - 1].strip()
            if prev and not BLOCK_MARKER.match(prev):
                problems.append(
                    f"{rel}:{t.start+1} table starts without a blank line before it "
                    f"(GFM cannot interrupt a paragraph; previous: {prev[:50]!r})"
                )

    for i, line in enumerate(lines):
        if line.strip().startswith("|") and not inside_table(i):
            problems.append(
                f"{rel}:{i+1} table row outside any parseable table - malformed table "
                f"(usually a separator with the wrong column count) or a split row: "
                f"{line.strip()[:60]!r}"
            )

    # (4) links and paths
    links = set(re.findall(r"\]\(([^)\s]+)\)", text))
    backticks = {m for m in re.findall(r"`([^`\n]+)`", text)
                 if "/" in m and re.search(r"\.(json|py|sh|md|png|glb)$", m)}
    bases = [os.path.dirname(path), os.path.dirname(os.path.dirname(path)), REPO]

    def resolves(cand: str) -> bool:
        tries = [cand] + ([cand.split()[-1]] if " " in cand else [])
        return any(os.path.exists(os.path.join(b, t.split("#")[0])) for t in tries for b in bases)

    def resolve_path(cand: str) -> str | None:
        for b in bases:
            p = os.path.join(b, cand)
            if os.path.exists(p):
                return p
        return None

    for c in sorted(links):
        if c.startswith(("http://", "https://", "mailto:")):
            continue
        if not resolves(c):
            problems.append(f"{rel} dead link -> {c}")
            continue
        # a fragment must match a real heading anchor in the target file, or renames
        # silently break every link that points here
        if "#" in c:
            target, frag = c.split("#", 1)
            if not frag:
                continue
            tp = resolve_path(target) if target else path
            if tp and os.path.isfile(tp) and frag not in anchors_of(tp):
                problems.append(f"{rel} dead anchor -> {c} (no heading produces #{frag} in {os.path.relpath(tp, REPO)})")
    for c in sorted(backticks):
        if any(ch in c for ch in "|*{}<>") or c.startswith(("input/", "output/")):
            continue
        if re.fullmatch(r"(2d|3d|2D|3D)/[^/]+\.(png|jpg|jpeg|webp|glb|fbx|obj|stl|ply)", c):
            continue  # box-side staging/output reference, not a repo path
        if not resolves(c):
            problems.append(f"{rel} dead path -> `{c}`")
    return problems


# --------------------------------------------------------------------------- repo-wide checks
def iter_flows():
    for pat in ("2d/workflows/*.json", "3d/workflows/*.json", "scripts/*"):
        for p in sorted(glob.glob(os.path.join(REPO, pat))):
            if os.path.isfile(p):
                yield p


def check_flow_coverage() -> list[str]:
    """Every flow must be reachable from the two indexes."""
    problems = []
    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    pipes = open(os.path.join(REPO, "PIPELINES.md"), encoding="utf-8").read()
    for f in iter_flows():
        rel = os.path.relpath(f, REPO).replace(os.sep, "/")
        base = os.path.basename(f)
        if base not in readme:
            problems.append(f"{rel} is in no README.md 'I want to make' row (unreachable)")
        if base not in pipes:
            problems.append(f"{rel} has no row in PIPELINES.md (missing from the capability index)")
    return problems


def check_flow_docs() -> list[str]:
    """Every workflow carries a MarkdownNote; every cited story exists."""
    problems = []
    howto = open(os.path.join(REPO, "HOWTO.md"), encoding="utf-8").read()
    stories = set(re.findall(r"^###\s+(S\d+)\.", howto, re.M))
    for f in glob.glob(os.path.join(REPO, "2d", "workflows", "*.json")) + \
             glob.glob(os.path.join(REPO, "3d", "workflows", "*.json")):
        rel = os.path.relpath(f, REPO).replace(os.sep, "/")
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            problems.append(f"{rel} unreadable JSON: {e}")
            continue
        notes = [n for n in d.get("nodes", []) if n.get("type") == "MarkdownNote"]
        if not notes:
            problems.append(
                f"{rel} has no MarkdownNote - its docs are only a group title, which the canvas "
                f"renders as a clipped label (run scripts/add_workflow_notes.py)"
            )
            continue
        wv = notes[0].get("widgets_values") or [""]
        txt = wv[0] if wv else ""
        if len(txt) < 200:
            problems.append(f"{rel} MarkdownNote is only {len(txt)} chars (<200)")

    pipes_text = open(os.path.join(REPO, "PIPELINES.md"), encoding="utf-8").read()
    idx = mdtable.find(pipes_text, "flow")
    if idx is None or "how-to" not in idx.header:
        problems.append("PIPELINES.md: index table has no 'how-to' column")
    else:
        col = idx.header.index("how-to")
        for r in idx.rows:
            for s in re.findall(r"S\d+", r[col] if col < len(r) else ""):
                if s not in stories:
                    problems.append(f"PIPELINES.md: {r[0]} cites story {s} that HOWTO.md does not define")
    return problems


def check_story_mapping() -> list[str]:
    """README job rows <-> HOWTO stories must stay complete in both directions."""
    problems = []
    howto = open(os.path.join(REPO, "HOWTO.md"), encoding="utf-8").read()
    defined = set(re.findall(r"^###\s+(S\d+)\.", howto, re.M))
    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    t = mdtable.find(readme, "I want to make")
    if t is None:
        return ["README.md: 'I want to make' table not found"]
    if "story" not in t.header:
        return ["README.md: 'I want to make' table has no 'story' column"]
    col = t.header.index("story")
    used = set()
    for r in t.rows:
        if col >= len(r):
            problems.append(f"README.md: row too short for the story column: {r[0][:40]}")
            continue
        v = r[col]
        # accept a bare id ("S5") or a link whose *text* is the id ("[S5](HOWTO.md#...)")
        as_link = re.fullmatch(r"\[(S\d+)\]\([^)]*\)", v)
        as_plain = re.fullmatch(r"S\d+", v)
        sid = as_link.group(1) if as_link else (v if as_plain else None)
        if sid is None:
            problems.append(f"README.md: {r[0][:40]}: story cell is not an S-number ({v!r})")
            continue
        used.add(sid)
        if sid not in defined:
            problems.append(f"README.md: {r[0][:40]}: cites story {sid} that HOWTO.md does not define")
    for s in sorted(defined - used):
        problems.append(f"HOWTO.md defines story {s} that no README job row references")
    return problems


def main() -> int:
    rc = getattr(sys.stdout, "reconfigure", None)
    if rc is not None:
        try:
            rc(errors="replace")
        except Exception:
            pass

    files = [p for p in glob.glob(os.path.join(REPO, "**", "*.md"), recursive=True)
             if f"{os.sep}.git{os.sep}" not in p]
    problems: list[str] = []
    for f in sorted(files):
        problems += lint_file(f, os.path.relpath(f, REPO))
    problems += check_flow_coverage()
    problems += check_flow_docs()
    problems += check_story_mapping()

    print(f"linted {len(files)} markdown file(s)")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  " + p)
        return 1
    print("no table, link, coverage or flow-doc problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
