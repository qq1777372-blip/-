"""Warehouse routes: warehouses, products, stock, inbound/outbound orders.

Split out of main.py unchanged -- every path, status code and response model is
the same, which is what tests/route_snapshot.txt pins. The shared pieces this
needs (session factory, role guard, audit log, upload dirs) are passed into
create_warehouse_router rather than imported, because they live in main.py and
importing them here would be a cycle.
"""

from __future__ import annotations

import mimetypes
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    AdminUser,
    Warehouse,
    WarehouseInboundItem,
    WarehouseInboundOrder,
    WarehouseOutboundItem,
    WarehouseOutboundOrder,
    WarehouseProduct,
    WarehouseStock,
    WarehouseStockMovement,
)
from schemas import (
    WarehouseInboundOrderCreate,
    WarehouseInboundOrderResponse,
    WarehouseOutboundOrderCreate,
    WarehouseOutboundOrderResponse,
    WarehouseOutboundStatusUpdate,
    WarehousePayload,
    WarehouseProductPayload,
    WarehouseProductResponse,
    WarehouseResponse,
    WarehouseStockResponse,
    WarehouseStockMovementResponse,
    WarehouseSummaryResponse,
)

def normalize_warehouse_text(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def generate_warehouse_order_no(prefix: str, timezone: ZoneInfo) -> str:
    return f"{prefix}{datetime.now(timezone):%Y%m%d%H%M%S}{secrets.randbelow(10000):04d}"


def get_warehouse_or_404(db: Session, warehouse_id: int) -> Warehouse:
    record = db.get(Warehouse, warehouse_id)
    if record is None:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return record


def get_warehouse_product_or_404(db: Session, product_id: int) -> WarehouseProduct:
    record = db.get(WarehouseProduct, product_id)
    if record is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return record


def build_warehouse_product_image_url(record: WarehouseProduct) -> str | None:
    if not record.image_path:
        return None
    return f"/warehouse/products/{record.id}/image-file?v={Path(record.image_path).name}"


def serialize_warehouse_product(record: WarehouseProduct) -> dict[str, Any]:
    return {
        "id": record.id, "sku": record.sku, "name": record.name, "barcode": record.barcode,
        "specification": record.specification, "unit": record.unit,
        "cost_price": float(record.cost_price or 0), "warning_quantity": record.warning_quantity,
        "is_active": record.is_active, "remark": record.remark,
        "image_url": build_warehouse_product_image_url(record), "image_name": record.image_name,
        "created_at": record.created_at, "updated_at": record.updated_at,
    }

def delete_warehouse_product_image_file(record: WarehouseProduct, uploads_dir: Path) -> None:
    if record.image_path:
        image_file = uploads_dir / record.image_path
        if image_file.exists():
            image_file.unlink()


async def save_warehouse_product_image(
    record: WarehouseProduct,
    upload: UploadFile,
    *,
    uploads_dir: Path,
    product_upload_dir: Path,
) -> None:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="请选择商品图片")
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="仅支持 JPG、PNG、WebP 图片")
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="图片 MIME 类型无效")
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片文件为空")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 15MB")
    delete_warehouse_product_image_file(record, uploads_dir)
    filename = f"product_{record.id}_{secrets.token_hex(8)}{suffix}"
    (product_upload_dir / filename).write_bytes(content)
    record.image_path = f"warehouse-products/{filename}"
    record.image_name = upload.filename


def merge_warehouse_order_lines(items: list[Any]) -> dict[int, int]:
    merged: dict[int, int] = {}
    for item in items:
        merged[item.product_id] = merged.get(item.product_id, 0) + item.quantity
    return merged

def serialize_warehouse_order_items(
    db: Session,
    item_model: type[WarehouseInboundItem] | type[WarehouseOutboundItem],
    order_id: int,
) -> list[dict[str, Any]]:
    items = db.scalars(select(item_model).where(item_model.order_id == order_id).order_by(item_model.id)).all()
    products = {
        product.id: product
        for product in db.scalars(
            select(WarehouseProduct).where(WarehouseProduct.id.in_([item.product_id for item in items]))
        ).all()
    } if items else {}
    return [
        {
            "product_id": item.product_id,
            "sku": products[item.product_id].sku,
            "product_name": products[item.product_id].name,
            "specification": products[item.product_id].specification,
            "unit": products[item.product_id].unit,
            "image_url": build_warehouse_product_image_url(products[item.product_id]),
            "quantity": item.quantity,
        }
        for item in items
        if item.product_id in products
    ]


def serialize_warehouse_inbound_order(db: Session, record: WarehouseInboundOrder) -> dict[str, Any]:
    warehouse = get_warehouse_or_404(db, record.warehouse_id)
    return {
        "id": record.id,
        "order_no": record.order_no,
        "warehouse_id": record.warehouse_id,
        "warehouse_name": warehouse.name,
        "source_type": record.source_type,
        "supplier": record.supplier,
        "status": record.status,
        "remark": record.remark,
        "operator_username": record.operator_username,
        "completed_at": record.completed_at,
        "created_at": record.created_at,
        "items": serialize_warehouse_order_items(db, WarehouseInboundItem, record.id),
    }

def serialize_warehouse_outbound_order(db: Session, record: WarehouseOutboundOrder) -> dict[str, Any]:
    warehouse = get_warehouse_or_404(db, record.warehouse_id)
    return {
        "id": record.id,
        "order_no": record.order_no,
        "warehouse_id": record.warehouse_id,
        "warehouse_name": warehouse.name,
        "external_order_no": record.external_order_no,
        "delivery_method": record.delivery_method,
        "recipient_name": record.recipient_name,
        "recipient_phone": record.recipient_phone,
        "recipient_address": record.recipient_address,
        "carrier": record.carrier,
        "tracking_no": record.tracking_no,
        "status": record.status,
        "remark": record.remark,
        "operator_username": record.operator_username,
        "shipped_at": record.shipped_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "items": serialize_warehouse_order_items(db, WarehouseOutboundItem, record.id),
    }


def reverse_warehouse_inbound_order(
    db: Session,
    order: WarehouseInboundOrder,
    current_user: AdminUser,
    *,
    reason: str,
) -> None:
    if order.status != "completed":
        raise HTTPException(status_code=409, detail="该入库单已撤销，不能重复操作")
    items = db.scalars(
        select(WarehouseInboundItem).where(WarehouseInboundItem.order_id == order.id).order_by(WarehouseInboundItem.id)
    ).all()
    for item in items:
        stock = db.scalar(
            select(WarehouseStock)
            .where(WarehouseStock.warehouse_id == order.warehouse_id, WarehouseStock.product_id == item.product_id)
            .with_for_update()
        )
        available = (stock.quantity - stock.locked_quantity) if stock else 0
        if stock is None or available < item.quantity:
            product = get_warehouse_product_or_404(db, item.product_id)
            raise HTTPException(
                status_code=409,
                detail=f"{product.sku} 当前可用库存不足，可能已出库或被锁定，无法撤销原入库",
            )

    for item in items:
        stock = db.scalar(
            select(WarehouseStock)
            .where(WarehouseStock.warehouse_id == order.warehouse_id, WarehouseStock.product_id == item.product_id)
            .with_for_update()
        )
        stock.quantity -= item.quantity
        db.flush()
        db.add(WarehouseStockMovement(
            warehouse_id=order.warehouse_id, product_id=item.product_id, movement_type="inbound_correction",
            quantity_change=-item.quantity, quantity_after=stock.quantity, reference_type="inbound_order_correction",
            reference_id=order.id, reference_no=order.order_no, operator_user_id=current_user.id,
            operator_username=current_user.username, remark=reason,
        ))


def create_warehouse_router(
    *,
    get_db: Callable[..., Any],
    require_role: Callable[[str], Any],
    write_audit_log: Callable[..., Any],
    commit_session: Callable[..., Any],
    timezone: ZoneInfo,
    uploads_dir: Path,
    product_upload_dir: Path,
) -> APIRouter:
    """Build the warehouse router.

    Paths stay absolute (no prefix) so the URLs match what main.py registered
    before the split and what tests/route_snapshot.txt pins.
    """
    router = APIRouter(tags=["warehouse"])

    @router.get("/warehouse/summary", response_model=WarehouseSummaryResponse, summary="Warehouse overview")
    def get_warehouse_summary(
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        today_start = datetime.combine(datetime.now(timezone).date(), datetime.min.time())
        low_stock_count = 0
        stocks = db.scalars(select(WarehouseStock)).all()
        products = {product.id: product for product in db.scalars(select(WarehouseProduct)).all()}
        for stock in stocks:
            product = products.get(stock.product_id)
            if product and stock.quantity - stock.locked_quantity <= product.warning_quantity:
                low_stock_count += 1
        movements = db.scalars(
            select(WarehouseStockMovement).where(WarehouseStockMovement.created_at >= today_start)
        ).all()
        return {
            "warehouse_count": db.scalar(select(func.count(Warehouse.id)).where(Warehouse.is_active.is_(True))) or 0,
            "product_count": db.scalar(select(func.count(WarehouseProduct.id)).where(WarehouseProduct.is_active.is_(True))) or 0,
            "total_quantity": sum(stock.quantity for stock in stocks),
            "total_cost": round(sum(stock.quantity * float(products.get(stock.product_id).cost_price or 0) for stock in stocks if products.get(stock.product_id)), 2),
            "low_stock_count": low_stock_count,
            "pending_outbound_count": db.scalar(
                select(func.count(WarehouseOutboundOrder.id)).where(
                    WarehouseOutboundOrder.status.notin_(("shipped", "cancelled"))
                )
            ) or 0,
            "today_inbound_quantity": sum(m.quantity_change for m in movements if m.quantity_change > 0),
            "today_outbound_quantity": abs(sum(m.quantity_change for m in movements if m.quantity_change < 0)),
        }

    @router.get("/warehouse/warehouses", response_model=list[WarehouseResponse], summary="List warehouses")
    def list_warehouses(db: Session = Depends(get_db), _: AdminUser = Depends(require_role("viewer"))):
        return db.scalars(select(Warehouse).order_by(Warehouse.is_active.desc(), Warehouse.id.desc())).all()

    @router.post("/warehouse/warehouses", response_model=WarehouseResponse, status_code=201, summary="Create warehouse")
    def create_warehouse(
        payload: WarehousePayload,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = Warehouse(**payload.model_dump())
        record.code = record.code.strip()
        record.name = record.name.strip()
        db.add(record)
        try:
            db.flush()
            write_audit_log(db, actor=current_user, action="warehouse_created", resource_type="warehouse", resource_id=record.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="仓库编码已存在") from exc
        db.refresh(record)
        return record

    @router.put("/warehouse/warehouses/{warehouse_id}", response_model=WarehouseResponse, summary="Update warehouse")
    def update_warehouse(
        warehouse_id: int,
        payload: WarehousePayload,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_warehouse_or_404(db, warehouse_id)
        for key, value in payload.model_dump().items():
            setattr(record, key, value)
        record.code = record.code.strip()
        record.name = record.name.strip()
        write_audit_log(db, actor=current_user, action="warehouse_updated", resource_type="warehouse", resource_id=record.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="仓库编码已存在") from exc
        db.refresh(record)
        return record

    @router.get("/warehouse/products", response_model=list[WarehouseProductResponse], summary="List warehouse products")
    def list_warehouse_products(db: Session = Depends(get_db), _: AdminUser = Depends(require_role("viewer"))):
        records = db.scalars(select(WarehouseProduct).order_by(WarehouseProduct.is_active.desc(), WarehouseProduct.id.desc())).all()
        return [serialize_warehouse_product(record) for record in records]

    @router.post("/warehouse/products", response_model=WarehouseProductResponse, status_code=201, summary="Create warehouse product")
    def create_warehouse_product(
        payload: WarehouseProductPayload,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        values = payload.model_dump()
        values["barcode"] = normalize_warehouse_text(values["barcode"])
        record = WarehouseProduct(**values)
        record.sku = record.sku.strip()
        record.name = record.name.strip()
        db.add(record)
        try:
            db.flush()
            write_audit_log(db, actor=current_user, action="warehouse_product_created", resource_type="warehouse_product", resource_id=record.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="SKU 或条码已存在") from exc
        db.refresh(record)
        return serialize_warehouse_product(record)

    @router.put("/warehouse/products/{product_id}", response_model=WarehouseProductResponse, summary="Update warehouse product")
    def update_warehouse_product(
        product_id: int,
        payload: WarehouseProductPayload,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_warehouse_product_or_404(db, product_id)
        values = payload.model_dump()
        values["barcode"] = normalize_warehouse_text(values["barcode"])
        for key, value in values.items():
            setattr(record, key, value)
        record.sku = record.sku.strip()
        record.name = record.name.strip()
        write_audit_log(db, actor=current_user, action="warehouse_product_updated", resource_type="warehouse_product", resource_id=record.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="SKU 或条码已存在") from exc
        db.refresh(record)
        return serialize_warehouse_product(record)

    @router.get("/warehouse/products/{product_id}/image-file", summary="View warehouse product image")
    def get_warehouse_product_image_file(
        product_id: int,
        db: Session = Depends(get_db),
        _: AdminUser = Depends(require_role("viewer")),
    ):
        record = get_warehouse_product_or_404(db, product_id)
        if not record.image_path:
            raise HTTPException(status_code=404, detail="商品图片不存在")
        image_file = (uploads_dir / record.image_path).resolve()
        try:
            image_file.relative_to(uploads_dir.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="商品图片不存在") from exc
        if not image_file.is_file():
            raise HTTPException(status_code=404, detail="商品图片不存在")
        media_type, _ = mimetypes.guess_type(image_file.name)
        return FileResponse(image_file, media_type=media_type or "application/octet-stream", filename=record.image_name or image_file.name, content_disposition_type="inline")

    @router.post("/warehouse/products/{product_id}/image", response_model=WarehouseProductResponse, summary="Upload warehouse product image")
    async def upload_warehouse_product_image(
        product_id: int,
        image: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        record = get_warehouse_product_or_404(db, product_id)
        await save_warehouse_product_image(
            record,
            image,
            uploads_dir=uploads_dir,
            product_upload_dir=product_upload_dir,
        )
        write_audit_log(db, actor=current_user, action="warehouse_product_image_updated", resource_type="warehouse_product", resource_id=record.id)
        commit_session(db, default_detail="商品图片保存失败")
        db.refresh(record)
        return serialize_warehouse_product(record)

    @router.get("/warehouse/stocks", response_model=list[WarehouseStockResponse], summary="List warehouse stocks")
    def list_warehouse_stocks(db: Session = Depends(get_db), _: AdminUser = Depends(require_role("viewer"))):
        warehouses = {record.id: record for record in db.scalars(select(Warehouse)).all()}
        products = {record.id: record for record in db.scalars(select(WarehouseProduct)).all()}
        stocks = {(record.warehouse_id, record.product_id): record for record in db.scalars(select(WarehouseStock)).all()}
        result = []
        for warehouse in warehouses.values():
            for product in products.values():
                stock = stocks.get((warehouse.id, product.id))
                quantity = stock.quantity if stock else 0
                locked_quantity = stock.locked_quantity if stock else 0
                available_quantity = quantity - locked_quantity
                result.append({
                    "id": stock.id if stock else None,
                    "warehouse_id": warehouse.id,
                    "warehouse_code": warehouse.code,
                    "warehouse_name": warehouse.name,
                    "product_id": product.id,
                    "sku": product.sku,
                    "product_name": product.name,
                    "barcode": product.barcode,
                    "specification": product.specification,
                    "unit": product.unit,
                    "cost_price": float(product.cost_price or 0),
                    "image_url": build_warehouse_product_image_url(product),
                    "quantity": quantity,
                    "locked_quantity": locked_quantity,
                    "available_quantity": available_quantity,
                    "warning_quantity": product.warning_quantity,
                    "is_low_stock": available_quantity <= product.warning_quantity,
                    "updated_at": stock.updated_at if stock else None,
                })
        return result

    @router.get("/warehouse/inbound-orders", response_model=list[WarehouseInboundOrderResponse], summary="List inbound orders")
    def list_warehouse_inbound_orders(db: Session = Depends(get_db), _: AdminUser = Depends(require_role("viewer"))):
        records = db.scalars(select(WarehouseInboundOrder).order_by(WarehouseInboundOrder.id.desc()).limit(500)).all()
        return [serialize_warehouse_inbound_order(db, record) for record in records]

    @router.post("/warehouse/inbound-orders", response_model=WarehouseInboundOrderResponse, status_code=201, summary="Complete inbound order")
    def create_warehouse_inbound_order(
        payload: WarehouseInboundOrderCreate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        warehouse = get_warehouse_or_404(db, payload.warehouse_id)
        if not warehouse.is_active:
            raise HTTPException(status_code=409, detail="仓库已停用")
        lines = merge_warehouse_order_lines(payload.items)
        products = {product_id: get_warehouse_product_or_404(db, product_id) for product_id in lines}
        if any(not product.is_active for product in products.values()):
            raise HTTPException(status_code=409, detail="入库商品中包含已停用商品")
        now = datetime.utcnow()
        order = WarehouseInboundOrder(
            order_no=generate_warehouse_order_no("RK", timezone), warehouse_id=warehouse.id,
            source_type=payload.source_type, supplier=normalize_warehouse_text(payload.supplier),
            status="completed", remark=normalize_warehouse_text(payload.remark),
            operator_user_id=current_user.id, operator_username=current_user.username,
            completed_at=now,
        )
        db.add(order)
        db.flush()
        for product_id, quantity in lines.items():
            db.add(WarehouseInboundItem(order_id=order.id, product_id=product_id, quantity=quantity))
            stock = db.scalar(
                select(WarehouseStock)
                .where(WarehouseStock.warehouse_id == warehouse.id, WarehouseStock.product_id == product_id)
                .with_for_update()
            )
            if stock is None:
                stock = WarehouseStock(warehouse_id=warehouse.id, product_id=product_id, quantity=0, locked_quantity=0)
                db.add(stock)
            stock.quantity += quantity
            db.flush()
            db.add(WarehouseStockMovement(
                warehouse_id=warehouse.id, product_id=product_id, movement_type="inbound",
                quantity_change=quantity, quantity_after=stock.quantity, reference_type="inbound_order",
                reference_id=order.id, reference_no=order.order_no, operator_user_id=current_user.id,
                operator_username=current_user.username, remark=order.remark,
            ))
        write_audit_log(db, actor=current_user, action="warehouse_inbound_completed", resource_type="warehouse_inbound_order", resource_id=order.id, details={"order_no": order.order_no})
        db.commit()
        db.refresh(order)
        return serialize_warehouse_inbound_order(db, order)

    @router.put("/warehouse/inbound-orders/{order_id}", response_model=WarehouseInboundOrderResponse, summary="Correct inbound order")
    def update_warehouse_inbound_order(
        order_id: int,
        payload: WarehouseInboundOrderCreate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        order = db.get(WarehouseInboundOrder, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="入库单不存在")
        warehouse = get_warehouse_or_404(db, payload.warehouse_id)
        if not warehouse.is_active:
            raise HTTPException(status_code=409, detail="仓库已停用")
        lines = merge_warehouse_order_lines(payload.items)
        products = {product_id: get_warehouse_product_or_404(db, product_id) for product_id in lines}
        if any(not product.is_active for product in products.values()):
            raise HTTPException(status_code=409, detail="入库商品中包含已停用商品")
        try:
            reverse_warehouse_inbound_order(db, order, current_user, reason="编辑入库单，回退原库存")
            old_items = db.scalars(select(WarehouseInboundItem).where(WarehouseInboundItem.order_id == order.id)).all()
            for item in old_items:
                db.delete(item)
            order.warehouse_id = warehouse.id
            order.source_type = payload.source_type
            order.supplier = normalize_warehouse_text(payload.supplier)
            order.remark = normalize_warehouse_text(payload.remark)
            order.operator_user_id = current_user.id
            order.operator_username = current_user.username
            order.completed_at = datetime.utcnow()
            for product_id, quantity in lines.items():
                db.add(WarehouseInboundItem(order_id=order.id, product_id=product_id, quantity=quantity))
                stock = db.scalar(
                    select(WarehouseStock)
                    .where(WarehouseStock.warehouse_id == warehouse.id, WarehouseStock.product_id == product_id)
                    .with_for_update()
                )
                if stock is None:
                    stock = WarehouseStock(warehouse_id=warehouse.id, product_id=product_id, quantity=0, locked_quantity=0)
                    db.add(stock)
                stock.quantity += quantity
                db.flush()
                db.add(WarehouseStockMovement(
                    warehouse_id=warehouse.id, product_id=product_id, movement_type="inbound_correction",
                    quantity_change=quantity, quantity_after=stock.quantity, reference_type="inbound_order_correction",
                    reference_id=order.id, reference_no=order.order_no, operator_user_id=current_user.id,
                    operator_username=current_user.username, remark="编辑入库单，重新入库",
                ))
            write_audit_log(db, actor=current_user, action="warehouse_inbound_corrected", resource_type="warehouse_inbound_order", resource_id=order.id, details={"order_no": order.order_no})
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        db.refresh(order)
        return serialize_warehouse_inbound_order(db, order)

    @router.delete("/warehouse/inbound-orders/{order_id}", response_model=WarehouseInboundOrderResponse, summary="Cancel inbound order")
    def cancel_warehouse_inbound_order(
        order_id: int,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        order = db.get(WarehouseInboundOrder, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="入库单不存在")
        try:
            reverse_warehouse_inbound_order(db, order, current_user, reason="撤销错误入库单")
            order.status = "cancelled"
            write_audit_log(db, actor=current_user, action="warehouse_inbound_cancelled", resource_type="warehouse_inbound_order", resource_id=order.id, details={"order_no": order.order_no})
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        db.refresh(order)
        return serialize_warehouse_inbound_order(db, order)

    @router.get("/warehouse/outbound-orders", response_model=list[WarehouseOutboundOrderResponse], summary="List outbound orders")
    def list_warehouse_outbound_orders(db: Session = Depends(get_db), _: AdminUser = Depends(require_role("viewer"))):
        records = db.scalars(select(WarehouseOutboundOrder).order_by(WarehouseOutboundOrder.id.desc()).limit(500)).all()
        return [serialize_warehouse_outbound_order(db, record) for record in records]

    @router.post("/warehouse/outbound-orders", response_model=WarehouseOutboundOrderResponse, status_code=201, summary="Create outbound order")
    def create_warehouse_outbound_order(
        payload: WarehouseOutboundOrderCreate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        warehouse = get_warehouse_or_404(db, payload.warehouse_id)
        if not warehouse.is_active:
            raise HTTPException(status_code=409, detail="仓库已停用")
        lines = merge_warehouse_order_lines(payload.items)
        products = {product_id: get_warehouse_product_or_404(db, product_id) for product_id in lines}
        if any(not product.is_active for product in products.values()):
            raise HTTPException(status_code=409, detail="出库商品中包含已停用商品")
        stocks: dict[int, WarehouseStock] = {}
        for product_id, quantity in lines.items():
            stock = db.scalar(
                select(WarehouseStock)
                .where(WarehouseStock.warehouse_id == warehouse.id, WarehouseStock.product_id == product_id)
                .with_for_update()
            )
            available = (stock.quantity - stock.locked_quantity) if stock else 0
            if stock is None or available < quantity:
                raise HTTPException(status_code=409, detail=f"SKU {products[product_id].sku} 可用库存不足，当前可用 {available}")
            stocks[product_id] = stock
        order = WarehouseOutboundOrder(
            order_no=generate_warehouse_order_no("CK", timezone), warehouse_id=warehouse.id,
            external_order_no=normalize_warehouse_text(payload.external_order_no),
            delivery_method=payload.delivery_method,
            recipient_name=normalize_warehouse_text(payload.recipient_name), recipient_phone=normalize_warehouse_text(payload.recipient_phone),
            recipient_address=normalize_warehouse_text(payload.recipient_address), carrier=normalize_warehouse_text(payload.carrier),
            tracking_no=normalize_warehouse_text(payload.tracking_no), status="pending", remark=normalize_warehouse_text(payload.remark),
            operator_user_id=current_user.id, operator_username=current_user.username,
        )
        db.add(order)
        db.flush()
        for product_id, quantity in lines.items():
            stocks[product_id].locked_quantity += quantity
            db.add(WarehouseOutboundItem(order_id=order.id, product_id=product_id, quantity=quantity))
        write_audit_log(db, actor=current_user, action="warehouse_outbound_created", resource_type="warehouse_outbound_order", resource_id=order.id, details={"order_no": order.order_no})
        db.commit()
        db.refresh(order)
        return serialize_warehouse_outbound_order(db, order)

    @router.patch("/warehouse/outbound-orders/{order_id}/status", response_model=WarehouseOutboundOrderResponse, summary="Advance outbound workflow")
    def update_warehouse_outbound_status(
        order_id: int,
        payload: WarehouseOutboundStatusUpdate,
        db: Session = Depends(get_db),
        current_user: AdminUser = Depends(require_role("editor")),
    ):
        order = db.scalar(
            select(WarehouseOutboundOrder)
            .where(WarehouseOutboundOrder.id == order_id)
            .with_for_update()
        )
        if order is None:
            raise HTTPException(status_code=404, detail="出库单不存在")
        transitions = {
            "pending": {"picking", "cancelled"}, "picking": {"checked", "cancelled"},
            "checked": {"packed", "cancelled"}, "packed": {"shipped", "cancelled"},
            "shipped": set(), "cancelled": set(),
        }
        if payload.status not in transitions.get(order.status, set()):
            raise HTTPException(status_code=409, detail="不能从当前状态执行该操作")
        items = db.scalars(select(WarehouseOutboundItem).where(WarehouseOutboundItem.order_id == order.id)).all()
        stocks: dict[int, WarehouseStock] = {}
        for item in items:
            stock = db.scalar(
                select(WarehouseStock)
                .where(WarehouseStock.warehouse_id == order.warehouse_id, WarehouseStock.product_id == item.product_id)
                .with_for_update()
            )
            if stock is None or stock.locked_quantity < item.quantity:
                raise HTTPException(status_code=409, detail="锁定库存异常，请检查库存流水")
            stocks[item.product_id] = stock
        order.carrier = normalize_warehouse_text(payload.carrier) or order.carrier
        order.tracking_no = normalize_warehouse_text(payload.tracking_no) or order.tracking_no
        if payload.status == "shipped":
            if order.delivery_method == "shipping" and (not order.carrier or not order.tracking_no):
                raise HTTPException(status_code=422, detail="发货前必须填写快递公司和物流单号")
            for item in items:
                stock = stocks[item.product_id]
                if stock.quantity < item.quantity:
                    raise HTTPException(status_code=409, detail="实际库存不足，无法出库")
                stock.quantity -= item.quantity
                stock.locked_quantity -= item.quantity
                db.add(WarehouseStockMovement(
                    warehouse_id=order.warehouse_id, product_id=item.product_id, movement_type="outbound",
                    quantity_change=-item.quantity, quantity_after=stock.quantity, reference_type="outbound_order",
                    reference_id=order.id, reference_no=order.order_no, operator_user_id=current_user.id,
                    operator_username=current_user.username, remark=order.remark,
                ))
            order.shipped_at = datetime.utcnow()
        elif payload.status == "cancelled":
            for item in items:
                stocks[item.product_id].locked_quantity -= item.quantity
        order.status = payload.status
        order.operator_user_id = current_user.id
        order.operator_username = current_user.username
        write_audit_log(db, actor=current_user, action="warehouse_outbound_status_updated", resource_type="warehouse_outbound_order", resource_id=order.id, details={"order_no": order.order_no, "status": order.status})
        db.commit()
        db.refresh(order)
        return serialize_warehouse_outbound_order(db, order)

    @router.get("/warehouse/movements", response_model=list[WarehouseStockMovementResponse], summary="List stock movements")
    def list_warehouse_movements(db: Session = Depends(get_db), _: AdminUser = Depends(require_role("viewer"))):
        records = db.scalars(select(WarehouseStockMovement).order_by(WarehouseStockMovement.id.desc()).limit(1000)).all()
        warehouses = {record.id: record for record in db.scalars(select(Warehouse)).all()}
        products = {record.id: record for record in db.scalars(select(WarehouseProduct)).all()}
        return [{
            "id": record.id, "warehouse_id": record.warehouse_id,
            "warehouse_name": warehouses.get(record.warehouse_id).name if warehouses.get(record.warehouse_id) else "-",
            "product_id": record.product_id,
            "sku": products.get(record.product_id).sku if products.get(record.product_id) else "-",
            "product_name": products.get(record.product_id).name if products.get(record.product_id) else "-",
            "movement_type": record.movement_type, "quantity_change": record.quantity_change,
            "quantity_after": record.quantity_after, "reference_type": record.reference_type,
            "reference_id": record.reference_id, "reference_no": record.reference_no,
            "operator_username": record.operator_username, "remark": record.remark, "created_at": record.created_at,
        } for record in records]

    return router
