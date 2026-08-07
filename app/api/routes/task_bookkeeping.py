"""Task bookkeeping: shops, owners, records, and the batch operations.

Moved out of main.py unchanged. Handlers keep their absolute paths (the router
declares no prefix) so the URL surface is byte-identical -- see
tests/route_snapshot.txt.

Five helpers stay in main.py because /global-search and
/internal/ops/alert-digest reach them; they arrive here as keyword arguments.
Importing them from main.py instead would be a cycle.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    AdminUser,
    TaskBookkeepingOwner,
    TaskBookkeepingRecord,
    TaskBookkeepingShop,
)
from schemas import (
    TaskBookkeepingBatchActionResponse,
    TaskBookkeepingBatchDeleteRequest,
    TaskBookkeepingBatchStatusUpdateRequest,
    TaskBookkeepingOwnerCreate,
    TaskBookkeepingOwnerResponse,
    TaskBookkeepingRecordCreate,
    TaskBookkeepingRecordResponse,
    TaskBookkeepingRecordUpdate,
    TaskBookkeepingShopCreate,
    TaskBookkeepingShopResponse,
    TaskBookkeepingSummaryResponse,
)


def create_task_bookkeeping_router(
    *,
    get_db,
    require_role,
    commit_session,
    write_audit_log,
    create_sqlite_backup,
    get_task_bookkeeping_local_now,
    normalize_task_bookkeeping_datetime,
    serialize_task_bookkeeping_record,
    build_task_bookkeeping_summary,
) -> APIRouter:
    router = APIRouter(tags=["task-bookkeeping"])

    def get_task_bookkeeping_record_or_404(db: Session, record_id: int) -> TaskBookkeepingRecord:
        db_record = db.get(TaskBookkeepingRecord, record_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="Task bookkeeping record not found")
        return db_record

    def get_task_bookkeeping_shop_or_404(db: Session, shop_id: int) -> TaskBookkeepingShop:
        db_record = db.get(TaskBookkeepingShop, shop_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="Task bookkeeping shop not found")
        return db_record

    def get_task_bookkeeping_owner_or_404(db: Session, owner_id: int) -> TaskBookkeepingOwner:
        db_record = db.get(TaskBookkeepingOwner, owner_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="Task bookkeeping owner not found")
        return db_record

    def ensure_task_bookkeeping_shop(db: Session, name: str) -> None:
        existing = db.scalar(select(TaskBookkeepingShop).where(TaskBookkeepingShop.name == name))
        if existing is not None:
            return

        db.add(TaskBookkeepingShop(name=name))
        db.flush()

    def ensure_task_bookkeeping_owner(db: Session, name: str) -> None:
        existing = db.scalar(select(TaskBookkeepingOwner).where(TaskBookkeepingOwner.name == name))
        if existing is not None:
            return

        db.add(TaskBookkeepingOwner(name=name))
        db.flush()

    @router.post(
        "/task-bookkeeping/shops",
        response_model=TaskBookkeepingShopResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a task bookkeeping shop",
    )
    def create_task_bookkeeping_shop(
        payload: TaskBookkeepingShopCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        existing = db.scalar(select(TaskBookkeepingShop).where(TaskBookkeepingShop.name == payload.name))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Task bookkeeping shop already exists")

        db_record = TaskBookkeepingShop(name=payload.name)
        db.add(db_record)
        commit_session(
            db,
            default_detail="Failed to create task bookkeeping shop",
            integrity_detail="Task bookkeeping shop already exists",
        )
        db.refresh(db_record)
        return db_record

    @router.get(
        "/task-bookkeeping/shops",
        response_model=list[TaskBookkeepingShopResponse],
        summary="List all task bookkeeping shops",
    )
    def list_task_bookkeeping_shops(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(TaskBookkeepingShop).order_by(TaskBookkeepingShop.name.asc(), TaskBookkeepingShop.id.asc())
        return db.scalars(stmt).all()

    @router.delete(
        "/task-bookkeeping/shops/{shop_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a task bookkeeping shop",
    )
    def delete_task_bookkeeping_shop(
        shop_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_task_bookkeeping_shop_or_404(db, shop_id)
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete task bookkeeping shop")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/task-bookkeeping/owners",
        response_model=TaskBookkeepingOwnerResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a task bookkeeping owner",
    )
    def create_task_bookkeeping_owner(
        payload: TaskBookkeepingOwnerCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        existing = db.scalar(select(TaskBookkeepingOwner).where(TaskBookkeepingOwner.name == payload.name))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Task bookkeeping owner already exists")

        db_record = TaskBookkeepingOwner(name=payload.name)
        db.add(db_record)
        commit_session(
            db,
            default_detail="Failed to create task bookkeeping owner",
            integrity_detail="Task bookkeeping owner already exists",
        )
        db.refresh(db_record)
        return db_record

    @router.get(
        "/task-bookkeeping/owners",
        response_model=list[TaskBookkeepingOwnerResponse],
        summary="List all task bookkeeping owners",
    )
    def list_task_bookkeeping_owners(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(TaskBookkeepingOwner).order_by(TaskBookkeepingOwner.name.asc(), TaskBookkeepingOwner.id.asc())
        return db.scalars(stmt).all()

    @router.delete(
        "/task-bookkeeping/owners/{owner_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a task bookkeeping owner",
    )
    def delete_task_bookkeeping_owner(
        owner_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_task_bookkeeping_owner_or_404(db, owner_id)
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete task bookkeeping owner")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/task-bookkeeping/summary",
        response_model=TaskBookkeepingSummaryResponse,
        summary="Get task bookkeeping summary",
    )
    def get_task_bookkeeping_summary(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(TaskBookkeepingRecord).order_by(TaskBookkeepingRecord.task_time.desc(), TaskBookkeepingRecord.id.desc())
        records = db.scalars(stmt).all()
        return build_task_bookkeeping_summary(records)

    @router.post(
        "/task-bookkeeping/records",
        response_model=TaskBookkeepingRecordResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a task bookkeeping record",
    )
    def create_task_bookkeeping_record(
        payload: TaskBookkeepingRecordCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        ensure_task_bookkeeping_shop(db, payload.shop_name)
        ensure_task_bookkeeping_owner(db, payload.owner_name)

        db_record = TaskBookkeepingRecord(
            task_time=normalize_task_bookkeeping_datetime(payload.task_time) or get_task_bookkeeping_local_now(),
            shop_name=payload.shop_name,
            owner_name=payload.owner_name,
            principal_amount=payload.principal_amount,
            order_count=payload.order_count,
            commission_amount=payload.commission_amount,
            gift_amount=payload.gift_amount,
            signed_status=payload.signed_status,
            settlement_status=payload.settlement_status,
            note=payload.note,
        )
        db.add(db_record)
        commit_session(db, default_detail="Failed to create task bookkeeping record")
        db.refresh(db_record)
        return serialize_task_bookkeeping_record(db_record)

    @router.get(
        "/task-bookkeeping/records",
        response_model=list[TaskBookkeepingRecordResponse],
        summary="List all task bookkeeping records",
    )
    def list_task_bookkeeping_records(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(TaskBookkeepingRecord).order_by(TaskBookkeepingRecord.task_time.desc(), TaskBookkeepingRecord.id.desc())
        records = db.scalars(stmt).all()
        return [serialize_task_bookkeeping_record(record) for record in records]

    @router.get(
        "/task-bookkeeping/records/{record_id}",
        response_model=TaskBookkeepingRecordResponse,
        summary="Get a task bookkeeping record by ID",
    )
    def get_task_bookkeeping_record(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return serialize_task_bookkeeping_record(get_task_bookkeeping_record_or_404(db, record_id))

    @router.put(
        "/task-bookkeeping/records/{record_id}",
        response_model=TaskBookkeepingRecordResponse,
        summary="Update a task bookkeeping record",
    )
    def update_task_bookkeeping_record(
        record_id: int,
        payload: TaskBookkeepingRecordUpdate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_task_bookkeeping_record_or_404(db, record_id)
        ensure_task_bookkeeping_shop(db, payload.shop_name)
        ensure_task_bookkeeping_owner(db, payload.owner_name)

        db_record.task_time = normalize_task_bookkeeping_datetime(payload.task_time) or db_record.task_time
        db_record.shop_name = payload.shop_name
        db_record.owner_name = payload.owner_name
        db_record.principal_amount = payload.principal_amount
        db_record.order_count = payload.order_count
        db_record.commission_amount = payload.commission_amount
        db_record.gift_amount = payload.gift_amount
        db_record.signed_status = payload.signed_status
        db_record.settlement_status = payload.settlement_status
        db_record.note = payload.note

        commit_session(db, default_detail="Failed to update task bookkeeping record")
        db.refresh(db_record)
        return serialize_task_bookkeeping_record(db_record)

    @router.delete(
        "/task-bookkeeping/records/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a task bookkeeping record",
    )
    def delete_task_bookkeeping_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_task_bookkeeping_record_or_404(db, record_id)
        write_audit_log(
            db,
            actor=current_user,
            action="task_bookkeeping_record_deleted",
            resource_type="task_bookkeeping_record",
            resource_id=db_record.id,
            details=serialize_task_bookkeeping_record(db_record),
        )
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete task bookkeeping record")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.patch(
        "/task-bookkeeping/records/batch-status",
        response_model=TaskBookkeepingBatchActionResponse,
        summary="Batch update task bookkeeping record status",
    )
    def batch_update_task_bookkeeping_record_status(
        payload: TaskBookkeepingBatchStatusUpdateRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        stmt = select(TaskBookkeepingRecord).where(TaskBookkeepingRecord.id.in_(payload.record_ids))
        records = db.scalars(stmt).all()
        if len(records) != len(set(payload.record_ids)):
            raise HTTPException(status_code=404, detail="One or more task bookkeeping records were not found")

        for record in records:
            setattr(record, payload.field, payload.value)

        write_audit_log(
            db,
            actor=current_user,
            action="task_bookkeeping_status_batch_updated",
            resource_type="task_bookkeeping_record",
            details={
                "record_ids": [record.id for record in records],
                "field": payload.field,
                "value": payload.value,
            },
        )
        commit_session(db, default_detail="Failed to batch update task bookkeeping records")
        return {"updated_count": len(records)}

    @router.post(
        "/task-bookkeeping/records/batch-delete",
        response_model=TaskBookkeepingBatchActionResponse,
        summary="Batch delete task bookkeeping records",
    )
    def batch_delete_task_bookkeeping_records(
        payload: TaskBookkeepingBatchDeleteRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        stmt = select(TaskBookkeepingRecord).where(TaskBookkeepingRecord.id.in_(payload.record_ids))
        records = db.scalars(stmt).all()
        if len(records) != len(set(payload.record_ids)):
            raise HTTPException(status_code=404, detail="One or more task bookkeeping records were not found")

        backup_path = create_sqlite_backup("task-bookkeeping-batch-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="task_bookkeeping_records_batch_deleted",
            resource_type="task_bookkeeping_record",
            details={
                "record_ids": [record.id for record in records],
                "backup_path": backup_path,
            },
        )

        for record in records:
            db.delete(record)

        commit_session(db, default_detail="Failed to batch delete task bookkeeping records")
        return {"updated_count": len(records)}

    return router
