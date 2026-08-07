"""Independent check of split_scan's CAN MOVE verdict.

Deliberately not sharing code with split_scan.py: that tool has been wrong
twice (once on the closure rule, once by ignoring already-extracted routers),
and a second implementation is the only way to catch a third mistake.
"""
from __future__ import annotations
import ast, re
from pathlib import Path

ROOT = Path(".")
BATCH_ROUTES = {
    "list_fields", "create_field_definition", "update_field_definition",
    "reorder_field_definitions", "delete_field_definition",
    "create_shop_record", "list_shop_records", "get_shop_record",
    "update_shop_record", "delete_shop_record", "batch_delete_shop_records",
}
CLAIMED_MOVABLE = {
    "build_field_name", "get_field_or_404", "get_shop_record_or_404",
    "is_empty_value", "list_field_definitions", "normalize_field_value",
    "serialize_record", "sync_legacy_columns", "validate_record_values",
}

src = Path("main.py").read_text(encoding="utf-8").lstrip("﻿")
tree = ast.parse(src)
defs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

def loads(node):
    return {c.id for c in ast.walk(node) if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load)}

moving = BATCH_ROUTES | CLAIMED_MOVABLE
bad = []
for helper in sorted(CLAIMED_MOVABLE):
    callers = sorted(n for n, node in defs.items() if n != helper and helper in loads(node))
    outside = [c for c in callers if c not in moving]
    # already-extracted routers are a separate namespace: they receive helpers
    # as kwargs from main.py, so a hit there also blocks the move.
    in_routers = [
        p.name for p in sorted((ROOT / "app/api/routes").glob("*.py"))
        if re.search(rf"\b{re.escape(helper)}\b", p.read_text(encoding="utf-8"))
    ]
    verdict = "MOVE" if not outside and not in_routers else "BLOCKED"
    if verdict == "BLOCKED":
        bad.append(helper)
    print(f"  {verdict:<8} {helper:<26} callers={len(callers)} outside={outside or '-'} routers={in_routers or '-'}")

print(f"\nagrees with split_scan: {not bad}" + (f"  disagreement: {bad}" if bad else ""))
