"""Find names a generated router file uses but never defines.

The moved handler bodies came out of main.py, where every helper and constant was
a module global. In the new file each of those names must arrive one of three
ways: imported at the top, passed into the factory as a kwarg, or bound inside
the factory. Anything else is a NameError that fires only when that one handler
runs -- and registering a route never runs its body, so the route-contract test
cannot see it.

Known limitation, and the direction matters: names bound anywhere in the factory
subtree count as defined, so a name assigned in handler A and read in handler B
passes. That under-reports rather than false-alarms. Validate with a negative
control before trusting a clean result -- inject an undefined name and confirm
this exits 1:

  python scripts/dev/check_freenames.py app/api/routes/settings.py
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path


def bound_names(node: ast.AST) -> set[str]:
    """Every name this subtree binds, by any means Python offers."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            names.add(child.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(child.name)
        elif isinstance(child, ast.arg):
            names.add(child.arg)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            names.add(child.name)
        elif isinstance(child, ast.alias):
            names.add((child.asname or child.name).split(".")[0])
        elif isinstance(child, ast.Global):
            names.update(child.names)
    return names


def module_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                        names.add(child.id)
    return names


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    target = Path(sys.argv[1])
    if not target.is_file():
        raise SystemExit(f"no such file: {target}")

    source = target.read_text(encoding="utf-8")
    tree = ast.parse(source)

    factories = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("create_")
    ]
    if len(factories) != 1:
        raise SystemExit(f"expected exactly one create_* factory, found {len(factories)}")
    factory = factories[0]

    kwargs = {arg.arg for arg in factory.args.kwonlyargs} | {arg.arg for arg in factory.args.args}
    known = module_level_names(tree) | kwargs | bound_names(factory) | set(dir(builtins))

    used: dict[str, int] = {}
    for child in ast.walk(factory):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            used.setdefault(child.id, child.lineno)

    unknown = {name: line for name, line in used.items() if name not in known}

    print(f"{target.name}")
    print(f"  factory      : {factory.name}")
    print(f"  kwargs       : {len(kwargs)}")
    print(f"  names loaded : {len(used)}")
    if unknown:
        print(f"\n  UNDEFINED ({len(unknown)}) -- each is a latent NameError:")
        for name, line in sorted(unknown.items(), key=lambda item: item[1]):
            print(f"    line {line:>5}  {name}")
        return 1
    print("\n  no undefined names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
