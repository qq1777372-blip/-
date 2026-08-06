from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.routing import APIRoute

from main import app

SNAPSHOT_PATH = Path(__file__).with_name("route_snapshot.txt")


def collect_routes() -> list[str]:
    """Every HTTP route the app serves, as sorted "METHOD path" lines.

    HEAD and OPTIONS are dropped: Starlette adds them automatically, so they say
    nothing about what the code declares.
    """
    rows: set[str] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or []:
            if method in {"HEAD", "OPTIONS"}:
                continue
            rows.add(f"{method} {route.path}")
    return sorted(rows)


def read_snapshot() -> list[str]:
    lines = SNAPSHOT_PATH.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


class RouteContractTests(unittest.TestCase):
    def test_modular_routes_are_registered_once(self) -> None:
        paths = [route.path for route in app.routes]
        self.assertEqual(paths.count("/dashboard/server-status"), 1)
        self.assertEqual(paths.count("/health/live"), 1)
        self.assertEqual(paths.count("/health/ready"), 1)
        self.assertEqual(paths.count("/warehouse/summary"), 1)

    def test_no_method_and_path_is_registered_twice(self) -> None:
        """A duplicate means two handlers claim one URL and the first one wins.

        This is the failure mode when a route is moved into a router but the
        original is left behind in main.py -- the app still starts, and the stale
        handler keeps serving.
        """
        seen: dict[str, int] = {}
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods or []:
                if method in {"HEAD", "OPTIONS"}:
                    continue
                key = f"{method} {route.path}"
                seen[key] = seen.get(key, 0) + 1
        duplicates = sorted(key for key, count in seen.items() if count > 1)
        self.assertEqual(duplicates, [], f"routes registered more than once: {duplicates}")

    def test_routes_match_the_snapshot(self) -> None:
        """Pins all 212 URLs so a refactor cannot silently change the API surface.

        The frontends hardcode these paths and each dev server proxies them by
        prefix, so a moved route breaks a page with a 404 that only shows up
        locally -- nginx hides it in production.
        """
        current = collect_routes()
        expected = read_snapshot()
        missing = sorted(set(expected) - set(current))
        added = sorted(set(current) - set(expected))
        self.assertEqual(
            (missing, added),
            ([], []),
            "route surface changed.\n"
            f"  removed ({len(missing)}): {missing}\n"
            f"  added ({len(added)}): {added}\n"
            "If intended, regenerate: python tests/test_route_contract.py --update",
        )


def update_snapshot() -> int:
    rows = collect_routes()
    header = [
        '# Snapshot of every HTTP route main.py registers, as "METHOD path".',
        "#",
        "# This is a refactor safety net, not a design document: splitting main.py into",
        "# routers must not move, rename or drop a single path. If a change here is",
        "# intentional, regenerate with:",
        "#",
        "#   python tests/test_route_contract.py --update",
        "#",
        "# and review the diff -- an unexpected line means a URL the frontends call",
        "# just changed.",
    ]
    SNAPSHOT_PATH.write_text("\n".join(header + rows) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {SNAPSHOT_PATH} with {len(rows)} routes")
    return 0


if __name__ == "__main__":
    if "--update" in sys.argv:
        raise SystemExit(update_snapshot())
    unittest.main()
