from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from main import (
    get_system_settings,
    list_system_alerts,
    update_system_alert_status,
    update_system_settings,
)
from models import AdminUser, Warehouse, WarehouseProduct, WarehouseStock
from schemas import SystemAlertStatusRequest, SystemSettingsResponse


class SystemAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = AdminUser(username="admin", password_hash="unused", role="superadmin", is_active=True)
        warehouse = Warehouse(code="WH", name="主仓")
        product = WarehouseProduct(sku="SKU-1", name="测试商品", unit="件", warning_quantity=3, is_active=True)
        self.db.add_all([self.user, warehouse, product])
        self.db.flush()
        self.db.add(WarehouseStock(warehouse_id=warehouse.id, product_id=product.id, quantity=2, locked_quantity=0))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_low_stock_alert_can_be_acknowledged_and_reopened(self) -> None:
        # items/total are narrowed by the category filter, but the counts are
        # deliberately global: they feed a badge that shows everything still
        # outstanding, not just the tab being viewed. The fixture product has no
        # cost price and no profit rows, so it also raises two data alerts.
        result = list_system_alerts(category="inventory", status_filter="open", db=self.db, _=self.user)
        self.assertEqual(result["total"], 1)
        self.assertEqual([item["category"] for item in result["items"]], ["inventory"])
        open_before = result["open_count"]
        alert_key = result["items"][0]["key"]

        acknowledged = update_system_alert_status(
            alert_key, SystemAlertStatusRequest(acknowledged=True), self.db, self.user,
        )
        self.assertEqual(acknowledged["open_count"], open_before - 1)
        self.assertEqual(acknowledged["acknowledged_count"], 1)

        reopened = update_system_alert_status(
            alert_key, SystemAlertStatusRequest(acknowledged=False), self.db, self.user,
        )
        self.assertEqual(reopened["open_count"], open_before)
        self.assertEqual(reopened["acknowledged_count"], 0)

    def test_system_settings_are_persisted(self) -> None:
        payload = SystemSettingsResponse(session_duration_hours=24, license_expiry_days=45)
        saved = update_system_settings(payload, self.db, self.user)
        self.assertEqual(saved["session_duration_hours"], 24)
        self.assertEqual(get_system_settings(self.db)["license_expiry_days"], 45)


if __name__ == "__main__":
    unittest.main()
