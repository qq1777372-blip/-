from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine


def create_health_router(*, engine: Engine, frontend_dist_dir: Path) -> APIRouter:
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

        version_file = frontend_dist_dir / "version.json"
        try:
            version_payload = json.loads(version_file.read_text(encoding="utf-8"))
            checks["frontend"] = {
                "status": "ok",
                "version": str(version_payload.get("version", "unknown")),
            }
        except (OSError, json.JSONDecodeError) as exc:
            checks["frontend"] = {"status": "error", "detail": type(exc).__name__}

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
