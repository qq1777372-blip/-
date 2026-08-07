"""Peer-shop records: CRUD, batch delete, and license-image upload.

Moved out of main.py unchanged. The handlers keep their absolute paths (the
router declares no prefix) so the URL surface is byte-identical -- see
tests/route_snapshot.txt.

Shared helpers arrive as keyword arguments rather than imports: main.py owns
them and importing from it here would be a cycle.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AdminUser, PeerShop
from schemas import (
    BatchActionResponse,
    BatchDeleteRequest,
    PeerShopCreate,
    PeerShopResponse,
    PeerShopUpdate,
)


def create_peer_shop_router(
    *,
    get_db,
    require_role,
    commit_session,
    write_audit_log,
    parse_json_object,
    dump_json_object,
    resolve_upload_file,
    image_file_response,
    create_sqlite_backup,
    uploads_dir: Path,
    peer_shop_upload_dir: Path,
) -> APIRouter:
    # The moved bodies reference these two as module constants. Aliasing here
    # keeps the factory signature conventional without editing a single line of
    # the code that came out of main.py.
    UPLOADS_DIR = uploads_dir
    PEER_SHOP_UPLOAD_DIR = peer_shop_upload_dir

    router = APIRouter(tags=["peer-shops"])

    def build_peer_shop_image_url(record: PeerShop) -> str | None:
        if not record.image_path:
            return None

        return f"/peer-shops/{record.id}/image-file?v={Path(record.image_path).name}"

    def serialize_peer_shop(record: PeerShop) -> dict[str, Any]:
        return {
            "id": record.id,
            "shop_name": record.shop_name,
            "shop_url": record.shop_url,
            "remark": record.remark,
            "extra_fields": parse_json_object(record.extra_fields),
            "created_at": record.created_at,
            "extra_fields": parse_json_object(record.extra_fields),
            "image_name": record.image_name,
            "image_url": build_peer_shop_image_url(record),
        }

    def get_peer_shop_or_404(db: Session, record_id: int) -> PeerShop:
        db_record = db.get(PeerShop, record_id)
        if db_record is None:
            raise HTTPException(status_code=404, detail="Peer shop not found")
        return db_record

    def delete_peer_shop_image_file(record: PeerShop) -> None:
        if not record.image_path:
            return

        image_file = UPLOADS_DIR / record.image_path
        if image_file.exists():
            image_file.unlink()

    def clear_peer_shop_image(record: PeerShop) -> None:
        delete_peer_shop_image_file(record)
        record.image_path = None
        record.image_name = None

    async def save_peer_shop_image(record: PeerShop, upload: UploadFile) -> None:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="璇烽€夋嫨鍥剧墖鏂囦欢")

        suffix = Path(upload.filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(status_code=400, detail="浠呮敮鎸?jpg銆乸ng銆亀ebp 鍥剧墖")
        if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail="鍥剧墖 MIME 绫诲瀷鏃犳晥")

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="鍥剧墖鏂囦欢涓虹┖")
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="鍥剧墖澶у皬涓嶈兘瓒呰繃 15MB")

        clear_peer_shop_image(record)

        filename = f"peer_shop_{record.id}_{secrets.token_hex(8)}{suffix}"
        save_path = PEER_SHOP_UPLOAD_DIR / filename
        save_path.write_bytes(content)

        record.image_path = f"peer-shops/{filename}"
        record.image_name = upload.filename

    @router.post(
        "/peer-shops",
        response_model=PeerShopResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a peer shop record",
    )
    def create_peer_shop(
        payload: PeerShopCreate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        values = payload.model_dump()
        values["extra_fields"] = dump_json_object(values.get("extra_fields") or {})
        db_record = PeerShop(**values)
        db.add(db_record)
        commit_session(db, default_detail="Failed to create peer shop")
        db.refresh(db_record)
        return serialize_peer_shop(db_record)


    @router.get(
        "/peer-shops",
        response_model=list[PeerShopResponse],
        summary="List all peer shops",
    )
    def list_peer_shops(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        records = db.scalars(select(PeerShop).order_by(PeerShop.created_at.desc(), PeerShop.id.desc())).all()
        return [serialize_peer_shop(record) for record in records]


    @router.get(
        "/peer-shops/{record_id}",
        response_model=PeerShopResponse,
        summary="Get a peer shop by ID",
    )
    def get_peer_shop(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        return serialize_peer_shop(get_peer_shop_or_404(db, record_id))


    @router.get(
        "/peer-shops/{record_id}/image-file",
        summary="Download a protected peer-shop license image",
    )
    def get_peer_shop_image_file(
        record_id: int,
        thumb: int = 0,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        db_record = get_peer_shop_or_404(db, record_id)
        if not db_record.image_path:
            raise HTTPException(status_code=404, detail="Peer-shop image not found")

        image_file = resolve_upload_file(db_record.image_path)
        if image_file is None:
            raise HTTPException(status_code=404, detail="Peer-shop image not found")

        return image_file_response(image_file, db_record.image_name, thumbnail=bool(thumb))


    @router.put(
        "/peer-shops/{record_id}",
        response_model=PeerShopResponse,
        summary="Update a peer shop",
    )
    def update_peer_shop(
        record_id: int,
        payload: PeerShopUpdate,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_peer_shop_or_404(db, record_id)
        for key, value in payload.model_dump().items():
            if key == "extra_fields":
                value = dump_json_object(value or {})
            setattr(db_record, key, value)

        commit_session(db, default_detail="Failed to update peer shop")
        db.refresh(db_record)
        return serialize_peer_shop(db_record)


    @router.delete(
        "/peer-shops/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Delete a peer shop",
    )
    def delete_peer_shop(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_peer_shop_or_404(db, record_id)
        write_audit_log(
            db,
            actor=current_user,
            action="peer_shop_deleted",
            resource_type="peer_shop",
            resource_id=db_record.id,
            details={
                "shop_name": db_record.shop_name,
                "shop_url": db_record.shop_url,
                "image_name": db_record.image_name,
            },
        )
        delete_peer_shop_image_file(db_record)
        db.delete(db_record)
        commit_session(db, default_detail="Failed to delete peer shop")
        return Response(status_code=status.HTTP_204_NO_CONTENT)


    @router.post(
        "/peer-shops/batch-delete",
        response_model=BatchActionResponse,
        summary="Batch delete peer shops",
    )
    def batch_delete_peer_shops(
        payload: BatchDeleteRequest,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        stmt = select(PeerShop).where(PeerShop.id.in_(payload.record_ids))
        records = db.scalars(stmt).all()
        if len(records) != len(set(payload.record_ids)):
            raise HTTPException(status_code=404, detail="One or more peer shops were not found")

        backup_path = create_sqlite_backup("peer-shops-batch-delete")
        write_audit_log(
            db,
            actor=current_user,
            action="peer_shops_batch_deleted",
            resource_type="peer_shop",
            details={
                "record_ids": [record.id for record in records],
                "backup_path": backup_path,
            },
        )

        for record in records:
            delete_peer_shop_image_file(record)
            db.delete(record)

        commit_session(db, default_detail="Failed to batch delete peer shops")
        return {"updated_count": len(records)}


    @router.post(
        "/peer-shops/{record_id}/image",
        response_model=PeerShopResponse,
        summary="Upload or replace peer-shop license image",
    )
    async def upload_peer_shop_image(
        record_id: int,
        image: UploadFile = File(...),
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_peer_shop_or_404(db, record_id)
        await save_peer_shop_image(db_record, image)
        commit_session(db, default_detail="Failed to upload peer-shop image")
        db.refresh(db_record)
        return serialize_peer_shop(db_record)


    @router.delete(
        "/peer-shops/{record_id}/image",
        response_model=PeerShopResponse,
        summary="Delete peer-shop license image",
    )
    def delete_peer_shop_image(
        record_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("editor")),
    ):
        db_record = get_peer_shop_or_404(db, record_id)
        if not db_record.image_path:
            raise HTTPException(status_code=404, detail="Peer-shop image not found")

        clear_peer_shop_image(db_record)
        commit_session(db, default_detail="Failed to delete peer-shop image")
        db.refresh(db_record)
        return serialize_peer_shop(db_record)


    return router
