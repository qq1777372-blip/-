"""Shop records and the custom field definitions that shape them.

Moved out of main.py unchanged. The handlers keep their absolute paths (the
router declares no prefix) so the URL surface stays byte-identical -- see
tests/route_snapshot.txt.

These two domains ship together because they are one mechanism: a shop record
stores its non-system columns as JSON, and /custom-fields is what defines those
columns. Splitting them would mean passing the whole field-configuration set
(validate_record_values, sync_legacy_columns, the SYSTEM_FIELD_* maps) across a
module boundary for no gain.

Shared helpers arrive as keyword arguments rather than imports: main.py owns
them and importing from it here would be a cycle.
"""

from __future__ import annotations

import re
from datetime import date as date_type
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AdminUser, CustomField, ShopRecord
from schemas import (
    BatchActionResponse,
    BatchDeleteRequest,
    FieldDefinitionCreate,
    FieldDefinitionReorderRequest,
    FieldDefinitionResponse,
    FieldDefinitionUpdate,
    ShopRecordCreate,
    ShopRecordResponse,
    ShopRecordUpdate,
)


def create_shop_records_router(
    *,
    get_db,
    require_role,
    commit_session,
    write_audit_log,
    create_sqlite_backup,
    dump_json_object,
    parse_record_values,
    internal_reserved_field_names,
    system_field_map,
    system_field_label_map,
    legacy_field_names,
) -> APIRouter:
    # The moved bodies still spell these as main.py globals. Aliasing here
    # keeps the factory signature conventional while leaving every copied
    # line untouched.
    INTERNAL_RESERVED_FIELD_NAMES = internal_reserved_field_names
    SYSTEM_FIELD_MAP = system_field_map
    SYSTEM_FIELD_LABEL_MAP = system_field_label_map
    LEGACY_FIELD_NAMES = legacy_field_names

    router = APIRouter(tags=["shop-records"])

    def serialize_record(record: ShopRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "values": parse_record_values(record),
        }

    def list_field_definitions(db: Session) -> list[CustomField]:
        stmt = select(CustomField).order_by(CustomField.sort_order.asc(), CustomField.id.asc())
        return db.scalars(stmt).all()

    def get_field_or_404(db: Session, field_id: int) -> CustomField:
        db_field = db.get(CustomField, field_id)
        if db_field is None:
            raise HTTPException(status_code=404, detail="Field not found")
        return db_field

    def get_shop_record_or_404(db: Session, record_id: int) -> ShopRecord:
        db_record = db.get(ShopRecord, record_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="Shop record not found")
        return db_record

    def is_empty_value(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def normalize_field_value(field: CustomField, value: Any) -> Any:
        if is_empty_value(value):
            if field.required:
                raise HTTPException(status_code=422, detail=f"Field '{field.label}' is required")
            return None

        if field.field_type == "number":
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"Field '{field.label}' must be a number") from exc

        if field.field_type == "date":
            if isinstance(value, date_type):
                return value.isoformat()
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"Field '{field.label}' must be a date string")
            try:
                return date_type.fromisoformat(value.strip()).isoformat()
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"Field '{field.label}' must use YYYY-MM-DD format") from exc

        normalized = str(value).strip()
        if field.required and not normalized:
            raise HTTPException(status_code=422, detail=f"Field '{field.label}' is required")
        return normalized or None

    def validate_record_values(values: dict[str, Any] | None, db: Session) -> dict[str, Any]:
        payload = values or {}
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="values must be an object")

        fields = list_field_definitions(db)
        field_map = {field.field_name: field for field in fields}
        unknown_fields = sorted(set(payload) - set(field_map))
        if unknown_fields:
            raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(unknown_fields)}")

        normalized: dict[str, Any] = {}
        for field in fields:
            normalized_value = normalize_field_value(field, payload.get(field.field_name))
            if normalized_value is not None:
                normalized[field.field_name] = normalized_value

        return normalized

    def sync_legacy_columns(record: ShopRecord, values: dict[str, Any]) -> None:
        record.shop_name = values.get("shop_name")
        record.platform = values.get("platform")
        record.daily_revenue = values.get("daily_revenue")
        record.remark = values.get("remark")
        record.date = date_type.fromisoformat(values["date"]) if values.get("date") else None
        record.extra_fields = dump_json_object(
            {key: value for key, value in values.items() if key not in LEGACY_FIELD_NAMES},
        )
        record.record_data = dump_json_object(values)

    def build_field_name(label: str, requested_field_name: str | None, db: Session) -> str:
        existing_names = set(db.scalars(select(CustomField.field_name)).all())

        if requested_field_name:
            if requested_field_name in INTERNAL_RESERVED_FIELD_NAMES:
                raise HTTPException(status_code=400, detail="Field name conflicts with an internal field")
            if requested_field_name in existing_names:
                raise HTTPException(status_code=400, detail="Field name already exists")
            return requested_field_name

        system_match = SYSTEM_FIELD_LABEL_MAP.get(label.strip())
        if system_match and system_match["field_name"] not in existing_names:
            return str(system_match["field_name"])

        generated = re.sub(r"[^a-zA-Z0-9_]+", "_", label.strip().lower()).strip("_")
        if not generated:
            generated = "custom_field"
        if generated[0].isdigit():
            generated = f"field_{generated}"

        candidate = generated
        suffix = 1
        while candidate in INTERNAL_RESERVED_FIELD_NAMES or candidate in existing_names:
            candidate = f"{generated}_{suffix}"
            suffix += 1
        return candidate

    @router.get(
        "/custom-fields",
        response_model=list[FieldDefinitionResponse],
        summary="List table headers",
    )
    def list_fields(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return list_field_definitions(db)

    @router.post(
        "/custom-fields",
        response_model=FieldDefinitionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a table header",
    )
    def create_field_definition(
        field: FieldDefinitionCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        existing_label = db.scalar(select(CustomField).where(CustomField.label == field.label))
        if existing_label is not None:
            raise HTTPException(status_code=409, detail="Field label already exists")

        field_name = build_field_name(field.label, field.field_name, db)
        next_sort_order = (db.scalar(select(func.max(CustomField.sort_order))) or 0) + 1
        is_builtin = field_name in SYSTEM_FIELD_MAP

        db_field = CustomField(
            field_name=field_name,
            label=field.label,
            field_type=field.field_type,
            required=field.required,
            sort_order=next_sort_order,
            is_visible=True,
            is_builtin=is_builtin,
        )
        db.add(db_field)
        commit_session(
            db,
            default_detail="Failed to create field",
            integrity_detail="Field label or field name already exists",
        )
        db.refresh(db_field)
        return db_field

    @router.patch(
        "/custom-fields/{field_id}",
        response_model=FieldDefinitionResponse,
        summary="Update custom field display settings",
    )
    def update_field_definition(
        field_id: int,
        payload: FieldDefinitionUpdate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        db_field = get_field_or_404(db, field_id)

        if payload.required is not None:
            db_field.required = payload.required

        if payload.is_visible is not None:
            if db_field.is_builtin and not payload.is_visible:
                raise HTTPException(status_code=400, detail="Built-in fields cannot be hidden")
            db_field.is_visible = payload.is_visible

        commit_session(db, default_detail="Failed to update field settings")
        db.refresh(db_field)
        return db_field

    @router.post(
        "/custom-fields/reorder",
        response_model=list[FieldDefinitionResponse],
        summary="Reorder custom fields",
    )
    def reorder_field_definitions(
        payload: FieldDefinitionReorderRequest,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        fields = list_field_definitions(db)
        current_ids = [field.id for field in fields]
        if sorted(current_ids) != sorted(payload.field_ids):
            raise HTTPException(status_code=400, detail="field_ids must match all existing fields")

        field_map = {field.id: field for field in fields}
        for index, field_id in enumerate(payload.field_ids, start=1):
            field_map[field_id].sort_order = index

        commit_session(db, default_detail="Failed to reorder fields")
        return list_field_definitions(db)

    @router.delete(
        "/custom-fields/{field_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a table header",
    )
    def delete_field_definition(
        field_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("superadmin")),
    ):
        db_field = get_field_or_404(db, field_id)

        for record in db.scalars(select(ShopRecord)).all():
            values = parse_record_values(record)
            if db_field.field_name not in values:
                continue
            values.pop(db_field.field_name, None)
            sync_legacy_columns(record, values)

        db.delete(db_field)
        commit_session(db, default_detail="Failed to delete field")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/shop-records",
        response_model=ShopRecordResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a shop record",
    )
    def create_shop_record(
        record: ShopRecordCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        values = validate_record_values(record.values, db)
        db_record = ShopRecord()
        sync_legacy_columns(db_record, values)
        db.add(db_record)
        commit_session(db, default_detail="Failed to create shop record")
        db.refresh(db_record)
        return serialize_record(db_record)

    @router.get(
        "/shop-records",
        response_model=list[ShopRecordResponse],
        summary="List all shop records",
    )
    def list_shop_records(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(ShopRecord).order_by(ShopRecord.id.desc())
        records = db.scalars(stmt).all()
        return [serialize_record(record) for record in records]

    @router.get(
        "/shop-records/{record_id}",
        response_model=ShopRecordResponse,
        summary="Get a shop record by ID",
    )
    def get_shop_record(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        db_record = get_shop_record_or_404(db, record_id)
        return serialize_record(db_record)

    @router.put(
        "/shop-records/{record_id}",
        response_model=ShopRecordResponse,
        summary="Update a shop record",
    )
    def update_shop_record(
        record_id: int,
        record: ShopRecordUpdate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_shop_record_or_404(db, record_id)
        values = validate_record_values(record.values, db)
        sync_legacy_columns(db_record, values)
        commit_session(db, default_detail="Failed to update shop record")
        db.refresh(db_record)
        return serialize_record(db_record)

    @router.delete(
        "/shop-records/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a shop record",
    )
    def delete_shop_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_shop_record_or_404(db, record_id)
        write_audit_log(
            db,
            actor=current_user,
            action="shop_record_deleted",
            resource_type="shop_record",
            resource_id=db_record.id,
            details={"values": parse_record_values(db_record)},
        )
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete shop record")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/shop-records/batch-delete",
        response_model=BatchActionResponse,
        summary="Batch delete shop records",
    )
    def batch_delete_shop_records(
        payload: BatchDeleteRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        stmt = select(ShopRecord).where(ShopRecord.id.in_(payload.record_ids))
        records = db.scalars(stmt).all()
        if len(records) != len(set(payload.record_ids)):
            raise HTTPException(status_code=404, detail="One or more shop records were not found")

        backup_path = create_sqlite_backup("shop-records-batch-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="shop_records_batch_deleted",
            resource_type="shop_record",
            details={
                "record_ids": [record.id for record in records],
                "backup_path": backup_path,
            },
        )

        for record in records:
            db.delete(record)

        commit_session(db, default_detail="Failed to batch delete shop records")
        return {"updated_count": len(records)}

    return router
