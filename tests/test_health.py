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

    def test_ready_reports_app_version_when_app_dist_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as web_dir, tempfile.TemporaryDirectory() as app_dir:
            (Path(web_dir) / "version.json").write_text(
                json.dumps({"version": "web-1"}),
                encoding="utf-8",
            )
            (Path(app_dir) / "version.json").write_text(
                json.dumps({"version": "0.8.46-alpha"}),
                encoding="utf-8",
            )
            app = FastAPI()
            app.include_router(
                create_health_router(
                    engine=create_engine("sqlite:///:memory:"),
                    frontend_dist_dir=Path(web_dir),
                    app_dist_dir=Path(app_dir),
                ),
            )

            response = TestClient(app).get("/health/ready")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["checks"]["app"]["version"], "0.8.46-alpha")
            self.assertEqual(response.json()["checks"]["frontend"]["version"], "web-1")

    def test_ready_returns_503_when_only_the_app_build_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as web_dir, tempfile.TemporaryDirectory() as app_dir:
            (Path(web_dir) / "version.json").write_text(
                json.dumps({"version": "web-1"}),
                encoding="utf-8",
            )
            app = FastAPI()
            app.include_router(
                create_health_router(
                    engine=create_engine("sqlite:///:memory:"),
                    frontend_dist_dir=Path(web_dir),
                    app_dist_dir=Path(app_dir),
                ),
            )

            response = TestClient(app).get("/health/ready")

            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["checks"]["frontend"]["status"], "ok")
            self.assertEqual(response.json()["checks"]["app"]["status"], "error")

    def test_ready_omits_app_check_when_no_app_dist_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as web_dir:
            (Path(web_dir) / "version.json").write_text(
                json.dumps({"version": "web-1"}),
                encoding="utf-8",
            )
            app = FastAPI()
            app.include_router(
                create_health_router(
                    engine=create_engine("sqlite:///:memory:"),
                    frontend_dist_dir=Path(web_dir),
                ),
            )

            response = TestClient(app).get("/health/ready")

            self.assertEqual(response.status_code, 200)
            self.assertNotIn("app", response.json()["checks"])


if __name__ == "__main__":
    unittest.main()
