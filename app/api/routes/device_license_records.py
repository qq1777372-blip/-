"""Mobile device records and license records, including license images.

Moved out of main.py unchanged. Every handler keeps its absolute path (the router
declares no prefix) so the URL surface is byte-identical -- see
tests/route_snapshot.txt.

The upload plumbing (resolve_upload_file, image_file_response) stays in main.py:
peer_shops.py is still handed both, so moving them here would break that router
rather than this one. They arrive as keyword arguments, as does everything else
main.py owns.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AdminUser, LicenseRecord, MobileDeviceRecord
from schemas import (
    BatchActionResponse,
    BatchDeleteRequest,
    LicenseRecordCreate,
    LicenseRecordResponse,
    LicenseRecordUpdate,
    MobileDeviceRecordCreate,
    MobileDeviceRecordResponse,
    MobileDeviceRecordUpdate,
)


def create_device_license_router(
    *,
    get_db,
    require_role,
    commit_session,
    write_audit_log,
    create_sqlite_backup,
    parse_json_object,
    dump_json_object,
    resolve_upload_file,
    image_file_response,
    uploads_dir: Path,
    license_upload_dir: Path,
) -> APIRouter:
    # The moved bodies read these two as module constants. Aliasing keeps the
    # factory signature lowercase without editing a line of the moved code.
    UPLOADS_DIR = uploads_dir
    LICENSE_UPLOAD_DIR = license_upload_dir

    router = APIRouter(tags=["records"])

    def build_license_image_url(record: LicenseRecord) -> str | None:
        if not record.image_path:
            return None

        return f"/license-records/{record.id}/image-file?v={Path(record.image_path).name}"

    def serialize_license_record(record: LicenseRecord) -> dict[str, Any]:
        try:
            extra_fields = json.loads(record.extra_fields or "{}")
        except (TypeError, ValueError):
            extra_fields = {}
        return {
            "id": record.id,
            "subject_name": record.subject_name,
            "credit_code": record.credit_code,
            "legal_representative": record.legal_representative,
            "issue_date": record.issue_date,
            "expiry_date": record.expiry_date,
            "remark": record.remark,
            "extra_fields": extra_fields,
            "created_at": record.created_at,
            "image_name": record.image_name,
            "image_url": build_license_image_url(record),
        }

    def serialize_mobile_device_record(record: MobileDeviceRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "device_name": record.device_name,
            "primary_card": record.primary_card,
            "secondary_card": record.secondary_card,
            "remark": record.remark,
            "extra_fields": parse_json_object(record.extra_fields),
            "created_at": record.created_at,
        }

    def get_license_record_or_404(db: Session, record_id: int) -> LicenseRecord:
        db_record = db.get(LicenseRecord, record_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="License record not found")
        return db_record

    def get_mobile_device_record_or_404(db: Session, record_id: int) -> MobileDeviceRecord:
        db_record = db.get(MobileDeviceRecord, record_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="Mobile device record not found")
        return db_record

    def delete_license_image_file(record: LicenseRecord) -> None:
        if not record.image_path:
            return

        image_file = UPLOADS_DIR / record.image_path
        if image_file.exists():
            image_file.unlink()

    def clear_license_image(record: LicenseRecord) -> None:
        delete_license_image_file(record)
        record.image_path = None
        record.image_name = None

    async def save_license_image(record: LicenseRecord, upload: UploadFile) -> None:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="璇烽€夋嫨鍥剧墖鏂囦欢")

        suffix = Path(upload.filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(status_code=400, detail="浠呮敮鎸?jpg銆乸ng銆亀ebp 鍥剧墖")
        if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail="图片 MIME 类型无效")

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="图片文件为空")
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片大小不能超过 15MB")

        clear_license_image(record)

        filename = f"license_{record.id}_{secrets.token_hex(8)}{suffix}"
        save_path = LICENSE_UPLOAD_DIR / filename
        save_path.write_bytes(content)

        record.image_path = f"licenses/{filename}"
        record.image_name = upload.filename

    @router.post(
        "/mobile-devices",
        response_model=MobileDeviceRecordResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a mobile device record",
    )
    def create_mobile_device_record(
        payload: MobileDeviceRecordCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        values = payload.model_dump()
        values["extra_fields"] = dump_json_object(values.get("extra_fields") or {})
        db_record = MobileDeviceRecord(**values)
        db.add(db_record)
        commit_session(db, default_detail="Failed to create mobile device record")
        db.refresh(db_record)
        return serialize_mobile_device_record(db_record)

    @router.get(
        "/mobile-devices",
        response_model=list[MobileDeviceRecordResponse],
        summary="List all mobile device records",
    )
    def list_mobile_device_records(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(MobileDeviceRecord).order_by(MobileDeviceRecord.id.desc())
        records = db.scalars(stmt).all()
        return [serialize_mobile_device_record(record) for record in records]

    @router.get(
        "/mobile-devices/{record_id}",
        response_model=MobileDeviceRecordResponse,
        summary="Get a mobile device record by ID",
    )
    def get_mobile_device_record(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return serialize_mobile_device_record(get_mobile_device_record_or_404(db, record_id))

    @router.put(
        "/mobile-devices/{record_id}",
        response_model=MobileDeviceRecordResponse,
        summary="Update a mobile device record",
    )
    def update_mobile_device_record(
        record_id: int,
        payload: MobileDeviceRecordUpdate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_mobile_device_record_or_404(db, record_id)
        for key, value in payload.model_dump().items():
            if key == "extra_fields":
                value = dump_json_object(value or {})
            setattr(db_record, key, value)

        commit_session(db, default_detail="Failed to update mobile device record")
        db.refresh(db_record)
        return serialize_mobile_device_record(db_record)

    @router.delete(
        "/mobile-devices/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a mobile device record",
    )
    def delete_mobile_device_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_mobile_device_record_or_404(db, record_id)
        write_audit_log(
            db,
            actor=current_user,
            action="mobile_device_record_deleted",
            resource_type="mobile_device_record",
            resource_id=db_record.id,
            details={
                "device_name": db_record.device_name,
                "primary_card": db_record.primary_card,
                "secondary_card": db_record.secondary_card,
            },
        )
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete mobile device record")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/mobile-devices/batch-delete",
        response_model=BatchActionResponse,
        summary="Batch delete mobile device records",
    )
    def batch_delete_mobile_device_records(
        payload: BatchDeleteRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        stmt = select(MobileDeviceRecord).where(MobileDeviceRecord.id.in_(payload.record_ids))
        records = db.scalars(stmt).all()
        if len(records) != len(set(payload.record_ids)):
            raise HTTPException(status_code=404, detail="One or more mobile device records were not found")

        backup_path = create_sqlite_backup("mobile-devices-batch-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="mobile_device_records_batch_deleted",
            resource_type="mobile_device_record",
            details={
                "record_ids": [record.id for record in records],
                "backup_path": backup_path,
            },
        )

        for record in records:
            db.delete(record)

        commit_session(db, default_detail="Failed to batch delete mobile device records")
        return {"updated_count": len(records)}

    @router.post(
        "/license-records",
        response_model=LicenseRecordResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a license record",
    )
    def create_license_record(
        payload: LicenseRecordCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        existing_code = db.scalar(select(LicenseRecord).where(LicenseRecord.credit_code == payload.credit_code))
        if existing_code is not None:
            raise HTTPException(status_code=409, detail="统一社会信用代码已存在")

        record_data = payload.model_dump()
        record_data["extra_fields"] = json.dumps(record_data.get("extra_fields") or {}, ensure_ascii=False)
        db_record = LicenseRecord(**record_data)
        db.add(db_record)
        commit_session(
            db,
            default_detail="Failed to create license record",
            integrity_detail="统一社会信用代码已存在",
        )
        db.refresh(db_record)
        return serialize_license_record(db_record)

    @router.get(
        "/license-records",
        response_model=list[LicenseRecordResponse],
        summary="List all license records",
    )
    def list_license_records(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        stmt = select(LicenseRecord).order_by(LicenseRecord.created_at.desc(), LicenseRecord.id.desc())
        records = db.scalars(stmt).all()
        return [serialize_license_record(record) for record in records]

    @router.get(
        "/license-records/{record_id}",
        response_model=LicenseRecordResponse,
        summary="Get a license record by ID",
    )
    def get_license_record(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return serialize_license_record(get_license_record_or_404(db, record_id))

    @router.get(
        "/license-records/{record_id}/image-file",
        summary="Download a protected license image",
    )
    def get_license_image_file(
        record_id: int,
        thumb: int = 0,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        db_record = get_license_record_or_404(db, record_id)
        if not db_record.image_path:
            raise HTTPException(status_code=404, detail="License image not found")

        image_file = resolve_upload_file(db_record.image_path)
        if image_file is None:
            raise HTTPException(status_code=404, detail="License image not found")

        return image_file_response(image_file, db_record.image_name, thumbnail=bool(thumb))

    @router.put(
        "/license-records/{record_id}",
        response_model=LicenseRecordResponse,
        summary="Update a license record",
    )
    def update_license_record(
        record_id: int,
        payload: LicenseRecordUpdate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_license_record_or_404(db, record_id)

        existing_code = db.scalar(
            select(LicenseRecord).where(
                LicenseRecord.credit_code == payload.credit_code,
                LicenseRecord.id != record_id,
            ),
        )
        if existing_code is not None:
            raise HTTPException(status_code=409, detail="统一社会信用代码已存在")

        record_data = payload.model_dump()
        record_data["extra_fields"] = json.dumps(record_data.get("extra_fields") or {}, ensure_ascii=False)
        for key, value in record_data.items():
            setattr(db_record, key, value)

        commit_session(
            db,
            default_detail="Failed to update license record",
            integrity_detail="统一社会信用代码已存在",
        )
        db.refresh(db_record)
        return serialize_license_record(db_record)

    @router.delete(
        "/license-records/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a license record",
    )
    def delete_license_record(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_license_record_or_404(db, record_id)
        write_audit_log(
            db,
            actor=current_user,
            action="license_record_deleted",
            resource_type="license_record",
            resource_id=db_record.id,
            details={
                "subject_name": db_record.subject_name,
                "credit_code": db_record.credit_code,
                "image_name": db_record.image_name,
            },
        )
        delete_license_image_file(db_record)
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete license record")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/license-records/batch-delete",
        response_model=BatchActionResponse,
        summary="Batch delete license records",
    )
    def batch_delete_license_records(
        payload: BatchDeleteRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        stmt = select(LicenseRecord).where(LicenseRecord.id.in_(payload.record_ids))
        records = db.scalars(stmt).all()
        if len(records) != len(set(payload.record_ids)):
            raise HTTPException(status_code=404, detail="One or more license records were not found")

        backup_path = create_sqlite_backup("license-records-batch-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="license_records_batch_deleted",
            resource_type="license_record",
            details={
                "record_ids": [record.id for record in records],
                "backup_path": backup_path,
            },
        )

        for record in records:
            delete_license_image_file(record)
            db.delete(record)

        commit_session(db, default_detail="Failed to batch delete license records")
        return {"updated_count": len(records)}

    @router.post(
        "/license-records/{record_id}/image",
        response_model=LicenseRecordResponse,
        summary="Upload or replace license image",
    )
    async def upload_license_image(
        record_id: int,
        image: UploadFile = File(...),
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_license_record_or_404(db, record_id)
        await save_license_image(db_record, image)
        commit_session(db, default_detail="Failed to upload license image")
        db.refresh(db_record)
        return serialize_license_record(db_record)

    @router.delete(
        "/license-records/{record_id}/image",
        response_model=LicenseRecordResponse,
        summary="Delete license image",
    )
    def delete_license_image(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_license_record_or_404(db, record_id)
        if not db_record.image_path:
            raise HTTPException(status_code=404, detail="License image not found")

        clear_license_image(db_record)
        commit_session(db, default_detail="Failed to delete license image")
        db.refresh(db_record)
        return serialize_license_record(db_record)

    return router
