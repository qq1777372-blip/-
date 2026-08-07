"""Plan one step of the main.py router split, and refuse to plan an unsafe one.

Splitting main.py is a multi-session job. Four things have to be checked before
any code moves, and each of them was a real bug the first time it was missed:

  * a domain's routes are NOT contiguous -- /task-bookkeeping spans 1276 lines
    with 34 other domains' routes inside it, so a single cut takes someone
    else's handler with it. Routes are therefore extracted per definition.
  * a helper reachable from a route that STAYS in main.py cannot move. The test
    for this is the transitive closure, not one level: build_task_bookkeeping_
    order_no is used by /global-search, and the two datetime helpers it calls
    are blocked by it in turn.
  * a moved catch-all (/ui/{path:path}) registers earlier than it used to,
    because include_router runs before the rest of main.py's decorators. It can
    then shadow a route that stayed. route_snapshot.txt compares the SET of
    paths and cannot see this.
  * every free name in the moved code must arrive as an import or a kwarg, or
    it is a NameError that only fires when that one handler runs -- which
    registering a route never does.

Usage (note MSYS2_ARG_CONV_EXCL: Git Bash rewrites a leading-slash argument
into a Windows path, which silently turns "/ui" into "D:/Program Files/Git/ui"):

  MSYS2_ARG_CONV_EXCL='*' python scripts/dev/split_scan.py /system-settings /ui-settings
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MAIN = ROOT / "main.py"
SNAPSHOT = ROOT / "tests" / "route_snapshot.txt"


def load_main() -> tuple[str, list[str], ast.Module]:
    # main.py carries a UTF-8 BOM; ast.parse rejects it as a non-printable
    # character. Stripping it does not shift line numbers -- the BOM sits before
    # line 1's first token.
    source = MAIN.read_text(encoding="utf-8").lstrip("\ufeff")
    return source, source.splitlines(), ast.parse(source)


def module_defs(tree: ast.Module) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def span_of(node: ast.AST) -> tuple[int, int]:
    """First line that must move through last. Decorators count."""
    start = node.lineno
    for dec in getattr(node, "decorator_list", []):
        start = min(start, dec.lineno)
    return start, node.end_lineno or node.lineno


def app_routes(tree: ast.Module) -> list[tuple[str, str, str, int, int]]:
    """(name, method, path, start, end) for every @app.<verb>(...) handler."""
    rows = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if getattr(dec.func.value, "id", None) != "app":
                continue
            verb = dec.func.attr.upper()
            if verb not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                continue
            first = dec.args[0] if dec.args else None
            # A non-literal path (DOCS_ROUTE and friends) is reported as None
            # rather than a shared "?" placeholder, which would make unrelated
            # routes look like duplicates of each other.
            path = first.value if isinstance(first, ast.Constant) else None
            start, end = span_of(node)
            rows.append((node.name, verb, path, start, end))
    return rows


def names_loaded(node: ast.AST) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }


def main() -> int:
    prefixes = [arg for arg in sys.argv[1:] if arg.startswith("/")]
    if not prefixes:
        raise SystemExit(__doc__)

    source, lines, tree = load_main()
    defs = module_defs(tree)
    routes = app_routes(tree)

    literal = [row for row in routes if row[2] is not None]
    pairs = [(row[1], row[2]) for row in literal]
    dupes = sorted({pair for pair in pairs if pairs.count(pair) > 1})
    if dupes:
        raise SystemExit(f"ABORT: main.py already has duplicate routes: {dupes}")

    print(f"main.py: {len(lines)} lines, parses OK, {len(routes)} @app routes")

    def in_batch(path: str | None) -> bool:
        return path is not None and any(
            path == prefix or path.startswith(prefix + "/") for prefix in prefixes
        )

    moving = [row for row in literal if in_batch(row[2])]
    staying = [row for row in literal if not in_batch(row[2])]
    if not moving:
        raise SystemExit(f"no routes match {prefixes}")

    print(f"\nbatch {prefixes}: {len(moving)} routes")
    for name, verb, path, start, end in sorted(moving, key=lambda row: row[3]):
        print(f"  {start:>6}-{end:<6} {verb:<7} {path:<44} {name}")

    # --- every moved path must already be in the snapshot, or the split is
    # inventing a URL rather than relocating one.
    snapshot = {
        line.strip()
        for line in SNAPSHOT.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    absent = [f"{verb} {path}" for _, verb, path, _, _ in moving if f"{verb} {path}" not in snapshot]
    print(f"\nall moved paths in snapshot: {not absent}")
    if absent:
        raise SystemExit(f"ABORT: not in snapshot: {absent}")

    # --- transitive closure: start from the moving routes, walk into helpers.
    moving_names = {row[0] for row in moving}
    reachable: set[str] = set()
    frontier = list(moving_names)
    while frontier:
        current = frontier.pop()
        node = defs.get(current)
        if node is None:
            continue
        for name in names_loaded(node):
            if name in defs and name not in reachable and name not in moving_names:
                reachable.add(name)
                frontier.append(name)

    staying_names = {row[0] for row in staying}

    # Routers already split out receive helpers from main.py as keyword
    # arguments, so main.py's own call sites are not the whole picture. Moving a
    # helper that an existing router still expects breaks that router instead of
    # main.py -- resolve_upload_file and image_file_response looked free here
    # while peer_shops.py was using both.
    external_users: dict[str, list[str]] = {}
    routes_dir = ROOT / "app" / "api" / "routes"
    for path in sorted(routes_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            other = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        used_there = {
            child.id
            for child in ast.walk(other)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
        }
        for name in used_there:
            external_users.setdefault(name, []).append(path.name)

    def users_of(target: str) -> list[str]:
        out = []
        for name, node in defs.items():
            if name == target or name in moving_names:
                continue
            if target in names_loaded(node):
                out.append(name)
        # Prefixed so the report shows which file blocks the move, and so these
        # can never be mistaken for a def inside main.py.
        out.extend(f"router:{filename}" for filename in external_users.get(target, []))
        return sorted(out)

    # A helper moves only if EVERY caller moves with it -- either a batch route
    # or another helper that is itself still movable.
    #
    # Start by assuming the whole closure can move, then demote until stable.
    # The earlier version asked the opposite question ("is any caller a staying
    # *route*?") and so missed the common case: a helper whose only callers are
    # other plain helpers that stay. parse_json_object was reported movable while
    # build_legacy_record_data, parse_record_values and
    # serialize_mobile_device_record all still called it -- moving it would have
    # been three NameErrors in main.py.
    blocked: dict[str, list[str]] = {}
    movable_set = set(reachable)
    changed = True
    while changed:
        changed = False
        for helper in sorted(movable_set):
            # users_of already drops the batch routes and the helper itself, so
            # whatever is left has to be inside movable_set or the helper stays.
            outside = [user for user in users_of(helper) if user not in movable_set]
            if outside:
                blocked[helper] = outside
                movable_set.discard(helper)
                changed = True

    movable = sorted(movable_set)

    print(f"\nCAN MOVE ({len(movable)} helpers):")
    for helper in movable:
        start, end = span_of(defs[helper])
        print(f"  {start:>6}-{end:<6} {helper}")

    print(f"\nMUST STAY -> pass as kwargs ({len(blocked)}):")
    for helper, users in sorted(blocked.items()):
        shown = ", ".join(users[:4]) + (" ..." if len(users) > 4 else "")
        print(f"  {helper:<42} blocked by: {shown}")

    # --- free names of everything that moves, split into what to import vs what
    # has to be a kwarg.
    moved_nodes = [defs[name] for name in sorted(moving_names | set(movable)) if name in defs]
    used: set[str] = set()
    for node in moved_nodes:
        used |= names_loaded(node)

    local = moving_names | set(movable)
    imported: set[str] = set()
    assigned: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imported.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            # Only the assignment TARGETS, never the value. Walking the whole
            # statement descends into comprehensions on the right-hand side and
            # reports their loop variables as module constants -- that is how
            # `value` (from a set comprehension on line 211) and `item` (from two
            # dict comprehensions on 407-408) turned up in an earlier kwarg list.
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                        assigned[child.id] = node.lineno

    kwarg_consts = sorted(
        (assigned[name], name) for name in used if name in assigned and name != "app"
    )
    kwarg_funcs = sorted(name for name in used if name in blocked)
    to_import = sorted(name for name in used if name in imported)

    print(f"\nFACTORY KWARGS -- constants ({len(kwarg_consts)}):")
    for line, name in kwarg_consts:
        print(f"  {line:>6}  {name}")
    print(f"\nFACTORY KWARGS -- functions ({len(kwarg_funcs)}):")
    for name in kwarg_funcs:
        print(f"          {name}")
    print(f"\nIMPORT IN NEW FILE ({len(to_import)}):")
    print("          " + ", ".join(to_import))

    if "app" in used:
        holders = [node.name for node in moved_nodes if "app" in names_loaded(node)]
        print(f"\n  note: 'app' referenced by {len(holders)} defs -- confirm these are")
        print("        only @app.<verb> decorators (mechanically rewritten to @router)")

    # --- shadowing: a moved catch-all now registers before everything left in
    # main.py.
    catch_alls = [(path, name) for name, _, path, _, _ in moving if path and "{path:path}" in path]
    if catch_alls:
        print("\nCATCH-ALL SHADOW CHECK:")
        for path, name in catch_alls:
            prefix = path.split("{")[0]
            hit = sorted({row[2] for row in staying if row[2] and row[2].startswith(prefix)})
            flag = "SHADOWS" if hit else "clear  "
            print(f"  {flag} {path:<32} staying routes under {prefix!r}: {len(hit)}")
            for path_hit in hit:
                print(f"      !! {path_hit}")
        if any(row[2].startswith(path.split("{")[0]) for path, _ in catch_alls for row in staying if row[2]):
            raise SystemExit("ABORT: a staying route would be shadowed")

    total = sum(span_of(node)[1] - span_of(node)[0] + 1 for node in moved_nodes)
    print(f"\n{len(moved_nodes)} defs to move, {total} source lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
