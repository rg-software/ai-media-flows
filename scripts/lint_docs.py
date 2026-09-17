#!/usr/bin/env python3
"""Lint the repo's Markdown: tables that won't render, and dead internal links.

Why this exists: our docs are hand-merged constantly (scripts patch table rows), and
that has already produced two silent breakages —
  * a separator row with one column too many, which makes strict renderers drop the
    ENTIRE table (2d/EXPERIMENTS-2D.md),
  * a literal newline inside a cell, which splits a row in half and leaves an orphan
    paragraph (same file).
Neither is visible when you read the raw text, and both waste a reviewer's time.

Checks:
  1. Every GFM table: header / separator / each data row must have the same number of
     columns. Escaped pipes (\\|) inside cells are handled correctly.
  2. Rows split across lines, and orphan lines interrupting a table.
  3. Relative Markdown links and backticked repo paths that don't resolve.

Usage:  python scripts/lint_docs.py [paths...]     (default: every *.md in the repo)
Exit code 1 if anything is wrong, so it can gate a commit.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESC = "\x00"  # placeholder for escaped pipes


def split_cells(line: str) -> list[str]:
    """Split a table row on unescaped pipes, dropping the outer empties and trimming."""
    protected = line.replace("\\|", ESC)
    parts = protected.strip().split("|")
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


def lint_file(path: str, rel: str) -> list[str]:
    problems: list[str] = []
    lines = open(path, encoding="utf-8").read().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # a table starts where a row is followed by a separator row
        if line.startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            # GFM: a table cannot interrupt a *paragraph* — it needs a blank line before it.
            # A heading, list item, blockquote or another table row before it is fine.
            prev = lines[i - 1].strip() if i > 0 else ""
            block_marker = re.match(r"^(#{1,6}\s|\||>\s?|[-*+]\s|\d+[.)]\s|-{3,})", prev)
            if prev and not block_marker:
                problems.append(
                    f"{rel}:{i+1} table starts without a blank line before it "
                    f"(previous: {prev[:50]!r})"
                )
            nhead = len(split_cells(line))
            nsep = len(split_cells(lines[i + 1]))
            if nhead != nsep:
                problems.append(
                    f"{rel}:{i+1} separator has {nsep} columns but the header has {nhead} "
                    f"-> strict renderers will drop this whole table"
                )
            if not line.endswith("|"):
                problems.append(f"{rel}:{i+1} header row does not end with '|'")
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                row = lines[j].strip()
                n = len(split_cells(row))
                if not row.endswith("|"):
                    problems.append(
                        f"{rel}:{j+1} table row does not end with '|' (split cell? "
                        f"expects {nhead} columns, found {n})"
                    )
                elif n != nhead:
                    problems.append(
                        f"{rel}:{j+1} row has {n} columns, header has {nhead}"
                    )
                j += 1
            # an unterminated table row followed immediately by prose = a split row
            if j < len(lines) and lines[j].strip() and not lines[j].strip().startswith("#"):
                if lines[j - 1].strip().startswith("|") and not lines[j].strip().startswith("|"):
                    problems.append(
                        f"{rel}:{j+1} prose line interrupts a table (a cell contained a "
                        f"literal newline?): {lines[j].strip()[:70]!r}"
                    )
            i = j
            continue
        i += 1

    # links + backticked repo paths.
    # This repo uses three reference conventions, so we accept a path if it resolves
    # against ANY plausible base rather than picking one and reporting false rot:
    #   * markdown links        -> file-relative (standard)
    #   * `2d/workflows/x.json` -> repo-root-relative
    #   * `workflows/x.json`    -> scenario-relative (what AGENTS.md specifies)
    # Also skipped: box-side staging paths (`input/...`) which are deliberately not in
    # the repo, and anything containing a placeholder (`{a,b}`, `<name>`, `*`).
    text = "\n".join(lines)
    links = set(re.findall(r"\]\(([^)\s]+)\)", text))
    backticks = {
        m
        for m in re.findall(r"`([^`\n]+)`", text)
        if "/" in m and re.search(r"\.(json|py|sh|md|png|glb)$", m)
    }
    bases = [os.path.dirname(path), os.path.dirname(os.path.dirname(path)), REPO]
    def resolves(cand: str) -> bool:
        """True if cand (or, for a command example like `python scripts/x.py`, its last
        whitespace-separated token) exists relative to any plausible base."""
        tries = [cand]
        if " " in cand:
            tries.append(cand.split()[-1])
        return any(
            os.path.exists(os.path.join(b, t.split("#")[0])) for t in tries for b in bases
        )

    for c in sorted(links):
        if c.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not resolves(c):
            problems.append(f"{rel} dead link -> {c}")
    for c in sorted(backticks):
        if any(ch in c for ch in "|*{}<>") or c.startswith(("input/", "output/")):
            continue
        # `2d/char_knight.png` (scenario + bare filename) is a reference to the ComfyUI
        # staging/output dir on the box, not to a path in this repo — staging refs always
        # look like this, while in-repo refs always have a subdir (workflows/, evidence/).
        if re.fullmatch(r"(2d|3d|2D|3D)/[^/]+\.(png|jpg|jpeg|webp|glb|fbx|obj|stl|ply)", c):
            continue
        if not resolves(c):
            problems.append(f"{rel} dead path -> `{c}`")
    return problems


def check_flow_coverage() -> list[str]:
    """Every curated flow must be reachable from the two indexes, so a new flow cannot
    silently become unfindable:
      * README.md   -> the job-oriented "I want to…" table
      * PIPELINES.md -> the capability index
    """
    problems: list[str] = []
    flows: list[str] = []
    for pattern in ("2d/workflows/*.json", "3d/workflows/*.json", "scripts/*"):
        if pattern.startswith("scripts"):
            flows += [p for p in glob.glob(os.path.join(REPO, pattern)) if os.path.isfile(p)]
        else:
            flows += glob.glob(os.path.join(REPO, pattern))  # scratch/ is excluded by the glob
    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    pipes = open(os.path.join(REPO, "PIPELINES.md"), encoding="utf-8").read()
    for f in sorted(flows):
        rel = os.path.relpath(f, REPO).replace(os.sep, "/")
        base = os.path.basename(f)
        if base not in readme:
            problems.append(f"{rel} is in no README.md 'I want to' row (unreachable from the front door)")
        if base not in pipes:
            problems.append(f"{rel} has no row in PIPELINES.md (missing from the capability index)")
    return problems


def check_flow_docs() -> list[str]:
    """A flow's documentation must exist and be reachable, so a user who opens a flow in the
    canvas (or lands on its index row) can always find out what to do with it:
      * every workflow carries a MarkdownNote - a group title renders as a clipped label, a
        MarkdownNote renders as a readable panel (it is what ComfyUI's own templates use);
      * every PIPELINES index row names a HOWTO story, and that story must exist.
    """
    problems: list[str] = []
    howto = open(os.path.join(REPO, "HOWTO.md"), encoding="utf-8").read()
    stories = set(re.findall(r"^###\s+(S\d+)\.", howto, re.M))

    for f in sorted(glob.glob(os.path.join(REPO, "2d", "workflows", "*.json")) +
                    glob.glob(os.path.join(REPO, "3d", "workflows", "*.json"))):
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
        text = wv[0] if wv else ""
        if len(text) < 200:
            problems.append(f"{rel} MarkdownNote is only {len(text)} chars (<200)")

    lines = open(os.path.join(REPO, "PIPELINES.md"), encoding="utf-8").read().split("\n")
    hi = next((i for i, l in enumerate(lines) if re.match(r"^\|\s*flow\s*\|", l)), None)
    if hi is None:
        problems.append("PIPELINES.md: index header not found")
    else:
        hdr = split_cells(lines[hi])
        if "how-to" not in hdr:
            problems.append("PIPELINES.md: index has no 'how-to' column")
        else:
            col = hdr.index("how-to")
            for i in range(hi + 2, len(lines)):
                if not lines[i].strip().startswith("|"):
                    break
                c = split_cells(lines[i])
                flow = c[0].strip("`")
                if col >= len(c):
                    problems.append(f"PIPELINES.md:{i+1} {flow}: row too short for the how-to column")
                    continue
                for s in re.findall(r"S\d+", c[col]):
                    if s not in stories:
                        problems.append(
                            f"PIPELINES.md:{i+1} {flow}: cites story {s} that HOWTO.md does not define"
                        )
    return problems


def check_story_mapping() -> list[str]:
    """The README's job table and HOWTO's stories are many-to-one (one story can serve several
    job rows, because the procedure is shared). That mapping must stay complete both ways, or a
    reader is sent to a story that does not exist - or a story becomes unreachable.

      * every job row names a story, and that story exists in HOWTO.md
      * every story in HOWTO.md is referenced by at least one job row
    """
    problems: list[str] = []
    howto = open(os.path.join(REPO, "HOWTO.md"), encoding="utf-8").read()
    defined = set(re.findall(r"^###\s+(S\d+)\.", howto, re.M))

    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read().split("\n")
    hi = next((i for i, l in enumerate(readme) if l.strip().startswith("| I want to make / do")), None)
    if hi is None:
        return ["README.md: 'I want to make' table not found"]

    hdr = split_cells(readme[hi])
    if "story" not in hdr:
        return ["README.md: 'I want to make' table has no 'story' column"]
    col = hdr.index("story")

    used: set[str] = set()
    for i in range(hi + 2, len(readme)):
        if not readme[i].strip().startswith("|"):
            break
        c = split_cells(readme[i])
        if col >= len(c):
            problems.append(f"README.md:{i+1} row too short for the story column: {c[0][:40]}")
            continue
        m = re.fullmatch(r"S\d+", c[col])
        if not m:
            problems.append(f"README.md:{i+1} {c[0][:40]}: story cell is not an S-number ({c[col]!r})")
            continue
        used.add(c[col])
        if c[col] not in defined:
            problems.append(f"README.md:{i+1} {c[0][:40]}: cites story {c[col]} that HOWTO.md does not define")

    for s in sorted(defined - used):
        problems.append(f"HOWTO.md defines story {s} that no README job row references")
    return problems


def main() -> int:
    rc = getattr(sys.stdout, "reconfigure", None)  # may be absent on odd runtimes
    if rc is not None:
        try:  # keep output from dying on consoles with a non-UTF-8 codepage
            rc(errors="replace")
        except Exception:
            pass
    args = sys.argv[1:]
    if args:
        files = [a for a in args if a.endswith(".md")]
    else:
        files = [
            p
            for p in glob.glob(os.path.join(REPO, "**", "*.md"), recursive=True)
            if f"{os.sep}.git{os.sep}" not in p
        ]
    all_problems: list[str] = []
    for f in sorted(files):
        rel = os.path.relpath(f, REPO)
        all_problems += lint_file(f, rel)
    all_problems += check_flow_coverage()
    all_problems += check_flow_docs()
    all_problems += check_story_mapping()

    print(f"linted {len(files)} markdown file(s)")
    if all_problems:
        print(f"\n{len(all_problems)} problem(s):")
        for p in all_problems:
            print("  " + p)
        return 1
    print("no table or link problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
