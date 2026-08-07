"""System settings, UI table settings, system alerts, and the audit log feed.

Moved out of main.py unchanged. Every handler keeps its absolute path (the router
declares no prefix) so the URL surface is byte-identical -- see
tests/route_snapshot.txt.

Shared helpers arrive as keyword arguments rather than imports: main.py owns them
and importing from it here would be a cycle. Only serialize_audit_log moved --
the rest are reachable from handlers that stayed behind.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AdminUser, AppSetting, AuditLog
from schemas import (
    AuditLogResponse,
    SystemAlertListResponse,
    SystemAlertStatusRequest,
    SystemSettingsResponse,
)


def create_settings_router(
    *,
    get_db,
    require_role,
    commit_session,
    write_audit_log,
    parse_json_object,
    get_setting,
    read_json_setting,
    write_json_setting,
    get_system_settings,
    build_system_alerts,
    system_settings_key: str,
    system_alert_ack_key: str,
    ui_table_setting_keys,
) -> APIRouter:
    # The moved bodies read these three as module constants. Aliasing keeps the
    # factory signature lowercase without editing a line of the moved code.
    SYSTEM_SETTINGS_KEY = system_settings_key
    SYSTEM_ALERT_ACK_KEY = system_alert_ack_key
    UI_TABLE_SETTING_KEYS = ui_table_setting_keys

    router = APIRouter(tags=["settings"])

    def serialize_audit_log(record: AuditLog) -> dict[str, Any]:
        return {
            "id": record.id,
            "actor_user_id": record.actor_user_id,
            "actor_username": record.actor_username,
            "action": record.action,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "details": parse_json_object(record.details_json),
            "created_at": record.created_at,
        }

    @router.get(
        "/audit-logs",
        response_model=list[AuditLogResponse],
        summary="List security and operation audit logs",
    )
    def list_audit_logs(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(500)
        return [serialize_audit_log(record) for record in db.scalars(stmt).all()]

    @router.get("/system-alerts", response_model=SystemAlertListResponse, summary="List current system alerts")
    def list_system_alerts(
        category: str | None = None,
        status_filter: str = "all",
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        all_items = build_system_alerts(db)
        items = [item for item in all_items if not category or item["category"] == category]
        if status_filter == "open": items = [item for item in items if not item["acknowledged"]]
        if status_filter == "acknowledged": items = [item for item in items if item["acknowledged"]]
        return {
            "total": len(items),
            "open_count": sum(not item["acknowledged"] for item in all_items),
            "acknowledged_count": sum(item["acknowledged"] for item in all_items),
            "critical_count": sum(not item["acknowledged"] and item["severity"] == "critical" for item in all_items),
            "items": items,
        }

    @router.patch("/system-alerts/{alert_key:path}", response_model=SystemAlertListResponse, summary="Acknowledge or reopen an alert")
    def update_system_alert_status(
        alert_key: str,
        payload: SystemAlertStatusRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        active_keys = {item["key"] for item in build_system_alerts(db)}
        if alert_key not in active_keys:
            raise HTTPException(status_code=404, detail="提醒已不存在或对应问题已经解决")
        acknowledgements = read_json_setting(db, SYSTEM_ALERT_ACK_KEY, {})
        if not isinstance(acknowledgements, dict): acknowledgements = {}
        if payload.acknowledged:
            acknowledgements[alert_key] = {"at": datetime.utcnow().isoformat(), "by": current_user.username}
        else:
            acknowledgements.pop(alert_key, None)
        write_json_setting(db, SYSTEM_ALERT_ACK_KEY, acknowledgements)
        write_audit_log(
            db, actor=current_user, action="system_alert_acknowledged" if payload.acknowledged else "system_alert_reopened",
            resource_type="system_alert", details={"alert_key": alert_key},
        )
        commit_session(db, default_detail="Failed to update system alert")
        return list_system_alerts(db=db, _=current_user)

    @router.get("/system-settings", response_model=SystemSettingsResponse, summary="Read system settings")
    def read_system_settings(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        return get_system_settings(db)

    @router.put("/system-settings", response_model=SystemSettingsResponse, summary="Update system settings")
    def update_system_settings(
        payload: SystemSettingsResponse,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("superadmin")),
    ):
        value = payload.model_dump()
        write_json_setting(db, SYSTEM_SETTINGS_KEY, value)
        write_audit_log(
            db, actor=current_user, action="system_settings_updated", resource_type="system_settings", details=value,
        )
        commit_session(db, default_detail="Failed to update system settings")
        return value

    @router.get("/ui-settings/{setting_key}", summary="Read shared table settings")
    def read_ui_setting(
        setting_key: str,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        if setting_key not in UI_TABLE_SETTING_KEYS:
            raise HTTPException(status_code=404, detail="Unknown UI setting")
        setting = get_setting(db, f"ui:{setting_key}")
        if setting is None:
            return {"key": setting_key, "value": None}
        try:
            value = json.loads(setting.value)
        except (TypeError, ValueError):
            value = None
        return {"key": setting_key, "value": value}

    @router.put("/ui-settings/{setting_key}", summary="Save shared table settings")
    def save_ui_setting(
        setting_key: str,
        payload: dict[str, Any],
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        if setting_key not in UI_TABLE_SETTING_KEYS:
            raise HTTPException(status_code=404, detail="Unknown UI setting")
        serialized = json.dumps(payload.get("value"), ensure_ascii=False, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > 20_000:
            raise HTTPException(status_code=400, detail="UI setting is too large")
        storage_key = f"ui:{setting_key}"
        setting = get_setting(db, storage_key)
        if setting is None:
            setting = AppSetting(key=storage_key, value=serialized)
            db.add(setting)
        else:
            setting.value = serialized
        commit_session(db, default_detail="Failed to save UI setting")
        return {"key": setting_key, "value": payload.get("value")}

    return router
