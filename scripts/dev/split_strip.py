"""Delete a batch of module-level defs from main.py after a router has taken them.

Takes the names on the command line, looks each one up through the AST, and
deletes highest line first so an earlier cut cannot shift a span still to be
removed. Nothing is written unless all of these hold:

  * every name exists exactly once at module level
  * no two spans overlap
  * no remaining line still mentions a deleted name
  * the result parses

A partial strip is the dangerous outcome: main.py keeps a stale handler, the app
still starts, and both it and the router claim the same URL -- with the original
winning, because it registered first. The duplicate-route test is the only thing
that catches it.

  python scripts/dev/split_strip.py serialize_audit_log list_audit_logs ...
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parent.parent.parent / "main.py"
BOM = "﻿"


def span_of(node: ast.AST) -> tuple[int, int]:
    """1-based inclusive line span, decorators included."""
    start = node.lineno
    for dec in getattr(node, "decorator_list", []):
        start = min(start, dec.lineno)
    return start, node.end_lineno or node.lineno


def main() -> int:
    names = sys.argv[1:]
    if not names:
        raise SystemExit(__doc__)

    raw = MAIN.read_text(encoding="utf-8")
    had_bom = raw.startswith(BOM)
    source = raw[len(BOM) :] if had_bom else raw
    lines = source.splitlines()
    tree = ast.parse(source)

    spans: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in names:
            continue
        if node.name in spans:
            raise SystemExit(f"ABORT: {node.name} defined twice at module level")
        spans[node.name] = span_of(node)

    missing = [name for name in names if name not in spans]
    if missing:
        raise SystemExit(f"ABORT: not found at module level: {missing}")

    ordered = sorted(spans.values())
    for (_, end), (start, _) in zip(ordered, ordered[1:]):
        if start <= end:
            raise SystemExit(f"ABORT: overlapping spans near line {start}")

    before = len(lines)
    removed = 0
    for start, end in sorted(spans.values(), reverse=True):
        del lines[start - 1 : end]
        removed += end - start + 1

    text = "\n".join(lines).rstrip("\n") + "\n"
    # Cutting a def out from between two others leaves four or more newlines.
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    stale = sorted(name for name in names if re.search(rf"\b{re.escape(name)}\b", text))
    if stale:
        raise SystemExit(f"ABORT: still referenced after strip: {stale}")

    ast.parse(text)
    MAIN.write_text((BOM if had_bom else "") + text, encoding="utf-8", newline="\n")

    print(f"removed {removed} lines across {len(spans)} defs")
    print(f"main.py: {before} -> {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
