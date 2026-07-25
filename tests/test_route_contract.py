from __future__ import annotations

import unittest

from main import app


class RouteContractTests(unittest.TestCase):
    def test_modular_routes_are_registered_once(self) -> None:
        paths = [route.path for route in app.routes]
        self.assertEqual(paths.count("/dashboard/server-status"), 1)
        self.assertEqual(paths.count("/health/live"), 1)
        self.assertEqual(paths.count("/health/ready"), 1)


if __name__ == "__main__":
    unittest.main()
