#!/usr/bin/env python3
"""Table-aware markdown handling, built on an AST (markdown-it-py) rather than string splitting.

**Why this exists.** Five separate documentation bugs came from treating tables as plain text:
a NUL placeholder that was never restored (which made the file *binary*, so its git diff became
invisible), a separator row mistaken for a header (which silently dropped a row), escaped pipes
(`\\|`) confusing naive splitting, a literal newline splitting a row in half, and tables that
interrupted a paragraph. Parsing fixes the class: the parser hands us each cell's *content* with
escapes already decoded, so emitting only has to re-escape.

**Design choice: the AST is for reading, not for reformatting.** A general formatter
(`mdformat`/pandoc) would also rewrite our house style — turning `---` into `______`, renumbering
ordered lists, re-wrapping prose — which is a 26-file diff and a stylistic regression. So this
module parses with markdown-it and *renders in our style* (space-padded cells, `---` separators,
`\\|` escapes, `<br>` for in-cell breaks).

**Proving it.** `--self-test` round-trips every table in the repo: parse -> render -> parse, and
asserts the header and every cell are byte-identical. If our content ever contains a construct the
renderer does not preserve, the self-test fails loudly rather than silently corrupting a file.

Usage:
    uv run python scripts/mdtable.py --self-test
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

from markdown_it import MarkdownIt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# commonmark + the two GFM extras we actually use. Deliberately NOT the "gfm-like" preset:
# that enables linkify, which needs another package (linkify-it-py) for a feature our docs
# do not use (auto-linking bare URLs).
MD = MarkdownIt("commonmark").enable(["table", "strikethrough"])


# --------------------------------------------------------------------------- AST -> markdown
def inline_to_md(tok) -> str:
    """Render an inline token's children back to markdown (the constructs our docs use)."""
    out: list[str] = []
    hrefs: list[str] = []
    for c in tok.children or []:
        t = c.type
        if t == "text":
            out.append(c.content)
        elif t == "code_inline":
            out.append("`" + c.content + "`")
        elif t in ("strong_open", "strong_close"):
            out.append("**")
        elif t in ("em_open", "em_close"):
            out.append("*")
        elif t in ("s_open", "s_close"):
            out.append("~~")
        elif t == "link_open":
            hrefs.append(c.attrGet("href") or "")
            out.append("[")
        elif t == "link_close":
            out.append("](" + (hrefs.pop() if hrefs else "") + ")")
        elif t == "image":
            out.append(f"![{c.content}]({c.attrGet('src') or ''})")
        elif t == "softbreak":
            out.append(" ")
        elif t == "hardbreak":
            out.append("<br>")
        elif t in ("html_inline", "html_block"):
            out.append(c.content)
        elif c.children:
            out.append(inline_to_md(c))
        else:
            out.append(c.content)
    return "".join(out).strip()


class Table:
    def __init__(self, start: int, end: int, header: list[str], rows: list[list[str]]):
        self.start, self.end = start, end      # line indices into the source
        self.header, self.rows = header, rows

    def __repr__(self) -> str:
        return f"Table(lines {self.start}-{self.end}, {len(self.header)} cols, {len(self.rows)} rows)"


def parse(text: str) -> list[Table]:
    """Return every table in `text`, with cell *content* and the line span it occupies."""
    toks = MD.parse(text)
    out: list[Table] = []
    start: int | None = None
    end: int | None = None
    collected: list[list[str]] = []   # all rows, header first
    row: list[str] | None = None
    for t in toks:
        if t.type == "table_open":
            # `map` = [start_line, end_line) of the whole table: markdown-it sets it on the
            # OPEN token, not on the close (where it is None) - reading it from close gave an
            # empty span and made every row look like it sat outside a table.
            start, end = (int(t.map[0]), int(t.map[1])) if t.map else (0, 0)
            collected, row = [], None
        elif t.type == "table_close":
            if collected:
                out.append(Table(start or 0, end or 0, collected[0], collected[1:]))
            start = end = None
            collected, row = [], None
        elif t.type == "tr_open":
            row = []
        elif t.type == "tr_close":
            if row is not None:
                collected.append(row)
            row = None
        elif t.type == "inline" and row is not None:
            row.append(inline_to_md(t))
    return out


def render(header: list[str], rows: list[list[str]], aligns: list[str] | None = None) -> list[str]:
    """Render a pipe table in this repo's style (padded cells, `---` separator, escaped pipes)."""
    n = len(header)
    aligns = aligns or ["---"] * n
    body = [[_escape(c) for c in r] + [""] * (n - len(r)) for r in rows]
    head = [_escape(c) for c in header]
    widths = [max(len(head[k]), *(len(r[k]) for r in body)) if body else len(head[k]) for k in range(n)]
    out = ["| " + " | ".join(head[k].ljust(widths[k]) for k in range(n)) + " |"]
    out.append("|" + "|".join("-" * (widths[k] + 2) for k in range(n)) + "|")
    out += ["| " + " | ".join(r[k].ljust(widths[k]) for k in range(n)) + " |" for r in body]
    return out


def _escape(cell: str) -> str:
    return cell.replace("\n", "<br>").replace("|", "\\|")


# --------------------------------------------------------------------------- helpers
def find(text: str, first_cell_contains: str) -> Table | None:
    for t in parse(text):
        if t.header and first_cell_contains in t.header[0]:
            return t
    return None


def replace(text: str, table: Table, header: list[str], rows: list[list[str]]) -> str:
    """Swap a table's block for freshly rendered lines, preserving everything around it."""
    lines = text.split("\n")
    new = render(header, rows)
    return "\n".join(lines[: table.start] + new + lines[table.end:])


def add_column(text: str, first_cell_contains: str, name: str, value_by_key, key_index: int = 0) -> str:
    """Append a column, deriving each cell from `value_by_key(cell at key_index)`."""
    t = find(text, first_cell_contains)
    if t is None:
        raise SystemExit(f"no table whose first header cell contains {first_cell_contains!r}")
    if name in t.header:
        raise SystemExit(f"column {name!r} already present")
    rows = [r + [value_by_key(r[key_index])] for r in t.rows]
    return replace(text, t, t.header + [name], rows)


# --------------------------------------------------------------------------- self-test
def self_test() -> int:
    files = [p for p in glob.glob(os.path.join(REPO, "**", "*.md"), recursive=True)
             if f"{os.sep}.git{os.sep}" not in p]
    checked = fails = 0
    for p in sorted(files):
        rel = os.path.relpath(p, REPO).replace(os.sep, "/")
        text = open(p, encoding="utf-8").read()
        for tb in parse(text):
            checked += 1
            round_tripped = "\n".join(render(tb.header, tb.rows))
            again = parse(round_tripped)
            if not again:
                print(f"  FAIL {rel}: table at line {tb.start+1} did not re-parse")
                fails += 1
                continue
            r2 = again[0]
            if r2.header != tb.header:
                print(f"  FAIL {rel}:{tb.start+1} header changed")
                print(f"        before: {tb.header}")
                print(f"        after : {r2.header}")
                fails += 1
            elif r2.rows != tb.rows:
                for i, (a, b) in enumerate(zip(tb.rows, r2.rows)):
                    if a != b:
                        print(f"  FAIL {rel}:{tb.start+1} row {i} changed")
                        for k, (x, y) in enumerate(zip(a, b)):
                            if x != y:
                                print(f"        col {k}: {x!r}")
                                print(f"           ->  {y!r}")
                        break
                else:
                    print(f"  FAIL {rel}:{tb.start+1} row count {len(tb.rows)} -> {len(r2.rows)}")
                fails += 1
    print(f"self-test: {checked} table(s) round-tripped across {len(files)} file(s); {fails} failure(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
