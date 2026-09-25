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
     referenced by at least one row. Since `workflows/jobs.json` became the single source for the
     job -> flow -> story mapping, `check_job_docs` additionally asserts that the README table, every
     PIPELINES story cell and every workflow's note footer still *equal* what that registry renders -
     so the mapping cannot drift, and adding or moving a job is a one-file edit
     (`scripts/gen_job_docs.py --write`).
  8. **Prose wrapping:** prose is one line per paragraph. A single newline reflows on GitHub but
     renders as a visible break in a default Obsidian, and splits sentences so they cannot be
     grepped. `--fix-wrapping` rewrites files into the canonical form.
  9. **Workflow link integrity:** every workflow's node link references agree with its authoritative
     `links` array. ComfyUI wires from the array, so a stale reference (a hand-edit that shifted
     ids) is inert until it points at a link of the wrong TYPE - then the canvas reports "Invalid
     connection" (how `inpaint.json` shipped with SaveImage fed by a MASK). Fix with
     `uv run python scripts/fix_workflow_links.py --write`.
  10. **Commentary nodes stay out of the execution order:** a `MarkdownNote`/`Note` must not take an
     execution slot, or the ComfyUI frontend cannot attribute the workflow's nodes to a pack and offers
     them as an install prompt ("Unknown pack: <nodes>") - which reads as a missing pack although every
     node loads and `/prompt` accepts the graph (`pbr-material.json` shipped that way, and the symptom
     cost a debugging round because it is invisible to every server-side check). Build workflows with
     `scripts/build_workflow.py` (`--spec`), which cannot produce it.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdtable  # noqa: E402
import fix_workflow_links  # noqa: E402
import check_job_docs  # noqa: E402

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


# --- prose wrapping -----------------------------------------------------------------------------
# We keep prose as ONE LINE PER PARAGRAPH. Why: GitHub reflows a single newline, but Obsidian only
# ignores it when "Strict line breaks" is on (its default is off), so a hard-wrapped sentence shows a
# visible mid-sentence break there. Unwrapped, the source renders identically in both tools, under
# either setting -- and a sentence becomes greppable again. This predicate is deliberately shared by
# the check and the fixer so they cannot drift.
FENCE = re.compile(r"^\s*(```|~~~)")
REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s")
HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
LIST_ITEM = re.compile(r"^\s{0,3}([-*+]|\d+[.)])\s")
HARD_BREAK = re.compile(r"(?:  +|\\)$")


def _starts_block(line: str) -> bool:
    """True if the line opens a new block, so it never wraps onto the line above."""
    s = line.strip()
    if not s or s[0] == "<" or FENCE.match(line) or REFDEF.match(line) or HR.match(line):
        return True
    return bool(BLOCK_MARKER.match(s))


def _walk_prose(lines: list[str]):
    """Shared walk: yield each line tagged 'keep' or 'wrap' (a continuation of the block above)."""
    in_fence = joinable = False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            joinable = False
            yield "keep", line
            continue
        if in_fence:
            joinable = False
            yield "keep", line
            continue
        s = line.strip()
        if not s:
            joinable = False
            yield "keep", line
            continue
        if len(line) - len(line.lstrip(" ")) >= 4 and not joinable:
            # An indented code block needs a blank line above it (CommonMark: it cannot interrupt a
            # paragraph), so an indented line directly under prose is a lazy continuation, not code.
            joinable = False
            yield "keep", line
            continue
        if _starts_block(line):
            joinable = bool(LIST_ITEM.match(line))      # a list item absorbs its own wraps
            yield "keep", line
            continue
        yield ("wrap" if joinable else "keep"), line
        joinable = not HARD_BREAK.search(line)


def find_hard_wraps(lines: list[str]) -> list[int]:
    """Indices of prose lines that merely continue the paragraph or list item above them."""
    return [i for i, (kind, _) in enumerate(_walk_prose(lines)) if kind == "wrap"]


def unwrap_prose(lines: list[str]) -> list[str]:
    """Join hard-wrapped continuations into the line above (idempotent)."""
    out: list[str] = []
    for kind, line in _walk_prose(lines):
        if kind == "wrap" and out:
            out[-1] = out[-1].rstrip() + " " + line.strip()
        else:
            out.append(line)
    return out


def iter_headings(text: str):
    """(line_no, text) for real ATX headings; fenced code is skipped so shell comments don't count."""
    in_fence = False
    for i, line in enumerate(text.split("\n")):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if m:
            yield i, m.group(1)


def github_anchor(h: str) -> str:
    """GitHub's heading id: drop punctuation, then replace EACH space with a hyphen (no collapsing)."""
    s = h.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    return s.replace(" ", "-") or "section"


def obsidian_anchor(h: str) -> str:
    """What the Obsidian `gfm-compatibility` plugin computes: whitespace runs collapse to ONE hyphen."""
    s = h.strip().lower()
    s = re.sub(r"[^\w\s\-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", "-", s) or "section"


_ANCHOR_CACHE: dict[str, set[str]] = {}


def anchors_of(path: str) -> set[str]:
    """Every anchor a file's headings produce, GitHub's algorithm incl. the -1/-2 dedup suffixes."""
    if path not in _ANCHOR_CACHE:
        got: set[str] = set()
        seen: dict[str, int] = {}
        for _, h in iter_headings(open(path, encoding="utf-8", errors="replace").read()):
            base = github_anchor(h)
            n = seen.get(base, 0)
            seen[base] = n + 1
            got.add(base if n == 0 else f"{base}-{n}")
        _ANCHOR_CACHE[path] = got
    return _ANCHOR_CACHE[path]


def check_heading_anchors() -> list[str]:
    """A heading must slugify identically on GitHub and in Obsidian, or one of the two breaks.

    The two disagree whenever punctuation sits *between spaces*: GitHub turns each space into a
    hyphen (`picture---remove` -> actually `picture--remove`), while the plugin collapses the run
    (one hyphen). Now that we write GitHub's slugs, a divergent heading means one tool cannot find
    it, so the fix is to avoid that punctuation in headings (`: ` or parentheses instead).
    """
    problems = []
    for f in sorted(glob.glob(os.path.join(REPO, "**", "*.md"), recursive=True)):
        if f"{os.sep}.git{os.sep}" in f:
            continue
        rel = os.path.relpath(f, REPO).replace(os.sep, "/")
        text = open(f, encoding="utf-8", errors="replace").read()
        for i, h in iter_headings(text):
            g, o = github_anchor(h), obsidian_anchor(h)
            if g != o:
                problems.append(
                    f"{rel}:{i+1} heading has different slugs in GitHub (#{g}) and Obsidian (#{o}) - "
                    f"avoid space-surrounded punctuation (em dash, spaced / & + = or arrows/emoji), "
                    f"prefer ': ' or parentheses: {h[:60]!r}"
                )
    return problems


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

    # prose wrapping: one line per paragraph (see the note above _starts_block)
    for i in find_hard_wraps(lines):
        problems.append(
            f"{rel}:{i+1} hard-wrapped prose -> join into the line above "
            f"(fix: `uv run python scripts/lint_docs.py --fix-wrapping`): {lines[i].strip()[:50]!r}"
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
# Contributor tooling = acts on the docs/tables, maintains OUR repo (the canonical fixture set, promotion
# into assets/), or is an *experiment probe* that reproduces a measurement rather than producing a user
# asset. Documented for contributors in AGENTS.md, so it is deliberately *not* a flow reachable from the
# README job table.
CONTRIBUTOR_TOOLS = {"lint_docs.py", "mdtable.py", "add_workflow_notes.py",
                     "gen_assets.py", "publish_assets.sh", "fix_workflow_links.py", "pose_probe.py",
                     "build_workflow.py", "check_workflows.py",
                     # the job/story/flow registry and its renderer+gate (see workflows/jobs.json)
                     "gen_job_docs.py", "check_job_docs.py",
                     # engine-import contract: check a GLB offline, and add the normals Hy3D drops
                     "check_gltf_contract.py", "fix_gltf_normals.py"}


def iter_flows():
    for pat in ("2d/workflows/*.json", "3d/workflows/*.json", "scripts/*"):
        for p in sorted(glob.glob(os.path.join(REPO, pat))):
            if os.path.isfile(p) and os.path.basename(p) not in CONTRIBUTOR_TOOLS:
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
            problems.append(f"{rel} is named nowhere in README.md (unreachable - a job row, or the "
                            f"'Not for end users' table for superseded/headless entries)")
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


def check_workflow_order() -> list[str]:
    """A workflow's commentary nodes (MarkdownNote/Note) must be outside the execution order.

    ComfyUI re-derives execution order from the link graph, so the `order` values themselves are only a
    saved hint - files do legitimately differ here (`pose-skeleton.json` ships every node at 0,
    `hy3d-full-workflow.json` repeats values, `outpaint.json` is dense) and all of them load. What is not
    safe is a commentary node *interleaved into* the execution order: `pbr-material.json` shipped with its
    MarkdownNote at `order: 13` among execution nodes 1..12, and the frontend then could not attribute the
    other nodes to a pack - it fell back to an install prompt naming the node types ("Unknown pack:
    MarigoldModelLoader ..."), which reads exactly like a missing pack, even though the nodes load fine and
    `/prompt` accepts the graph. All 25 other workflows put the note at order 0.

    Deliberately narrow: it asserts only what was actually observed to break frontend attribution, not a
    canonical numbering, because the frontend symptom is unreproducible from here (posting to /prompt
    bypasses the UI loader) and over-claiming would fail files that demonstrably work.
    """
    problems = []
    for p in sorted(glob.glob(os.path.join(REPO, "*", "workflows", "*.json"))):
        rel = os.path.relpath(p, REPO).replace(os.sep, "/")
        try:
            data = json.loads(open(p, encoding="utf-8").read())
        except Exception as exc:
            problems.append(f"{rel}: unreadable JSON ({exc})")
            continue
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            continue
        execs = [n for n in nodes if n.get("type") not in ("MarkdownNote", "Note")]
        for n in nodes:
            if n.get("type") not in ("MarkdownNote", "Note"):
                continue
            o = n.get("order")
            if isinstance(o, int) and o != 0:
                problems.append(
                    f"{rel}: {n.get('type')} node {n.get('id')} is numbered in the execution order "
                    f"(order {o}) - commentary nodes must not take an execution slot, or the frontend "
                    f"cannot attribute the workflow's nodes and offers them as an install prompt; set it to 0")
    return problems


def check_workflow_links() -> list[str]:
    """Every workflow's node link references must agree with its `links` array.

    ComfyUI wires from the array, so a stale reference is inert until it carries the wrong type -
    which is when the canvas errors ("Invalid connection"). Checked by fix_workflow_links so the
    gate and the repair tool cannot drift.
    """
    problems = []
    for p in fix_workflow_links.iter_curated():
        rel = os.path.relpath(p, REPO).replace(os.sep, "/")
        problems += fix_workflow_links.check_data(fix_workflow_links.load(p), rel)
    if problems:
        problems.append("workflow link refs disagree with the links array -> "
                        "run: uv run python scripts/fix_workflow_links.py --write")
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

    if "--fix-wrapping" in sys.argv:
        changed = 0
        for f in sorted(files):
            raw = open(f, "rb").read()
            if b"\x00" in raw:
                continue
            lines = raw.decode("utf-8", "replace").split("\n")
            fixed = unwrap_prose(lines)
            if fixed != lines:
                with open(f, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n".join(fixed))
                changed += 1
                print(f"  rewrapped {os.path.relpath(f, REPO)} "
                      f"({len(lines) - len(fixed)} line(s) joined)")
        print(f"rewrapped {changed} file(s)")
        return 0

    problems: list[str] = []
    for f in sorted(files):
        problems += lint_file(f, os.path.relpath(f, REPO))
    problems += check_flow_coverage()
    problems += check_flow_docs()
    problems += check_story_mapping()
    problems += check_job_docs.check()
    problems += check_heading_anchors()
    problems += check_workflow_links()
    problems += check_workflow_order()

    print(f"linted {len(files)} markdown file(s)")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  " + p)
        return 1
    print("no table, link, coverage, workflow-link or flow-doc problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
