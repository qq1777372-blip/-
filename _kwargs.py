"""List every main.py module-level name a set of defs references.

That set is exactly the factory signature: anything the moved code loads that
main.py owns, and that is not a builtin, not bound locally, and not one of the
defs moving with it.
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

MAIN = Path("main.py")
NAMES = [
    # helpers that move
    "frontend_index_response", "frontend_ui_response", "app_frontend_index_response",
    "app_frontend_response", "is_bare_mobile_webview", "mobile_app_upgrade_redirect",
    "build_login_redirect_url", "tutorials_index_response", "tutorials_site_response",
    # routes that move
    "shop_record_page", "license_page", "vue_ui_root", "legacy_mobile_app_root",
    "legacy_mobile_app_page", "vue_ui_page", "mobile_app_root", "mobile_app_page",
    "company_expenses_app_redirect", "company_expenses_app", "tutorials_root",
    "tutorials_index", "tutorials_page", "login_page", "register_page",
]


def bound(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for c in ast.walk(node):
        if isinstance(c, ast.Name) and isinstance(c.ctx, (ast.Store, ast.Del)):
            out.add(c.id)
        elif isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(c.name)
        elif isinstance(c, ast.arg):
            out.add(c.arg)
        elif isinstance(c, ast.ExceptHandler) and c.name:
            out.add(c.name)
        elif isinstance(c, ast.alias):
            out.add((c.asname or c.name).split(".")[0])
    return out


src = MAIN.read_text(encoding="utf-8").lstrip("﻿")
tree = ast.parse(src)

imported: set[str] = set()
classes: set[str] = set()
assigned: dict[str, int] = {}
funcs: dict[str, ast.AST] = {}
for n in tree.body:
    if isinstance(n, (ast.Import, ast.ImportFrom)):
        for a in n.names:
            imported.add((a.asname or a.name).split(".")[0])
    elif isinstance(n, ast.ClassDef):
        classes.add(n.name)
    elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        funcs[n.name] = n
    elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        for c in ast.walk(n):
            if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Store):
                assigned.setdefault(c.id, n.lineno)

missing = [x for x in NAMES if x not in funcs]
if missing:
    raise SystemExit(f"not found at module level: {missing}")

moving = set(NAMES)
bi = set(dir(builtins))

needed_consts: dict[str, int] = {}
needed_funcs: set[str] = set()
needed_imports: set[str] = set()
needed_classes: set[str] = set()

for name in NAMES:
    node = funcs[name]
    local = bound(node)
    for c in ast.walk(node):
        if not (isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load)):
            continue
        n = c.id
        if n in bi or n in local or n in moving:
            continue
        if n in assigned:
            needed_consts[n] = assigned[n]
        elif n in funcs:
            needed_funcs.add(n)
        elif n in imported:
            needed_imports.add(n)
        elif n in classes:
            needed_classes.add(n)
        else:
            print(f"  ?? unresolved: {n} (in {name})")

print("MODULE CONSTANTS -> factory kwargs:")
for n, line in sorted(needed_consts.items(), key=lambda kv: kv[1]):
    print(f"  {line:>6}  {n}")
print(f"\nMAIN.PY FUNCTIONS -> factory kwargs ({len(needed_funcs)}):")
for n in sorted(needed_funcs):
    print(f"          {n}")
print(f"\nIMPORTS -> import directly in the new file ({len(needed_imports)}):")
print("         ", ", ".join(sorted(needed_imports)))
if needed_classes:
    print(f"\nCLASSES: {sorted(needed_classes)}")
print(f"\ntotal kwargs: {len(needed_consts) + len(needed_funcs)}")
