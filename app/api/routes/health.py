from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine


def read_build_version(dist_dir: Path) -> dict[str, Any]:
    """Report the version.json a deployed build left behind.

    Missing or unparsable means the deploy did not finish, so it is an error and
    not an "unknown" version: a release that cannot prove which build is live is
    exactly what the readiness probe exists to catch.
    """
    try:
        payload = json.loads((dist_dir / "version.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "detail": type(exc).__name__}
    return {"status": "ok", "version": str(payload.get("version", "unknown"))}


def create_health_router(
    *,
    engine: Engine,
    frontend_dist_dir: Path,
    app_dist_dir: Path | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live", summary="Process liveness probe")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready", summary="Application readiness probe")
    def readiness() -> Any:
        started_at = time.perf_counter()
        checks: dict[str, dict[str, Any]] = {}

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["database"] = {"status": "ok"}
        except Exception as exc:
            checks["database"] = {"status": "error", "detail": type(exc).__name__}

        checks["frontend"] = read_build_version(frontend_dist_dir)
        # The mobile App ships on its own cadence, so its build is reported as a
        # separate check. Only wired up when a dist dir is supplied, which keeps
        # callers that serve no App unaffected.
        if app_dist_dir is not None:
            checks["app"] = read_build_version(app_dist_dir)

        ready = all(check["status"] == "ok" for check in checks.values())
        payload = {
            "status": "ok" if ready else "error",
            "checks": checks,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        }
        if ready:
            return payload
        return JSONResponse(status_code=503, content=payload)

    return router
