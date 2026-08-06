"""Generate a randomized local development dataset.

Why this exists: the checked-in shop_records.db is a copy of production, so
debugging against it means real shop names, real money and real people. This
script builds a throwaway database from scratch instead, with the same shape but
invented content.

Two stores are written, matching what the backend actually reads:

  dev.db            main SQLAlchemy database (accounts, shops, tasks, expenses,
                    profits, warehouse)
  dev_sycm.db       the 生意参谋 store, plain sqlite3, path comes from
                    SYCM_DATA_DB_PATH

The sycm data deliberately includes the two cases the dedup logic has to tell
apart:

  - one shop collected under two 千牛 account ids (sub-account), which must be
    merged into a single canonical_shop_id
  - two genuinely different shops that share a normalized name, which must NOT
    be merged

Usage:
    py -3 scripts/seed_dev_data.py                  # writes dev.db + dev_sycm.db
    py -3 scripts/seed_dev_data.py --seed 7         # reproducible variation
    py -3 scripts/seed_dev_data.py --force          # overwrite existing files

Every account's password is `dev12345`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import sqlite3
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEV_PASSWORD = "dev12345"

SHOP_WORDS_A = ["星野", "云澜", "松间", "拾光", "南屿", "青柚", "叁鹿", "白鲸", "初禾", "木野"]
SHOP_WORDS_B = ["家居", "服饰", "食品", "数码", "美妆", "文具", "户外", "母婴"]
OWNER_NAMES = ["赵一", "钱二", "孙三", "李四", "周五", "吴六"]
EXPENSE_CATEGORIES = ["办公用品", "差旅交通", "平台服务费", "推广投放", "物流快递", "设备采购"]
PAYMENT_ACCOUNTS = ["对公账户", "支付宝-运营", "微信-运营", "备用金"]
PRODUCT_WORDS = ["收纳盒", "保温杯", "帆布袋", "充电线", "记事本", "毛巾", "香薰", "键盘垫"]


def hash_password(password: str) -> str:
    """Mirror of main.hash_password so seeding needs no app import."""
    iterations = 300_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def full_permissions(level: str) -> str:
    modules = [
        "dashboard", "links", "task_bookkeeping", "dingtalk_profits", "shop_records",
        "peer_shops", "licenses", "account_usage", "mobile_devices", "warehouse",
    ]
    return json.dumps({module: level for module in modules}, ensure_ascii=False)


def write_license_placeholder(subject_name: str, credit_code: str) -> tuple[str, str] | None:
    """Draw a fake license image into uploads/licenses.

    The list and detail pages read `image_url`, which the backend only builds
    when `image_path` is set -- with no file the row falls back to a letter
    avatar, so dev data needs a real bitmap on disk. PNG (not SVG) because the
    thumbnail path runs it through Pillow.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    target_dir = PROJECT_ROOT / "uploads" / "licenses"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"dev-{credit_code}.png"
    image = Image.new("RGB", (840, 592), "#f6f4ee")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 821, 573), outline="#b23c3c", width=3)
    draw.text((54, 62), "营业执照 (开发占位图)", fill="#b23c3c")
    draw.text((54, 132), f"名称  {subject_name}", fill="#2b2b2b")
    draw.text((54, 178), f"统一社会信用代码  {credit_code}", fill="#2b2b2b")
    draw.text((54, 224), "本图由 seed_dev_data.py 生成，非真实证照", fill="#7a7a7a")
    draw.ellipse((596, 372, 776, 552), outline="#b23c3c", width=3)
    draw.text((648, 456), "开发专用", fill="#b23c3c")
    image.save(target_dir / filename, "PNG")
    return f"licenses/{filename}", f"{subject_name}营业执照.png"


def seed_main_db(db_path: Path, rng: random.Random) -> dict[str, int]:
    from app.core.database import Base
    from models import (
        AccountUsageRecord, AdminUser, AppSetting, CompanyExpenseRecord,
        DingTalkProfitRecord, LicenseRecord, MobileDeviceRecord, PeerShop, SavedLink,
        ShopRecord, TaskBookkeepingOwner, TaskBookkeepingRecord, Warehouse,
        WarehouseInboundItem, WarehouseInboundOrder, WarehouseOutboundItem,
        WarehouseOutboundOrder, WarehouseProduct, WarehouseStock, WarehouseStockMovement,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    counts: dict[str, int] = {}

    # --- accounts: one per role, so permission gates can be exercised locally.
    accounts = [
        ("admin", "开发超管", "superadmin", None),
        ("editor", "开发编辑", "editor", full_permissions("write")),
        ("viewer", "开发只读", "viewer", full_permissions("read")),
        ("limited", "仅记账", "viewer", json.dumps({"task_bookkeeping": "write"}, ensure_ascii=False)),
    ]
    users = []
    for username, display_name, role, permissions in accounts:
        user = AdminUser(
            username=username,
            display_name=display_name,
            password_hash=hash_password(DEV_PASSWORD),
            role=role,
            permissions_json=permissions,
            is_active=True,
        )
        users.append(user)
    db.add_all(users)
    db.flush()
    counts["accounts"] = len(users)
    admin = users[0]

    # --- shops / peers / licenses / devices / account usage
    shop_names = []
    for _ in range(12):
        name = f"{rng.choice(SHOP_WORDS_A)}{rng.choice(SHOP_WORDS_B)}旗舰店"
        if name not in shop_names:
            shop_names.append(name)
    for index, name in enumerate(shop_names):
        db.add(ShopRecord(
            shop_name=name,
            platform=rng.choice(["淘宝", "天猫", "拼多多", "抖店"]),
            daily_revenue=round(rng.uniform(300, 9000), 2),
            remark="开发用假数据",
            date=date.today() - timedelta(days=index),
            extra_fields="{}",
            record_data="{}",
        ))
    counts["shops"] = len(shop_names)

    for index in range(6):
        db.add(PeerShop(
            shop_name=f"{rng.choice(SHOP_WORDS_A)}{rng.choice(SHOP_WORDS_B)}同行店",
            shop_url=f"https://example.invalid/shop/{index}",
            remark="竞品跟踪（假数据）",
            extra_fields="{}",
        ))
    counts["peers"] = 6

    for index in range(5):
        issued = date.today() - timedelta(days=rng.randint(200, 900))
        subject_name = f"{rng.choice(SHOP_WORDS_A)}{rng.choice(SHOP_WORDS_B)}有限公司"
        # Unique and obviously fake: never looks like a real credit code.
        credit_code = f"DEV{index:02d}{rng.randint(10**10, 10**11 - 1)}"
        placeholder = write_license_placeholder(subject_name, credit_code)
        db.add(LicenseRecord(
            subject_name=subject_name,
            credit_code=credit_code,
            legal_representative=rng.choice(OWNER_NAMES),
            issue_date=issued,
            expiry_date=issued + timedelta(days=rng.choice([365, 730, 1825])),
            remark="开发用假执照",
            extra_fields="{}",
            image_path=placeholder[0] if placeholder else None,
            image_name=placeholder[1] if placeholder else None,
        ))
    counts["licenses"] = 5

    for index in range(4):
        db.add(MobileDeviceRecord(
            device_name=f"开发机-{index + 1}",
            primary_card=f"170{rng.randint(10**7, 10**8 - 1)}",
            remark="假设备",
            extra_fields="{}",
        ))
    counts["devices"] = 4

    for index in range(6):
        db.add(AccountUsageRecord(
            account_name=f"dev_account_{index + 1}",
            phone_number=f"170{rng.randint(10**7, 10**8 - 1)}",
            device_name=f"开发机-{rng.randint(1, 4)}",
            usage_notes="假账号使用记录",
            is_banned=index == 5,
            banned_reason="风控测试" if index == 5 else None,
            extra_fields="{}",
        ))
    counts["account_usage"] = 6

    # --- task bookkeeping: mixed statuses so the 待办提醒 cards are non-empty.
    owners = [TaskBookkeepingOwner(name=name) for name in OWNER_NAMES[:4]]
    db.add_all(owners)
    db.flush()
    task_total = 0
    for index in range(40):
        principal = round(rng.uniform(80, 2600), 2)
        db.add(TaskBookkeepingRecord(
            task_time=datetime.now() - timedelta(days=rng.randint(0, 60), hours=rng.randint(0, 23)),
            shop_name=rng.choice(shop_names),
            owner_name=rng.choice(OWNER_NAMES[:4]),
            principal_amount=principal,
            order_count=rng.randint(1, 6),
            commission_amount=round(principal * rng.uniform(0.02, 0.09), 2),
            gift_amount=round(rng.uniform(0, 60), 2),
            # Only "pending" and "completed" pass the response schema
            # (TaskStatusType); "signed"/"settled" reach the DB fine but make
            # /task-bookkeeping/summary fail response validation with a 500.
            signed_status=rng.choice(["pending", "completed", "completed", "completed"]),
            settlement_status=rng.choice(["pending", "pending", "completed"]),
            note="假任务记录",
        ))
        task_total += 1
    counts["tasks"] = task_total

    # --- company expenses across the last few months
    expense_total = 0
    today = date.today()
    for index in range(60):
        # A third lands inside the current month so the summary card on the
        # 公司记账 page is not ¥0.00 on a fresh seed.
        if index % 3 == 0:
            expense_date = today.replace(day=1) + timedelta(days=rng.randint(0, today.day - 1))
        else:
            expense_date = today - timedelta(days=rng.randint(0, 120))
        # Values must match the Literals in schemas.py (CompanyExpensePaymentType
        # / CompanyExpenseReimbursementStatus) or the list endpoint 500s on
        # response validation. They are also coupled: the backend forces
        # not_required whenever the company paid, so only employee rows carry a
        # real reimbursement state.
        payment_type = rng.choice(["company", "company", "employee"])
        if payment_type == "company":
            reimbursement_status = "not_required"
        else:
            reimbursement_status = rng.choice(["pending", "pending", "reimbursed"])
        db.add(CompanyExpenseRecord(
            expense_date=expense_date,
            amount=Decimal(str(round(rng.uniform(15, 3200), 2))),
            category=rng.choice(EXPENSE_CATEGORIES),
            payment_type=payment_type,
            payment_account=rng.choice(PAYMENT_ACCOUNTS),
            expense_scope="公共费用",
            description="开发用假流水",
            approval_status=rng.choice(["approved", "approved", "pending"]),
            reimbursement_status=reimbursement_status,
            submitter_user_id=admin.id,
            submitter_name=admin.display_name or admin.username,
        ))
        expense_total += 1
    counts["company_expenses"] = expense_total

    # --- dingtalk profits: 6 whole months so the home chart has bars.
    profit_total = 0
    source_id = 1
    for month_offset in range(6):
        anchor = (date.today().replace(day=1) - timedelta(days=month_offset * 30)).replace(day=1)
        for _ in range(rng.randint(3, 7)):
            db.add(DingTalkProfitRecord(
                source_record_id=source_id,
                report_date=anchor + timedelta(days=rng.randint(0, 27)),
                store_name=rng.choice(shop_names),
                # A few negative months keep the chart's negative branch reachable.
                profit=round(rng.uniform(-400, 5200), 2),
                reporter_name=rng.choice(OWNER_NAMES),
                reporter_id=f"dev-reporter-{rng.randint(1, 6)}",
                batch_id=f"dev-batch-{month_offset}",
            ))
            source_id += 1
            profit_total += 1
    counts["profit_records"] = profit_total

    # --- warehouse: products, stock, one inbound and one outbound order.
    warehouses = [
        Warehouse(code="DEV-A", name="开发主仓", is_active=True, remark="假仓库"),
        Warehouse(code="DEV-B", name="开发备仓", is_active=True, remark="假仓库"),
    ]
    db.add_all(warehouses)
    db.flush()

    products = []
    for index in range(10):
        products.append(WarehouseProduct(
            sku=f"DEV-SKU-{index + 1:03d}",
            name=f"{rng.choice(PRODUCT_WORDS)}{index + 1}",
            unit="件",
            # Non-zero so the "缺少成本价" data alert stays quiet by default.
            cost_price=round(rng.uniform(3, 180), 2),
            warning_quantity=rng.randint(5, 20),
            is_active=True,
            remark="假商品",
        ))
    db.add_all(products)
    db.flush()
    counts["products"] = len(products)

    low_stock = 0
    for product in products:
        for warehouse in warehouses:
            quantity = rng.randint(0, 120)
            if quantity < product.warning_quantity:
                low_stock += 1
            db.add(WarehouseStock(
                warehouse_id=warehouse.id,
                product_id=product.id,
                quantity=quantity,
                locked_quantity=0,
            ))
    counts["stock_rows"] = len(products) * len(warehouses)
    counts["low_stock_rows"] = low_stock

    inbound = WarehouseInboundOrder(
        order_no="DEV-IN-0001",
        warehouse_id=warehouses[0].id,
        source_type="purchase",
        supplier="开发供应商",
        status="completed",
        operator_user_id=admin.id,
        operator_username=admin.username,
        completed_at=datetime.now() - timedelta(days=3),
    )
    db.add(inbound)
    db.flush()
    for product in products[:4]:
        quantity = rng.randint(10, 60)
        db.add(WarehouseInboundItem(order_id=inbound.id, product_id=product.id, quantity=quantity))
        db.add(WarehouseStockMovement(
            warehouse_id=warehouses[0].id,
            product_id=product.id,
            movement_type="inbound",
            quantity_change=quantity,
            quantity_after=quantity,
            reference_type="inbound_order",
            reference_id=inbound.id,
            reference_no=inbound.order_no,
            operator_user_id=admin.id,
            operator_username=admin.username,
        ))

    outbound = WarehouseOutboundOrder(
        order_no="DEV-OUT-0001",
        warehouse_id=warehouses[0].id,
        external_order_no="DEV-EXT-0001",
        delivery_method="shipping",
        recipient_name="张测试",
        recipient_phone="17000000000",
        recipient_address="示例省示例市示例路 1 号",
        carrier="示例快递",
        tracking_no="DEV000000001",
        status="pending",
        operator_user_id=admin.id,
        operator_username=admin.username,
    )
    db.add(outbound)
    db.flush()
    for product in products[:2]:
        db.add(WarehouseOutboundItem(order_id=outbound.id, product_id=product.id, quantity=rng.randint(1, 5)))
    counts["warehouse_orders"] = 2

    # --- links + the shared home layout, so the App has something to read.
    for index in range(5):
        db.add(SavedLink(
            title=f"开发链接 {index + 1}",
            url=f"https://example.invalid/doc/{index + 1}",
            category=rng.choice(["规范", "工具", "培训"]),
            description="假链接",
            sort_order=index,
            author_user_id=admin.id,
            author_username=admin.username,
        ))
    counts["links"] = 5

    db.add(AppSetting(
        key="ui:home-modules",
        value=json.dumps(
            ["sycm", "company-expenses", "tasks", "profits", "shops", "warehouse-stock", "links", "knowledge"],
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    ))

    db.commit()
    db.close()
    engine.dispose()
    return counts


def sycm_metric(value: float) -> dict[str, object]:
    """One metric the way the live collector wraps it."""
    return {"cycleCrc": None, "value": value}


def sycm_overview(
    rng: random.Random, uv: float, pv: float, cart: float, buyers: float, pay_amt: float
) -> str:
    """Shape a metrics blob the way the live collector does: {"value": n}.

    The headline six are passed in so they agree with the snapshot's own
    columns. The rest are the fields the 详细指标 tab reads -- without them that
    tab renders empty.
    """
    metric = sycm_metric
    itm_uv = round(uv * rng.uniform(0.55, 0.95))
    crt_byr = round(buyers * rng.uniform(1.05, 1.8))
    return json.dumps({
        "uv": metric(uv),
        "pv": metric(pv),
        "cartByrCnt": metric(cart),
        "payByrCnt": metric(buyers),
        "payAmt": metric(pay_amt),
        "payRate": metric(round(buyers / uv, 4) if uv else 0.0),
        "itmUv": metric(float(itm_uv)),
        "itmPv": metric(round(itm_uv * rng.uniform(1.3, 2.6), 2)),
        "newUv": metric(float(round(uv * rng.uniform(0.35, 0.7)))),
        "oldUv": metric(float(round(uv * rng.uniform(0.2, 0.5)))),
        "cltCnt": metric(float(rng.randint(0, 140))),
        "shopCltByrCnt": metric(float(rng.randint(0, 90))),
        "itmCltByrCnt": metric(float(rng.randint(0, 120))),
        "crtByrCnt": metric(float(crt_byr)),
        "payOrdCnt": metric(float(round(buyers * rng.uniform(1.0, 1.6)))),
        "uvValue": metric(round(pay_amt / uv, 4) if uv else 0.0),
        "payPct": metric(round(pay_amt / buyers, 2) if buyers else 0.0),
        "crtRate": metric(round(crt_byr / uv, 4) if uv else 0.0),
    }, ensure_ascii=False, separators=(",", ":"))


SYCM_SOURCE_CHANNELS = ["手淘搜索", "手淘推荐", "购物车", "我的淘宝", "直通车", "淘内免费其他"]


def sycm_source_tree(rng: random.Random, uv: float, buyers: float, pay_amt: float) -> str:
    """Shape the traffic-source rows the way the live collector does.

    Must be a JSON *array* -- /api/sycm/upload rejects anything else, and the
    工作台 流量来源 tab reads pageName/uv/payByrCnt/payAmt off each entry.
    """
    weights = [rng.uniform(0.5, 3.0) for _ in SYCM_SOURCE_CHANNELS]
    total = sum(weights)
    rows = []
    for channel, weight in zip(SYCM_SOURCE_CHANNELS, weights):
        share = weight / total
        rows.append({
            "pageName": sycm_metric(channel),
            "uv": sycm_metric(float(round(uv * share))),
            "payByrCnt": sycm_metric(float(round(buyers * share))),
            "payAmt": sycm_metric(round(pay_amt * share, 2)),
        })
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def seed_sycm_db(db_path: Path, rng: random.Random) -> dict[str, int]:
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS sycm_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id TEXT NOT NULL,
            shop_name TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            received_at TEXT NOT NULL,
            uv REAL,
            pv REAL,
            cart_byr_cnt REAL,
            pay_byr_cnt REAL,
            pay_amt REAL,
            pay_rate REAL,
            overview_json TEXT NOT NULL,
            source_tree_json TEXT NOT NULL,
            period TEXT NOT NULL DEFAULT 'today',
            date_end TEXT NOT NULL DEFAULT '',
            UNIQUE(shop_id, collected_at)
        );
        CREATE TABLE IF NOT EXISTS sycm_shop_aliases (
            account_id TEXT PRIMARY KEY,
            canonical_shop_id TEXT NOT NULL,
            shop_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sycm_sync_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            requested_by INTEGER,
            requested_at TEXT NOT NULL,
            claimed_at TEXT,
            completed_at TEXT,
            error TEXT NOT NULL DEFAULT '',
            results_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS sycm_collector_devices (
            device_id TEXT PRIMARY KEY,
            device_name TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sycm_shop_owners (
            shop_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        """
    )

    now = datetime.now()
    stamp = now.isoformat(timespec="seconds")
    devices = [
        ("dev-device-a", "开发采集机 A"),
        ("dev-device-b", "开发采集机 B"),
    ]
    for device_id, device_name in devices:
        connection.execute(
            "INSERT OR REPLACE INTO sycm_collector_devices VALUES (?,?,?,?)",
            (device_id, device_name, stamp, stamp),
        )

    # account_id -> (shop_name, canonical_shop_id)
    #
    # 2110000000001/2 are the SAME shop seen through a main and a sub 千牛
    # account: the dedup logic must fold them together. 2110000000003/4 share a
    # normalized name but are different businesses and must stay separate --
    # that is the case with no test coverage today.
    accounts = [
        ("2110000000001", "开发星野家居旗舰店", "2110000000001"),
        ("2110000000002", "开发星野家居旗舰店", "2110000000001"),
        ("2110000000003", "开发云澜服饰旗舰店", "2110000000003"),
        ("2110000000004", "开发云澜服饰旗舰店", "2110000000004"),
        ("2110000000005", "开发松间食品旗舰店", "2110000000005"),
    ]
    connection.execute(
        "INSERT OR REPLACE INTO sycm_shop_aliases VALUES (?,?,?,?,?)",
        ("2110000000002", "2110000000001", "开发星野家居旗舰店", "migration", stamp),
    )

    snapshots = 0
    for account_id, shop_name, canonical in accounts:
        owner_device = devices[0][0] if canonical.endswith(("1", "3")) else devices[1][0]
        connection.execute(
            "INSERT OR REPLACE INTO sycm_shop_owners VALUES (?,?,?,?)",
            (canonical, owner_device, stamp, stamp),
        )
        for day_offset in range(7):
            day = (now - timedelta(days=day_offset)).date()
            for period in ("today", "yesterday"):
                # `today` is an intraday rolling snapshot: several rows share a
                # (period, date_end) on purpose. The real unique key is
                # (shop_id, collected_at).
                sample_count = 3 if period == "today" else 1
                for sample in range(sample_count):
                    collected = datetime.combine(day, datetime.min.time()) + timedelta(
                        hours=9 + sample * 4, minutes=rng.randint(0, 59)
                    )
                    pay_amt = round(rng.uniform(120, 9800), 2)
                    uv = float(rng.randint(80, 4000))
                    pv = round(uv * rng.uniform(1.4, 3.2), 2)
                    cart = float(rng.randint(0, 120))
                    buyers = float(rng.randint(0, min(90, int(uv))))
                    overview = sycm_overview(rng, uv, pv, cart, buyers, pay_amt)
                    source_tree = sycm_source_tree(rng, uv, buyers, pay_amt)
                    try:
                        connection.execute(
                            """
                            INSERT INTO sycm_snapshots
                              (shop_id, shop_name, collected_at, received_at, uv, pv,
                               cart_byr_cnt, pay_byr_cnt, pay_amt, pay_rate,
                               overview_json, source_tree_json, period, date_end)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                account_id, shop_name, collected.isoformat(timespec="seconds"), stamp,
                                uv, pv, cart, buyers,
                                pay_amt, round(buyers / uv, 4) if uv else 0.0,
                                overview, source_tree, period, day.isoformat(),
                            ),
                        )
                        snapshots += 1
                    except sqlite3.IntegrityError:
                        pass

    connection.execute(
        "INSERT INTO sycm_sync_requests (status, requested_by, requested_at, completed_at) VALUES (?,?,?,?)",
        ("completed", 1, stamp, stamp),
    )
    connection.commit()
    counts = {
        "sycm_accounts": len(accounts),
        "sycm_aliases": 1,
        "sycm_snapshots": snapshots,
        "sycm_devices": len(devices),
    }
    connection.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a randomized local dev dataset")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible data")
    parser.add_argument("--force", action="store_true", help="overwrite existing dev databases")
    parser.add_argument("--main-db", default=str(PROJECT_ROOT / "dev.db"))
    parser.add_argument("--sycm-db", default=str(PROJECT_ROOT / "dev_sycm.db"))
    args = parser.parse_args()

    main_db = Path(args.main_db)
    sycm_db = Path(args.sycm_db)

    for path in (main_db, sycm_db):
        if path.exists():
            if not args.force:
                print(f"refusing to overwrite {path} (pass --force)", file=sys.stderr)
                return 1
            path.unlink()

    rng = random.Random(args.seed)
    counts = seed_main_db(main_db, rng)
    counts.update(seed_sycm_db(sycm_db, rng))

    print(f"main db : {main_db}")
    print(f"sycm db : {sycm_db}")
    for key in sorted(counts):
        print(f"  {key:<18} {counts[key]}")
    print()
    print("accounts: admin / editor / viewer / limited")
    print(f"password: {DEV_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
