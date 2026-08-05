from __future__ import annotations

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from database import Base
from main import (
    cancel_warehouse_inbound_order,
    create_warehouse_inbound_order,
    create_warehouse_outbound_order,
    update_warehouse_inbound_order,
    update_warehouse_outbound_status,
)
from models import AdminUser, Warehouse, WarehouseProduct, WarehouseStock, WarehouseStockMovement
from schemas import WarehouseInboundOrderCreate, WarehouseOutboundOrderCreate, WarehouseOutboundStatusUpdate


class WarehouseWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.user = AdminUser(id=1, username="tester", password_hash="unused", role="superadmin")
        self.warehouse = Warehouse(code="WH01", name="主仓")
        self.product = WarehouseProduct(sku="SKU-001", name="测试商品", warning_quantity=2)
        self.session.add_all([self.user, self.warehouse, self.product])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_inbound_lock_and_ship_stock_workflow(self) -> None:
        inbound = create_warehouse_inbound_order(
            WarehouseInboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 10}],
            ),
            self.session,
            self.user,
        )
        self.assertEqual(inbound["items"][0]["quantity"], 10)

        outbound = create_warehouse_outbound_order(
            WarehouseOutboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 4}],
            ),
            self.session,
            self.user,
        )
        stock = self.session.scalar(select(WarehouseStock))
        self.assertIsNotNone(stock)
        self.assertEqual((stock.quantity, stock.locked_quantity), (10, 4))

        for next_status in ("picking", "checked", "packed"):
            update_warehouse_outbound_status(
                outbound["id"], WarehouseOutboundStatusUpdate(status=next_status), self.session, self.user
            )
        update_warehouse_outbound_status(
            outbound["id"],
            WarehouseOutboundStatusUpdate(status="shipped", carrier="顺丰", tracking_no="SF123"),
            self.session,
            self.user,
        )

        self.session.refresh(stock)
        self.assertEqual((stock.quantity, stock.locked_quantity), (6, 0))
        movement = self.session.scalar(
            select(WarehouseStockMovement).where(WarehouseStockMovement.movement_type == "outbound")
        )
        self.assertIsNotNone(movement)
        self.assertEqual((movement.quantity_change, movement.quantity_after), (-4, 6))

    def test_outbound_rejects_insufficient_available_stock(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            create_warehouse_outbound_order(
                WarehouseOutboundOrderCreate(
                    warehouse_id=self.warehouse.id,
                    items=[{"product_id": self.product.id, "quantity": 1}],
                ),
                self.session,
                self.user,
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_pickup_outbound_does_not_require_carrier_or_tracking_number(self) -> None:
        create_warehouse_inbound_order(
            WarehouseInboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 2}],
            ),
            self.session,
            self.user,
        )
        outbound = create_warehouse_outbound_order(
            WarehouseOutboundOrderCreate(
                warehouse_id=self.warehouse.id,
                delivery_method="pickup",
                recipient_name="pickup customer",
                recipient_phone="13800000000",
                items=[{"product_id": self.product.id, "quantity": 1}],
            ),
            self.session,
            self.user,
        )
        self.assertEqual(outbound["delivery_method"], "pickup")
        for next_status in ("picking", "checked", "packed", "shipped"):
            outbound = update_warehouse_outbound_status(
                outbound["id"], WarehouseOutboundStatusUpdate(status=next_status), self.session, self.user
            )
        stock = self.session.scalar(select(WarehouseStock))
        self.assertEqual((stock.quantity, stock.locked_quantity), (1, 0))
        self.assertIsNone(outbound["tracking_no"])

    def test_cancel_releases_locked_stock(self) -> None:
        create_warehouse_inbound_order(
            WarehouseInboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 3}],
            ),
            self.session,
            self.user,
        )
        outbound = create_warehouse_outbound_order(
            WarehouseOutboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 2}],
            ),
            self.session,
            self.user,
        )
        update_warehouse_outbound_status(
            outbound["id"], WarehouseOutboundStatusUpdate(status="cancelled"), self.session, self.user
        )
        stock = self.session.scalar(select(WarehouseStock))
        self.assertEqual((stock.quantity, stock.locked_quantity), (3, 0))

    def test_edit_and_cancel_inbound_adjusts_stock_with_correction_movements(self) -> None:
        inbound = create_warehouse_inbound_order(
            WarehouseInboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 10}],
            ),
            self.session,
            self.user,
        )
        corrected = update_warehouse_inbound_order(
            inbound["id"],
            WarehouseInboundOrderCreate(
                warehouse_id=self.warehouse.id,
                supplier="corrected",
                items=[{"product_id": self.product.id, "quantity": 4}],
            ),
            self.session,
            self.user,
        )
        stock = self.session.scalar(select(WarehouseStock))
        self.assertEqual(stock.quantity, 4)
        self.assertEqual(corrected["items"][0]["quantity"], 4)

        cancelled = cancel_warehouse_inbound_order(inbound["id"], self.session, self.user)
        self.session.refresh(stock)
        self.assertEqual(stock.quantity, 0)
        self.assertEqual(cancelled["status"], "cancelled")
        changes = self.session.scalars(
            select(WarehouseStockMovement.quantity_change).order_by(WarehouseStockMovement.id)
        ).all()
        self.assertEqual(changes, [10, -10, 4, -4])

    def test_cancel_inbound_rejects_stock_already_locked(self) -> None:
        inbound = create_warehouse_inbound_order(
            WarehouseInboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 3}],
            ),
            self.session,
            self.user,
        )
        create_warehouse_outbound_order(
            WarehouseOutboundOrderCreate(
                warehouse_id=self.warehouse.id,
                items=[{"product_id": self.product.id, "quantity": 1}],
            ),
            self.session,
            self.user,
        )
        with self.assertRaises(HTTPException) as raised:
            cancel_warehouse_inbound_order(inbound["id"], self.session, self.user)
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
