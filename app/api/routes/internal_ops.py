"""DingTalk profit rows and the ops alert digest.

Moved out of main.py unchanged. The handlers keep their absolute paths (the
router declares no prefix) so the URL surface stays byte-identical -- see
tests/route_snapshot.txt.

What these seven routes have in common is that no page owns them. Two are
server-to-server: /internal/dingtalk-profits/* authenticate with a shared header
token, not a session, because the caller is the DingTalk receiver rather than a
browser. Two more are read-only ops probes under /internal/ops/. The remaining
three serve the console's profit views and do use session auth -- they live here
because they read the same rows the sync endpoints write, and splitting the
writer from the readers would put serialize_dingtalk_profit_record on a module
boundary for no gain.

Shared helpers arrive as keyword arguments rather than imports: main.py owns
them and importing from it here would be a cycle.
"""

from __future__ import annotations

import hmac
from datetime import date as date_type
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from models import AdminUser, DingTalkProfitRecord, TaskBookkeepingRecord
from schemas import (
    DingTalkProfitDeleteBatchRequest,
    DingTalkProfitDeleteBatchResponse,
    DingTalkProfitMonthlySummaryResponse,
    DingTalkProfitRecordResponse,
    DingTalkProfitSummaryResponse,
    DingTalkProfitSyncBatchRequest,
    DingTalkProfitSyncBatchResponse,
)


def create_internal_ops_router(
    *,
    get_db,
    require_role,
    commit_session,
    build_system_alerts,
    build_task_bookkeeping_summary,
    internal_sync_token_header,
    task_bookkeeping_timezone,
) -> APIRouter:
    # The moved bodies still spell these as main.py globals. Aliasing here
    # keeps the factory signature conventional while leaving every copied
    # line untouched.
    INTERNAL_SYNC_TOKEN_HEADER = internal_sync_token_header
    TASK_BOOKKEEPING_TIMEZONE = task_bookkeeping_timezone

    router = APIRouter(tags=["internal-ops"])

    def parse_external_datetime(raw_value: datetime | str | None) -> datetime | None:
        if raw_value is None or isinstance(raw_value, datetime):
            return raw_value

        normalized = str(raw_value).strip()
        if not normalized:
            return None

        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return datetime.fromisoformat(normalized.replace(" ", "T"))

    def serialize_dingtalk_profit_record(record: DingTalkProfitRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "source_record_id": record.source_record_id,
            "report_date": record.report_date,
            "store_name": record.store_name,
            "profit": float(record.profit or 0),
            "reporter_name": record.reporter_name,
            "reporter_id": record.reporter_id,
            "batch_id": record.batch_id,
            "source_message_id": record.source_message_id,
            "source_create_time": record.source_create_time,
            "source_update_time": record.source_update_time,
            "synced_at": record.synced_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def build_dingtalk_profit_summary(db: Session) -> dict[str, Any]:
        total_records = db.scalar(select(func.count(DingTalkProfitRecord.id))) or 0
        total_profit = db.scalar(select(func.coalesce(func.sum(DingTalkProfitRecord.profit), 0.0))) or 0.0
        unique_store_count = db.scalar(
            select(func.count(func.distinct(DingTalkProfitRecord.store_name))),
        ) or 0
        unique_reporter_count = db.scalar(
            select(func.count(func.distinct(DingTalkProfitRecord.reporter_name))),
        ) or 0
        latest_report_date = db.scalar(select(func.max(DingTalkProfitRecord.report_date)))
        latest_sync_time = db.scalar(select(func.max(DingTalkProfitRecord.synced_at)))

        return {
            "total_records": int(total_records),
            "total_profit": float(total_profit or 0),
            "unique_store_count": int(unique_store_count),
            "unique_reporter_count": int(unique_reporter_count),
            "latest_report_date": latest_report_date,
            "latest_sync_time": latest_sync_time,
        }

    def build_dingtalk_profit_monthly_summary(db: Session) -> list[dict[str, Any]]:
        records = db.scalars(
            select(DingTalkProfitRecord).order_by(
                DingTalkProfitRecord.report_date.desc(),
                DingTalkProfitRecord.source_record_id.desc(),
            ),
        ).all()

        summary_map: dict[str, dict[str, Any]] = {}
        ordered_months: list[str] = []

        for record in records:
            month_key = record.report_date.strftime("%Y-%m")
            bucket = summary_map.get(month_key)
            if bucket is None:
                bucket = {
                    "month": month_key,
                    "total_profit": 0.0,
                    "record_count": 0,
                    "store_names": set(),
                    "reporter_names": set(),
                    "latest_report_date": record.report_date,
                }
                summary_map[month_key] = bucket
                ordered_months.append(month_key)

            bucket["total_profit"] += float(record.profit or 0)
            bucket["record_count"] += 1
            bucket["store_names"].add(record.store_name)
            bucket["reporter_names"].add(record.reporter_name)
            if record.report_date > bucket["latest_report_date"]:
                bucket["latest_report_date"] = record.report_date

        payload: list[dict[str, Any]] = []
        for month_key in ordered_months:
            bucket = summary_map[month_key]
            payload.append(
                {
                    "month": bucket["month"],
                    "total_profit": round(float(bucket["total_profit"]), 2),
                    "record_count": int(bucket["record_count"]),
                    "store_count": len(bucket["store_names"]),
                    "reporter_count": len(bucket["reporter_names"]),
                    "latest_report_date": bucket["latest_report_date"],
                },
            )

        payload.sort(key=lambda item: item["month"], reverse=True)
        return payload

    def require_internal_sync_token(
        internal_sync_token: str | None = Header(default=None, alias=INTERNAL_SYNC_TOKEN_HEADER),
    ) -> None:
        expected_token = settings.dingtalk_profit_sync_token
        if not expected_token:
            raise HTTPException(status_code=503, detail="Internal sync token is not configured")

        if not internal_sync_token or not hmac.compare_digest(internal_sync_token, expected_token):
            raise HTTPException(status_code=401, detail="Invalid internal sync token")

    @router.get(
        "/internal/ops/alert-digest",
        summary="Internal: operational digest for the DingTalk bot",
    )
    def get_internal_ops_alert_digest(
        db: Session = Depends(get_db),
        _: None = Depends(require_internal_sync_token),
    ):
        alerts = build_system_alerts(db)
        open_alerts = [item for item in alerts if not item["acknowledged"]]
        critical_alerts = [item for item in open_alerts if item["severity"] == "critical"]
        inventory_alerts = [item for item in open_alerts if item["category"] == "inventory"]

        task_summary = build_task_bookkeeping_summary(
            db.scalars(select(TaskBookkeepingRecord)).all(),
        )

        current_month = datetime.now(TASK_BOOKKEEPING_TIMEZONE).strftime("%Y-%m")
        month_profit = next(
            (
                bucket["total_profit"]
                for bucket in build_dingtalk_profit_monthly_summary(db)
                if bucket["month"] == current_month
            ),
            0.0,
        )

        report_day = date_type.today().isoformat()
        lines = [
            "📋 每日运营摘要 (%s)" % report_day,
            "------------------------",
            "当月钉钉利润：￥%s" % month_profit,
            "待签收任务：%s" % task_summary["pending_signed_count"],
            "待结算任务：%s" % task_summary["pending_settlement_count"],
            "库存预警：%s" % len(inventory_alerts),
            "",
        ]
        if open_alerts:
            lines.append(
                "⚠️ 待处理提醒 %d 条（严重 %d）"
                % (len(open_alerts), len(critical_alerts)),
            )
            for item in open_alerts[:8]:
                mark = "🔴" if item["severity"] == "critical" else "🟡"
                lines.append("%s %s" % (mark, item["title"]))
                lines.append("    %s" % item["description"])
            if len(open_alerts) > 8:
                lines.append(
                    "… 还有 %d 条，详见后台"
                    % (len(open_alerts) - 8),
                )
        else:
            lines.append("✅ 暂无待处理提醒")

        return {
            "date": report_day,
            "open_count": len(open_alerts),
            "critical_count": len(critical_alerts),
            "pending_signed_count": task_summary["pending_signed_count"],
            "pending_settlement_count": task_summary["pending_settlement_count"],
            "low_stock_count": len(inventory_alerts),
            "current_month_profit": month_profit,
            "text": "\n".join(lines),
        }

    @router.get(
        "/internal/ops/open-alerts",
        summary="Internal: unacknowledged system alerts for the DingTalk bot",
    )
    def get_internal_ops_open_alerts(
        db: Session = Depends(get_db),
        _: None = Depends(require_internal_sync_token),
    ):
        """Structured alert feed for the bot.

        The digest endpoint renders text truncated to 8 entries, which cannot be
        de-duplicated. This returns every open alert with its stable key so the bot
        can track exactly what it has already pushed and never repeat itself.
        """
        open_alerts = [item for item in build_system_alerts(db) if not item["acknowledged"]]
        return {
            "total": len(open_alerts),
            "items": [
                {
                    "key": item["key"],
                    "category": item["category"],
                    "severity": item["severity"],
                    "title": item["title"],
                    "description": item["description"],
                    "occurred_at": item["occurred_at"],
                }
                for item in open_alerts
            ],
        }

    @router.post(
        "/internal/dingtalk-profits/sync-batch",
        response_model=DingTalkProfitSyncBatchResponse,
        summary="Sync a DingTalk profit batch into the website",
    )
    def sync_dingtalk_profit_batch(
        payload: DingTalkProfitSyncBatchRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_internal_sync_token),
    ):
        normalized_records = {
            record.source_record_id: record
            for record in payload.records
        }
        source_record_ids = list(normalized_records)
        existing_records = {
            record.source_record_id: record
            for record in db.scalars(
                select(DingTalkProfitRecord).where(DingTalkProfitRecord.source_record_id.in_(source_record_ids)),
            ).all()
        }

        inserted_count = 0
        updated_count = 0
        sync_time = datetime.utcnow()

        for source_record_id, record in normalized_records.items():
            db_record = existing_records.get(source_record_id)
            if db_record is None:
                db_record = DingTalkProfitRecord(source_record_id=source_record_id)
                db.add(db_record)
                inserted_count += 1
            else:
                updated_count += 1

            db_record.report_date = record.report_date
            db_record.store_name = record.store_name
            db_record.profit = record.profit
            db_record.reporter_name = record.reporter_name
            db_record.reporter_id = record.reporter_id
            db_record.batch_id = record.batch_id
            db_record.source_message_id = record.source_message_id
            db_record.source_create_time = parse_external_datetime(record.source_create_time)
            db_record.source_update_time = parse_external_datetime(record.source_update_time)
            db_record.synced_at = sync_time

        commit_session(
            db,
            default_detail="Failed to sync DingTalk profit records",
            integrity_detail="Duplicate DingTalk source record detected",
        )
        return {
            "inserted_count": inserted_count,
            "updated_count": updated_count,
            "total_count": len(normalized_records),
        }

    @router.post(
        "/internal/dingtalk-profits/delete-batch",
        response_model=DingTalkProfitDeleteBatchResponse,
        summary="Delete a DingTalk profit batch from the website by source IDs",
    )
    def delete_dingtalk_profit_batch(
        payload: DingTalkProfitDeleteBatchRequest,
        db: Session = Depends(get_db),
        _: None = Depends(require_internal_sync_token),
    ):
        records = db.scalars(
            select(DingTalkProfitRecord).where(
                DingTalkProfitRecord.source_record_id.in_(payload.source_record_ids),
            ),
        ).all()
        for record in records:
            db.delete(record)

        commit_session(db, default_detail="Failed to delete DingTalk profit records")
        return {"deleted_count": len(records)}

    @router.get(
        "/dingtalk-profits/summary",
        response_model=DingTalkProfitSummaryResponse,
        summary="Get DingTalk profit sync summary",
    )
    def get_dingtalk_profit_summary(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return build_dingtalk_profit_summary(db)

    @router.get(
        "/dingtalk-profits/monthly-summary",
        response_model=list[DingTalkProfitMonthlySummaryResponse],
        summary="Get DingTalk profit monthly summary",
    )
    def get_dingtalk_profit_monthly_summary(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return build_dingtalk_profit_monthly_summary(db)

    @router.get(
        "/dingtalk-profits",
        response_model=list[DingTalkProfitRecordResponse],
        summary="List all synced DingTalk profit records",
    )
    def list_dingtalk_profit_records(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(DingTalkProfitRecord).order_by(
            DingTalkProfitRecord.report_date.desc(),
            DingTalkProfitRecord.source_record_id.desc(),
        )
        records = db.scalars(stmt).all()
        return [serialize_dingtalk_profit_record(record) for record in records]

    return router
