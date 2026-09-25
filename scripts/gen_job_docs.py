#!/usr/bin/env python3
"""Render workflows/jobs.json into the docs that carry the job -> flow -> story mapping.

WHY THIS EXISTS

Before this, the same mapping lived hardcoded in four places: README's job table, each PIPELINES row's
`how-to` column, and each workflow's MarkdownNote footer. Adding a job, moving one between stories, or
renumbering a story meant hand-editing ~45 references - and the 2026-09 renumber (S8-S13 permuted, applied
as a single regex pass precisely so it could not cascade) showed how easy a half-applied edit would be.
`workflows/jobs.json` is now the single source; this script writes the surfaces, and `lint_docs.py` gates
that they still agree.

WHAT IT WRITES

  * README.md          - the "I want to make / do" job table (rows in registry order)
  * PIPELINES.md       - every index row's story cell, as a link, from the flow's claim
  * <scenario>/workflows/*.json - each workflow's MarkdownNote footer story reference

WHAT IT DELIBERATELY DOES NOT WRITE

The prose of any note, the rest of each PIPELINES row, and HOWTO's stories themselves (their headings are
what anchors resolve against, so the story *text* is authored, not generated; the registry only mirrors it
and lint checks the mirror).

Usage:
    uv run python scripts/gen_job_docs.py            # report what would change
    uv run python scripts/gen_job_docs.py --write    # apply
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdtable  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(REPO, "workflows", "jobs.json")


def load_registry():
    reg = json.load(io.open(REGISTRY, encoding="utf-8"))
    for key in ("stories", "jobs", "flows"):
        if key not in reg:
            raise SystemExit("jobs.json: missing %r" % key)
    return reg


def story_link(reg, sid):
    """The README/PIPELINES style link for a story: [S5](HOWTO.md#s5-edit-a-picture-remove-replace-extend)."""
    title = reg["stories"][sid]
    slug = re.sub(r"[^a-z0-9 ]", "", title.lower()).strip().replace(" ", "-")
    return "[%s](HOWTO.md#%s-%s)" % (sid, sid.lower(), slug)


JOBS_HEADER = ["I want to make / do", "flow", "story"]
JOBS_ANCHOR = "<!-- jobs: generated from workflows/jobs.json by scripts/gen_job_docs.py -->"


def grouped_jobs(reg):
    """[(category_title, [job, ...]), ...] in the registry's category order."""
    titles = {c["id"]: c["title"] for c in reg.get("categories", [])}
    order = [c["id"] for c in reg.get("categories", [])]
    out = []
    for cid in order:
        jobs = [j for j in reg["jobs"] if j.get("category") == cid]
        if jobs:
            out.append((titles[cid], jobs))
    return out


def jobs_block(reg):
    """The whole generated block: one heading + table per category."""
    parts = [JOBS_ANCHOR]
    for title, jobs in grouped_jobs(reg):
        parts.append("")
        parts.append("### %s" % title)
        parts.append("")
        rows = [[j["want"], j["detail"], story_link(reg, j["story"])] for j in jobs]
        parts.extend(mdtable.render(JOBS_HEADER, rows))
    return "\n".join(parts) + "\n"


def _block_bounds(text):
    """[start, end) of the generated jobs block, delimited by the anchor and the next '## ' heading."""
    a = text.find(JOBS_ANCHOR)
    if a < 0:
        return None
    b = text.find("\n## ", a)
    return (a, len(text) if b < 0 else b + 1)


def render_readme(readme_text, reg):
    bounds = _block_bounds(readme_text)
    if bounds is None:
        raise SystemExit("README.md: jobs anchor not found (%s)" % JOBS_ANCHOR)
    a, b = bounds
    return readme_text[:a] + jobs_block(reg) + readme_text[b:]


def readme_tables(readme_text):
    """Every job table in the generated block, as data (rows of 3 cells), in file order."""
    bounds = _block_bounds(readme_text)
    if bounds is None:
        return None
    a, b = bounds
    seg = readme_text[a:b]
    out = []
    for t in mdtable.parse(seg):
        if t.header == JOBS_HEADER:
            out.append([list(r) for r in t.rows])
    return out


def readme_cells(readme_text, reg):
    """The rows the registry expects, concatenated per category in order (for comparison)."""
    want = []
    for _title, jobs in grouped_jobs(reg):
        want += [[j["want"], j["detail"], story_link(reg, j["story"])] for j in jobs]
    return want


def pipelines_cells(text):
    """The story cells as they are in a PIPELINES render, for cell-level comparison (padding is not content)."""
    t = mdtable.find(text, "flow")
    if t is None or "how-to" not in t.header:
        return None
    col = t.header.index("how-to")
    return [r[col].strip() for r in t.rows]


def render_pipelines(text, reg):
    t = mdtable.find(text, "flow")
    if t is None or "how-to" not in t.header:
        raise SystemExit("PIPELINES.md: index table not found")
    col = t.header.index("how-to")
    rows = [list(r) for r in t.rows]
    for r in rows:
        m = re.search(r"`([^`]+)`", r[0])
        if not m:
            continue
        meta = reg["flows"].get(m.group(1).split("/")[-1])
        if not meta:
            continue
        ids = meta.get("stories") or [meta["story"]]
        r[col] = ", ".join(story_link(reg, s) for s in ids)
    return mdtable.replace(text, t, t.header, rows)


def render_note_story(text, ids):
    """Rewrite the story ids in the note's footer, leaving the rest of the prose alone.

    Three cases, because the notes are not uniform:
      * a footer with `story **S5**` or `story **S5, S7**` -> the ids are replaced in place
      * a footer whose `*How to run it:*` clause is there but has no story -> one is inserted
      * a footer without the clause at all (pbr-material notes its *Why* only) -> the clause is added
    So a workflow can never silently drift out of the mapping.
    """
    link = ", ".join(ids)

    def sub(m):
        return m.group(1) + link + m.group(3)

    new, n = re.subn(r"(story \*\*)(S\d+(?:, S\d+)*)(\*\*)", sub, text)
    if n:
        return new, n

    # `*Why it is this way: …*` with no run-it clause -> prepend one, keeping the italic marker clean
    new, n = re.subn(r"^\*Why it is this way: (.*?)\*$",
                     lambda m: "*How to run it: story **%s** in `HOWTO.md`  ·  Why it is this way: %s*" % (link, m.group(1)),
                     text, count=1, flags=re.M)
    if n:
        return new, n

    # a `*How to run it:* …*` that mentions no story -> name it
    new, n = re.subn(r"(\*How to run it: )", lambda m: "%sstory **%s** in `HOWTO.md`; " % (m.group(1), link), text, count=1)
    return new, n


def main():
    ap = argparse.ArgumentParser(description="Render jobs.json into README/PIPELINES/workflow notes.")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    reg = load_registry()
    changed = 0

    # --- README
    path = os.path.join(REPO, "README.md")
    before = io.open(path, encoding="utf-8").read()
    after = render_readme(before, reg)
    if after != before:
        changed += 1
        print("README.md: job table %s" % ("written" if args.write else "WOULD CHANGE"))
        if args.write:
            io.open(path, "w", encoding="utf-8", newline="\n").write(after)

    # --- PIPELINES
    path = os.path.join(REPO, "PIPELINES.md")
    before = io.open(path, encoding="utf-8").read()
    after = render_pipelines(before, reg)
    if pipelines_cells(before) != pipelines_cells(after):
        changed += 1
        print("PIPELINES.md: story column %s" % ("written" if args.write else "WOULD CHANGE"))
        if args.write:
            io.open(path, "w", encoding="utf-8", newline="\n").write(after)

    # --- workflow notes
    for p in sorted(glob.glob(os.path.join(REPO, "*", "workflows", "*.json"))):
        name = os.path.basename(p)
        meta = reg["flows"].get(name)
        if not meta:
            continue
        ids = meta.get("stories") or [meta["story"]]
        w = json.load(io.open(p, encoding="utf-8"))
        touched = False
        for n in w["nodes"]:
            if n.get("type") not in ("MarkdownNote", "Note"):
                continue
            text = n["widgets_values"][0]
            new, count = render_note_story(text, ids)
            if count and new != text:
                n["widgets_values"][0] = new
                touched = True
        if touched:
            changed += 1
            print("%s: note story -> %s %s" % (name, ", ".join(ids), "written" if args.write else "WOULD CHANGE"))
            if args.write:
                io.open(p, "w", encoding="utf-8", newline="\n").write(
                    json.dumps(w, indent=1, ensure_ascii=False))

    print("\n%d surface(s) %s" % (changed, "updated" if args.write else "would change"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
