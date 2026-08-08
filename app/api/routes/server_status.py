"""Server runtime status for the local machine and any reporting peers.

`collect_server_status` can only read the machine it runs on -- /proc, systemctl
and disk_usage are all local. To show a second box, that box runs
`scripts/ops/report_server_status.py`, which collects the same payload and POSTs
it to /dashboard/server-status/push. Reports land in one AppSetting row keyed by
node id; the GET merges them with a fresh local reading.

The response keeps the local machine's fields at the top level because the mobile
ServerPage reads them directly. `nodes` is additive and lists the whole fleet,
local node included, so new UI can iterate one array.
"""

from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.redis import cache_get_json, cache_set_json
from app.services.server_status import collect_server_status
from schemas import (
    ServerStatusPushRequest,
    ServerStatusPushResponse,
    ServerStatusResponse,
)

# One AppSetting row holds every reported node: {node_id: {label, reported_at,
# generated_at, metrics}}. A row per node would need a migration for what is
# cache-like data that any node rewrites on its next report.
SERVER_STATUS_NODES_KEY = "server_status_reported_nodes"


def _parse_node_specs(raw_value: str) -> list[tuple[str, str]]:
    """Parse `id:label,id:label` into pairs, tolerating a bare `id`.

    Listing the expected peers up front is what lets a node that has never
    reported (or stopped reporting) show as missing instead of silently not
    appearing at all.
    """
    specs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chunk in raw_value.split(","):
        entry = chunk.strip()
        if not entry:
            continue
        node_id, _, label = entry.partition(":")
        node_id = node_id.strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        specs.append((node_id, label.strip() or node_id))
    return specs


def _as_aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    # Reports cross machines, so a naive stamp would be compared against a local
    # aware one and blow up. Assume UTC for anything unlabelled.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def create_server_status_router(
    *,
    engine: Engine,
    base_dir: Path,
    require_superadmin: Callable[..., Any],
    get_db: Callable[..., Any],
    read_json_setting: Callable[[Session, str, Any], Any],
    write_json_setting: Callable[[Session, str, Any], None],
    commit_session: Callable[..., Any],
    node_id: str,
    node_label: str,
    remote_node_specs: str,
    push_token: str,
    stale_after_seconds: int,
) -> APIRouter:
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])
    expected_remote_nodes = _parse_node_specs(remote_node_specs)

    def collect_local_status() -> dict[str, Any]:
        return collect_server_status(
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

    def read_reported_nodes(db: Session) -> dict[str, Any]:
        stored = read_json_setting(db, SERVER_STATUS_NODES_KEY, {})
        return stored if isinstance(stored, dict) else {}

    def build_node_rows(db: Session, local_metrics: dict[str, Any]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        reported = read_reported_nodes(db)

        rows: list[dict[str, Any]] = [
            {
                "node_id": node_id,
                "label": node_label,
                "is_local": True,
                "state": "online",
                "reported_at": local_metrics["generated_at"],
                "age_seconds": 0,
                "message": None,
                "metrics": local_metrics,
            },
        ]

        # Configured peers first and in order, then anything that reported without
        # being listed -- a new agent should show up without a config change.
        ordered_ids = [entry[0] for entry in expected_remote_nodes]
        labels = dict(expected_remote_nodes)
        ordered_ids += sorted(key for key in reported if key not in labels and key != node_id)

        for remote_id in ordered_ids:
            entry = reported.get(remote_id)
            stored_label = entry.get("label") if isinstance(entry, dict) else None
            label = labels.get(remote_id) or stored_label or remote_id

            if not isinstance(entry, dict) or not isinstance(entry.get("metrics"), dict):
                rows.append({
                    "node_id": remote_id, "label": label, "is_local": False,
                    "state": "missing", "reported_at": None, "age_seconds": None,
                    "message": "尚未收到该服务器的上报数据", "metrics": None,
                })
                continue

            reported_at = _as_aware(entry.get("reported_at"))
            age = int((now - reported_at).total_seconds()) if reported_at else None
            # A stale report is kept on screen rather than dropped: last-known
            # numbers plus an explicit age is more useful than an empty card.
            is_stale = age is None or age > stale_after_seconds
            rows.append({
                "node_id": remote_id, "label": label, "is_local": False,
                "state": "stale" if is_stale else "online",
                "reported_at": reported_at,
                "age_seconds": age,
                "message": f"数据已超过 {stale_after_seconds} 秒未更新" if is_stale else None,
                "metrics": entry["metrics"],
            })

        return rows

    @router.get(
        "/server-status",
        response_model=ServerStatusResponse,
        summary="Get server and database status",
    )
    def server_status(
        refresh: bool = False,
        db: Session = Depends(get_db),
        _: Any = Depends(require_superadmin),
    ):
        cache_key = "dashboard:server-status"
        payload: dict[str, Any] | None = None
        if not refresh:
            cached_payload = cache_get_json(cache_key)
            if isinstance(cached_payload, dict):
                payload = cached_payload
        if payload is None:
            payload = collect_local_status()
            cache_set_json(cache_key, payload, ttl_seconds=30)

        # Node rows are assembled outside the cache: a peer report that arrives
        # during the 30s window should not wait for the local reading to expire.
        return {**payload, "nodes": build_node_rows(db, payload)}

    def require_push_token(
        token: str | None = Header(default=None, alias="X-Server-Status-Token"),
    ) -> None:
        if not push_token:
            raise HTTPException(status_code=503, detail="Server status push token is not configured")
        if not token or not hmac.compare_digest(token, push_token):
            raise HTTPException(status_code=401, detail="Invalid server status token")

    @router.post(
        "/server-status/push",
        response_model=ServerStatusPushResponse,
        summary="Internal: receive a server status report from another machine",
    )
    def push_server_status(
        payload: ServerStatusPushRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_push_token),
    ):
        if payload.node_id == node_id:
            raise HTTPException(status_code=409, detail="node_id collides with the local node")

        accepted_at = datetime.now(timezone.utc)
        label = payload.label or dict(expected_remote_nodes).get(payload.node_id) or payload.node_id
        nodes = read_reported_nodes(db)
        # mode="json" so datetimes inside metrics survive the AppSetting round trip.
        nodes[payload.node_id] = {
            "label": label,
            "reported_at": accepted_at.isoformat(),
            "metrics": json.loads(payload.metrics.model_dump_json()),
        }
        write_json_setting(db, SERVER_STATUS_NODES_KEY, nodes)
        commit_session(db, default_detail="服务器状态上报保存失败")
        return {"node_id": payload.node_id, "label": label, "accepted_at": accepted_at}

    return router
