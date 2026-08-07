"""Generate a router file by moving code out of main.py verbatim.

Third of the three split tools:

  split_scan.py   -- decide what can move and what the factory needs
  split_build.py  -- this: write the new router file
  split_strip.py  -- delete the moved spans from main.py

Every moved line is copied byte-for-byte from main.py. The only edits are
mechanical: ``@app.<verb>`` becomes ``@router.<verb>`` and everything gains one
level of indentation so it sits inside the factory. Nothing is retyped, which is
what keeps the Chinese error strings in these handlers intact -- Git Bash renders
them as mojibake, so hand-copying from a terminal would corrupt them silently.

Helpers are nested inside the factory rather than left at module level: their
bodies reference main.py globals (UPLOADS_DIR, SYSTEM_FIELD_MAP, ...) that now
arrive as kwargs, and nesting lets them close over those names with the moved
code unchanged. Uppercase aliases restore the original spelling.

Driven by a JSON spec so each batch is data, not another throwaway script:

  {
    "target":  "app/api/routes/shop_records.py",
    "factory": "create_shop_records_router",
    "tags":    ["shop-records"],
    "docstring": "Shop records and the custom field definitions ...",
    "imports": [
      "from models import AdminUser, CustomField, ShopRecord",
      "from schemas import ShopRecordCreate, ShopRecordResponse"
    ],
    "stdlib": ["import re", "from typing import Any"],
    "kwargs": {
      "get_db": null,                        // plain kwarg
      "system_field_map": "SYSTEM_FIELD_MAP" // kwarg aliased to a global
    },
    "helpers": ["serialize_record", "get_field_or_404"],
    "routes":  ["list_fields", "create_shop_record"]
  }

Order inside the file follows main.py, not the spec: route registration order
decides which handler wins when two paths overlap, so reordering could silently
shadow a route. ``python split_build.py spec.json``
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MAIN = ROOT / "main.py"


def load_main() -> tuple[list[str], dict[str, ast.AST]]:
    # lstrip the BOM: main.py carries one and ast.parse rejects it as a
    # non-printable character. It sits before line 1, so line numbers survive.
    source = MAIN.read_text(encoding="utf-8").lstrip("﻿")
    tree = ast.parse(source)
    defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return source.splitlines(), defs


def span_of(node: ast.AST) -> tuple[int, int]:
    """First line that has to move .. last, decorators included."""
    start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
    return start, node.end_lineno


def indent(lines: list[str]) -> str:
    return "\n".join("    " + line if line.strip() else line for line in lines)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python split_build.py <spec.json>")
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    lines, defs = load_main()

    wanted = list(spec["helpers"]) + list(spec["routes"])
    missing = [name for name in wanted if name not in defs]
    if missing:
        raise SystemExit(f"not found at module level in main.py: {missing}")

    # --- header
    kwargs: dict[str, str | None] = spec["kwargs"]
    parts: list[str] = ['"""' + spec["docstring"] + '"""\n\nfrom __future__ import annotations\n\n']
    for line in spec.get("stdlib", []):
        parts.append(line + "\n")
    if spec.get("stdlib"):
        parts.append("\n")
    for line in spec["imports"]:
        parts.append(line + "\n")
    parts.append("\n\ndef " + spec["factory"] + "(\n    *,\n")
    for name in kwargs:
        parts.append(f"    {name},\n")
    parts.append(") -> APIRouter:\n")

    aliases = {alias: name for name, alias in kwargs.items() if alias}
    if aliases:
        parts.append(
            "    # The moved bodies still spell these as main.py globals. Aliasing here\n"
            "    # keeps the factory signature conventional while leaving every copied\n"
            "    # line untouched.\n"
        )
        for alias, name in aliases.items():
            parts.append(f"    {alias} = {name}\n")
        parts.append("\n")

    tags = json.dumps(spec.get("tags", []))
    parts.append(f"    router = APIRouter(tags={tags})\n\n")

    # --- bodies, in main.py order
    ordered = sorted(wanted, key=lambda name: span_of(defs[name])[0])
    swapped = 0
    moved_lines = 0
    for name in ordered:
        start, end = span_of(defs[name])
        body = lines[start - 1 : end]
        moved_lines += len(body)
        out = []
        for line in body:
            if line.startswith("@app."):
                line = "@router." + line[len("@app.") :]
                swapped += 1
            out.append(line)
        parts.append(indent(out))
        parts.append("\n\n")

    parts.append("    return router\n")

    target = ROOT / spec["target"]
    target.write_text("".join(parts), encoding="utf-8", newline="\n")

    written = target.read_text(encoding="utf-8")
    ast.parse(written)  # a generated file that cannot parse must not ship

    if swapped != len(spec["routes"]):
        raise SystemExit(
            f"rewrote {swapped} @app decorators but spec lists {len(spec['routes'])} routes"
        )
    if "@app." in written:
        raise SystemExit("an @app. reference survived -- would bind to the wrong object")

    print(f"wrote {spec['target']}: {len(written.splitlines())} lines, parses OK")
    print(f"  helpers {len(spec['helpers'])}, routes {swapped}, kwargs {len(kwargs)}")
    print(f"  source lines taken from main.py: {moved_lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
