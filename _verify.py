from __future__ import annotations
import ast
from pathlib import Path

MOVING = {
    "frontend_index_response", "frontend_ui_response", "app_frontend_index_response",
    "app_frontend_response", "is_bare_mobile_webview", "mobile_app_upgrade_redirect",
    "build_login_redirect_url", "tutorials_index_response", "tutorials_site_response",
    "shop_record_page", "license_page", "vue_ui_root", "legacy_mobile_app_root",
    "legacy_mobile_app_page", "vue_ui_page", "mobile_app_root", "mobile_app_page",
    "company_expenses_app_redirect", "company_expenses_app", "tutorials_root",
    "tutorials_index", "tutorials_page", "login_page", "register_page",
}
HELPERS = {
    "frontend_index_response", "frontend_ui_response", "app_frontend_index_response",
    "app_frontend_response", "is_bare_mobile_webview", "mobile_app_upgrade_redirect",
    "build_login_redirect_url", "tutorials_index_response", "tutorials_site_response",
}

src = Path("main.py").read_text(encoding="utf-8").lstrip("﻿")
tree = ast.parse(src)

# who calls each helper, among defs that are NOT moving
callers: dict[str, set[str]] = {h: set() for h in HELPERS}
for n in tree.body:
    if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    if n.name in MOVING:
        continue
    for c in ast.walk(n):
        if isinstance(c, ast.Name) and c.id in HELPERS and isinstance(c.ctx, ast.Load):
            callers[c.id].add(n.name)

# also check module-level code (outside any function) and lifespan
toplevel: dict[str, list[int]] = {h: [] for h in HELPERS}
for n in tree.body:
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        continue
    for c in ast.walk(n):
        if isinstance(c, ast.Name) and c.id in HELPERS and isinstance(c.ctx, ast.Load):
            toplevel[c.id].append(c.lineno)

blocked = False
for h in sorted(HELPERS):
    ext = sorted(callers[h])
    tl = toplevel[h]
    if ext or tl:
        blocked = True
        print(f"BLOCKED  {h}")
        if ext:
            print(f"           external callers: {ext}")
        if tl:
            print(f"           module-level refs at lines: {tl}")
    else:
        print(f"ok       {h}")

print()
print("VERDICT:", "some helpers are shared -- do not move them" if blocked else "all 9 helpers are exclusive to this batch")
