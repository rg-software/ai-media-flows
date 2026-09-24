#!/usr/bin/env python3
"""Gate: workflows/jobs.json must agree with the docs it feeds.

Cell-level, not byte-level: a table's *padding* is not content (mdtable re-renders a table with its own
column widths, so a historical wider row can shift spaces by two while every cell is identical). What must
agree is the cells themselves.

Checks:
  1. every README job row == the registry's (want, detail, story link), in order
  2. every PIPELINES story cell == the flow's claim, links and order included
  3. every workflow's note footer cites exactly its registry story (or stories)
  4. every workflow file has a claim, and every claim names a real workflow
  5. every story id used exists in the registry and in HOWTO's headings, and the *titles* match
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdtable  # noqa: E402
from gen_job_docs import REGISTRY, REPO, load_registry, render_note_story, story_link  # noqa: E402


def check() -> list[str]:
    problems: list[str] = []
    reg = load_registry()

    # 5. stories exist in HOWTO and the titles agree
    howto = io.open(os.path.join(REPO, "HOWTO.md"), encoding="utf-8").read()
    defined = dict(re.findall(r"^### (S\d+)\. (.+)$", howto, re.M))
    for sid, title in reg["stories"].items():
        if sid not in defined:
            problems.append("jobs.json: story %s is not a heading in HOWTO.md" % sid)
        elif defined[sid].strip() != title.strip():
            problems.append("jobs.json: story %s title %r != HOWTO's %r" % (sid, title, defined[sid]))

    # 1. README job rows
    readme = io.open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    t = mdtable.find(readme, "I want to make")
    if t is None:
        problems.append("README.md: job table not found")
    else:
        want = [[j["want"], j["detail"], story_link(reg, j["story"])] for j in reg["jobs"]]
        have = [list(r) for r in t.rows]
        if want != have:
            problems.append("README.md: job table does not match jobs.json (%d vs %d rows)"
                            % (len(want), len(have)))
            for i, (a, b) in enumerate(zip(want, have)):
                if a != b:
                    problems.append("  row %d: %r != %r" % (i, a[0][:40], b[0][:40]))
        if "story" not in t.header:
            problems.append("README.md: job table has no 'story' column")

    # 2. PIPELINES story cells
    pipes = io.open(os.path.join(REPO, "PIPELINES.md"), encoding="utf-8").read()
    p = mdtable.find(pipes, "flow")
    if p is None or "how-to" not in p.header:
        problems.append("PIPELINES.md: index table has no 'how-to' column")
    else:
        col = p.header.index("how-to")
        for r in p.rows:
            m = re.search(r"`([^`]+)`", r[0])
            if not m:
                continue
            name = m.group(1).split("/")[-1]
            meta = reg["flows"].get(name)
            if not meta:
                continue
            ids = meta.get("stories") or [meta["story"]]
            want = ", ".join(story_link(reg, s) for s in ids)
            if r[col].strip() != want:
                problems.append("PIPELINES.md: %s story cell %r != jobs.json %r"
                                % (name, r[col].strip()[:50], want[:50]))

    # 3/4. workflow notes and claims
    files = {os.path.basename(f)
             for f in glob.glob(os.path.join(REPO, "*", "workflows", "*.json"))}
    for name in sorted(files - set(reg["flows"])):
        problems.append("jobs.json: no story claim for workflow %s" % name)
    for name, meta in sorted(reg["flows"].items()):
        if name.endswith(".json") and name not in files:
            problems.append("jobs.json: claims %s but that workflow file does not exist" % name)
        ids = meta.get("stories") or [meta["story"]]
        for s in ids:
            if s not in reg["stories"]:
                problems.append("jobs.json: %s claims story %s which has no entry" % (name, s))
        if not name.endswith(".json"):
            continue
        # locate the file rather than guessing the scenario folder from its name: a new flow may not
        # follow the packing's naming (sv3d-turnaround.json lives in 3d/, not 2d/)
        hits = glob.glob(os.path.join(REPO, "*", "workflows", name))
        if not hits:
            problems.append("jobs.json: claims %s but no such workflow file exists" % name)
            continue
        w = json.load(io.open(hits[0], encoding="utf-8"))
        note = [n for n in w["nodes"] if n.get("type") in ("Note", "MarkdownNote")]
        if not note:
            continue
        text = note[0]["widgets_values"][0]
        if "story **" not in text:
            problems.append("%s: note has no story reference (run scripts/gen_job_docs.py --write)" % name)
            continue
        # re-rendering the note with its claim must be a no-op
        _, count = render_note_story(text, ids)
        if count == 0:
            problems.append("%s: note story line not in the expected form" % name)
        elif render_note_story(text, ids)[0] != text:
            problems.append("%s: note cites a different story than jobs.json (%s)"
                            % (name, ", ".join(ids)))
    return problems


if __name__ == "__main__":
    probs = check()
    for x in probs:
        print("  " + x)
    print("%d problem(s)" % len(probs))
    sys.exit(1 if probs else 0)
