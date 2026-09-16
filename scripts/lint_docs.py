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
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESC = "\x00"  # placeholder for escaped pipes


def split_cells(line: str) -> list[str]:
    """Split a table row on unescaped pipes, dropping the outer empties."""
    protected = line.replace("\\|", ESC)
    parts = protected.strip().split("|")
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return parts


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
    for c in sorted(links):
        if c.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not any(os.path.exists(os.path.join(b, c.split("#")[0])) for b in bases):
            problems.append(f"{rel} dead link -> {c}")
    for c in sorted(backticks):
        if any(ch in c for ch in "|*{}<>") or c.startswith(("input/", "output/")):
            continue
        # `2d/char_knight.png` (scenario + bare filename) is a reference to the ComfyUI
        # staging/output dir on the box, not to a path in this repo — staging refs always
        # look like this, while in-repo refs always have a subdir (workflows/, evidence/).
        if re.fullmatch(r"(2d|3d|2D|3D)/[^/]+\.(png|jpg|jpeg|webp|glb|fbx|obj|stl|ply)", c):
            continue
        if not any(os.path.exists(os.path.join(b, c.split("#")[0])) for b in bases):
            problems.append(f"{rel} dead path -> `{c}`")
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
