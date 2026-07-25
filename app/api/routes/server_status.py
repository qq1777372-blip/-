from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Engine

from app.core.redis import cache_get_json, cache_set_json
from app.services.server_status import collect_server_status
from schemas import ServerStatusResponse


def create_server_status_router(
    *,
    engine: Engine,
    base_dir: Path,
    require_superadmin: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get(
        "/server-status",
        response_model=ServerStatusResponse,
        summary="Get server and database status",
    )
    def server_status(
        refresh: bool = False,
        _: Any = Depends(require_superadmin),
    ):
        cache_key = "dashboard:server-status"
        if not refresh:
            cached_payload = cache_get_json(cache_key)
            if isinstance(cached_payload, dict):
                return cached_payload

        payload = collect_server_status(
            engine=engine,
            base_dir=base_dir,
            database_roots=(
                ("后台主库", base_dir),
                ("授权库", Path("/opt/license_server/data")),
                ("钉钉机器人", Path("/opt/dingding-bot")),
            ),
            services=(
                ("fastapiproject", "后台服务"),
                ("nginx", "Nginx 网关"),
                ("license_server", "授权服务"),
                ("dingding-bot", "钉钉机器人"),
            ),
        )
        cache_set_json(cache_key, payload, ttl_seconds=30)
        return payload

    return router
