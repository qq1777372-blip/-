from __future__ import annotations
import ast
from pathlib import Path

NAMES = [
    "frontend_index_response", "frontend_ui_response", "app_frontend_index_response",
    "app_frontend_response", "is_bare_mobile_webview", "mobile_app_upgrade_redirect",
    "build_login_redirect_url", "tutorials_index_response", "tutorials_site_response",
    "shop_record_page", "license_page", "vue_ui_root", "legacy_mobile_app_root",
    "legacy_mobile_app_page", "vue_ui_page", "mobile_app_root", "mobile_app_page",
    "company_expenses_app_redirect", "company_expenses_app", "tutorials_root",
    "tutorials_index", "tutorials_page", "login_page", "register_page",
]

src = Path("main.py").read_text(encoding="utf-8").lstrip("﻿")
lines = src.splitlines()
tree = ast.parse(src)

for n in tree.body:
    if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) or n.name not in NAMES:
        continue
    for c in ast.walk(n):
        if isinstance(c, ast.Name) and c.id == "app" and isinstance(c.ctx, ast.Load):
            print(f"{n.name}  line {c.lineno}:")
            print(f"    {lines[c.lineno - 1].strip()}")
