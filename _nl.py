from __future__ import annotations
import ast
from pathlib import Path
src = Path("main.py").read_text(encoding="utf-8").lstrip("﻿")
tree = ast.parse(src)
lines = src.splitlines()
for node in tree.body:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
            continue
        if getattr(dec.func.value, "id", None) != "app":
            continue
        lit = dec.args and isinstance(dec.args[0], ast.Constant)
        if not lit:
            print(f"{dec.lineno}-{node.end_lineno}  {dec.func.attr.upper():<7} {node.name}")
            for i in range(dec.lineno - 1, min(dec.lineno + 6, node.end_lineno)):
                print(f"    {i+1}: {lines[i]}")
            print()
