from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api.routes.health import create_health_router


class HealthRouterTests(unittest.TestCase):
    def test_ready_reports_database_and_frontend_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            (dist_dir / "version.json").write_text(
                json.dumps({"version": "test-version"}),
                encoding="utf-8",
            )
            app = FastAPI()
            app.include_router(
                create_health_router(
                    engine=create_engine("sqlite:///:memory:"),
                    frontend_dist_dir=dist_dir,
                ),
            )

            response = TestClient(app).get("/health/ready")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")
            self.assertEqual(
                response.json()["checks"]["frontend"]["version"],
                "test-version",
            )

    def test_ready_returns_503_when_frontend_build_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = FastAPI()
            app.include_router(
                create_health_router(
                    engine=create_engine("sqlite:///:memory:"),
                    frontend_dist_dir=Path(temp_dir),
                ),
            )

            response = TestClient(app).get("/health/ready")

            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["checks"]["frontend"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
