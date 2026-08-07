import hashlib
import hmac
import asyncio
import base64
import io
import json
import logging
import math
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, suppress
from datetime import date as date_type
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Generator
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import httpx
import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken

from fastapi import Cookie, Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.account_password_crypto import (
    AccountPasswordEncryptionError,
    decrypt_account_usage_secret,
    decrypt_account_password,
    encrypt_account_usage_secret,
    encrypt_account_password,
    is_account_usage_secret_encrypted,
    is_account_password_encrypted,
)
from app.core.config import settings
from app.core.redis import cache_get_json, cache_set_json
from app.api.routes.health import create_health_router
from app.api.routes.peer_shops import create_peer_shop_router
from app.api.routes.server_status import create_server_status_router
from app.api.routes.warehouse import create_warehouse_router
from database import Base, SessionLocal, engine
from models import (
    AccountUsageRecord,
    AdminSession,
    AdminUser,
    AuditLog,
    CompanyExpenseRecord,
    AppSetting,
    CustomField,
    DingTalkProfitRecord,
    LicenseRecord,
    LoginAttempt,
    MobileDeviceRecord,
    PeerShop,
    PersonalExpenseRecord,
    SavedLink,
    ShopRecord,
    TaskBookkeepingOwner,
    TaskBookkeepingRecord,
    TaskBookkeepingShop,
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
    AccountUsageBatchStatusUpdateRequest,
    AccountUsageRecordCreate,
    AccountUsageAccountNameRevealResponse,
    AccountUsagePasswordRevealRequest,
    AccountUsagePasswordRevealResponse,
    AccountUsageRecordResponse,
    AccountUsageRecordUpdate,
    AdminUserCreateRequest,
    AdminUserAccessUpdateRequest,
    AdminUserPasswordResetRequest,
    AdminSessionResponse,
    AdminUserResponse,
    AdminUserStatusUpdateRequest,
    AuditLogResponse,
    ChangePasswordRequest,
    CompanyExpenseCreate,
    CompanyExpenseResponse,
    CompanyExpenseStatusUpdate,
    CompanyExpenseSummaryResponse,
    CompanyExpenseUpdate,
    PersonalExpenseCreate,
    PersonalExpenseResponse,
    PersonalExpenseSummaryResponse,
    PersonalExpenseUpdate,
    CurrentUserProfileUpdateRequest,
    CurrentUserResponse,
    BatchActionResponse,
    BatchDeleteRequest,
    DashboardStatsResponse,
    SystemAlertListResponse,
    ExpenseCategoryListResponse,
    ExpenseCategoryUpdateRequest,
    SystemAlertStatusRequest,
    SystemSettingsResponse,
    ServerStatusResponse,
    DingTalkProfitDeleteBatchRequest,
    DingTalkProfitDeleteBatchResponse,
    DingTalkProfitMonthlySummaryResponse,
    DingTalkProfitRecordResponse,
    DingTalkProfitSummaryResponse,
    DingTalkProfitSyncBatchRequest,
    DingTalkProfitSyncBatchResponse,
    FieldDefinitionCreate,
    FieldDefinitionReorderRequest,
    FieldDefinitionResponse,
    FieldDefinitionUpdate,
    GlobalSearchResponse,
    LicenseRecordCreate,
    LicenseRecordResponse,
    LicenseRecordUpdate,
    LoginRequest,
    LoginCaptchaResponse,
    TotpConfirmRequest,
    TotpDisableRequest,
    TotpSetupRequest,
    TotpSetupResponse,
    MobileDeviceRecordCreate,
    MobileDeviceRecordResponse,
    MobileDeviceRecordUpdate,
    PeerShopCreate,
    PeerShopResponse,
    PeerShopUpdate,
    RegisterRequest,
    SavedLinkCreate,
    SavedLinkPushRequest,
    SavedLinkResponse,
    SavedLinkUpdate,
    SoftwareActivateRequest,
    SoftwareAuthDevicePayload,
    SoftwareAuthResponse,
    SoftwareLoginRequest,
    SoftwareRegisterRequest,
    SoftwareUserResponse,
    ShopRecordCreate,
    ShopRecordResponse,
    ShopRecordUpdate,
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
    WarehouseInboundOrderCreate,
    WarehouseInboundOrderResponse,
    WarehouseOutboundOrderCreate,
    WarehouseOutboundOrderResponse,
    WarehouseOutboundStatusUpdate,
    WarehousePayload,
    WarehouseProductPayload,
    WarehouseProductResponse,
    WarehouseResponse,
    WarehouseStockMovementResponse,
    WarehouseStockResponse,
    WarehouseSummaryResponse,
)


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
APP_FRONTEND_DIST_DIR = BASE_DIR / "app-frontend-dist"
TUTORIALS_DIST_DIR = BASE_DIR / "tutorials-dist"
UPLOADS_DIR = BASE_DIR / "uploads"
LICENSE_UPLOAD_DIR = UPLOADS_DIR / "licenses"
RULE_CATALOG_DB_PATH = Path(
    os.getenv("RULE_CATALOG_DB_PATH", "/srv/fastapiproject/rule_catalog/data/category_rules.db"),
)
PRODUCT_PARSE_CACHE_DB_PATH = Path(
    os.getenv("PRODUCT_PARSE_CACHE_DB_PATH", "/srv/fastapiproject/product_parse_cache/product_parse_cache.db"),
)
PUBLISH_FAILURE_REPORT_DB_PATH = Path(
    os.getenv("PUBLISH_FAILURE_REPORT_DB_PATH", "/srv/fastapiproject/publish_failure_reports/publish_failure_reports.db"),
)
SYCM_DATA_DB_PATH = Path(
    os.getenv("SYCM_DATA_DB_PATH", "/srv/fastapiproject/sycm_data/sycm_data.db"),
)
SYCM_UPLOAD_TOKEN_HEADER = "X-Sycm-Upload-Token"
PUBLISH_FAILURE_REPORT_READER_USERNAMES = {
    value.strip()
    for value in os.getenv("PUBLISH_FAILURE_REPORT_READER_USERNAMES", "1777372").split(",")
    if value.strip()
}
RULE_CATALOG_CACHE_TTL_SECONDS = 60.0
_rule_catalog_cache_lock = threading.Lock()
_rule_catalog_cache: dict[str, Any] = {
    "mtime_ns": None,
    "created_at": 0.0,
    "payload": None,
}
LINK_UPLOAD_DIR = UPLOADS_DIR / "links"
AVATAR_UPLOAD_DIR = UPLOADS_DIR / "avatars"
PEER_SHOP_UPLOAD_DIR = UPLOADS_DIR / "peer-shops"
WAREHOUSE_PRODUCT_UPLOAD_DIR = UPLOADS_DIR / "warehouse-products"
COMPANY_EXPENSE_UPLOAD_DIR = UPLOADS_DIR / "company-expenses"
PERSONAL_EXPENSE_UPLOAD_DIR = UPLOADS_DIR / "personal-expenses"
COMPANY_EXPENSE_APP_DIR = BASE_DIR / "company-expense-app"
EXPENSE_SHORTCUT_SETTING_PREFIX = "expense-shortcut-user:"
EXPENSE_SHORTCUT_AUTH_SCHEME = HTTPBearer(auto_error=False)
BACKUPS_DIR = BASE_DIR / "backups"
SESSION_COOKIE_NAME = "admin_session"
SESSION_DURATION_DAYS = 7
SOFTWARE_TOKEN_DURATION_DAYS = 30
SOFTWARE_AUTH_SCHEME = HTTPBearer(auto_error=False)
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
LOGIN_CAPTCHA_AFTER_FAILURES = 3
FIELD_CONFIG_INITIALIZED_KEY = "field_config_initialized"
SYSTEM_SETTINGS_KEY = "system:settings"
SYSTEM_ALERT_ACK_KEY = "system:alert_acknowledged"
EXPENSE_CATEGORIES_KEY = "expense:categories"
DEFAULT_EXPENSE_CATEGORIES = [
    "办公用品",
    "快递物流",
    "餐饮招待",
    "差旅交通",
    "软件服务",
    "广告推广",
    "采购货款",
    "其他消费",
]
INTERNAL_SYNC_TOKEN_HEADER = "X-Internal-Sync-Token"
INTERNAL_RESERVED_FIELD_NAMES = {"id", "extra_fields", "record_data"}
SAVED_LINK_URL_PATTERN = re.compile(r"https?://[^\s<]+", re.IGNORECASE)
SAVED_LINK_URL_TRAILING_CHARS = ".,!?;:)\"'}]>"
ROLE_LEVELS = {
    "software": 0,
    "viewer": 1,
    "editor": 2,
    "superadmin": 3,
}

PERMISSION_MODULES = {
    "dashboard",
    "links",
    "task_bookkeeping",
    "dingtalk_profits",
    "shop_records",
    "peer_shops",
    "licenses",
    "account_usage",
    "mobile_devices",
    "warehouse",
}
PERMISSION_LEVELS = {"none": 0, "read": 1, "write": 2}
PERMISSION_PATH_PREFIXES = (
    ("/warehouse", "warehouse"),
    ("/account-usage-records", "account_usage"),
    ("/task-bookkeeping", "task_bookkeeping"),
    ("/dingtalk-profits", "dingtalk_profits"),
    ("/license-records", "licenses"),
    ("/mobile-devices", "mobile_devices"),
    ("/peer-shops", "peer_shops"),
    ("/shop-records", "shop_records"),
    ("/custom-fields", "shop_records"),
    ("/saved-links", "links"),
    ("/global-search", "dashboard"),
    ("/dashboard", "dashboard"),
)


class RulePageImportRequest(BaseModel):
    platform: str = Field(default="")
    category_id: str = Field(default="")
    root_json: dict[str, Any]
    source: str = Field(default="software-client")


class ExpenseShortcutRecordRequest(BaseModel):
    book: str = Field(default="personal", max_length=20)
    amount: float = Field(..., gt=0, le=99999999)
    category: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=500)
    date: date_type | None = None
    transaction_type: str = Field(default="expense", max_length=20)
    payment_type: str = Field(default="company", max_length=20)
    payment_account: str = Field(default="", max_length=50)
    expense_scope: str = Field(default="", max_length=100)


class RuleCategoryNameDictionaryItem(BaseModel):
    category_id: str = Field(default="")
    category_name: str = Field(default="")


class RuleCategoryNameDictionaryImportRequest(BaseModel):
    platform: str = Field(default="")
    items: list[RuleCategoryNameDictionaryItem] = Field(default_factory=list)
    source: str = Field(default="software-client")


class RuleCategoryPackagePatchRequest(BaseModel):
    platform: str = Field(default="")
    category_id: str = Field(default="")
    package_patch: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="")
    source: str = Field(default="software-auto-rule-learn")


class RuleCategoryFetchStatusRequest(BaseModel):
    platform: str = Field(default="")
    category_id: str = Field(default="")
    fetch_status: str = Field(default="")
    last_fetch_error: str = Field(default="")
    source: str = Field(default="software-rule-fetch")


class ProductParseCacheUploadRequest(BaseModel):
    platform: str = Field(default="taobao")
    item_id: str = Field(default="")
    source_url: str = Field(default="")
    payload: dict[str, Any]
    source: str = Field(default="software-client")


class PublishFailureReportRequest(BaseModel):
    client_reported_at: str = Field(default="")
    platform: str = Field(default="taobao")
    shop_name: str = Field(default="")
    category_id: str = Field(default="")
    category_name: str = Field(default="")
    item_id: str = Field(default="")
    draft_id: str = Field(default="")
    task_id: int = Field(default=0)
    title: str = Field(default="")
    stage: str = Field(default="")
    error_reason: str = Field(default="")
    source_file: str = Field(default="")
    app_version: str = Field(default="")
    device_id: str = Field(default="")
    device_name: str = Field(default="")
    report_json: dict[str, Any] = Field(default_factory=dict)
    task_json: dict[str, Any] = Field(default_factory=dict)


OPENAPI_ROUTE = "/openapi.json"
DOCS_ROUTE = "/docs"
REDOC_ROUTE = "/redoc"
SYSTEM_FIELD_DEFINITIONS = (
    {
        "field_name": "shop_name",
        "label": "搴楅摵鍚嶇О",
        "field_type": "text",
        "required": True,
        "sort_order": 1,
    },
    {
        "field_name": "platform",
        "label": "骞冲彴",
        "field_type": "text",
        "required": True,
        "sort_order": 2,
    },
    {
        "field_name": "daily_revenue",
        "label": "日营收",
        "field_type": "number",
        "required": True,
        "sort_order": 3,
    },
    {
        "field_name": "date",
        "label": "鏃ユ湡",
        "field_type": "date",
        "required": True,
        "sort_order": 4,
    },
    {
        "field_name": "remark",
        "label": "澶囨敞",
        "field_type": "text",
        "required": False,
        "sort_order": 5,
    },
)
SYSTEM_FIELD_MAP = {item["field_name"]: item for item in SYSTEM_FIELD_DEFINITIONS}
SYSTEM_FIELD_LABEL_MAP = {item["label"]: item for item in SYSTEM_FIELD_DEFINITIONS}
LEGACY_FIELD_NAMES = tuple(SYSTEM_FIELD_MAP)
DEPOSIT_LABEL = "保证金"
DEPOSIT_FIELD_NAMES = {"deposit", "deposit_amount", "security_deposit", "margin"}
LICENSE_SERVER_BASE_URL = os.getenv("LICENSE_SERVER_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
LICENSE_SERVER_TIMEOUT_SECONDS = 15.0
LOGIN_CAPTCHA_TTL_SECONDS = 300
LOGIN_CAPTCHA_LENGTH = 4
LOGIN_CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TUTORIAL_DOC_CATEGORY_PREFIX = "tutorial:"
SAVED_LINK_PUSH_STATUS_IDLE = "idle"
SAVED_LINK_PUSH_STATUS_SCHEDULED = "scheduled"
SAVED_LINK_PUSH_STATUS_SENDING = "sending"
SAVED_LINK_PUSH_STATUS_SENT = "sent"
SAVED_LINK_PUSH_STATUS_FAILED = "failed"
SAVED_LINK_PUSH_POLL_SECONDS = 15
DINGTALK_ROBOT_TIMEOUT_SECONDS = 15.0

logger = logging.getLogger(__name__)
login_captcha_store: dict[str, dict[str, Any]] = {}
TASK_BOOKKEEPING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def parse_json_object(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def parse_json_array(raw_value: str | None) -> list[Any]:
    if not raw_value:
        return []

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []

    return parsed if isinstance(parsed, list) else []


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


def get_task_bookkeeping_local_now() -> datetime:
    return datetime.now(TASK_BOOKKEEPING_TIMEZONE).replace(tzinfo=None)


def normalize_task_bookkeeping_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value

    return value.astimezone(TASK_BOOKKEEPING_TIMEZONE).replace(tzinfo=None)


def _json_default_serializer(value: Any) -> Any:
    if isinstance(value, (datetime, date_type)):
        return value.isoformat()
    return str(value)


def dump_json_object(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=_json_default_serializer)


def build_legacy_record_data(record: ShopRecord) -> dict[str, Any]:
    values = parse_json_object(record.extra_fields)

    if record.shop_name:
        values["shop_name"] = record.shop_name
    if record.platform:
        values["platform"] = record.platform
    if record.daily_revenue is not None:
        values["daily_revenue"] = float(record.daily_revenue)
    if record.date:
        values["date"] = record.date.isoformat()
    if record.remark:
        values["remark"] = record.remark

    return values


def parse_record_values(record: ShopRecord) -> dict[str, Any]:
    record_data = parse_json_object(record.record_data)
    if record_data:
        return record_data
    return build_legacy_record_data(record)


def serialize_record(record: ShopRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "values": parse_record_values(record),
    }


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


def summarize_session_device(user_agent: str | None) -> str:
    normalized = (user_agent or "").strip().lower()
    if not normalized or normalized == "unknown":
        return "Unknown Device"

    if "iphone" in normalized:
        device = "iPhone"
    elif "ipad" in normalized:
        device = "iPad"
    elif "android" in normalized:
        device = "Android"
    elif "windows" in normalized:
        device = "Windows"
    elif "mac os x" in normalized or "macintosh" in normalized:
        device = "Mac"
    elif "linux" in normalized:
        device = "Linux"
    else:
        device = "Other Device"

    if "edg/" in normalized:
        browser = "Edge"
    elif "chrome/" in normalized and "edg/" not in normalized:
        browser = "Chrome"
    elif "firefox/" in normalized:
        browser = "Firefox"
    elif "safari/" in normalized and "chrome/" not in normalized:
        browser = "Safari"
    elif "micromessenger" in normalized:
        browser = "WeChat"
    else:
        browser = "Browser"

    return f"{device} / {browser}"


def serialize_admin_session(record: AdminSession, *, current_session_id: int | None = None) -> dict[str, Any]:
    return {
        "id": record.id,
        "ip_address": (record.ip_address or "unknown").strip() or "unknown",
        "user_agent": (record.user_agent or "unknown").strip() or "unknown",
        "device_name": summarize_session_device(record.user_agent),
        "created_at": record.created_at,
        "expires_at": record.expires_at,
        "is_current": record.id == current_session_id,
    }


def normalize_numeric_value(raw_value: Any) -> float | None:
    if raw_value in (None, ""):
        return None

    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    normalized = (
        str(raw_value)
        .strip()
        .replace(",", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("楼", "")
    )

    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def is_deposit_field(field: CustomField) -> bool:
    normalized_label = (field.label or "").strip()
    normalized_field_name = (field.field_name or "").strip().lower()

    return (
        normalized_label == DEPOSIT_LABEL
        or DEPOSIT_LABEL in normalized_label
        or normalized_field_name in DEPOSIT_FIELD_NAMES
    )


def get_sqlite_database_path() -> Path | None:
    if not settings.is_sqlite:
        return None

    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        return None

    raw_path = settings.database_url[len(prefix) :]
    if not raw_path:
        return None

    return Path(raw_path)


def sanitize_backup_label(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return normalized or "backup"


def create_sqlite_backup(label: str) -> str | None:
    database_path = get_sqlite_database_path()
    if database_path is None or not database_path.exists():
        return None

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{timestamp}-{sanitize_backup_label(label)}.sqlite3"
    backup_path = BACKUPS_DIR / backup_name

    source = sqlite3.connect(str(database_path))
    destination = sqlite3.connect(str(backup_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    try:
        return str(backup_path.relative_to(BASE_DIR))
    except ValueError:
        return str(backup_path)


def write_audit_log(
    db: Session,
    *,
    actor: AdminUser | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=dump_json_object(details or {}),
        ),
    )


def normalize_search_text(parts: list[Any]) -> str:
    return " ".join(str(part or "").strip() for part in parts).lower()


def build_global_search_item(
    *,
    item_id: int,
    category: str,
    title: str,
    route: str,
    subtitle: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "category": category,
        "title": title,
        "subtitle": subtitle,
        "detail": detail,
        "route": route,
    }


def build_admin_user_public_name(user: AdminUser) -> str:
    display_name = (user.display_name or "").strip()
    return display_name or user.username


def build_admin_user_avatar_url(user: AdminUser) -> str | None:
    if not user.avatar_path:
        return None

    return f"/admin-users/{user.id}/avatar-file?v={int(datetime.utcnow().timestamp())}"


def resolve_account_type(role: str) -> str:
    if role == "software":
        return "staff"
    if role == "superadmin":
        return "developer"
    if role == "viewer":
        return "viewer"
    return "admin"


def get_default_permissions(role: str) -> dict[str, str]:
    if role == "superadmin":
        return {module: "write" for module in sorted(PERMISSION_MODULES)}

    default_level = "write" if role == "editor" else "read"
    return {module: default_level for module in sorted(PERMISSION_MODULES)}


def resolve_admin_permissions(user: AdminUser) -> dict[str, str]:
    permissions = get_default_permissions(user.role)
    if user.role == "superadmin" or not user.permissions_json:
        return permissions

    try:
        stored_permissions = json.loads(user.permissions_json)
    except (TypeError, ValueError):
        return permissions

    if not isinstance(stored_permissions, dict):
        return permissions

    for module, level in stored_permissions.items():
        if module in PERMISSION_MODULES and level in PERMISSION_LEVELS:
            permissions[module] = level
    if permissions["dashboard"] == "none":
        permissions["dashboard"] = "read"
    return permissions


def normalize_admin_permissions(role: str, permissions: dict[str, str] | None) -> str | None:
    if role == "superadmin" or permissions is None:
        return None

    normalized = get_default_permissions(role)
    for module, level in permissions.items():
        if module in PERMISSION_MODULES and level in PERMISSION_LEVELS:
            normalized[module] = level
    if normalized["dashboard"] == "none":
        normalized["dashboard"] = "read"
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def serialize_admin_user(user: AdminUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "permissions": resolve_admin_permissions(user),
        "totp_enabled": bool(user.totp_enabled),
        "created_at": user.created_at,
    }


def serialize_current_user(user: AdminUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "account_type": resolve_account_type(user.role),
        "is_active": user.is_active,
        "avatar_url": build_admin_user_avatar_url(user),
        "avatar_name": user.avatar_name,
        "permissions": resolve_admin_permissions(user),
        "totp_enabled": bool(user.totp_enabled),
    }


def parse_software_license_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    text_value = str(value).strip()
    if not text_value:
        return None

    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return parsed


def is_software_user_activated(user: AdminUser) -> bool:
    if not user.is_active:
        return False
    if not user.software_license_key:
        return False
    if (user.software_license_status or "").strip().lower() != "active":
        return False
    if user.software_expire_at is not None and user.software_expire_at <= datetime.utcnow():
        return False
    return True


def serialize_software_user(user: AdminUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "account_type": resolve_account_type(user.role),
        "is_active": user.is_active,
        "is_activated": is_software_user_activated(user),
        "license_key": user.software_license_key,
        "plan_name": user.software_plan_name,
        "license_status": user.software_license_status,
        "activated_at": user.software_activated_at,
        "expire_at": user.software_expire_at,
        "last_validated_at": user.software_last_validated_at,
    }


def serialize_software_admin_user(user: AdminUser) -> dict[str, Any]:
    payload = serialize_software_user(user)
    payload["created_at"] = user.created_at
    return payload


THUMBNAIL_CACHE_DIR = UPLOADS_DIR / ".thumbnails"
THUMBNAIL_MAX_EDGE = 1280
THUMBNAIL_QUALITY = 78
# 只有超过这个大小才值得生成缩略图，小图直接回原文件
THUMBNAIL_MIN_SOURCE_BYTES = 400_000


def resolve_upload_file(relative_path: str) -> Path | None:
    """把数据库里的相对路径解析成 uploads 内的真实文件，越界或缺失返回 None。"""
    if not relative_path:
        return None
    candidate = (UPLOADS_DIR / relative_path).resolve()
    try:
        candidate.relative_to(UPLOADS_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def build_image_thumbnail(source: Path) -> Path | None:
    """生成并缓存 JPEG 缩略图；失败时返回 None 由调用方回退原图。"""
    try:
        stat = source.stat()
    except OSError:
        return None

    if stat.st_size < THUMBNAIL_MIN_SOURCE_BYTES:
        return None

    token = hashlib.sha256(
        f"{source}|{stat.st_mtime_ns}|{stat.st_size}|{THUMBNAIL_MAX_EDGE}|{THUMBNAIL_QUALITY}".encode("utf-8")
    ).hexdigest()[:32]
    cached = THUMBNAIL_CACHE_DIR / f"{token}.jpg"
    if cached.is_file():
        return cached

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    try:
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.LANCZOS)
            temporary = cached.with_suffix(".tmp")
            image.save(temporary, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True, progressive=True)
            temporary.replace(cached)
    except Exception:
        logger.warning("Failed to build thumbnail for %s", source, exc_info=True)
        return None

    return cached if cached.is_file() else None


def image_file_response(source: Path, download_name: str | None, *, thumbnail: bool) -> FileResponse:
    """thumbnail=True 时优先返回压缩图，无法生成则回退原图。"""
    if thumbnail:
        reduced = build_image_thumbnail(source)
        if reduced is not None:
            return FileResponse(
                reduced,
                media_type="image/jpeg",
                content_disposition_type="inline",
                headers={"Cache-Control": "private, max-age=604800"},
            )

    media_type, _ = mimetypes.guess_type(source.name)
    return FileResponse(
        source,
        media_type=media_type or "application/octet-stream",
        filename=download_name or source.name,
        content_disposition_type="inline",
    )


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


def mask_account_name(value: str | None) -> str:
    if not value:
        return "已隐藏"

    if "@" in value:
        local_part, _, domain = value.partition("@")
        if len(local_part) <= 2:
            masked_local = local_part[:1] + "*"
        else:
            masked_local = local_part[:2] + "*" * max(2, len(local_part) - 2)
        return f"{masked_local}@{domain}"

    if len(value) <= 2:
        return value[:1] + "*"

    if len(value) <= 6:
        return value[:2] + "*" * max(1, len(value) - 3) + value[-1:]

    return value[:3] + "*" * max(4, len(value) - 5) + value[-2:]


def serialize_account_usage_record(
    record: AccountUsageRecord,
    *,
    mask_account_name_value: bool = False,
) -> dict[str, Any]:
    account_name = None
    try:
        account_name = decrypt_account_usage_secret(record.account_name)
    except AccountPasswordEncryptionError:
        account_name = None

    return {
        "id": record.id,
        "account_name": mask_account_name(account_name) if mask_account_name_value else (account_name or ""),
        "phone_number": record.phone_number,
        "device_name": record.device_name,
        "usage_notes": record.usage_notes,
        "is_banned": record.is_banned,
        "banned_reason": record.banned_reason,
        "has_password": bool(record.password),
        "created_at": record.created_at,
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


def build_company_expense_no(record: CompanyExpenseRecord) -> str:
    return f"CE-{record.expense_date.strftime('%Y%m%d')}-{record.id:06d}"


def build_company_expense_attachment_url(record: CompanyExpenseRecord) -> str | None:
    if not record.attachment_path:
        return None
    return f"/company-expenses/{record.id}/attachment-file?v={Path(record.attachment_path).name}"


def serialize_company_expense(record: CompanyExpenseRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "expense_no": build_company_expense_no(record),
        "expense_date": record.expense_date,
        "amount": float(record.amount or 0),
        "category": record.category,
        "payment_type": record.payment_type,
        "payment_account": record.payment_account,
        "expense_scope": record.expense_scope,
        "description": record.description,
        "approval_status": record.approval_status,
        "reimbursement_status": record.reimbursement_status,
        "submitter_user_id": record.submitter_user_id,
        "submitter_name": record.submitter_name,
        "reviewer_name": record.reviewer_name,
        "reviewed_at": record.reviewed_at,
        "attachment_url": build_company_expense_attachment_url(record),
        "attachment_name": record.attachment_name,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def build_personal_expense_no(record: PersonalExpenseRecord) -> str:
    return f"PE-{record.record_date.strftime('%Y%m%d')}-{record.id:06d}"


def build_personal_expense_attachment_url(record: PersonalExpenseRecord) -> str | None:
    if not record.attachment_path:
        return None
    return f"/personal-expenses/{record.id}/attachment-file?v={Path(record.attachment_path).name}"


def serialize_personal_expense(record: PersonalExpenseRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "record_no": build_personal_expense_no(record),
        "record_date": record.record_date,
        "amount": float(record.amount or 0),
        "transaction_type": record.transaction_type,
        "category": record.category,
        "payment_account": record.payment_account,
        "description": record.description,
        "owner_user_id": record.owner_user_id,
        "owner_name": record.owner_name,
        "attachment_url": build_personal_expense_attachment_url(record),
        "attachment_name": record.attachment_name,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def build_task_bookkeeping_order_no(record: TaskBookkeepingRecord) -> str:
    anchor_time = (
        normalize_task_bookkeeping_datetime(record.task_time)
        or normalize_task_bookkeeping_datetime(record.created_at)
        or get_task_bookkeeping_local_now()
    )
    return f"TK-{anchor_time.strftime('%Y%m%d')}-{record.id:06d}"


def serialize_task_bookkeeping_record(record: TaskBookkeepingRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "order_no": build_task_bookkeeping_order_no(record),
        "task_time": record.task_time,
        "shop_name": record.shop_name,
        "owner_name": record.owner_name,
        "principal_amount": float(record.principal_amount or 0),
        "order_count": record.order_count,
        "commission_amount": float(record.commission_amount or 0),
        "gift_amount": float(record.gift_amount or 0),
        "signed_status": record.signed_status,
        "settlement_status": record.settlement_status,
        "note": record.note,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def normalize_saved_link_url_candidate(value: str) -> str:
    normalized = value.strip()
    while normalized and normalized[-1] in SAVED_LINK_URL_TRAILING_CHARS:
        normalized = normalized[:-1]
    return normalized


def extract_saved_link_urls(text_value: str | None) -> list[str]:
    if not text_value:
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for match in SAVED_LINK_URL_PATTERN.finditer(text_value):
        candidate = normalize_saved_link_url_candidate(match.group(0))
        if not candidate or candidate in seen:
            continue

        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        seen.add(candidate)
        urls.append(candidate)

    return urls


def resolve_saved_link_primary_url(url_value: str | None, description: str | None) -> str:
    normalized_url = str(url_value or "").strip()
    if normalized_url:
        return normalized_url

    extracted_urls = extract_saved_link_urls(description)
    if extracted_urls:
        return extracted_urls[0]

    return ""


def get_saved_link_local_now() -> datetime:
    return datetime.now(TASK_BOOKKEEPING_TIMEZONE).replace(tzinfo=None, microsecond=0)


def normalize_saved_link_schedule_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None, microsecond=0)
    return value.replace(microsecond=0)


def is_tutorial_doc_category(category: str | None) -> bool:
    normalized = str(category or "").strip().lower()
    return normalized.startswith(TUTORIAL_DOC_CATEGORY_PREFIX)


def strip_tutorial_doc_category(category: str | None) -> str:
    normalized = str(category or "").strip()
    if not is_tutorial_doc_category(normalized):
        return normalized
    return normalized[len(TUTORIAL_DOC_CATEGORY_PREFIX) :].strip() or "教程文档"


def build_saved_link_plain_text(description: str | None) -> str:
    source = str(description or "").strip()
    if not source:
        return ""

    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", source)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(SAVED_LINK_URL_PATTERN, " ", normalized)
    normalized = re.sub(r"[*_#>`~\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def build_saved_link_push_excerpt(record: SavedLink, max_length: int = 220) -> str:
    text = build_saved_link_plain_text(record.description)
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def build_saved_link_detail_url(record: SavedLink) -> str | None:
    base_url = settings.public_app_base_url.strip().rstrip("/")
    if not base_url:
        return None

    route = f"/ui/tutorial-docs/{record.id}" if is_tutorial_doc_category(record.category) else f"/ui/links/{record.id}"
    return f"{base_url}{route}"


def build_saved_link_push_markdown(record: SavedLink) -> tuple[str, str]:
    category_label = strip_tutorial_doc_category(record.category) or "未分类"
    primary_url = resolve_saved_link_primary_url(record.url, record.description) or None
    detail_url = build_saved_link_detail_url(record)
    push_title = f"{'【置顶】' if record.is_pinned else ''}{record.title}"
    excerpt = build_saved_link_push_excerpt(record)

    lines = [f"### {push_title}", ""]
    lines.append(f"> 分类：{category_label}")
    lines.append(f"> 发布人：{record.author_username}")
    lines.append(f"> 帖子编号：#{record.id}")

    if excerpt:
        lines.extend(["", excerpt])

    if primary_url:
        lines.extend(["", f"[原始链接]({primary_url})"])

    if detail_url:
        lines.append(f"[站内查看]({detail_url})")

    return push_title[:80], "\n".join(lines).strip()


def get_dingtalk_robot_request_url() -> str:
    webhook = settings.dingtalk_robot_webhook.strip()
    if not webhook:
        raise HTTPException(status_code=503, detail="未配置 DINGTALK_ROBOT_WEBHOOK，暂时无法推送帖子")

    secret = settings.dingtalk_robot_secret.strip()
    if not secret:
        return webhook

    timestamp = str(int(get_saved_link_local_now().timestamp() * 1000))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    signature = quote(
        base64.b64encode(
            hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest(),
        ).decode("utf-8"),
    )
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={signature}"


def push_saved_link_to_dingtalk(record: SavedLink) -> dict[str, Any]:
    title, text_body = build_saved_link_push_markdown(record)
    try:
        response = httpx.post(
            get_dingtalk_robot_request_url(),
            json={
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": text_body,
                },
            },
            timeout=DINGTALK_ROBOT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"钉钉机器人请求失败：{exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="钉钉机器人返回了无法解析的响应") from exc

    errcode = payload.get("errcode", 0) if isinstance(payload, dict) else 0
    if errcode not in (0, "0"):
        errmsg = str(payload.get("errmsg") or "未知错误").strip() if isinstance(payload, dict) else "未知错误"
        raise HTTPException(status_code=502, detail=f"钉钉机器人推送失败：{errmsg}")

    return payload if isinstance(payload, dict) else {}


def set_saved_link_push_state(
    record: SavedLink,
    *,
    status: str,
    scheduled_at: datetime | None = None,
    sent_at: datetime | None = None,
    error_text: str | None = None,
) -> None:
    record.push_status = status
    record.push_scheduled_at = normalize_saved_link_schedule_datetime(scheduled_at)
    record.push_sent_at = normalize_saved_link_schedule_datetime(sent_at)
    record.push_error = str(error_text or "").strip() or None


def serialize_saved_link(record: SavedLink, db: Session | None = None) -> dict[str, Any]:
    images = get_saved_link_images(record)
    primary_image = images[0] if images else None
    primary_url = resolve_saved_link_primary_url(record.url, record.description) or None
    author_user = db.get(AdminUser, record.author_user_id) if db is not None else None
    return {
        "id": record.id,
        "title": record.title,
        "url": primary_url,
        "category": record.category,
        "description": record.description,
        "sort_order": record.sort_order,
        "is_pinned": bool(record.is_pinned),
        "images": images,
        "image_url": primary_image["url"] if primary_image else None,
        "image_name": primary_image["name"] if primary_image else None,
        "author_user_id": record.author_user_id,
        "author_username": record.author_username,
        "author_avatar_url": build_admin_user_avatar_url(author_user) if author_user is not None else None,
        "push_status": record.push_status or SAVED_LINK_PUSH_STATUS_IDLE,
        "push_scheduled_at": record.push_scheduled_at,
        "push_sent_at": record.push_sent_at,
        "push_error": record.push_error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def build_task_bookkeeping_summary(records: list[TaskBookkeepingRecord]) -> dict[str, Any]:
    principal_total = sum(float(record.principal_amount or 0) for record in records)
    commission_total = sum(float(record.commission_amount or 0) for record in records)
    gift_total = sum(float(record.gift_amount or 0) for record in records)
    unsettled_principal_total = sum(
        float(record.principal_amount or 0)
        for record in records
        if record.settlement_status == "pending"
    )
    pending_signed_count = sum(1 for record in records if record.signed_status == "pending")
    pending_settlement_count = sum(1 for record in records if record.settlement_status == "pending")

    return {
        "total_records": len(records),
        "unsettled_principal_total": unsettled_principal_total,
        "commission_total": commission_total,
        "gift_total": gift_total,
        "principal_total": principal_total,
        "pending_signed_count": pending_signed_count,
        "pending_settlement_count": pending_settlement_count,
        "recent_records": [serialize_task_bookkeeping_record(record) for record in records[:5]],
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


def list_field_definitions(db: Session) -> list[CustomField]:
    stmt = select(CustomField).order_by(CustomField.sort_order.asc(), CustomField.id.asc())
    return db.scalars(stmt).all()


def commit_session(
    db: Session,
    *,
    default_detail: str,
    integrity_detail: str | None = None,
) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=integrity_detail or default_detail,
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=default_detail) from exc


def process_saved_link_push_by_id(link_id: int) -> None:
    db = SessionLocal()
    try:
        db_record = db.get(SavedLink, link_id)
        if db_record is None:
            return

        scheduled_at = normalize_saved_link_schedule_datetime(db_record.push_scheduled_at)
        now = get_saved_link_local_now()
        if db_record.push_status != SAVED_LINK_PUSH_STATUS_SCHEDULED:
            return
        if scheduled_at is None or scheduled_at > now:
            return

        set_saved_link_push_state(
            db_record,
            status=SAVED_LINK_PUSH_STATUS_SENDING,
            scheduled_at=scheduled_at,
            sent_at=None,
            error_text=None,
        )
        commit_session(db, default_detail="Failed to mark saved-link push as sending")

        try:
            push_saved_link_to_dingtalk(db_record)
        except HTTPException as exc:
            set_saved_link_push_state(
                db_record,
                status=SAVED_LINK_PUSH_STATUS_FAILED,
                scheduled_at=scheduled_at,
                sent_at=None,
                error_text=str(exc.detail),
            )
            commit_session(db, default_detail="Failed to persist saved-link push error state")
            write_audit_log(
                db,
                actor=None,
                action="saved_link_push_failed",
                resource_type="saved_link",
                resource_id=db_record.id,
                details=serialize_saved_link(db_record, db),
            )
            commit_session(db, default_detail="Failed to record saved-link push failure audit log")
            logger.warning("Saved-link push failed for #%s: %s", db_record.id, exc.detail)
            return

        set_saved_link_push_state(
            db_record,
            status=SAVED_LINK_PUSH_STATUS_SENT,
            scheduled_at=scheduled_at,
            sent_at=get_saved_link_local_now(),
            error_text=None,
        )
        commit_session(db, default_detail="Failed to persist saved-link push success state")
        write_audit_log(
            db,
            actor=None,
            action="saved_link_pushed",
            resource_type="saved_link",
            resource_id=db_record.id,
            details=serialize_saved_link(db_record, db),
        )
        commit_session(db, default_detail="Failed to record saved-link push audit log")
    except HTTPException as exc:
        logger.warning("Saved-link push worker HTTP error for #%s: %s", link_id, exc.detail)
    except Exception:
        logger.exception("Unexpected saved-link push worker error for #%s", link_id)
    finally:
        db.close()


async def saved_link_push_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                now = get_saved_link_local_now()
                stmt = (
                    select(SavedLink.id)
                    .where(
                        SavedLink.push_status == SAVED_LINK_PUSH_STATUS_SCHEDULED,
                        SavedLink.push_scheduled_at.is_not(None),
                        SavedLink.push_scheduled_at <= now,
                    )
                    .order_by(SavedLink.push_scheduled_at.asc(), SavedLink.id.asc())
                )
                due_ids = list(db.scalars(stmt).all())
            finally:
                db.close()

            for link_id in due_ids:
                await asyncio.to_thread(process_saved_link_push_by_id, link_id)
        except Exception:
            logger.exception("Saved-link push scheduler loop failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SAVED_LINK_PUSH_POLL_SECONDS)
        except asyncio.TimeoutError:
            continue


def rebuild_shop_record_table(inspector) -> None:
    columns = {column["name"]: column for column in inspector.get_columns("ShopRecord")}
    legacy_not_nullable = any(
        name in columns and not columns[name]["nullable"]
        for name in ("shop_name", "platform", "daily_revenue", "date")
    )
    if "record_data" in columns and not legacy_not_nullable:
        return

    column_selects = {
        "id": "id" if "id" in columns else "NULL",
        "shop_name": "shop_name" if "shop_name" in columns else "NULL",
        "platform": "platform" if "platform" in columns else "NULL",
        "daily_revenue": "daily_revenue" if "daily_revenue" in columns else "NULL",
        "remark": "remark" if "remark" in columns else "NULL",
        "date": "date" if "date" in columns else "NULL",
        "extra_fields": "COALESCE(extra_fields, '{}')" if "extra_fields" in columns else "'{}'",
        "record_data": "COALESCE(record_data, '{}')" if "record_data" in columns else "'{}'",
    }

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE ShopRecord RENAME TO ShopRecord_legacy"))
        connection.execute(
            text(
                """
                CREATE TABLE ShopRecord (
                    id INTEGER NOT NULL PRIMARY KEY,
                    shop_name VARCHAR(100),
                    platform VARCHAR(50),
                    daily_revenue FLOAT,
                    remark TEXT,
                    date DATE,
                    extra_fields TEXT NOT NULL DEFAULT '{}',
                    record_data TEXT NOT NULL DEFAULT '{}'
                )
                """,
            ),
        )
        connection.execute(
            text(
                f"""
                INSERT INTO ShopRecord (
                    id,
                    shop_name,
                    platform,
                    daily_revenue,
                    remark,
                    date,
                    extra_fields,
                    record_data
                )
                SELECT
                    {column_selects["id"]},
                    {column_selects["shop_name"]},
                    {column_selects["platform"]},
                    {column_selects["daily_revenue"]},
                    {column_selects["remark"]},
                    {column_selects["date"]},
                    {column_selects["extra_fields"]},
                    {column_selects["record_data"]}
                FROM ShopRecord_legacy
                """,
            ),
        )
        connection.execute(text("DROP TABLE ShopRecord_legacy"))


def rebuild_account_usage_record_table(inspector) -> None:
    table_names = set(inspector.get_table_names())
    if "AccountUsageRecord_legacy" in table_names:
        with engine.begin() as connection:
            connection.execute(text("DROP INDEX IF EXISTS ix_AccountUsageRecord_account_name"))
            connection.execute(text("DROP INDEX IF EXISTS ix_AccountUsageRecord_id"))
            connection.execute(text("DROP INDEX IF EXISTS ix_AccountUsageRecord_phone_number"))

            current_count = connection.execute(
                text("SELECT COUNT(*) FROM AccountUsageRecord"),
            ).scalar_one()
            if current_count == 0:
                connection.execute(
                    text(
                        """
                        INSERT INTO AccountUsageRecord (
                            id,
                            account_name,
                            password,
                            phone_number,
                            device_name,
                            usage_notes,
                            is_banned,
                            banned_reason,
                            created_at
                        )
                        SELECT
                            id,
                            account_name,
                            password,
                            phone_number,
                            device_name,
                            usage_notes,
                            is_banned,
                            banned_reason,
                            created_at
                        FROM AccountUsageRecord_legacy
                        """,
                    ),
                )

            connection.execute(
                text(
                    "CREATE INDEX ix_AccountUsageRecord_account_name ON AccountUsageRecord (account_name)",
                ),
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_AccountUsageRecord_id ON AccountUsageRecord (id)",
                ),
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_AccountUsageRecord_phone_number ON AccountUsageRecord (phone_number)",
                ),
            )
            connection.execute(text("DROP TABLE AccountUsageRecord_legacy"))
        return

    columns = {column["name"]: column for column in inspector.get_columns("AccountUsageRecord")}
    password_column = columns.get("password")
    account_name_column = columns.get("account_name")
    if password_column is None:
        return

    password_type = str(password_column["type"]).lower()
    account_name_type = str(account_name_column["type"]).lower() if account_name_column else ""
    account_name_ready = "varchar(512)" in account_name_type or "text" in account_name_type
    if "text" in password_type and account_name_ready:
        return

    with engine.begin() as connection:
        connection.execute(text("DROP INDEX IF EXISTS ix_AccountUsageRecord_account_name"))
        connection.execute(text("DROP INDEX IF EXISTS ix_AccountUsageRecord_id"))
        connection.execute(text("DROP INDEX IF EXISTS ix_AccountUsageRecord_phone_number"))
        connection.execute(text("ALTER TABLE AccountUsageRecord RENAME TO AccountUsageRecord_legacy"))
        connection.execute(
            text(
                """
                CREATE TABLE AccountUsageRecord (
                    id INTEGER NOT NULL PRIMARY KEY,
                    account_name VARCHAR(512) NOT NULL,
                    password TEXT,
                    phone_number VARCHAR(30),
                    device_name VARCHAR(50),
                    usage_notes TEXT,
                    is_banned BOOLEAN NOT NULL DEFAULT 0,
                    banned_reason VARCHAR(255),
                    created_at DATETIME NOT NULL
                )
                """,
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO AccountUsageRecord (
                    id,
                    account_name,
                    password,
                    phone_number,
                    device_name,
                    usage_notes,
                    is_banned,
                    banned_reason,
                    created_at
                )
                SELECT
                    id,
                    account_name,
                    password,
                    phone_number,
                    device_name,
                    usage_notes,
                    is_banned,
                    banned_reason,
                    created_at
                FROM AccountUsageRecord_legacy
                """,
            ),
        )
        connection.execute(
            text(
                "CREATE INDEX ix_AccountUsageRecord_account_name ON AccountUsageRecord (account_name)",
            ),
        )
        connection.execute(
            text(
                "CREATE INDEX ix_AccountUsageRecord_id ON AccountUsageRecord (id)",
            ),
        )
        connection.execute(
            text(
                "CREATE INDEX ix_AccountUsageRecord_phone_number ON AccountUsageRecord (phone_number)",
            ),
        )
        connection.execute(text("DROP TABLE AccountUsageRecord_legacy"))


def migrate_database() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "ShopRecord" in table_names:
        rebuild_shop_record_table(inspector)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "AccountUsageRecord" in table_names:
        if settings.is_sqlite:
            rebuild_account_usage_record_table(inspector)
        else:
            account_usage_columns = {
                column["name"]: column for column in inspector.get_columns("AccountUsageRecord")
            }
            password_column = account_usage_columns.get("password")
            password_type = str(password_column["type"]).lower() if password_column else ""
            with engine.begin() as connection:
                if password_column is not None and "text" not in password_type:
                    connection.execute(
                        text("ALTER TABLE AccountUsageRecord MODIFY COLUMN password TEXT NULL"),
                    )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "CustomField" in table_names:
        custom_columns = {column["name"] for column in inspector.get_columns("CustomField")}
        if "is_builtin" not in custom_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE CustomField ADD COLUMN is_builtin BOOLEAN NOT NULL DEFAULT 0"),
                )
        if "is_visible" not in custom_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE CustomField ADD COLUMN is_visible BOOLEAN NOT NULL DEFAULT 1"),
                )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "LicenseRecord" in table_names:
        license_columns = {column["name"] for column in inspector.get_columns("LicenseRecord")}
        with engine.begin() as connection:
            if "image_path" not in license_columns:
                connection.execute(
                    text("ALTER TABLE LicenseRecord ADD COLUMN image_path VARCHAR(255)"),
                )
            if "image_name" not in license_columns:
                connection.execute(
                    text("ALTER TABLE LicenseRecord ADD COLUMN image_name VARCHAR(255)"),
                )
            if "extra_fields" not in license_columns:
                connection.execute(
                    text("ALTER TABLE LicenseRecord ADD COLUMN extra_fields TEXT NOT NULL DEFAULT '{}'")
                )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "WarehouseProduct" in table_names:
        product_columns = {column["name"] for column in inspector.get_columns("WarehouseProduct")}
        with engine.begin() as connection:
            if "cost_price" not in product_columns:
                connection.execute(
                    text("ALTER TABLE WarehouseProduct ADD COLUMN cost_price REAL NOT NULL DEFAULT 0"),
                )
            if "image_path" not in product_columns:
                connection.execute(
                    text("ALTER TABLE WarehouseProduct ADD COLUMN image_path VARCHAR(255)"),
                )
            if "image_name" not in product_columns:
                connection.execute(
                    text("ALTER TABLE WarehouseProduct ADD COLUMN image_name VARCHAR(255)"),
                )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "WarehouseOutboundOrder" in table_names:
        outbound_columns = {column["name"] for column in inspector.get_columns("WarehouseOutboundOrder")}
        if "delivery_method" not in outbound_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE WarehouseOutboundOrder ADD COLUMN delivery_method VARCHAR(20) NOT NULL DEFAULT 'shipping'"),
                )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    for table_name in ("PeerShop", "AccountUsageRecord", "MobileDeviceRecord"):
        if table_name not in table_names:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "extra_fields" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN extra_fields TEXT NOT NULL DEFAULT '{{}}'")
                )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "SavedLink" in table_names:
        saved_link_columns = {column["name"] for column in inspector.get_columns("SavedLink")}
        with engine.begin() as connection:
            if "is_pinned" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0"),
                )
            if "images_json" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN images_json TEXT NOT NULL DEFAULT '[]'"),
                )
            if "image_path" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN image_path VARCHAR(255)"),
                )
            if "image_name" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN image_name VARCHAR(255)"),
                )
            if "author_user_id" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN author_user_id INTEGER NOT NULL DEFAULT 0"),
                )
            if "author_username" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN author_username VARCHAR(50) NOT NULL DEFAULT 'unknown'"),
                )
            if "push_status" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN push_status VARCHAR(20) NOT NULL DEFAULT 'idle'"),
                )
            if "push_scheduled_at" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN push_scheduled_at DATETIME"),
                )
            if "push_sent_at" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN push_sent_at DATETIME"),
                )
            if "push_error" not in saved_link_columns:
                connection.execute(
                    text("ALTER TABLE SavedLink ADD COLUMN push_error TEXT"),
                )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_SavedLink_is_pinned ON SavedLink (is_pinned)"),
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_SavedLink_push_status ON SavedLink (push_status)"),
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_SavedLink_push_scheduled_at ON SavedLink (push_scheduled_at)",
                ),
            )

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "AdminSession" in table_names:
        session_columns = {column["name"] for column in inspector.get_columns("AdminSession")}
        with engine.begin() as connection:
            if "ip_address" not in session_columns:
                connection.execute(
                    text("ALTER TABLE AdminSession ADD COLUMN ip_address VARCHAR(64) NOT NULL DEFAULT 'unknown'"),
                )
            if "user_agent" not in session_columns:
                connection.execute(
                    text("ALTER TABLE AdminSession ADD COLUMN user_agent VARCHAR(255) NOT NULL DEFAULT 'unknown'"),
                )
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "AdminUser" in table_names:
        admin_user_columns = {column["name"] for column in inspector.get_columns("AdminUser")}
        with engine.begin() as connection:
            if "display_name" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN display_name VARCHAR(50)"),
                )
            if "permissions_json" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN permissions_json TEXT"),
                )
            if "avatar_path" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN avatar_path VARCHAR(255)"),
                )
            if "avatar_name" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN avatar_name VARCHAR(255)"),
                )
            if "software_license_key" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN software_license_key VARCHAR(80)"),
                )
            if "software_plan_name" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN software_plan_name VARCHAR(100)"),
                )
            if "software_license_status" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN software_license_status VARCHAR(20)"),
                )
            if "software_activated_at" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN software_activated_at DATETIME"),
                )
            if "software_expire_at" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN software_expire_at DATETIME"),
                )
            if "software_last_validated_at" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN software_last_validated_at DATETIME"),
                )
            if "totp_enabled" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN totp_enabled BOOLEAN NOT NULL DEFAULT 0"),
                )
            if "totp_secret_encrypted" not in admin_user_columns:
                connection.execute(
                    text("ALTER TABLE AdminUser ADD COLUMN totp_secret_encrypted TEXT"),
                )


def migrate_account_usage_password_storage() -> None:
    db = SessionLocal()
    try:
        records = db.scalars(
            select(AccountUsageRecord).where(AccountUsageRecord.password.is_not(None)),
        ).all()

        needs_commit = False
        for record in records:
            if not record.password or is_account_password_encrypted(record.password):
                continue

            record.password = encrypt_account_password(record.password)
            needs_commit = True

        if needs_commit:
            commit_session(db, default_detail="Failed to migrate account password storage")
    finally:
        db.close()


def migrate_account_usage_account_name_storage() -> None:
    db = SessionLocal()
    try:
        records = db.scalars(select(AccountUsageRecord)).all()

        needs_commit = False
        for record in records:
            if is_account_usage_secret_encrypted(record.account_name):
                continue

            record.account_name = encrypt_account_usage_secret(record.account_name) or ""
            needs_commit = True

        if needs_commit:
            commit_session(db, default_detail="Failed to migrate account name storage")
    finally:
        db.close()


def has_admin_users(db: Session) -> bool:
    return db.scalar(select(AdminUser.id).limit(1)) is not None


def get_setting(db: Session, key: str) -> AppSetting | None:
    return db.get(AppSetting, key)


def get_expense_shortcut_setting(db: Session, user_id: int) -> AppSetting | None:
    return get_setting(db, f"{EXPENSE_SHORTCUT_SETTING_PREFIX}{user_id}")


def hash_expense_shortcut_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def read_expense_shortcut_setting(db: Session, user_id: int) -> dict[str, Any]:
    setting = get_expense_shortcut_setting(db, user_id)
    if setting is None:
        return {}
    try:
        value = json.loads(setting.value)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def write_expense_shortcut_setting(db: Session, user_id: int, value: dict[str, Any]) -> None:
    storage_key = f"{EXPENSE_SHORTCUT_SETTING_PREFIX}{user_id}"
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    setting = get_setting(db, storage_key)
    if setting is None:
        db.add(AppSetting(key=storage_key, value=serialized))
    else:
        setting.value = serialized


DEFAULT_SYSTEM_SETTINGS: dict[str, Any] = {
    "license_expiry_days": 30,
    "stale_task_days": 3,
    "login_failure_threshold": 3,
    "session_duration_hours": 168,
    "low_stock_alert_enabled": True,
    "pending_outbound_alert_enabled": True,
    "task_alert_enabled": True,
    "security_alert_enabled": True,
    "data_alert_enabled": True,
    "profit_stale_days": 3,
}


def read_json_setting(db: Session, key: str, default: Any) -> Any:
    setting = get_setting(db, key)
    if setting is None:
        return default
    try:
        value = json.loads(setting.value)
    except (TypeError, ValueError):
        return default
    return value


def write_json_setting(db: Session, key: str, value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    setting = get_setting(db, key)
    if setting is None:
        db.add(AppSetting(key=key, value=serialized))
    else:
        setting.value = serialized


def get_system_settings(db: Session) -> dict[str, Any]:
    stored = read_json_setting(db, SYSTEM_SETTINGS_KEY, {})
    merged = dict(DEFAULT_SYSTEM_SETTINGS)
    if isinstance(stored, dict):
        merged.update({key: stored[key] for key in DEFAULT_SYSTEM_SETTINGS if key in stored})
    return SystemSettingsResponse.model_validate(merged).model_dump()


def initialize_field_configuration() -> None:
    db = SessionLocal()
    try:
        initialized = get_setting(db, FIELD_CONFIG_INITIALIZED_KEY)
        existing_fields = db.scalars(
            select(CustomField).order_by(CustomField.sort_order.asc(), CustomField.id.asc()),
        ).all()
        existing_names = {field.field_name for field in existing_fields}
        existing_fields_by_name = {field.field_name: field for field in existing_fields}
        used_sort_orders = {field.sort_order for field in existing_fields}

        needs_commit = False
        if initialized is None:
            sort_order_offset = len(SYSTEM_FIELD_DEFINITIONS)
            for field in existing_fields:
                field.sort_order += sort_order_offset
            needs_commit = bool(existing_fields)
            used_sort_orders = {field.sort_order for field in existing_fields}

        max_sort_order = max((field.sort_order for field in existing_fields), default=0)
        for definition in SYSTEM_FIELD_DEFINITIONS:
            existing_field = existing_fields_by_name.get(definition["field_name"])
            desired_sort_order = definition["sort_order"]
            if existing_field is not None:
                if (
                    existing_field.is_builtin
                    and existing_field.sort_order != desired_sort_order
                    and desired_sort_order not in used_sort_orders
                ):
                    used_sort_orders.discard(existing_field.sort_order)
                    existing_field.sort_order = desired_sort_order
                    used_sort_orders.add(desired_sort_order)
                    needs_commit = True
                continue

            if definition["field_name"] in existing_names:
                continue

            assigned_sort_order = desired_sort_order if desired_sort_order not in used_sort_orders else max_sort_order + 1
            db.add(
                CustomField(
                    field_name=definition["field_name"],
                    label=definition["label"],
                    field_type=definition["field_type"],
                    required=definition["required"],
                    sort_order=assigned_sort_order,
                    is_visible=True,
                    is_builtin=True,
                ),
            )
            used_sort_orders.add(assigned_sort_order)
            max_sort_order = assigned_sort_order
            needs_commit = True

        if initialized is None:
            for record in db.scalars(select(ShopRecord)).all():
                record.record_data = dump_json_object(build_legacy_record_data(record))

            db.add(AppSetting(key=FIELD_CONFIG_INITIALIZED_KEY, value="1"))
            needs_commit = True

        if needs_commit:
            commit_session(db, default_detail="Failed to initialize field configuration")
    finally:
        db.close()


def hash_password(password: str) -> str:
    iterations = 300_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_hex, digest_hex = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except ValueError:
        return False

    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


def get_auth_fernet() -> Fernet:
    key_material = hashlib.sha256(settings.auth_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_totp_secret(secret: str) -> str:
    return get_auth_fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(encrypted_secret: str | None) -> str:
    if not encrypted_secret:
        raise HTTPException(status_code=409, detail="二次验证配置无效，请重新设置")
    try:
        return get_auth_fernet().decrypt(encrypted_secret.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError):
        raise HTTPException(status_code=409, detail="二次验证配置无法解密，请联系管理员") from None


def normalize_totp_code(code: str | None) -> str:
    return re.sub(r"\D", "", str(code or ""))


def verify_totp_code(secret: str, code: str | None) -> bool:
    normalized = normalize_totp_code(code)
    return len(normalized) == 6 and pyotp.TOTP(secret).verify(normalized, valid_window=1)


def build_totp_qr_data(provisioning_uri: str) -> str:
    image = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if settings.trust_proxy_headers and forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def get_client_user_agent(request: Request) -> str:
    user_agent = (request.headers.get("user-agent") or "").strip()
    return user_agent[:255] if user_agent else "unknown"


def build_auth_audit_details(request: Request, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ip_address": get_client_ip(request),
        "user_agent": get_client_user_agent(request),
    }
    for key, value in details.items():
        if value is not None:
            payload[key] = value
    return payload


def cleanup_expired_login_captchas() -> None:
    now = datetime.utcnow()
    expired_ids = [
        captcha_id
        for captcha_id, item in login_captcha_store.items()
        if item.get("expires_at") is None or item["expires_at"] <= now
    ]
    for captcha_id in expired_ids:
        login_captcha_store.pop(captcha_id, None)


def generate_login_captcha_code() -> str:
    return "".join(secrets.choice(LOGIN_CAPTCHA_ALPHABET) for _ in range(LOGIN_CAPTCHA_LENGTH))


def build_login_captcha_image_data(code: str) -> str:
    width = 132
    height = 44
    text_elements: list[str] = []
    line_elements: list[str] = []
    dot_elements: list[str] = []
    palette = ["#1d4ed8", "#0f766e", "#9333ea", "#c2410c"]

    for index, char in enumerate(code):
        x = 18 + index * 26 + secrets.randbelow(5)
        y = 28 + secrets.randbelow(8)
        rotation = secrets.randbelow(31) - 15
        color = palette[index % len(palette)]
        text_elements.append(
            (
                f'<text x="{x}" y="{y}" '
                f'transform="rotate({rotation} {x} {y})" '
                'font-family="Arial, sans-serif" font-size="24" font-weight="700" '
                f'fill="{color}">{char}</text>'
            ),
        )

    for _ in range(6):
        x1 = secrets.randbelow(width)
        y1 = secrets.randbelow(height)
        x2 = secrets.randbelow(width)
        y2 = secrets.randbelow(height)
        stroke = palette[secrets.randbelow(len(palette))]
        line_elements.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-opacity="0.22" stroke-width="1.2" />',
        )

    for _ in range(18):
        cx = secrets.randbelow(width)
        cy = secrets.randbelow(height)
        radius = 1 + secrets.randbelow(2)
        fill = palette[secrets.randbelow(len(palette))]
        dot_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" fill-opacity="0.18" />')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" rx="10" fill="#f8fafc" />'
        f'{"".join(dot_elements)}'
        f'{"".join(line_elements)}'
        f'{"".join(text_elements)}'
        "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def create_login_captcha() -> dict[str, Any]:
    cleanup_expired_login_captchas()
    captcha_id = secrets.token_urlsafe(24)
    captcha_code = generate_login_captcha_code()
    expires_at = datetime.utcnow() + timedelta(seconds=LOGIN_CAPTCHA_TTL_SECONDS)
    login_captcha_store[captcha_id] = {
        "code": captcha_code,
        "expires_at": expires_at,
    }
    return {
        "captcha_id": captcha_id,
        "image_data": build_login_captcha_image_data(captcha_code),
        "expires_in_seconds": LOGIN_CAPTCHA_TTL_SECONDS,
    }


def consume_login_captcha(captcha_id: str, captcha_code: str) -> None:
    cleanup_expired_login_captchas()
    normalized_id = str(captcha_id or "").strip()
    normalized_code = re.sub(r"\s+", "", str(captcha_code or "")).strip().upper()
    if not normalized_id or not normalized_code:
        raise HTTPException(status_code=400, detail="请输入验证码")

    captcha_entry = login_captcha_store.pop(normalized_id, None)
    if captcha_entry is None:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    expected_code = str(captcha_entry.get("code") or "").strip().upper()
    expires_at = captcha_entry.get("expires_at")
    if not expected_code or not isinstance(expires_at, datetime) or expires_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    if not hmac.compare_digest(expected_code, normalized_code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")


def count_active_sessions(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AdminSession)
            .where(
                AdminSession.user_id == user_id,
                AdminSession.expires_at > datetime.utcnow(),
            ),
        )
        or 0,
    )


def get_admin_session_by_token(db: Session, session_token: str | None) -> AdminSession | None:
    if not session_token:
        return None

    return db.scalar(
        select(AdminSession).where(AdminSession.token_hash == hash_session_token(session_token)),
    )


def get_login_attempt(db: Session, username: str, ip_address: str) -> LoginAttempt | None:
    return db.scalar(
        select(LoginAttempt).where(
            LoginAttempt.username == username,
            LoginAttempt.ip_address == ip_address,
        ),
    )


def is_login_captcha_required(db: Session, username: str, ip_address: str) -> bool:
    attempt = get_login_attempt(db, username, ip_address)
    if attempt is None:
        return False
    if attempt.locked_until is not None and attempt.locked_until <= datetime.utcnow():
        return False
    return attempt.failed_count >= LOGIN_CAPTCHA_AFTER_FAILURES


def ensure_login_not_locked(db: Session, username: str, ip_address: str) -> None:
    attempt = get_login_attempt(db, username, ip_address)
    if attempt is None:
        return

    now = datetime.utcnow()
    if attempt.locked_until is None or attempt.locked_until <= now:
        if attempt.failed_count and attempt.locked_until is not None:
            attempt.failed_count = 0
            attempt.locked_until = None
            commit_session(db, default_detail="Failed to refresh login lock state")
        return

    raise HTTPException(
        status_code=429,
        detail=f"登录失败次数过多，请 {LOGIN_LOCK_MINUTES} 分钟后再试",
    )


def record_login_failure(db: Session, username: str, ip_address: str) -> None:
    attempt = get_login_attempt(db, username, ip_address)
    now = datetime.utcnow()

    if attempt is None:
        attempt = LoginAttempt(
            username=username,
            ip_address=ip_address,
            failed_count=1,
            last_attempt_at=now,
        )
        db.add(attempt)
    else:
        if attempt.locked_until is not None and attempt.locked_until <= now:
            attempt.failed_count = 0
            attempt.locked_until = None

        attempt.failed_count += 1
        attempt.last_attempt_at = now

    if attempt.failed_count >= MAX_FAILED_LOGIN_ATTEMPTS:
        attempt.locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)

    commit_session(db, default_detail="Failed to record login failure")


def clear_login_failures(db: Session, username: str, ip_address: str) -> None:
    attempt = get_login_attempt(db, username, ip_address)
    if attempt is None:
        return

    db.delete(attempt)
    commit_session(db, default_detail="Failed to clear login failure history")


def clear_user_sessions(db: Session, user_id: int, *, exclude_session_id: int | None = None) -> int:
    stmt = select(AdminSession).where(AdminSession.user_id == user_id)
    if exclude_session_id is not None:
        stmt = stmt.where(AdminSession.id != exclude_session_id)

    sessions = db.scalars(stmt).all()
    for session in sessions:
        db.delete(session)
    commit_session(db, default_detail="Failed to clear user sessions")
    return len(sessions)


def create_software_session(
    user: AdminUser,
    db: Session,
    *,
    request: Request | None = None,
    device_id: str = "",
    device_name: str | None = None,
    platform: str | None = None,
    app_version: str | None = None,
) -> tuple[str, AdminSession]:
    expires_at = datetime.utcnow() + timedelta(days=SOFTWARE_TOKEN_DURATION_DAYS)
    raw_token = secrets.token_urlsafe(32)
    user_agent = "software-client"
    if platform or app_version or device_name:
        user_agent = " | ".join(
            part
            for part in [
                f"software:{platform or 'unknown'}",
                f"app:{app_version or 'unknown'}",
                f"device:{device_name or device_id or 'unknown'}",
            ]
            if part
        )[:255]

    admin_session = AdminSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        ip_address=get_client_ip(request) if request is not None else "unknown",
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(admin_session)
    commit_session(db, default_detail="Failed to create software session")
    db.refresh(admin_session)
    return raw_token, admin_session


def build_software_auth_response(
    user: AdminUser,
    token: str,
    session: AdminSession,
    *,
    message: str = "",
) -> dict[str, Any]:
    return {
        "token": token,
        "token_expires_at": session.expires_at,
        "user": serialize_software_user(user),
        "message": message,
    }


def can_use_software_client_api(user: AdminUser) -> bool:
    return user.role in {"software", "superadmin"}


def resolve_current_software_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
    *,
    require_activated: bool,
) -> AdminUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not hmac.compare_digest(credentials.scheme.lower(), "bearer"):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")

    user = resolve_current_user(credentials.credentials, db, required=True)
    if not can_use_software_client_api(user):
        raise HTTPException(status_code=403, detail="Only software client or superadmin accounts can use this API")
    if require_activated and not is_software_user_activated(user):
        raise HTTPException(status_code=403, detail="账号未激活或授权已过期")
    return user


def resolve_current_rule_api_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
    *,
    require_maintainer: bool,
) -> AdminUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not hmac.compare_digest(credentials.scheme.lower(), "bearer"):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")

    user = resolve_current_user(credentials.credentials, db, required=True)
    if require_maintainer:
        if user.role != "superadmin":
            raise HTTPException(status_code=403, detail="Only superadmin can maintain rule catalog")
        return user

    if user.role == "software":
        if not is_software_user_activated(user):
            raise HTTPException(status_code=403, detail="账号未激活或授权已过期")
        return user

    if ROLE_LEVELS.get(user.role, 0) >= ROLE_LEVELS["viewer"]:
        return user

    raise HTTPException(status_code=403, detail="Permission denied")


def resolve_current_product_cache_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> AdminUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not hmac.compare_digest(credentials.scheme.lower(), "bearer"):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")

    user = resolve_current_user(credentials.credentials, db, required=True)
    if user.role == "software":
        if not is_software_user_activated(user):
            raise HTTPException(status_code=403, detail="账号未激活或授权已过期")
        return user

    if ROLE_LEVELS.get(user.role, 0) >= ROLE_LEVELS["viewer"]:
        return user

    raise HTTPException(status_code=403, detail="Permission denied")


def normalize_rule_platform(platform: str) -> str:
    value = str(platform or "").strip().lower()
    if value in {"taobao", "tmall"}:
        return value
    raise HTTPException(status_code=400, detail="Unsupported rule platform")


def normalize_product_cache_platform(platform: str) -> str:
    value = str(platform or "").strip().lower()
    if value in {"taobao", "tmall", "pinduoduo", "pdd"}:
        return "pinduoduo" if value == "pdd" else value
    return "taobao"


def normalize_product_cache_item_id(item_id: Any) -> str:
    match = re.search(r"\d{8,}", str(item_id or "").strip())
    if not match:
        raise HTTPException(status_code=400, detail="Item ID is required")
    return match.group(0)


def extract_product_cache_text(payload: dict[str, Any], *path: str) -> str:
    node: Any = payload
    for key in path:
        if not isinstance(node, dict):
            return ""
        node = node.get(key)
    if node is None:
        return ""
    if isinstance(node, (dict, list)):
        return get_rule_json_text(node).strip()
    return str(node or "").strip()


def extract_product_cache_first_image(payload: dict[str, Any]) -> str:
    item_info = payload.get("item_info") if isinstance(payload.get("item_info"), dict) else {}
    images = item_info.get("main_images") if isinstance(item_info, dict) else None
    if isinstance(images, list):
        for value in images:
            text = str(value or "").strip()
            if text.startswith("http://") or text.startswith("https://"):
                return text
    return ""


def extract_product_cache_base_price(payload: dict[str, Any]) -> float | None:
    raw_price = payload.get("price")
    try:
        if raw_price is not None and str(raw_price).strip():
            value = float(str(raw_price).strip())
            if value >= 0:
                return value
    except (TypeError, ValueError):
        pass

    sku_list = payload.get("sku_list")
    prices: list[float] = []
    if isinstance(sku_list, list):
        for sku in sku_list:
            if not isinstance(sku, dict):
                continue
            try:
                value = float(str(sku.get("price") or "").strip())
            except (TypeError, ValueError):
                continue
            if value >= 0:
                prices.append(value)
    return min(prices) if prices else None


def get_product_parse_cache_db_path() -> Path:
    return PRODUCT_PARSE_CACHE_DB_PATH


def ensure_product_parse_cache_db() -> Path:
    db_path = get_product_parse_cache_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_parse_cache (
                platform TEXT NOT NULL,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                shop_name TEXT NOT NULL DEFAULT '',
                base_price REAL,
                first_main_image TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL DEFAULT '',
                uploader_user_id INTEGER,
                uploader_username TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                is_admin_locked INTEGER NOT NULL DEFAULT 0,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_hit_at TEXT,
                PRIMARY KEY (platform, item_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_product_parse_cache_updated_at ON product_parse_cache(updated_at)"
        )
        connection.commit()
    return db_path


def load_product_parse_cache(platform: str, item_id: str, user: AdminUser) -> dict[str, Any]:
    safe_platform = normalize_product_cache_platform(platform)
    safe_item_id = normalize_product_cache_item_id(item_id)
    db_path = ensure_product_parse_cache_db()
    now_text = datetime.utcnow().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT platform, item_id, title, shop_name, base_price, first_main_image,
                       source_url, payload_json, updated_at, hit_count
                FROM product_parse_cache
                WHERE platform = ? AND item_id = ?
                LIMIT 1
                """,
                (safe_platform, safe_item_id),
            ).fetchone()
            if row is None and safe_platform in {"taobao", "tmall"}:
                fallback_platform = "tmall" if safe_platform == "taobao" else "taobao"
                row = connection.execute(
                    """
                    SELECT platform, item_id, title, shop_name, base_price, first_main_image,
                           source_url, payload_json, updated_at, hit_count
                    FROM product_parse_cache
                    WHERE platform = ? AND item_id = ?
                    LIMIT 1
                    """,
                    (fallback_platform, safe_item_id),
                ).fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Product parse cache not found")

            connection.execute(
                """
                UPDATE product_parse_cache
                SET hit_count = hit_count + 1,
                    last_hit_at = ?
                WHERE platform = ? AND item_id = ?
                """,
                (now_text, row["platform"], row["item_id"]),
            )
            connection.commit()
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Product parse cache is unavailable") from exc

    try:
        payload = json.loads(row["payload_json"])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Product parse cache contains invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Product parse cache returned invalid payload")

    return {
        "success": True,
        "platform": row["platform"],
        "item_id": row["item_id"],
        "title": row["title"],
        "shop_name": row["shop_name"],
        "base_price": row["base_price"],
        "first_main_image": row["first_main_image"],
        "source_url": row["source_url"],
        "updated_at": row["updated_at"],
        "hit_count": int(row["hit_count"] or 0) + 1,
        "payload": payload,
    }


def list_product_parse_cache(
    platform: str,
    keyword: str,
    limit: int,
    offset: int,
    user: AdminUser,
) -> dict[str, Any]:
    platform_value = str(platform or "").strip().lower()
    all_platforms = platform_value in {"", "all", "*"}
    safe_platform = "all" if all_platforms else normalize_product_cache_platform(platform)
    safe_keyword = str(keyword or "").strip()
    safe_limit = max(1, min(int(limit or 100), 500))
    safe_offset = max(0, int(offset or 0))
    db_path = ensure_product_parse_cache_db()

    where_parts: list[str] = []
    parameters: list[Any] = []
    if not all_platforms:
        where_parts.append("platform = ?")
        parameters.append(safe_platform)
    if safe_keyword:
        like_value = f"%{safe_keyword}%"
        where_parts.append(
            """
            (
                item_id LIKE ?
                OR title LIKE ?
                OR shop_name LIKE ?
                OR source_url LIKE ?
            )
            """
        )
        parameters.extend([like_value, like_value, like_value, like_value])

    where_sql = " AND ".join(where_parts) if where_parts else "1 = 1"
    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM product_parse_cache WHERE {where_sql}",
                    parameters,
                ).fetchone()[0]
                or 0
            )
            rows = connection.execute(
                f"""
                SELECT platform, item_id, title, shop_name, base_price, first_main_image,
                       source_url, payload_json, updated_at, hit_count, uploader_username, source
                FROM product_parse_cache
                WHERE {where_sql}
                ORDER BY datetime(updated_at) DESC, item_id ASC
                LIMIT ? OFFSET ?
                """,
                [*parameters, safe_limit, safe_offset],
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Product parse cache is unavailable") from exc

    items: list[dict[str, Any]] = []
    for row in rows:
        payload: dict[str, Any] = {}
        try:
            parsed = json.loads(row["payload_json"])
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}

        items.append(
            {
                "platform": row["platform"],
                "item_id": row["item_id"],
                "title": row["title"],
                "shop_name": row["shop_name"],
                "base_price": row["base_price"],
                "first_main_image": row["first_main_image"],
                "source_url": row["source_url"],
                "updated_at": row["updated_at"],
                "hit_count": int(row["hit_count"] or 0),
                "uploader_username": row["uploader_username"],
                "source": row["source"],
                "payload": payload,
            }
        )

    return {
        "success": True,
        "platform": safe_platform,
        "keyword": safe_keyword,
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "items": items,
    }


def save_product_parse_cache(payload: ProductParseCacheUploadRequest, user: AdminUser) -> dict[str, Any]:
    safe_platform = normalize_product_cache_platform(payload.platform)
    safe_item_id = normalize_product_cache_item_id(
        payload.item_id
        or extract_product_cache_text(payload.payload, "item_info", "item_id")
        or payload.source_url
    )
    if not isinstance(payload.payload, dict) or not payload.payload:
        raise HTTPException(status_code=400, detail="Payload is required")

    preliminary_payload_bytes = json.dumps(payload.payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(preliminary_payload_bytes) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Product parse payload is too large")

    title = extract_product_cache_text(payload.payload, "item_info", "title")[:300]
    if not title:
        title = extract_product_cache_text(payload.payload, "title")[:300]
    if not title:
        raise HTTPException(status_code=400, detail="Payload title is required")

    item_info = payload.payload.get("item_info")
    if isinstance(item_info, dict):
        item_info["item_id"] = safe_item_id
    else:
        payload.payload["item_info"] = {"item_id": safe_item_id, "title": title}

    json_text = json.dumps(payload.payload, ensure_ascii=False, separators=(",", ":"))
    payload_bytes = json_text.encode("utf-8")
    if len(payload_bytes) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Product parse payload is too large")

    shop_name = extract_product_cache_text(payload.payload, "item_info", "shop_name")[:200]
    first_main_image = extract_product_cache_first_image(payload.payload)[:1000]
    source_url = str(payload.source_url or "").strip()[:1000]
    source = str(payload.source or "").strip()[:120]
    now_text = datetime.utcnow().isoformat(timespec="seconds")
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    db_path = ensure_product_parse_cache_db()

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT is_admin_locked, payload_sha256
                FROM product_parse_cache
                WHERE platform = ? AND item_id = ?
                LIMIT 1
                """,
                (safe_platform, safe_item_id),
            ).fetchone()
            if row is not None and int(row["is_admin_locked"] or 0):
                return {
                    "success": True,
                    "stored": False,
                    "reason": "admin_locked",
                    "platform": safe_platform,
                    "item_id": safe_item_id,
                }

            connection.execute(
                """
                INSERT INTO product_parse_cache (
                    platform, item_id, title, shop_name, base_price, first_main_image,
                    source_url, payload_json, payload_sha256, uploader_user_id,
                    uploader_username, source, is_admin_locked, hit_count,
                    created_at, updated_at, last_hit_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, NULL)
                ON CONFLICT(platform, item_id) DO UPDATE SET
                    title = excluded.title,
                    shop_name = excluded.shop_name,
                    base_price = excluded.base_price,
                    first_main_image = excluded.first_main_image,
                    source_url = excluded.source_url,
                    payload_json = excluded.payload_json,
                    payload_sha256 = excluded.payload_sha256,
                    uploader_user_id = excluded.uploader_user_id,
                    uploader_username = excluded.uploader_username,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    safe_platform,
                    safe_item_id,
                    title,
                    shop_name,
                    extract_product_cache_base_price(payload.payload),
                    first_main_image,
                    source_url,
                    json_text,
                    payload_hash,
                    user.id,
                    user.username,
                    source or "software-client",
                    now_text,
                    now_text,
                ),
            )
            connection.commit()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Product parse cache is unavailable") from exc

    return {
        "success": True,
        "stored": True,
        "platform": safe_platform,
        "item_id": safe_item_id,
        "title": title,
        "payload_sha256": payload_hash,
    }


def delete_product_parse_cache(platform: str, item_id: str, user: AdminUser) -> dict[str, Any]:
    safe_platform = normalize_product_cache_platform(platform)
    safe_item_id = normalize_product_cache_item_id(item_id)
    db_path = ensure_product_parse_cache_db()

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT platform, item_id, title
                FROM product_parse_cache
                WHERE platform = ? AND item_id = ?
                LIMIT 1
                """,
                (safe_platform, safe_item_id),
            ).fetchone()
            if row is None and safe_platform in {"taobao", "tmall"}:
                fallback_platform = "tmall" if safe_platform == "taobao" else "taobao"
                row = connection.execute(
                    """
                    SELECT platform, item_id, title
                    FROM product_parse_cache
                    WHERE platform = ? AND item_id = ?
                    LIMIT 1
                    """,
                    (fallback_platform, safe_item_id),
                ).fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Product parse cache not found")

            connection.execute(
                """
                DELETE FROM product_parse_cache
                WHERE platform = ? AND item_id = ?
                """,
                (row["platform"], row["item_id"]),
            )
            connection.commit()
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Product parse cache is unavailable") from exc

    return {
        "success": True,
        "deleted": True,
        "platform": row["platform"],
        "item_id": row["item_id"],
        "title": row["title"],
    }


def get_publish_failure_report_db_path() -> Path:
    return PUBLISH_FAILURE_REPORT_DB_PATH


def ensure_publish_failure_report_db() -> Path:
    db_path = get_publish_failure_report_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS publish_failure_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_user_id INTEGER,
                reporter_username TEXT NOT NULL DEFAULT '',
                reporter_role TEXT NOT NULL DEFAULT '',
                reporter_account_type TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                client_reported_at TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                shop_name TEXT NOT NULL DEFAULT '',
                category_id TEXT NOT NULL DEFAULT '',
                category_name TEXT NOT NULL DEFAULT '',
                item_id TEXT NOT NULL DEFAULT '',
                draft_id TEXT NOT NULL DEFAULT '',
                task_id INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL DEFAULT '',
                error_reason TEXT NOT NULL DEFAULT '',
                source_file TEXT NOT NULL DEFAULT '',
                app_version TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                device_name TEXT NOT NULL DEFAULT '',
                report_json TEXT NOT NULL DEFAULT '{}',
                task_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_publish_failure_reports_created_at ON publish_failure_reports(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_publish_failure_reports_category_id ON publish_failure_reports(category_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_publish_failure_reports_item_id ON publish_failure_reports(item_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_publish_failure_reports_platform_category ON publish_failure_reports(platform, category_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_publish_failure_reports_reporter_username ON publish_failure_reports(reporter_username)"
        )
        connection.commit()
    return db_path


def trim_publish_failure_text(value: Any, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def serialize_publish_failure_json(value: dict[str, Any], max_size: int, field_name: str) -> str:
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON object")
    json_text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(json_text.encode("utf-8")) > max_size:
        raise HTTPException(status_code=413, detail=f"{field_name} is too large")
    return json_text


def parse_publish_failure_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def save_publish_failure_report(payload: PublishFailureReportRequest, user: AdminUser) -> dict[str, Any]:
    safe_platform = normalize_product_cache_platform(payload.platform)
    report_json_text = serialize_publish_failure_json(payload.report_json, 512 * 1024, "report_json")
    task_json_text = serialize_publish_failure_json(payload.task_json, 2 * 1024 * 1024, "task_json")
    now_text = datetime.utcnow().isoformat(timespec="seconds")
    db_path = ensure_publish_failure_report_db()

    try:
        task_id = max(0, int(payload.task_id or 0))
    except (TypeError, ValueError):
        task_id = 0

    try:
        with sqlite3.connect(str(db_path)) as connection:
            cursor = connection.execute(
                """
                INSERT INTO publish_failure_reports (
                    reporter_user_id, reporter_username, reporter_role, reporter_account_type,
                    created_at, client_reported_at, platform, shop_name, category_id, category_name,
                    item_id, draft_id, task_id, title, stage, error_reason, source_file,
                    app_version, device_id, device_name, report_json, task_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    trim_publish_failure_text(user.username, 120),
                    trim_publish_failure_text(user.role, 40),
                    trim_publish_failure_text(getattr(user, "account_type", "") or user.role, 40),
                    now_text,
                    trim_publish_failure_text(payload.client_reported_at, 64),
                    safe_platform,
                    trim_publish_failure_text(payload.shop_name, 200),
                    trim_publish_failure_text(payload.category_id, 80),
                    trim_publish_failure_text(payload.category_name, 300),
                    trim_publish_failure_text(payload.item_id, 80),
                    trim_publish_failure_text(payload.draft_id, 120),
                    task_id,
                    trim_publish_failure_text(payload.title, 500),
                    trim_publish_failure_text(payload.stage, 120),
                    trim_publish_failure_text(payload.error_reason, 8000),
                    trim_publish_failure_text(payload.source_file, 500),
                    trim_publish_failure_text(payload.app_version, 80),
                    trim_publish_failure_text(payload.device_id, 160),
                    trim_publish_failure_text(payload.device_name, 200),
                    report_json_text,
                    task_json_text,
                ),
            )
            connection.commit()
            report_id = int(cursor.lastrowid or 0)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Publish failure report storage is unavailable") from exc

    return {
        "success": True,
        "id": report_id,
        "created_at": now_text,
    }


def list_publish_failure_reports(
    platform: str,
    keyword: str,
    category_id: str,
    item_id: str,
    stage: str,
    limit: int,
    offset: int,
    user: AdminUser,
) -> dict[str, Any]:
    platform_value = str(platform or "").strip().lower()
    all_platforms = platform_value in {"", "all", "*"}
    safe_platform = "all" if all_platforms else normalize_product_cache_platform(platform)
    safe_keyword = trim_publish_failure_text(keyword, 200)
    safe_category_id = trim_publish_failure_text(category_id, 80)
    safe_item_id = trim_publish_failure_text(item_id, 80)
    safe_stage = trim_publish_failure_text(stage, 120)
    safe_limit = max(1, min(int(limit or 100), 500))
    safe_offset = max(0, int(offset or 0))
    db_path = ensure_publish_failure_report_db()

    where_parts: list[str] = []
    parameters: list[Any] = []
    if not all_platforms:
        where_parts.append("platform = ?")
        parameters.append(safe_platform)
    if safe_keyword:
        like_value = f"%{safe_keyword}%"
        where_parts.append(
            """
            (
                error_reason LIKE ?
                OR title LIKE ?
                OR shop_name LIKE ?
                OR category_name LIKE ?
                OR reporter_username LIKE ?
                OR source_file LIKE ?
                OR stage LIKE ?
                OR item_id LIKE ?
                OR category_id LIKE ?
            )
            """
        )
        parameters.extend([like_value] * 9)
    if safe_category_id:
        where_parts.append("category_id LIKE ?")
        parameters.append(f"%{safe_category_id}%")
    if safe_item_id:
        where_parts.append("item_id LIKE ?")
        parameters.append(f"%{safe_item_id}%")
    if safe_stage:
        where_parts.append("stage LIKE ?")
        parameters.append(f"%{safe_stage}%")

    where_sql = " AND ".join(where_parts) if where_parts else "1 = 1"
    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM publish_failure_reports WHERE {where_sql}",
                    parameters,
                ).fetchone()[0]
                or 0
            )
            rows = connection.execute(
                f"""
                SELECT id, reporter_user_id, reporter_username, reporter_role, reporter_account_type,
                       created_at, client_reported_at, platform, shop_name, category_id, category_name,
                       item_id, draft_id, task_id, title, stage, error_reason, source_file,
                       app_version, device_id, device_name, report_json, task_json
                FROM publish_failure_reports
                WHERE {where_sql}
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, safe_limit, safe_offset],
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Publish failure report storage is unavailable") from exc

    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": int(row["id"] or 0),
                "reporter_user_id": row["reporter_user_id"],
                "reporter_username": row["reporter_username"],
                "reporter_role": row["reporter_role"],
                "reporter_account_type": row["reporter_account_type"],
                "created_at": row["created_at"],
                "client_reported_at": row["client_reported_at"],
                "platform": row["platform"],
                "shop_name": row["shop_name"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "item_id": row["item_id"],
                "draft_id": row["draft_id"],
                "task_id": int(row["task_id"] or 0),
                "title": row["title"],
                "stage": row["stage"],
                "error_reason": row["error_reason"],
                "source_file": row["source_file"],
                "app_version": row["app_version"],
                "device_id": row["device_id"],
                "device_name": row["device_name"],
                "report_json": parse_publish_failure_json(row["report_json"]),
                "task_json": parse_publish_failure_json(row["task_json"]),
            }
        )

    return {
        "success": True,
        "platform": safe_platform,
        "keyword": safe_keyword,
        "category_id": safe_category_id,
        "item_id": safe_item_id,
        "stage": safe_stage,
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "items": items,
    }


def normalize_rule_category_id(category_id: str) -> str:
    value = str(category_id or "").strip()
    match = re.search(r"\d+", value)
    normalized = match.group(0) if match else value
    if not normalized:
        raise HTTPException(status_code=400, detail="Category ID is required")
    if len(normalized) > 64:
        raise HTTPException(status_code=400, detail="Category ID is too long")
    return normalized


def build_rule_placeholder_category_name(category_id: str) -> str:
    return f"类目 {str(category_id or '').strip()}"


def is_rule_placeholder_category_name(category_name: Any, category_id: str) -> bool:
    text = str(category_name or "").strip()
    safe_category_id = str(category_id or "").strip()
    if not text:
        return True
    if safe_category_id and text == build_rule_placeholder_category_name(safe_category_id):
        return True
    if safe_category_id and re.fullmatch(r"类目\s*" + re.escape(safe_category_id), text, re.IGNORECASE):
        return True
    return False


def is_trusted_rule_category_name(category_name: Any, category_id: str) -> bool:
    text = str(category_name or "").strip()
    return bool(text) and not is_rule_placeholder_category_name(text, category_id)


def choose_rule_category_name(category_id: str, *candidates: Any) -> str:
    safe_category_id = str(category_id or "").strip()
    for candidate in candidates:
        text = str(candidate or "").strip()
        if is_trusted_rule_category_name(text, safe_category_id):
            return text
    return build_rule_placeholder_category_name(safe_category_id)


def get_rule_dictionary_category_name(connection: sqlite3.Connection, platform: str, category_id: str) -> str:
    try:
        row = connection.execute(
            """
            SELECT category_name
            FROM category_name_dictionary
            WHERE platform = ? AND category_id = ?
            LIMIT 1
            """,
            (platform, category_id),
        ).fetchone()
    except sqlite3.Error:
        return ""
    if row is None:
        return ""
    value = row["category_name"] if isinstance(row, sqlite3.Row) else row[0]
    return str(value or "").strip()


def parse_rule_json_payload(raw_json: str | None) -> dict[str, Any]:
    if not raw_json:
        return {}
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Rule catalog contains invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Rule catalog returned an invalid rule payload")
    return payload


def get_rule_catalog_db_path() -> Path:
    return RULE_CATALOG_DB_PATH


def get_rule_page_import_root_path() -> Path:
    return get_rule_catalog_db_path().parent / "page_imports"


def invalidate_rule_catalog_cache() -> None:
    with _rule_catalog_cache_lock:
        _rule_catalog_cache["mtime_ns"] = None
        _rule_catalog_cache["created_at"] = 0.0
        _rule_catalog_cache["payload"] = None


def get_cached_rule_catalog_payload(db_path: Path) -> dict[str, Any] | None:
    try:
        mtime_ns = db_path.stat().st_mtime_ns
    except OSError:
        return None

    now = time.monotonic()
    with _rule_catalog_cache_lock:
        payload = _rule_catalog_cache.get("payload")
        if (
            isinstance(payload, dict)
            and _rule_catalog_cache.get("mtime_ns") == mtime_ns
            and now - float(_rule_catalog_cache.get("created_at") or 0.0) < RULE_CATALOG_CACHE_TTL_SECONDS
        ):
            return payload
    return None


def set_cached_rule_catalog_payload(db_path: Path, payload: dict[str, Any]) -> None:
    try:
        mtime_ns = db_path.stat().st_mtime_ns
    except OSError:
        return

    with _rule_catalog_cache_lock:
        _rule_catalog_cache["mtime_ns"] = mtime_ns
        _rule_catalog_cache["created_at"] = time.monotonic()
        _rule_catalog_cache["payload"] = payload


def get_rule_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)


def get_rule_json_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text_value = str(value).strip().lower()
    return text_value in {"true", "1", "yes", "y"}


def normalize_rule_prop_id(raw: Any) -> str:
    match = re.search(r"p-(\d+)|(\d+)", str(raw or "").strip())
    if not match:
        return ""
    return match.group(1) or match.group(2) or ""


def normalize_rule_prop_key(raw: Any) -> str:
    prop_id = normalize_rule_prop_id(raw)
    return f"p-{prop_id}" if prop_id else ""


def find_first_rule_property_value(node: Any, property_name: str) -> str:
    if not property_name:
        return ""
    if isinstance(node, dict):
        for key, child in node.items():
            if str(key).lower() == property_name.lower():
                return get_rule_json_text(child).strip()
            nested = find_first_rule_property_value(child, property_name)
            if nested:
                return nested
    elif isinstance(node, list):
        for child in node:
            nested = find_first_rule_property_value(child, property_name)
            if nested:
                return nested
    return ""


def iter_rule_json_objects(node: Any):
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from iter_rule_json_objects(child)
    elif isinstance(node, list):
        for child in node:
            yield from iter_rule_json_objects(child)


def collect_rule_enum_map(node: Any, enum_map: dict[str, str]) -> None:
    if node is None:
        return
    if isinstance(node, dict):
        text_value = get_rule_json_text(node.get("text")).strip()
        id_value = get_rule_json_text(node.get("value")).strip()
        if text_value and id_value and text_value not in enum_map:
            enum_map[text_value] = id_value
        for child in node.values():
            collect_rule_enum_map(child, enum_map)
    elif isinstance(node, list):
        for child in node:
            collect_rule_enum_map(child, enum_map)


def extract_rule_default_text(value_node: Any) -> str:
    if isinstance(value_node, dict):
        return get_rule_json_text(value_node.get("text")).strip()
    return ""


def build_bind_prop_rule_node(source: dict[str, Any], prop_key: str) -> dict[str, Any] | None:
    label = get_rule_json_text(source.get("label")).strip() or prop_key
    required = get_rule_json_bool(source.get("required"))
    default_text = extract_rule_default_text(source.get("value"))
    enum_map: dict[str, str] = {}
    collect_rule_enum_map(source.get("dataSource"), enum_map)
    if not required and not enum_map and not label:
        return None

    payload: dict[str, Any] = {
        "label": label,
        "required": required,
    }
    if default_text:
        payload["defaultText"] = default_text
    if enum_map:
        payload["enumMap"] = enum_map
    return payload


def collect_rule_bind_props(
    node: Any,
    result: dict[str, dict[str, Any]],
    parent_property_name: str = "",
) -> None:
    if node is None:
        return
    if isinstance(node, dict):
        prop_key = normalize_rule_prop_key(parent_property_name) or normalize_rule_prop_key(node.get("name"))
        if prop_key:
            rule_node = build_bind_prop_rule_node(node, prop_key)
            if rule_node is not None:
                result[prop_key] = rule_node
        for key, child in node.items():
            collect_rule_bind_props(child, result, str(key))
    elif isinstance(node, list):
        for child in node:
            collect_rule_bind_props(child, result, parent_property_name)


def extract_rule_bind_props(root: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    collect_rule_bind_props(root, result)
    return result


def score_rule_named_object(obj: dict[str, Any]) -> int:
    score = 0
    if get_rule_json_text(obj.get("uiType")).strip():
        score += 20
    if isinstance(obj.get("subItems"), list) and obj["subItems"]:
        score += 15
    if isinstance(obj.get("dataSource"), list) and obj["dataSource"]:
        score += 10
    if get_rule_json_text(obj.get("label")).strip():
        score += 4
    for key in ("required", "hasCustomProp", "maxCustomItems"):
        if key in obj:
            score += 3
    if "showRemark" in obj:
        score += 3
    if "remarkMaxLength" in obj:
        score += 2
    return score


def find_first_rule_named_object(root: Any, property_name: str) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = -1
    for obj in iter_rule_json_objects(root):
        candidates: list[dict[str, Any]] = []
        if get_rule_json_text(obj.get("name")).strip().lower() == property_name.lower():
            candidates.append(obj)
        child = obj.get(property_name)
        if isinstance(child, dict):
            candidates.append(child)
        for candidate in candidates:
            score = score_rule_named_object(candidate)
            if best is None or score > best_score:
                best = candidate
                best_score = score
    return best


def extract_rule_mapped_sale_props(root: Any) -> list[tuple[str, str]]:
    best: list[tuple[str, str]] = []
    for obj in iter_rule_json_objects(root):
        node = obj.get("catSalePropMap") if isinstance(obj, dict) else None
        if not isinstance(node, dict):
            continue
        mapped: list[tuple[str, str]] = []
        for key, value in node.items():
            prop_id = normalize_rule_prop_id(key)
            label = get_rule_json_text(value).strip()
            if prop_id and label:
                mapped.append((prop_id, label))
        if len(mapped) > len(best):
            best = mapped
    return best


def extract_rule_sale_prop_info(root: Any) -> dict[str, Any]:
    color_prop_id = normalize_rule_prop_id(find_first_rule_property_value(root, "aliColorEnable"))
    size_prop_id = normalize_rule_prop_id(find_first_rule_property_value(root, "sizeSaleProp"))
    color_label = ""
    size_label = ""
    mapped_sale_props = extract_rule_mapped_sale_props(root)
    is_single_sale_prop = len(mapped_sale_props) == 1

    if not color_prop_id and not is_single_sale_prop:
        for prop_id, label in mapped_sale_props:
            if "颜色" in label or "花色" in label or prop_id == "1627207":
                color_prop_id = prop_id
                color_label = label
                break
        if not color_prop_id and mapped_sale_props:
            color_prop_id, color_label = mapped_sale_props[0]

    if not size_prop_id:
        for prop_id, label in mapped_sale_props:
            if prop_id != color_prop_id:
                size_prop_id = prop_id
                size_label = label
                break

    if not color_prop_id and find_first_rule_named_object(root, "p-1627207") is not None:
        color_prop_id = "1627207"
    if not color_label and color_prop_id:
        named = find_first_rule_named_object(root, f"p-{color_prop_id}")
        if named:
            color_label = get_rule_json_text(named.get("label")).strip()
    if not size_prop_id:
        for candidate in ("20509", "31745"):
            if find_first_rule_named_object(root, f"p-{candidate}") is not None:
                size_prop_id = candidate
                break
    if not size_label and size_prop_id:
        named = find_first_rule_named_object(root, f"p-{size_prop_id}")
        if named:
            size_label = get_rule_json_text(named.get("label")).strip()

    secondary_required = False
    if size_prop_id:
        named = find_first_rule_named_object(root, f"p-{size_prop_id}")
        if named is not None:
            secondary_required = get_rule_json_bool(named.get("required"))

    return {
        "colorPropId": color_prop_id,
        "colorLabel": color_label or ("颜色分类" if color_prop_id else ""),
        "sizePropId": size_prop_id,
        "sizeLabel": size_label or ("尺码" if size_prop_id else ""),
        "secondaryRequired": secondary_required,
    }


def build_rule_sale_prop_node(sale_info: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    color_prop_id = str(sale_info.get("colorPropId") or "").strip()
    size_prop_id = str(sale_info.get("sizePropId") or "").strip()
    if color_prop_id:
        payload["colorPropId"] = color_prop_id
        payload["colorLabel"] = str(sale_info.get("colorLabel") or "颜色分类").strip() or "颜色分类"
    if size_prop_id:
        payload["sizePropId"] = size_prop_id
        payload["sizeLabel"] = str(sale_info.get("sizeLabel") or "尺码").strip() or "尺码"
        if bool(sale_info.get("secondaryRequired")):
            payload["secondaryRequired"] = True
    return payload


def extract_rule_direct_options(node: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []

    def visit(child: Any) -> None:
        if isinstance(child, dict):
            size_list = child.get("sizeList")
            if isinstance(size_list, list):
                for item in size_list:
                    if not isinstance(item, dict):
                        continue
                    text = get_rule_json_text(item.get("text")).strip()
                    value = get_rule_json_text(item.get("value")).strip()
                    if text and value:
                        result.append({"text": text, "value": value})
                return

            text = get_rule_json_text(child.get("text")).strip()
            value = get_rule_json_text(child.get("value")).strip()
            if text and value and "subName" not in child and "colors" not in child:
                result.append({"text": text, "value": value})

            for value_node in child.values():
                visit(value_node)
        elif isinstance(child, list):
            for item in child:
                visit(item)

    visit(node)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in result:
        key = item["text"].strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def extract_rule_size_groups(size_node: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not isinstance(size_node, dict):
        return [], {}

    sub_items = size_node.get("subItems")
    if not isinstance(sub_items, list):
        return [], {}

    group_names: dict[str, str] = {}
    group_meta: dict[str, dict[str, str]] = {}
    for sub_item in sub_items:
        if not isinstance(sub_item, dict):
            continue
        if get_rule_json_text(sub_item.get("name")).strip().lower() != "selectedsizegroupid":
            continue
        data_source = sub_item.get("dataSource")
        if not isinstance(data_source, list):
            continue
        for group_item in data_source:
            if not isinstance(group_item, dict):
                continue
            sub_name = get_rule_json_text(group_item.get("subName")).strip()
            if not sub_name:
                value = get_rule_json_text(group_item.get("value")).strip()
                sub_name = f"sizeGroup_{value}" if value else ""
            if not sub_name:
                continue
            text = get_rule_json_text(group_item.get("text")).strip()
            value = get_rule_json_text(group_item.get("value")).strip()
            group_type = get_rule_json_text(group_item.get("sizeGroupType")).strip()
            group_names[sub_name] = text or value or sub_name
            group_meta[sub_name] = {
                "text": text,
                "value": value,
                "sizeGroupType": group_type,
            }

    groups: list[dict[str, Any]] = []
    for sub_item in sub_items:
        if not isinstance(sub_item, dict):
            continue
        node_name = get_rule_json_text(sub_item.get("name")).strip()
        if not node_name.lower().startswith("sizegroup_"):
            continue
        options = extract_rule_direct_options(sub_item.get("dataSource"))
        sizes = [item["text"] for item in options if item.get("text")]
        if not sizes:
            continue
        group_payload: dict[str, Any] = {
            "name": group_names.get(node_name) or node_name,
            "sizes": sizes,
            "options": options,
        }
        meta = group_meta.get(node_name) or {}
        if meta.get("text"):
            group_payload["text"] = meta["text"]
        if meta.get("value"):
            group_payload["value"] = meta["value"]
        if meta.get("sizeGroupType"):
            group_payload["sizeGroupType"] = meta["sizeGroupType"]
        groups.append(group_payload)

    default_group = next((meta for meta in group_meta.values() if meta.get("text") or meta.get("value") or meta.get("sizeGroupType")), {})
    return groups, default_group


def enrich_rule_sale_prop_node(root: Any, sale_prop: dict[str, Any], sale_info: dict[str, Any]) -> None:
    color_prop_id = str(sale_info.get("colorPropId") or "").strip()
    size_prop_id = str(sale_info.get("sizePropId") or "").strip()

    if color_prop_id:
        color_node = find_first_rule_named_object(root, f"p-{color_prop_id}")
        color_options = extract_rule_direct_options(color_node)
        if color_options:
            sale_prop["colorOptions"] = color_options[:300]
            sale_prop["colorEnumTexts"] = [item["text"] for item in color_options[:300] if item.get("text")]
            sale_prop["colorEnumValueIds"] = [item["value"] for item in color_options[:300] if item.get("value")]
        if isinstance(color_node, dict):
            max_custom = get_rule_json_text(color_node.get("maxCustomItems")).strip()
            if max_custom.isdigit():
                sale_prop["colorMaxCustomItems"] = int(max_custom)

    if not size_prop_id:
        return

    size_node = find_first_rule_named_object(root, f"p-{size_prop_id}")
    size_options = extract_rule_direct_options(size_node)
    if size_options:
        sale_prop["supportedSizeOptions"] = size_options[:500]
        sale_prop["supportedSizes"] = [item["text"] for item in size_options[:500] if item.get("text")]

    groups, default_group = extract_rule_size_groups(size_node)
    if groups:
        sale_prop["supportedSizeGroups"] = groups[:80]
    if default_group:
        if default_group.get("text"):
            sale_prop["sizeGroupText"] = default_group["text"]
        if default_group.get("value"):
            sale_prop["sizeGroupValue"] = default_group["value"]
        if default_group.get("sizeGroupType"):
            sale_prop["sizeGroupType"] = default_group["sizeGroupType"]

    if isinstance(size_node, dict):
        if "required" in size_node:
            sale_prop["secondaryRequired"] = get_rule_json_bool(size_node.get("required"))
        if get_rule_json_bool(size_node.get("hasCustomProp")) or get_rule_json_bool(size_node.get("custom")):
            sale_prop["secondarySupportsFreeText"] = True


def infer_rule_platform_from_page(root: Any, raw_text: str) -> str:
    marker = " ".join(
        [
            find_first_rule_property_value(root, "requestDomain"),
            find_first_rule_property_value(root, "hostName"),
            find_first_rule_property_value(root, "identityId"),
        ],
    )
    if "item.upload.taobao.com" in marker.lower() or "general-taobao" in marker.lower():
        return "taobao"
    if "sell.publish.tmall.com" in marker.lower() or "general-tmall" in marker.lower():
        return "tmall"
    lower_text = f"{marker} {raw_text[:5000]}".lower()
    if "tmall" in lower_text:
        return "tmall"
    if "taobao" in lower_text:
        return "taobao"
    return ""


def count_rule_enum_values(bind_props: dict[str, dict[str, Any]]) -> int:
    total = 0
    for prop in bind_props.values():
        enum_map = prop.get("enumMap")
        if isinstance(enum_map, dict):
            total += len(enum_map)
    return total


def get_rule_nested_value(root: Any, *path: str) -> Any:
    current = root
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_rule_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_rule_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else format(value, "g")


def extract_rule_size_mapping_package(root: dict[str, Any]) -> dict[str, Any]:
    required = get_rule_json_bool(
        get_rule_nested_value(root, "components", "sizeMapping", "props", "value", "sizeTabRequired")
    ) or get_rule_json_bool(
        get_rule_nested_value(root, "models", "formValues", "sizeMapping", "sizeTabRequired")
    )

    data_source = get_rule_nested_value(root, "components", "sizeModelTry", "props", "dataSource")
    field_specs: list[str] = []
    if isinstance(data_source, list):
        for field in data_source:
            if not isinstance(field, dict):
                continue
            if not get_rule_json_bool(field.get("required")):
                continue
            if get_rule_json_text(field.get("uiType")).strip().lower() != "number":
                continue

            name = get_rule_json_text(field.get("name")).strip()
            label = get_rule_json_text(field.get("label")).strip()
            if not name or not label:
                continue

            minimum = normalize_rule_number(field.get("minimum"))
            maximum = normalize_rule_number(field.get("maximum"))
            if minimum is not None and maximum is not None and maximum >= minimum:
                base_value = minimum + math.floor((maximum - minimum) / 2)
            else:
                base_value = max(minimum or 0, 1)

            options = ["required=1"]
            if minimum is not None:
                options.append("min=" + format_rule_number(minimum))
            if maximum is not None:
                options.append("max=" + format_rule_number(maximum))
            if name.lower() == "tizhong":
                options.append("source=remarkWeightKg")
            field_specs.append(
                f"{name}:{label}:{format_rule_number(float(base_value))}:1:{','.join(options)}"
            )

    fields = ";".join(field_specs)
    return {
        "forceSingleSizeMapping": required,
        "sizeMappingTemplateId": "3574321" if required and fields else "",
        "sizeMappingFields": fields if required else "",
    }


def merge_rule_objects(current: Any, imported: Any) -> dict[str, Any]:
    merged = dict(current) if isinstance(current, dict) else {}
    if isinstance(imported, dict):
        for key, value in imported.items():
            if value is not None:
                merged[key] = value
    return merged


def merge_imported_rule_node(current_node: dict[str, Any], imported_node: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current_node) if isinstance(current_node, dict) else {}
    for key in ("platform", "categoryId", "categoryName", "notes"):
        value = get_rule_json_text(imported_node.get(key)).strip()
        if value:
            merged[key] = value
    merged["bindProp"] = imported_node.get("bindProp") if isinstance(imported_node.get("bindProp"), dict) else {}
    merged["saleProp"] = merge_rule_objects(merged.get("saleProp"), imported_node.get("saleProp"))
    merged["package"] = merge_rule_objects(merged.get("package"), imported_node.get("package"))
    return merged


def rule_payload_has_effective_fields(rule: dict[str, Any]) -> bool:
    for key in ("keyProp", "bindProp"):
        if isinstance(rule.get(key), dict) and bool(rule.get(key)):
            return True

    sale_prop = rule.get("saleProp")
    if isinstance(sale_prop, dict):
        for key in ("colorPropId", "sizePropId", "secondaryRequired"):
            value = sale_prop.get(key)
            if isinstance(value, bool):
                if value:
                    return True
            elif str(value or "").strip():
                return True

    package_payload = rule.get("package")
    if isinstance(package_payload, dict):
        ignored_keys = {"packageKey", "packageName", "notes", "importedFromPage"}
        for key, value in package_payload.items():
            if key in ignored_keys:
                continue
            if isinstance(value, bool) and value:
                return True
            if not isinstance(value, bool) and str(value or "").strip():
                return True

    return False


def get_rule_section(rule: dict[str, Any], key: str) -> dict[str, Any]:
    value = rule.get(key)
    return value if isinstance(value, dict) else {}


def get_rule_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).strip()


def get_rule_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_rule_size_mode_text(size_mode: str) -> str:
    return {
        "height-weight-chest": "身高/体重/胸围尺码映射",
        "simple-enum": "简单枚举尺码",
        "direct-size-array": "原生回放直传尺码数组",
        "single-size-mapping": "单尺码映射",
        "standard-sale-prop": "标准颜色/尺码 saleProp",
        "default": "平台默认尺码模式",
    }.get(size_mode, "平台默认尺码模式")


def resolve_rule_size_mode(package_payload: dict[str, Any], sale_prop: dict[str, Any]) -> str:
    if get_rule_bool(package_payload.get("useHeightWeightChestSizeMapping")):
        return "height-weight-chest"
    if get_rule_bool(package_payload.get("useSimpleEnumSizeSaleProp")):
        return "simple-enum"
    if get_rule_bool(package_payload.get("useTaobaoNativeReplayDirectSizeArray")):
        return "direct-size-array"
    if get_rule_bool(package_payload.get("forceSingleSizeMapping")):
        return "single-size-mapping"
    if get_rule_text(sale_prop.get("sizePropId")):
        return "standard-sale-prop"
    return "default"


def build_rule_support_level(has_explicit_package: bool, bind_prop: dict[str, Any], sale_prop: dict[str, Any]) -> str:
    has_mapping = bool(bind_prop) or bool(sale_prop)
    if has_explicit_package and has_mapping:
        return "专用类目包 + 属性映射"
    if has_explicit_package:
        return "专用类目包"
    return "属性映射兼容"


def build_rule_required_bind_prop_summary(bind_prop: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    required_labels: list[str] = []
    required_keys: list[str] = []
    for key, value in bind_prop.items():
        if not isinstance(value, dict) or not get_rule_bool(value.get("required")):
            continue
        label = get_rule_text(value.get("label")) or key
        required_keys.append(str(key))
        required_labels.append(f"{label} ({key})")
    if not required_labels:
        return "当前没有显式 required=true 的 bindProp 字段", [], []
    return " / ".join(required_labels), required_keys, required_labels


def is_material_rule_field(key: str, label: str, aliases: list[str]) -> bool:
    text = " ".join([key, label, *aliases])
    if "克重" in text:
        return False
    return any(token in text.lower() for token in ["材质", "面料", "fabric", "material"])


def build_rule_material_summary(bind_prop: dict[str, Any], uses_material_array: bool) -> tuple[str, list[str], list[str]]:
    material_labels: list[str] = []
    material_keys: list[str] = []
    for key, value in bind_prop.items():
        if not isinstance(value, dict):
            continue
        label = get_rule_text(value.get("label")) or str(key)
        aliases = value.get("aliases") if isinstance(value.get("aliases"), list) else []
        alias_texts = [get_rule_text(alias) for alias in aliases if get_rule_text(alias)]
        if is_material_rule_field(str(key), label, alias_texts):
            material_keys.append(str(key))
            material_labels.append(f"{label} ({key})")

    parts: list[str] = []
    if material_labels:
        parts.append("类目材质字段：" + " / ".join(material_labels))
    if uses_material_array:
        parts.append("发布链路默认补材质成分数组 p-149422948")
    return ("；".join(parts) if parts else "未发现专用材质规则", material_keys, material_labels)


def build_rule_sale_prop_summary(sale_prop: dict[str, Any], size_mode_text: str) -> str:
    if not sale_prop:
        return f"未维护专用 saleProp，当前按“{size_mode_text}”处理"
    color_prop_id = normalize_rule_prop_id(get_rule_text(sale_prop.get("colorPropId")))
    size_prop_id = normalize_rule_prop_id(get_rule_text(sale_prop.get("sizePropId")))
    color_label = get_rule_text(sale_prop.get("colorLabel")) or "颜色"
    size_label = get_rule_text(sale_prop.get("sizeLabel")) or "尺码"
    size_group_type = get_rule_text(sale_prop.get("sizeGroupType"))
    parts: list[str] = []
    if color_prop_id:
        parts.append(f"{color_label}({color_prop_id})")
    if size_prop_id:
        parts.append(f"{size_label}({size_prop_id})")
    if size_group_type:
        parts.append("尺码组 " + size_group_type)
    if get_rule_bool(sale_prop.get("secondaryRequired")):
        parts.append("二级规格必填")
    parts.append(size_mode_text)
    return " / ".join(part for part in parts if part)


def build_rule_special_rules(package_payload: dict[str, Any], has_explicit_package: bool, secondary_required: bool) -> list[str]:
    rules: list[str] = []
    if secondary_required:
        rules.append("二级规格必填")
    flag_texts = {
        "useTaobaoNativeReplay": "走淘宝原生回放提交流程",
        "useTaobaoNativeReplayDirectSizeArray": "直接提交尺码数组",
        "forceSquareMainImages": "主图强制 1:1 方图",
        "forceTaobaoNoBrand": "品牌固定使用无品牌",
        "forceSingleSizeMapping": "强制单尺码映射",
        "useSimpleEnumSizeSaleProp": "尺码 saleProp 走简单枚举",
        "useHeightWeightChestSizeMapping": "尺码映射走身高/体重/胸围",
        "requireVerticalGuideImage": "需要额外 2:3 竖图引导图",
        "appendSizeRemarkToSubmittedSizeText": "提交尺码时拼接备注文本",
        "requireMultiDiscountPromotion": "多件优惠必填（默认 9.9 折）",
        "requireSkuCombineContent": "SKU包含产品必填",
        "requireSkuQuality": "SKU分类必填",
        "requireBarcode": "商品条形码必填",
    }
    for key, text in flag_texts.items():
        if get_rule_bool(package_payload.get(key)):
            rules.append(text)
    if not rules:
        rules.append("沿用专用类目包默认流程" if has_explicit_package else "走平台默认流程")
    return rules


def build_rule_catalog_summary(rule: dict[str, Any], has_explicit_package: bool) -> dict[str, Any]:
    bind_prop = get_rule_section(rule, "bindProp")
    sale_prop = get_rule_section(rule, "saleProp")
    package_payload = get_rule_section(rule, "package")
    size_mode = resolve_rule_size_mode(package_payload, sale_prop)
    size_mode_text = get_rule_size_mode_text(size_mode)
    secondary_required = get_rule_bool(sale_prop.get("secondaryRequired"))
    uses_material_array = has_explicit_package or bool(bind_prop)
    required_text, required_keys, required_labels = build_rule_required_bind_prop_summary(bind_prop)
    material_text, material_keys, material_labels = build_rule_material_summary(bind_prop, uses_material_array)
    special_rules = build_rule_special_rules(package_payload, has_explicit_package, secondary_required)
    notes = "；".join(
        part
        for part in [get_rule_text(package_payload.get("notes")), get_rule_text(rule.get("notes"))]
        if part
    ) or "无额外备注"
    return {
        "support_level": build_rule_support_level(has_explicit_package, bind_prop, sale_prop),
        "package_key": get_rule_text(package_payload.get("packageKey")),
        "package_name": get_rule_text(package_payload.get("packageName")),
        "size_mode": size_mode,
        "size_mode_text": size_mode_text,
        "required_bind_prop_text": required_text,
        "material_rule_text": material_text,
        "sale_prop_text": build_rule_sale_prop_summary(sale_prop, size_mode_text),
        "special_rule_text": " / ".join(special_rules),
        "source_text": "服务器规则库（Rule API）",
        "notes": notes,
        "force_square_main_images": get_rule_bool(package_payload.get("forceSquareMainImages")),
        "force_taobao_no_brand": get_rule_bool(package_payload.get("forceTaobaoNoBrand")),
        "force_single_size_mapping": get_rule_bool(package_payload.get("forceSingleSizeMapping")),
        "size_mapping_template_id": get_rule_text(package_payload.get("sizeMappingTemplateId")),
        "size_mapping_fields": get_rule_text(package_payload.get("sizeMappingFields")),
        "use_simple_enum_size_sale_prop": get_rule_bool(package_payload.get("useSimpleEnumSizeSaleProp")),
        "use_height_weight_chest_size_mapping": get_rule_bool(package_payload.get("useHeightWeightChestSizeMapping")),
        "require_vertical_guide_image": get_rule_bool(package_payload.get("requireVerticalGuideImage")),
        "require_multi_discount_promotion": get_rule_bool(package_payload.get("requireMultiDiscountPromotion")),
        "require_sku_combine_content": get_rule_bool(package_payload.get("requireSkuCombineContent")),
        "require_sku_quality": get_rule_bool(package_payload.get("requireSkuQuality")),
        "require_barcode": get_rule_bool(package_payload.get("requireBarcode")),
        "use_taobao_native_replay": get_rule_bool(package_payload.get("useTaobaoNativeReplay")),
        "use_taobao_native_replay_direct_size_array": get_rule_bool(package_payload.get("useTaobaoNativeReplayDirectSizeArray")),
        "secondary_sale_prop_required": secondary_required,
        "uses_material_composition_array": uses_material_array,
        "required_bind_prop_keys": required_keys,
        "required_bind_prop_labels": required_labels,
        "material_prop_keys": material_keys,
        "material_prop_labels": material_labels,
        "special_rules": special_rules,
    }


def truncate_rule_catalog_text(value: Any, max_length: int) -> str:
    text = get_rule_text(value)
    if max_length <= 0 or len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def compact_rule_catalog_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "support_level": get_rule_text(summary.get("support_level")),
        "package_key": get_rule_text(summary.get("package_key")),
        "package_name": get_rule_text(summary.get("package_name")),
        "size_mode": get_rule_text(summary.get("size_mode")),
        "size_mode_text": get_rule_text(summary.get("size_mode_text")),
        "required_bind_prop_text": truncate_rule_catalog_text(summary.get("required_bind_prop_text"), 220),
        "material_rule_text": truncate_rule_catalog_text(summary.get("material_rule_text"), 180),
        "sale_prop_text": truncate_rule_catalog_text(summary.get("sale_prop_text"), 180),
        "special_rule_text": truncate_rule_catalog_text(summary.get("special_rule_text"), 180),
        "source_text": get_rule_text(summary.get("source_text")),
        "notes": truncate_rule_catalog_text(summary.get("notes"), 120),
        "force_square_main_images": get_rule_bool(summary.get("force_square_main_images")),
        "force_taobao_no_brand": get_rule_bool(summary.get("force_taobao_no_brand")),
        "force_single_size_mapping": get_rule_bool(summary.get("force_single_size_mapping")),
        "size_mapping_template_id": get_rule_text(summary.get("size_mapping_template_id")),
        "size_mapping_fields": truncate_rule_catalog_text(summary.get("size_mapping_fields"), 500),
        "use_simple_enum_size_sale_prop": get_rule_bool(summary.get("use_simple_enum_size_sale_prop")),
        "use_height_weight_chest_size_mapping": get_rule_bool(summary.get("use_height_weight_chest_size_mapping")),
        "require_vertical_guide_image": get_rule_bool(summary.get("require_vertical_guide_image")),
        "require_multi_discount_promotion": get_rule_bool(summary.get("require_multi_discount_promotion")),
        "require_sku_combine_content": get_rule_bool(summary.get("require_sku_combine_content")),
        "require_sku_quality": get_rule_bool(summary.get("require_sku_quality")),
        "require_barcode": get_rule_bool(summary.get("require_barcode")),
        "use_taobao_native_replay": get_rule_bool(summary.get("use_taobao_native_replay")),
        "use_taobao_native_replay_direct_size_array": get_rule_bool(summary.get("use_taobao_native_replay_direct_size_array")),
        "secondary_sale_prop_required": get_rule_bool(summary.get("secondary_sale_prop_required")),
        "uses_material_composition_array": get_rule_bool(summary.get("uses_material_composition_array")),
    }


def build_rule_catalog_list_summary(rule: dict[str, Any], has_explicit_package: bool) -> dict[str, Any]:
    return compact_rule_catalog_summary(build_rule_catalog_summary(rule, has_explicit_package))


def parse_uploaded_rule_page_json(
    platform: str,
    category_id: str,
    root: dict[str, Any],
    *,
    source_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_text = json.dumps(root, ensure_ascii=False, separators=(",", ":"))
    safe_platform = normalize_rule_platform(platform or infer_rule_platform_from_page(root, raw_text))
    safe_category_id = normalize_rule_category_id(
        category_id or find_first_rule_property_value(root, "catId"),
    )
    page_category_id = normalize_rule_category_id(find_first_rule_property_value(root, "catId") or safe_category_id)
    if page_category_id != safe_category_id:
        raise HTTPException(status_code=400, detail="Uploaded page category ID does not match request")

    category_name = choose_rule_category_name(
        safe_category_id,
        find_first_rule_property_value(root, "categoryName"),
    )
    sale_info = extract_rule_sale_prop_info(root)
    bind_props = extract_rule_bind_props(root)
    for prop_id_key in ("colorPropId", "sizePropId"):
        prop_id = str(sale_info.get(prop_id_key) or "").strip()
        if prop_id:
            bind_props.pop(f"p-{prop_id}", None)
    sale_prop = build_rule_sale_prop_node(sale_info)
    enrich_rule_sale_prop_node(root, sale_prop, sale_info)
    if not bind_props and not sale_prop:
        if get_rule_json_bool(root.get("sessionExpired")):
            raise HTTPException(status_code=422, detail="店铺登录已过期，抓到的是登录跳转页，不是类目发布页")
        raise HTTPException(status_code=422, detail="页面 JSON 没有解析到有效规则字段，请确认店铺发布页已正常加载")

    imported_node = {
        "platform": safe_platform,
        "categoryId": safe_category_id,
        "categoryName": category_name,
        "bindProp": bind_props,
        "saleProp": sale_prop,
        "package": {
            "importedFromPage": True,
            "notes": f"已从服务器页面导入: {source_name}",
            **extract_rule_size_mapping_package(root),
        },
        "notes": f"服务器页面导入: {source_name} | bindProp={len(bind_props)} | enum={count_rule_enum_values(bind_props)}",
    }
    result = {
        "platform": safe_platform,
        "categoryId": safe_category_id,
        "categoryName": category_name,
        "colorPropId": str(sale_info.get("colorPropId") or "").strip(),
        "sizePropId": str(sale_info.get("sizePropId") or "").strip(),
        "secondaryRequired": bool(sale_info.get("secondaryRequired")),
        "bindPropCount": len(bind_props),
        "enumValueCount": count_rule_enum_values(bind_props),
    }
    return imported_node, result


def mark_rule_page_import_failed(platform: str, category_id: str, error_message: str) -> None:
    try:
        safe_platform = normalize_rule_platform(platform)
        safe_category_id = normalize_rule_category_id(category_id)
    except HTTPException:
        return

    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        return

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.execute(
                """
                UPDATE category_rules
                SET fetch_status = 'failed',
                    last_fetch_error = ?,
                    updated_at = ?
                WHERE platform = ? AND category_id = ?
                """,
                (
                    str(error_message or "")[:500],
                    datetime.utcnow().isoformat(timespec="seconds"),
                    safe_platform,
                    safe_category_id,
                ),
            )
            connection.commit()
            invalidate_rule_catalog_cache()
    except sqlite3.Error:
        return


def update_category_rule_fetch_status(
    platform: str,
    category_id: str,
    fetch_status: str,
    last_fetch_error: str,
    *,
    source_name: str,
) -> dict[str, Any]:
    safe_platform = normalize_rule_platform(platform)
    safe_category_id = normalize_rule_category_id(category_id)
    safe_fetch_status = str(fetch_status or "").strip().lower()
    if safe_fetch_status not in {"success", "failed", "unfetched"}:
        raise HTTPException(status_code=400, detail="Unsupported rule fetch status")

    error_text = "" if safe_fetch_status == "success" else str(last_fetch_error or "").strip()[:500]
    source_text = str(source_name or "software-rule-fetch").strip()[:120] or "software-rule-fetch"
    now_text = datetime.utcnow().isoformat(timespec="seconds")
    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Rule catalog is not configured")

    try:
        with sqlite3.connect(str(db_path)) as connection:
            cursor = connection.execute(
                """
                UPDATE category_rules
                SET fetch_status = ?,
                    last_fetch_error = ?,
                    updated_at = ?
                WHERE platform = ? AND category_id = ?
                """,
                (
                    safe_fetch_status,
                    error_text,
                    now_text,
                    safe_platform,
                    safe_category_id,
                ),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Rule not found")
            connection.commit()
            invalidate_rule_catalog_cache()
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Rule catalog is unavailable") from exc

    return {
        "platform": safe_platform,
        "categoryId": safe_category_id,
        "fetchStatus": safe_fetch_status,
        "lastFetchError": error_text,
        "source": source_text,
        "updatedAt": now_text,
    }


def save_uploaded_rule_page_json(
    platform: str,
    category_id: str,
    root: dict[str, Any],
    *,
    source_name: str,
) -> dict[str, Any]:
    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Rule catalog is not configured")

    imported_node, result = parse_uploaded_rule_page_json(
        platform,
        category_id,
        root,
        source_name=source_name,
    )
    safe_platform = result["platform"]
    safe_category_id = result["categoryId"]
    category_name = result["categoryName"]
    now_text = datetime.utcnow().isoformat(timespec="seconds")
    snapshot_dir = get_rule_page_import_root_path() / safe_platform / safe_category_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{safe_category_id}.json"
    snapshot_path.write_text(json.dumps(root, ensure_ascii=False, indent=2), encoding="utf-8")
    result["snapshotFilePath"] = str(snapshot_path)

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            dictionary_category_name = get_rule_dictionary_category_name(
                connection,
                safe_platform,
                safe_category_id,
            )
            row = connection.execute(
                """
                SELECT category_name, default_rule_json, current_rule_json, has_explicit_package
                FROM category_rules
                WHERE platform = ? AND category_id = ?
                """,
                (safe_platform, safe_category_id),
            ).fetchone()
            current_node: dict[str, Any] = {}
            default_rule_json = ""
            has_explicit_package = 0
            if row is not None:
                current_node = parse_rule_json_payload(row["current_rule_json"]) or parse_rule_json_payload(row["default_rule_json"])
                default_rule_json = row["default_rule_json"] or ""
                has_explicit_package = int(row["has_explicit_package"] or 0)

            category_name = choose_rule_category_name(
                safe_category_id,
                dictionary_category_name,
                category_name,
                row["category_name"] if row is not None else "",
            )

            merged_node = merge_imported_rule_node(current_node, imported_node)
            current_json = json.dumps(merged_node, ensure_ascii=False, indent=2)
            if not default_rule_json:
                default_rule_json = current_json

            connection.execute(
                """
                INSERT INTO category_rules (
                    platform, category_id, category_name, has_explicit_package, is_customized,
                    default_rule_json, current_rule_json, updated_at, fetch_status, last_fetch_error
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, 'success', '')
                ON CONFLICT(platform, category_id) DO UPDATE SET
                    category_name = excluded.category_name,
                    has_explicit_package = category_rules.has_explicit_package,
                    is_customized = 1,
                    default_rule_json = CASE
                        WHEN category_rules.default_rule_json = '' THEN excluded.default_rule_json
                        ELSE category_rules.default_rule_json
                    END,
                    current_rule_json = excluded.current_rule_json,
                    updated_at = excluded.updated_at,
                    fetch_status = 'success',
                    last_fetch_error = ''
                """,
                (
                    safe_platform,
                    safe_category_id,
                    category_name,
                    has_explicit_package,
                    default_rule_json,
                    current_json,
                    now_text,
                ),
            )
            if is_trusted_rule_category_name(category_name, safe_category_id):
                connection.execute(
                    """
                    INSERT INTO category_name_dictionary (
                        platform, category_id, category_name, source, is_verified, first_seen_at, last_seen_at
                    )
                    VALUES (?, ?, ?, 'server_page_import', 1, ?, ?)
                    ON CONFLICT(platform, category_id) DO UPDATE SET
                        category_name = excluded.category_name,
                        source = excluded.source,
                        is_verified = 1,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (safe_platform, safe_category_id, category_name, now_text, now_text),
                )
            connection.commit()
            invalidate_rule_catalog_cache()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Rule catalog is unavailable") from exc

    result["categoryName"] = category_name
    return result


def rewrite_rule_payload_category_name(raw_json: str | None, category_name: str) -> str:
    if not raw_json:
        return ""
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return raw_json or ""
    if not isinstance(payload, dict):
        return raw_json or ""
    payload["categoryName"] = category_name
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_rule_dictionary_placeholder_node(platform: str, category_id: str, category_name: str) -> dict[str, Any]:
    return {
        "platform": platform,
        "categoryId": category_id,
        "categoryName": category_name,
        "keyProp": {},
        "bindProp": {},
        "saleProp": {},
        "package": {
            "packageKey": "",
            "packageName": "平台默认尺码模式",
            "notes": "",
        },
        "notes": "",
        "source": "server-dictionary-import",
    }


def import_rule_category_name_dictionary(
    platform: str,
    items: list[RuleCategoryNameDictionaryItem],
    *,
    source_name: str,
) -> dict[str, Any]:
    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Rule catalog is not configured")

    safe_platform = normalize_rule_platform(platform)
    now_text = datetime.utcnow().isoformat(timespec="seconds")
    source_text = str(source_name or "software-client").strip()[:120] or "software-client"
    total_count = len(items or [])
    imported_count = 0
    skipped_count = 0
    updated_rule_count = 0
    created_rule_count = 0
    samples: list[dict[str, str]] = []

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            for item in items or []:
                try:
                    safe_category_id = normalize_rule_category_id(getattr(item, "category_id", ""))
                except HTTPException:
                    skipped_count += 1
                    continue

                category_name = str(getattr(item, "category_name", "") or "").strip()
                if not is_trusted_rule_category_name(category_name, safe_category_id):
                    skipped_count += 1
                    continue

                connection.execute(
                    """
                    INSERT INTO category_name_dictionary (
                        platform, category_id, category_name, source, is_verified, first_seen_at, last_seen_at
                    )
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(platform, category_id) DO UPDATE SET
                        category_name = excluded.category_name,
                        source = excluded.source,
                        is_verified = 1,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        safe_platform,
                        safe_category_id,
                        category_name,
                        source_text,
                        now_text,
                        now_text,
                    ),
                )

                rule_row = connection.execute(
                    """
                    SELECT default_rule_json, current_rule_json
                    FROM category_rules
                    WHERE platform = ? AND category_id = ?
                    """,
                    (safe_platform, safe_category_id),
                ).fetchone()
                if rule_row is not None:
                    connection.execute(
                        """
                        UPDATE category_rules
                        SET category_name = ?,
                            default_rule_json = ?,
                            current_rule_json = ?,
                            updated_at = ?
                        WHERE platform = ? AND category_id = ?
                        """,
                        (
                            category_name,
                            rewrite_rule_payload_category_name(rule_row["default_rule_json"], category_name),
                            rewrite_rule_payload_category_name(rule_row["current_rule_json"], category_name),
                            now_text,
                            safe_platform,
                            safe_category_id,
                        ),
                    )
                    updated_rule_count += 1
                else:
                    placeholder_node = build_rule_dictionary_placeholder_node(
                        safe_platform,
                        safe_category_id,
                        category_name,
                    )
                    placeholder_json = json.dumps(placeholder_node, ensure_ascii=False, indent=2)
                    connection.execute(
                        """
                        INSERT INTO category_rules (
                            platform, category_id, category_name, has_explicit_package, is_customized,
                            default_rule_json, current_rule_json, updated_at, fetch_status, last_fetch_error
                        )
                        VALUES (?, ?, ?, 0, 0, ?, ?, ?, 'unfetched', '')
                        """,
                        (
                            safe_platform,
                            safe_category_id,
                            category_name,
                            placeholder_json,
                            placeholder_json,
                            now_text,
                        ),
                    )
                    created_rule_count += 1

                imported_count += 1
                if len(samples) < 10:
                    samples.append(
                        {
                            "categoryId": safe_category_id,
                            "categoryName": category_name,
                        }
                    )

            connection.commit()
            invalidate_rule_catalog_cache()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Rule catalog is unavailable") from exc

    return {
        "platform": safe_platform,
        "totalCount": total_count,
        "importedCount": imported_count,
        "skippedCount": skipped_count,
        "updatedRuleCount": updated_rule_count,
        "createdRuleCount": created_rule_count,
        "samples": samples,
    }


def load_latest_rule_page_snapshot_payload(platform: str, category_id: str) -> dict[str, Any] | None:
    safe_platform = normalize_rule_platform(platform)
    safe_category_id = normalize_rule_category_id(category_id)
    snapshot_dir = get_rule_page_import_root_path() / safe_platform / safe_category_id
    if not snapshot_dir.exists() or not snapshot_dir.is_dir():
        return None

    candidates = sorted(
        (path for path in snapshot_dir.iterdir() if path.is_file() and path.suffix.lower() in {".json", ".txt"}),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None

    latest = candidates[0]
    try:
        content = latest.read_text(encoding="utf-8")
    except OSError:
        return None

    return {
        "fileName": latest.name,
        "size": latest.stat().st_size,
        "updatedAt": datetime.utcfromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds"),
        "content": content,
    }


def can_view_full_rule_snapshot(user: AdminUser | None) -> bool:
    if user is None:
        return False
    return ROLE_LEVELS.get(user.role, 0) >= ROLE_LEVELS["superadmin"]


def load_category_rule_payload(platform: str, category_id: str, *, include_snapshot: bool = False) -> dict[str, Any]:
    safe_platform = normalize_rule_platform(platform)
    safe_category_id = normalize_rule_category_id(category_id)
    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Rule catalog is not configured")

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT cr.platform, cr.category_id, cr.category_name, cr.current_rule_json, cr.default_rule_json,
                       cr.updated_at, cr.fetch_status, cr.last_fetch_error,
                       d.category_name AS dictionary_category_name
                FROM category_rules cr
                LEFT JOIN category_name_dictionary d
                    ON d.platform = cr.platform AND d.category_id = cr.category_id
                WHERE cr.platform = ? AND cr.category_id = ?
                """,
                (safe_platform, safe_category_id),
            ).fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Rule catalog is unavailable") from exc

    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    fetch_status = str(row["fetch_status"] or "").strip().lower()
    if fetch_status and fetch_status != "success":
        detail = str(row["last_fetch_error"] or "").strip() or "Rule has not been fetched successfully"
        raise HTTPException(status_code=409, detail=detail)

    rule = parse_rule_json_payload(row["current_rule_json"]) or parse_rule_json_payload(row["default_rule_json"])
    if not rule_payload_has_effective_fields(rule):
        raise HTTPException(status_code=404, detail="Rule has no effective server data")

    rule["platform"] = safe_platform
    rule["categoryId"] = safe_category_id
    category_name = choose_rule_category_name(
        safe_category_id,
        row["dictionary_category_name"],
        row["category_name"],
        rule.get("categoryName"),
    )
    rule["categoryName"] = category_name

    package_payload = rule.get("package")
    if not isinstance(package_payload, dict):
        package_payload = {}

    payload = {
        "platform": safe_platform,
        "category_id": safe_category_id,
        "category_name": category_name,
        "updated_at": row["updated_at"],
        "rule": rule,
        "package": package_payload,
    }
    if include_snapshot:
        snapshot_payload = load_latest_rule_page_snapshot_payload(safe_platform, safe_category_id)
        if snapshot_payload is not None:
            payload["snapshot"] = snapshot_payload
    return payload


AUTO_RULE_PACKAGE_PATCH_BOOL_KEYS = {
    "requireVerticalGuideImage",
    "requireMultiDiscountPromotion",
    "requireSkuCombineContent",
    "requireSkuQuality",
    "requireBarcode",
}


def normalize_auto_rule_package_patch(raw_patch: dict[str, Any]) -> dict[str, bool]:
    if not isinstance(raw_patch, dict):
        return {}

    normalized: dict[str, bool] = {}
    for key in sorted(AUTO_RULE_PACKAGE_PATCH_BOOL_KEYS):
        if get_rule_bool(raw_patch.get(key)):
            normalized[key] = True
    return normalized


def patch_category_rule_package(
    platform: str,
    category_id: str,
    package_patch: dict[str, Any],
    *,
    source_name: str,
    reason: str = "",
) -> dict[str, Any]:
    safe_platform = normalize_rule_platform(platform)
    safe_category_id = normalize_rule_category_id(category_id)
    if not safe_platform or not safe_category_id:
        raise HTTPException(status_code=400, detail="Invalid platform or category_id")

    normalized_patch = normalize_auto_rule_package_patch(package_patch)
    if not normalized_patch:
        raise HTTPException(status_code=400, detail="No supported rule fields to patch")

    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Rule catalog is not configured")

    updated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT platform, category_id, category_name, current_rule_json, default_rule_json,
                       updated_at, fetch_status, last_fetch_error
                FROM category_rules
                WHERE platform = ? AND category_id = ?
                """,
                (safe_platform, safe_category_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Rule not found")

            fetch_status = str(row["fetch_status"] or "").strip().lower()
            if fetch_status and fetch_status != "success":
                detail = str(row["last_fetch_error"] or "").strip() or "Rule has not been fetched successfully"
                raise HTTPException(status_code=409, detail=detail)

            rule = parse_rule_json_payload(row["current_rule_json"]) or parse_rule_json_payload(row["default_rule_json"])
            if not isinstance(rule, dict):
                rule = {}

            rule["platform"] = safe_platform
            rule["categoryId"] = safe_category_id
            rule["categoryName"] = choose_rule_category_name(
                safe_category_id,
                row["category_name"],
                rule.get("categoryName"),
            )

            package_payload = rule.get("package")
            if not isinstance(package_payload, dict):
                package_payload = {}

            changed_keys: list[str] = []
            for key, value in normalized_patch.items():
                if package_payload.get(key) is not True:
                    changed_keys.append(key)
                package_payload[key] = value
            rule["package"] = package_payload

            auto_learned = rule.get("_autoLearnedRules")
            if not isinstance(auto_learned, dict):
                auto_learned = {}
            for key in normalized_patch:
                auto_learned[key] = {
                    "source": str(source_name or "software-auto-rule-learn").strip()[:120],
                    "reason": str(reason or "").strip()[:300],
                    "updatedAt": updated_at,
                }
            rule["_autoLearnedRules"] = auto_learned

            if changed_keys:
                connection.execute(
                    """
                    UPDATE category_rules
                    SET current_rule_json = ?,
                        is_customized = 1,
                        updated_at = ?
                    WHERE platform = ? AND category_id = ?
                    """,
                    (
                        json.dumps(rule, ensure_ascii=False, separators=(",", ":")),
                        updated_at,
                        safe_platform,
                        safe_category_id,
                    ),
                )
                connection.commit()
                invalidate_rule_catalog_cache()

    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Rule catalog is unavailable") from exc

    return {
        "platform": safe_platform,
        "categoryId": safe_category_id,
        "changedKeys": changed_keys,
        "packagePatch": normalized_patch,
        "updatedAt": updated_at if changed_keys else "",
    }


def load_category_rule_catalog_payload() -> dict[str, Any]:
    db_path = get_rule_catalog_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Rule catalog is not configured")

    cached_payload = get_cached_rule_catalog_payload(db_path)
    if cached_payload is not None:
        return cached_payload

    try:
        with sqlite3.connect(str(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT cr.platform, cr.category_id, cr.category_name, cr.has_explicit_package,
                       cr.is_customized, cr.current_rule_json, cr.default_rule_json,
                       cr.updated_at, cr.fetch_status, cr.last_fetch_error,
                       d.category_name AS dictionary_category_name
                FROM category_rules cr
                LEFT JOIN category_name_dictionary d
                    ON d.platform = cr.platform AND d.category_id = cr.category_id
                ORDER BY
                    CASE lower(cr.platform) WHEN 'taobao' THEN 0 WHEN 'tmall' THEN 1 ELSE 2 END,
                    CAST(cr.category_id AS INTEGER),
                    cr.category_id
                """
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Rule catalog is unavailable") from exc

    categories: list[dict[str, Any]] = []
    customized_count = 0
    for row in rows:
        safe_platform = normalize_rule_platform(row["platform"])
        safe_category_id = normalize_rule_category_id(row["category_id"])
        rule = parse_rule_json_payload(row["current_rule_json"]) or parse_rule_json_payload(row["default_rule_json"])
        if not isinstance(rule, dict):
            rule = {}
        rule["platform"] = safe_platform
        rule["categoryId"] = safe_category_id
        rule["source"] = "server-rule-api"
        category_name = choose_rule_category_name(
            safe_category_id,
            row["dictionary_category_name"],
            row["category_name"],
            rule.get("categoryName"),
        )
        rule["categoryName"] = category_name

        is_customized = bool(row["is_customized"])
        if is_customized:
            customized_count += 1
        has_explicit_package = bool(row["has_explicit_package"])
        summary = build_rule_catalog_list_summary(rule, has_explicit_package)

        categories.append(
            {
                "platform": safe_platform,
                "category_id": safe_category_id,
                "category_name": category_name,
                "has_explicit_package": has_explicit_package,
                "is_customized": is_customized,
                "fetch_status": str(row["fetch_status"] or "").strip(),
                "last_fetch_error": str(row["last_fetch_error"] or "").strip(),
                "updated_at": row["updated_at"],
                "summary": summary,
            }
        )

    payload = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "database_path": str(db_path),
        "record_count": len(categories),
        "customized_count": customized_count,
        "categories": categories,
    }
    set_cached_rule_catalog_payload(db_path, payload)
    return payload


def sync_software_license_payload(user: AdminUser, license_payload: dict[str, Any]) -> None:
    status_value = str(license_payload.get("status") or "").strip().lower()
    user.software_license_key = str(license_payload.get("license_key") or user.software_license_key or "").strip()
    user.software_plan_name = str(license_payload.get("plan_name") or "").strip() or None
    user.software_license_status = status_value or None
    user.software_activated_at = parse_software_license_datetime(license_payload.get("activated_at"))
    user.software_expire_at = parse_software_license_datetime(license_payload.get("expire_at"))
    user.software_last_validated_at = datetime.utcnow()


def refresh_software_license_for_login(
    user: AdminUser,
    payload: SoftwareAuthDevicePayload,
    db: Session,
) -> None:
    if not user.software_license_key:
        return

    response_payload = request_public_license_server(
        "POST",
        "/api/license/validate",
        json_payload={
            "license_key": user.software_license_key,
            "device_id": payload.device_id,
            "device_name": payload.device_name or "",
            "platform": payload.platform,
            "app_version": payload.app_version or "",
        },
    )
    license_payload = response_payload.get("license")
    if not isinstance(license_payload, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected license payload")

    sync_software_license_payload(user, license_payload)
    commit_session(db, default_detail="Failed to refresh software license")
    db.refresh(user)
    if not is_software_user_activated(user):
        raise HTTPException(status_code=403, detail="账号授权已过期或不可用")


def request_public_license_server(
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any],
) -> dict[str, Any]:
    url = f"{LICENSE_SERVER_BASE_URL}{path}"

    try:
        with httpx.Client(timeout=LICENSE_SERVER_TIMEOUT_SECONDS) as client:
            response = client.request(method, url, json=json_payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="License server is unavailable") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="License server returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected payload")
    if response.status_code >= 400:
        detail = str(payload.get("message") or payload.get("detail") or "License server request failed")
        raise HTTPException(status_code=response.status_code, detail=detail)
    if payload.get("status") == "error":
        detail = str(payload.get("message") or "License server request failed")
        raise HTTPException(status_code=400, detail=detail)

    return payload


def activate_software_license_for_user(
    user: AdminUser,
    payload: SoftwareActivateRequest,
    db: Session,
) -> dict[str, Any]:
    existing_user = db.scalar(
        select(AdminUser).where(
            AdminUser.software_license_key == payload.license_key,
            AdminUser.id != user.id,
        ),
    )
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="卡密已绑定其他账号")

    response_payload = request_public_license_server(
        "POST",
        "/api/license/activate",
        json_payload={
            "license_key": payload.license_key,
            "device_id": payload.device_id,
            "device_name": payload.device_name or "",
            "platform": payload.platform,
            "app_version": payload.app_version or "",
        },
    )
    license_payload = response_payload.get("license")
    if not isinstance(license_payload, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected license payload")

    sync_software_license_payload(user, license_payload)
    commit_session(db, default_detail="Failed to bind software license")
    db.refresh(user)
    return license_payload


def get_license_server_admin_token() -> str:
    token = os.getenv("LICENSE_ADMIN_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="License server integration is not configured")
    return token


def request_license_server(
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{LICENSE_SERVER_BASE_URL}{path}"

    try:
        with httpx.Client(timeout=LICENSE_SERVER_TIMEOUT_SECONDS) as client:
            response = client.request(
                method,
                url,
                json=json_payload,
                headers={"X-Admin-Token": get_license_server_admin_token()},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="License server is unavailable") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="License server returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected payload")

    if response.status_code == 401:
        raise HTTPException(status_code=502, detail="License server admin token is invalid")
    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="License server request failed")
    if response.status_code >= 400:
        detail = str(payload.get("message") or payload.get("detail") or "License server request failed")
        raise HTTPException(status_code=response.status_code, detail=detail)
    if payload.get("status") == "error":
        detail = str(payload.get("message") or "License server request failed")
        raise HTTPException(status_code=400, detail=detail)

    return payload


def proxy_public_license_server_request(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    content_type: str | None = None,
) -> Response:
    url = f"{LICENSE_SERVER_BASE_URL}{path}"
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = content_type

    try:
        with httpx.Client(timeout=LICENSE_SERVER_TIMEOUT_SECONDS) as client:
            upstream_response = client.request(
                method,
                url,
                content=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="License server is unavailable") from exc

    upstream_content_type = upstream_response.headers.get("content-type", "application/json")
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_content_type.split(";")[0].strip() or "application/json",
    )


def normalize_license_feature_flags(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    raise HTTPException(status_code=400, detail="feature_flags must be an object")


def normalize_license_admin_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    plan_name = str(payload.get("plan_name") or "").strip()
    if not plan_name:
        raise HTTPException(status_code=400, detail="plan_name is required")

    try:
        count = int(payload.get("count", 1))
        duration_days = int(payload.get("duration_days", 30))
        max_devices = int(payload.get("max_devices", 1))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="count, duration_days and max_devices must be integers") from exc

    if count < 1 or count > 100:
        raise HTTPException(status_code=400, detail="count must be between 1 and 100")
    if duration_days < 0 or duration_days > 3650:
        raise HTTPException(status_code=400, detail="duration_days must be between 0 and 3650")
    if max_devices < 1 or max_devices > 1000:
        raise HTTPException(status_code=400, detail="max_devices must be between 1 and 1000")

    note = str(payload.get("note") or "").strip()
    return {
        "plan_name": plan_name,
        "count": count,
        "duration_days": duration_days,
        "max_devices": max_devices,
        "note": note,
        "feature_flags": normalize_license_feature_flags(payload.get("feature_flags")),
    }


def normalize_license_admin_status_payload(payload: dict[str, Any]) -> dict[str, str]:
    status_value = str(payload.get("status") or "").strip().lower()
    if status_value not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="status must be active or disabled")
    return {"status": status_value}


def normalize_license_admin_unbind_payload(payload: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}

    device_id = str(payload.get("device_id") or "").strip()
    return {"device_id": device_id} if device_id else {}
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


def get_license_record_or_404(db: Session, record_id: int) -> LicenseRecord:
    db_record = db.get(LicenseRecord, record_id)
    if db_record is None:
        raise HTTPException(status_code=404, detail="License record not found")
    return db_record


def get_account_usage_record_or_404(db: Session, record_id: int) -> AccountUsageRecord:
    db_record = db.get(AccountUsageRecord, record_id)
    if db_record is None:
        raise HTTPException(status_code=404, detail="Account usage record not found")
    return db_record


def get_mobile_device_record_or_404(db: Session, record_id: int) -> MobileDeviceRecord:
    db_record = db.get(MobileDeviceRecord, record_id)
    if db_record is None:
        raise HTTPException(status_code=404, detail="Mobile device record not found")
    return db_record


def get_company_expense_or_404(db: Session, record_id: int) -> CompanyExpenseRecord:
    record = db.get(CompanyExpenseRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="公司消费记录不存在")
    return record


async def save_company_expense_attachment(record: CompanyExpenseRecord, upload: UploadFile) -> None:
    original_name = Path(upload.filename or "expense-proof").name
    suffix = Path(original_name).suffix.lower()
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="仅支持 JPG、PNG、WEBP、GIF 或 PDF 凭证")

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="凭证文件不能为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="凭证文件不能超过 20MB")

    filename = f"expense_{record.id}_{secrets.token_hex(8)}{suffix}"
    save_path = COMPANY_EXPENSE_UPLOAD_DIR / filename
    save_path.write_bytes(content)
    record.attachment_path = str(save_path)
    record.attachment_name = original_name


def get_personal_expense_or_404(
    db: Session,
    record_id: int,
    current_user: AdminUser,
) -> PersonalExpenseRecord:
    record = db.get(PersonalExpenseRecord, record_id)
    if record is None or record.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="?????????")
    return record


async def save_personal_expense_attachment(record: PersonalExpenseRecord, upload: UploadFile) -> None:
    original_name = Path(upload.filename or "personal-expense-proof").name
    suffix = Path(original_name).suffix.lower()
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="??? JPG?PNG?WEBP?GIF ? PDF ??")
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="????????")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="???????? 20MB")
    filename = f"personal_expense_{record.id}_{secrets.token_hex(8)}{suffix}"
    save_path = PERSONAL_EXPENSE_UPLOAD_DIR / filename
    save_path.write_bytes(content)
    record.attachment_path = str(save_path)
    record.attachment_name = original_name


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


def get_saved_link_or_404(db: Session, link_id: int) -> SavedLink:
    db_record = db.get(SavedLink, link_id)
    if db_record is None:
        raise HTTPException(status_code=404, detail="Saved link not found")
    return db_record


def ensure_saved_link_write_access(record: SavedLink, current_user: AdminUser) -> None:
    if current_user.role == "superadmin":
        return
    if record.author_user_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="Only the publisher or a superadmin can modify this post")


def get_saved_link_images(record: SavedLink) -> list[dict[str, str | None]]:
    parsed_images = []
    for item in parse_json_array(record.images_json):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        storage_name = Path(path).name
        parsed_images.append(
            {
                "name": str(item.get("name") or "").strip() or None,
                "url": f"/saved-links/{record.id}/images/{storage_name}",
                "path": path,
                "storage_name": storage_name,
            },
        )

    if parsed_images:
        return parsed_images

    if record.image_path:
        storage_name = Path(record.image_path).name
        return [
            {
                "name": record.image_name,
                "url": f"/saved-links/{record.id}/images/{storage_name}",
                "path": record.image_path,
                "storage_name": storage_name,
            },
        ]

    return []


def set_saved_link_images(record: SavedLink, images: list[dict[str, str | None]]) -> None:
    normalized_images: list[dict[str, str | None]] = []
    for image in images:
        image_path = str(image.get("path") or "").strip()
        if not image_path:
            continue

        image_name = str(image.get("name") or "").strip() or None
        normalized_images.append(
            {
                "path": image_path,
                "name": image_name,
            },
        )

    record.images_json = json.dumps(normalized_images, ensure_ascii=False)
    if normalized_images:
        first_image = normalized_images[0]
        record.image_path = str(first_image["path"])
        record.image_name = str(first_image.get("name") or "").strip() or None
        return

    record.image_path = None
    record.image_name = None


def find_saved_link_image(record: SavedLink, image_name: str) -> tuple[int, dict[str, str | None]] | None:
    normalized_name = image_name.strip()
    if not normalized_name:
        return None

    for index, image in enumerate(get_saved_link_images(record)):
        if str(image.get("storage_name") or "").strip() == normalized_name:
            return index, image

    return None


def delete_saved_link_storage_file(image_path: str | None) -> None:
    normalized_path = str(image_path or "").strip()
    if not normalized_path:
        return

    image_file = UPLOADS_DIR / normalized_path
    if image_file.exists():
        image_file.unlink()


async def store_saved_link_image(record: SavedLink, upload: UploadFile) -> dict[str, str | None]:
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

    filename = f"saved_link_{record.id}_{secrets.token_hex(8)}{suffix}"
    save_path = LINK_UPLOAD_DIR / filename
    save_path.write_bytes(content)
    return {
        "path": f"links/{filename}",
        "name": upload.filename,
    }


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
        raise HTTPException(status_code=400, detail="鍥剧墖 MIME 绫诲瀷鏃犳晥")

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="鍥剧墖鏂囦欢涓虹┖")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="鍥剧墖澶у皬涓嶈兘瓒呰繃 15MB")

    clear_license_image(record)

    filename = f"license_{record.id}_{secrets.token_hex(8)}{suffix}"
    save_path = LICENSE_UPLOAD_DIR / filename
    save_path.write_bytes(content)

    record.image_path = f"licenses/{filename}"
    record.image_name = upload.filename


def delete_admin_avatar_file(user: AdminUser) -> None:
    if not user.avatar_path:
        return

    image_file = UPLOADS_DIR / user.avatar_path
    if image_file.exists():
        image_file.unlink()


def clear_admin_avatar(user: AdminUser) -> None:
    delete_admin_avatar_file(user)
    user.avatar_path = None
    user.avatar_name = None


async def save_admin_avatar(user: AdminUser, upload: UploadFile) -> None:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="璇烽€夋嫨澶村儚鏂囦欢")

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="浠呮敮鎸?jpg銆乸ng銆亀ebp 鍥剧墖")
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="澶村儚 MIME 绫诲瀷鏃犳晥")

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="澶村儚鏂囦欢涓虹┖")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="澶村儚澶у皬涓嶈兘瓒呰繃 5MB")

    clear_admin_avatar(user)

    filename = f"avatar_{user.id}_{secrets.token_hex(8)}{suffix}"
    save_path = AVATAR_UPLOAD_DIR / filename
    save_path.write_bytes(content)

    user.avatar_path = f"avatars/{filename}"
    user.avatar_name = upload.filename


def delete_saved_link_image_file(record: SavedLink) -> None:
    for image in get_saved_link_images(record):
        delete_saved_link_storage_file(str(image.get("path") or ""))

    set_saved_link_images(record, [])


async def save_saved_link_images(record: SavedLink, uploads: list[UploadFile]) -> None:
    valid_uploads = [upload for upload in uploads if upload is not None]
    if not valid_uploads:
        raise HTTPException(status_code=400, detail="请选择至少一张图片")
    if len(valid_uploads) > 9:
        raise HTTPException(status_code=400, detail="最多上传 9 张图片")

    delete_saved_link_image_file(record)

    stored_images: list[dict[str, str | None]] = []
    for upload in valid_uploads:
        stored_images.append(await store_saved_link_image(record, upload))

    set_saved_link_images(record, stored_images)


async def append_saved_link_images(record: SavedLink, uploads: list[UploadFile]) -> None:
    valid_uploads = [upload for upload in uploads if upload is not None]
    if not valid_uploads:
        raise HTTPException(status_code=400, detail="请选择至少一张图片")

    existing_images = get_saved_link_images(record)
    if len(existing_images) + len(valid_uploads) > 9:
        raise HTTPException(status_code=400, detail="最多上传 9 张图片")

    stored_images = [*existing_images]
    for upload in valid_uploads:
        stored_images.append(await store_saved_link_image(record, upload))

    set_saved_link_images(record, stored_images)


async def replace_saved_link_image(record: SavedLink, image_name: str, upload: UploadFile) -> None:
    matched_image = find_saved_link_image(record, image_name)
    if matched_image is None:
        raise HTTPException(status_code=404, detail="Saved-link image not found")

    image_index, image_entry = matched_image
    stored_images = get_saved_link_images(record)
    replacement_image = await store_saved_link_image(record, upload)
    delete_saved_link_storage_file(str(image_entry.get("path") or ""))
    stored_images[image_index] = replacement_image
    set_saved_link_images(record, stored_images)


def remove_saved_link_image(record: SavedLink, image_name: str) -> None:
    matched_image = find_saved_link_image(record, image_name)
    if matched_image is None:
        raise HTTPException(status_code=404, detail="Saved-link image not found")

    image_index, image_entry = matched_image
    stored_images = get_saved_link_images(record)
    delete_saved_link_storage_file(str(image_entry.get("path") or ""))
    stored_images.pop(image_index)
    set_saved_link_images(record, stored_images)


def get_admin_user_or_404(db: Session, user_id: int) -> AdminUser:
    db_user = db.get(AdminUser, user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Admin user not found")
    return db_user


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


def create_session_cookie(
    user: AdminUser,
    response: Response,
    db: Session,
    *,
    request: Request | None = None,
) -> AdminSession:
    duration_hours = int(get_system_settings(db)["session_duration_hours"])
    expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
    raw_token = secrets.token_urlsafe(32)
    admin_session = AdminSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        ip_address=get_client_ip(request) if request is not None else "unknown",
        user_agent=get_client_user_agent(request) if request is not None else "unknown",
        expires_at=expires_at,
    )

    db.add(admin_session)
    commit_session(db, default_detail="Failed to create login session")
    db.refresh(admin_session)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=duration_hours * 60 * 60,
        httponly=True,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
        path="/",
    )
    return admin_session


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def resolve_current_session(session_token: str | None, db: Session, *, required: bool) -> AdminSession | None:
    if not session_token:
        if required:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return None

    db_session = get_admin_session_by_token(db, session_token)
    if db_session is None:
        if required:
            raise HTTPException(status_code=401, detail="Session revoked. Please sign in again.")
        return None

    if db_session.expires_at <= datetime.utcnow():
        db.delete(db_session)
        db.commit()
        if required:
            raise HTTPException(status_code=401, detail="Session expired")
        return None

    return db_session


def resolve_current_user(session_token: str | None, db: Session, *, required: bool) -> AdminUser | None:
    db_session = resolve_current_session(session_token, db, required=required)
    if db_session is None:
        return None

    user = db.get(AdminUser, db_session.user_id)
    if user is None or not user.is_active:
        db.delete(db_session)
        db.commit()
        if required:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return None

    return user


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_expense_shortcut_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(EXPENSE_SHORTCUT_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="\u7f3a\u5c11\u5feb\u6377\u8bb0\u8d26\u4ee4\u724c")
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=401, detail="\u5feb\u6377\u8bb0\u8d26\u4ee4\u724c\u65e0\u6548")
    token_hash = hash_expense_shortcut_token(token)
    settings_rows = db.scalars(
        select(AppSetting).where(AppSetting.key.like(f"{EXPENSE_SHORTCUT_SETTING_PREFIX}%"))
    ).all()
    for setting in settings_rows:
        try:
            stored = json.loads(setting.value)
        except (TypeError, ValueError):
            continue
        stored_hash = str(stored.get("token_hash") or "") if isinstance(stored, dict) else ""
        if not stored_hash or not hmac.compare_digest(stored_hash, token_hash):
            continue
        try:
            user_id = int(setting.key.removeprefix(EXPENSE_SHORTCUT_SETTING_PREFIX))
        except ValueError:
            break
        user = db.get(AdminUser, user_id)
        if user is None or not user.is_active:
            break
        return user
    raise HTTPException(status_code=401, detail="\u5feb\u6377\u8bb0\u8d26\u4ee4\u724c\u65e0\u6548\u6216\u5df2\u64a4\u9500")


def get_current_software_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    return resolve_current_software_user(credentials, db, require_activated=True)


def get_current_software_user_allow_inactive(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    return resolve_current_software_user(credentials, db, require_activated=False)


def get_current_rule_api_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    return resolve_current_rule_api_user(credentials, db, require_maintainer=False)


def get_current_rule_catalog_maintainer(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    return resolve_current_rule_api_user(credentials, db, require_maintainer=True)


def get_current_product_cache_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    return resolve_current_product_cache_user(credentials, db)


def get_current_publish_failure_report_writer(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    return resolve_current_product_cache_user(credentials, db)


def get_current_publish_failure_report_reader(
    credentials: HTTPAuthorizationCredentials | None = Depends(SOFTWARE_AUTH_SCHEME),
    db: Session = Depends(get_db),
) -> AdminUser:
    user = resolve_current_product_cache_user(credentials, db)
    if user.role == "software":
        if user.username in PUBLISH_FAILURE_REPORT_READER_USERNAMES:
            return user
        raise HTTPException(status_code=403, detail="Only debug accounts can view publish failure reports")
    if ROLE_LEVELS.get(user.role, 0) >= ROLE_LEVELS["viewer"]:
        return user
    raise HTTPException(status_code=403, detail="Permission denied")


def get_current_user(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AdminUser:
    user = resolve_current_user(session_token, db, required=True)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if user.role != "superadmin":
        permission_module = next(
            (module for prefix, module in PERMISSION_PATH_PREFIXES if request.url.path.startswith(prefix)),
            None,
        )
        if permission_module:
            permissions = resolve_admin_permissions(user)
            actual_level = PERMISSION_LEVELS.get(permissions.get(permission_module, "none"), 0)
            required_level = 1 if request.method in {"GET", "HEAD", "OPTIONS"} else 2
            if actual_level < required_level:
                raise HTTPException(status_code=403, detail="当前账号没有此模块的操作权限")

    return user


def get_current_user_optional(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AdminUser | None:
    return resolve_current_user(session_token, db, required=False)


def get_current_admin_session(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AdminSession:
    return resolve_current_session(session_token, db, required=True)


def get_current_admin_session_optional(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AdminSession | None:
    return resolve_current_session(session_token, db, required=False)


def require_internal_sync_token(
    internal_sync_token: str | None = Header(default=None, alias=INTERNAL_SYNC_TOKEN_HEADER),
) -> None:
    expected_token = settings.dingtalk_profit_sync_token
    if not expected_token:
        raise HTTPException(status_code=503, detail="Internal sync token is not configured")

    if not internal_sync_token or not hmac.compare_digest(internal_sync_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid internal sync token")


def require_sycm_upload_token(
    upload_token: str | None = Header(default=None, alias=SYCM_UPLOAD_TOKEN_HEADER),
) -> None:
    expected_token = os.getenv("SYCM_UPLOAD_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail="SYCM upload token is not configured")
    if not upload_token or not hmac.compare_digest(upload_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid SYCM upload token")


def ensure_sycm_data_db() -> None:
    SYCM_DATA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(
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
                UNIQUE(shop_id, collected_at)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS ix_sycm_shop_time ON sycm_snapshots(shop_id, collected_at DESC)")
        snapshot_columns = {row[1] for row in connection.execute("PRAGMA table_info(sycm_snapshots)")}
        if "period" not in snapshot_columns:
            connection.execute("ALTER TABLE sycm_snapshots ADD COLUMN period TEXT NOT NULL DEFAULT 'today'")
        if "date_start" not in snapshot_columns:
            connection.execute("ALTER TABLE sycm_snapshots ADD COLUMN date_start TEXT NOT NULL DEFAULT ''")
        if "date_end" not in snapshot_columns:
            connection.execute("ALTER TABLE sycm_snapshots ADD COLUMN date_end TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_sycm_period_shop_time ON sycm_snapshots(period, shop_id, collected_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sycm_shop_aliases (
                account_id TEXT PRIMARY KEY,
                canonical_shop_id TEXT NOT NULL,
                shop_name TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_sycm_alias_canonical ON sycm_shop_aliases(canonical_shop_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sycm_sync_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                requested_by INTEGER,
                requested_at TEXT NOT NULL,
                claimed_at TEXT,
                completed_at TEXT,
                error TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_sycm_sync_status ON sycm_sync_requests(status, requested_at)"
        )
        sync_columns = {row[1] for row in connection.execute("PRAGMA table_info(sycm_sync_requests)")}
        if "results_json" not in sync_columns:
            connection.execute("ALTER TABLE sycm_sync_requests ADD COLUMN results_json TEXT NOT NULL DEFAULT '[]'")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sycm_collector_devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sycm_shop_owners (
                shop_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS ix_sycm_owner_device ON sycm_shop_owners(device_id)")
        connection.commit()


def sycm_metric(overview: dict[str, Any], name: str) -> float | None:
    value = overview.get(name)
    if not isinstance(value, dict):
        return None
    number = value.get("value")
    return float(number) if isinstance(number, (int, float)) else None


def require_role(min_role: str) -> Callable[[AdminUser], AdminUser]:
    def dependency(request: Request, current_user: AdminUser = Depends(get_current_user)) -> AdminUser:
        current_level = ROLE_LEVELS.get(current_user.role, 0)
        required_level = ROLE_LEVELS[min_role]
        if min_role == "editor":
            permission_module = next(
                (module for prefix, module in PERMISSION_PATH_PREFIXES if request.url.path.startswith(prefix)),
                None,
            )
            if permission_module and resolve_admin_permissions(current_user).get(permission_module) == "write":
                return current_user
        if current_level < required_level:
            raise HTTPException(status_code=403, detail="Permission denied")
        return current_user

    return dependency


@asynccontextmanager
async def lifespan(_: FastAPI):
    LICENSE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    LINK_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PEER_SHOP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    WAREHOUSE_PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    COMPANY_EXPENSE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PERSONAL_EXPENSE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_product_parse_cache_db()
    ensure_publish_failure_report_db()
    ensure_sycm_data_db()
    saved_link_push_stop_event = asyncio.Event()
    saved_link_push_task: asyncio.Task[None] | None = None
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
        migrate_database()
        Base.metadata.create_all(bind=engine)
    initialize_field_configuration()
    migrate_account_usage_account_name_storage()
    migrate_account_usage_password_storage()
    saved_link_push_task = asyncio.create_task(saved_link_push_worker(saved_link_push_stop_event))
    try:
        yield
    finally:
        saved_link_push_stop_event.set()
        if saved_link_push_task is not None:
            saved_link_push_task.cancel()
            with suppress(asyncio.CancelledError):
                await saved_link_push_task


app = FastAPI(
    title=settings.app_name,
    description="Backend service for managing shop records",
    version="4.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    create_health_router(
        engine=engine,
        frontend_dist_dir=FRONTEND_DIST_DIR,
        app_dist_dir=APP_FRONTEND_DIST_DIR,
    ),
)
app.include_router(
    create_server_status_router(
        engine=engine,
        base_dir=BASE_DIR,
        require_superadmin=require_role("superadmin"),
    ),
)
app.include_router(
    create_warehouse_router(
        get_db=get_db,
        require_role=require_role,
        write_audit_log=write_audit_log,
        commit_session=commit_session,
        timezone=TASK_BOOKKEEPING_TIMEZONE,
        uploads_dir=UPLOADS_DIR,
        product_upload_dir=WAREHOUSE_PRODUCT_UPLOAD_DIR,
    ),
)
app.include_router(
    create_peer_shop_router(
        get_db=get_db,
        require_role=require_role,
        commit_session=commit_session,
        write_audit_log=write_audit_log,
        parse_json_object=parse_json_object,
        dump_json_object=dump_json_object,
        resolve_upload_file=resolve_upload_file,
        image_file_response=image_file_response,
        create_sqlite_backup=create_sqlite_backup,
        uploads_dir=UPLOADS_DIR,
        peer_shop_upload_dir=PEER_SHOP_UPLOAD_DIR,
    ),
)


def resolve_canonical_shop_id(connection: sqlite3.Connection, account_id: str) -> str:
    """把千牛账号 ID（unb）解析成规范店铺 ID。

    unb 是登录账号 ID，同一家店的主账号和子账号各有一个，直接当店铺主键会造成
    同店重复。sycm_shop_aliases 记录 account_id -> canonical_shop_id 的映射；
    未登记的账号返回自身，保证老客户端继续上传旧 ID 也能正常工作。
    """
    if not account_id:
        return account_id
    try:
        row = connection.execute(
            "SELECT canonical_shop_id FROM sycm_shop_aliases WHERE account_id=?",
            (account_id,),
        ).fetchone()
    except sqlite3.Error:
        return account_id
    if row is None:
        return account_id
    canonical = str(row[0] if not isinstance(row, sqlite3.Row) else row["canonical_shop_id"] or "").strip()
    return canonical or account_id


def resolve_canonical_shop_ids(connection: sqlite3.Connection, account_ids: list[str]) -> dict[str, str]:
    """批量解析，返回 account_id -> canonical_shop_id（未登记的映射到自身）。"""
    mapping = {account_id: account_id for account_id in account_ids}
    if not account_ids:
        return mapping
    placeholders = ",".join("?" for _ in account_ids)
    try:
        rows = connection.execute(
            f"SELECT account_id, canonical_shop_id FROM sycm_shop_aliases WHERE account_id IN ({placeholders})",
            tuple(account_ids),
        ).fetchall()
    except sqlite3.Error:
        return mapping
    for row in rows:
        account_id = str(row[0] if not isinstance(row, sqlite3.Row) else row["account_id"])
        canonical = str(row[1] if not isinstance(row, sqlite3.Row) else row["canonical_shop_id"] or "").strip()
        if canonical:
            mapping[account_id] = canonical
    return mapping


@app.post("/api/sycm/upload", status_code=202)
async def upload_sycm_snapshot(
    request: Request,
    _: None = Depends(require_sycm_upload_token),
):
    raw_body = await request.body()
    if len(raw_body) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="SYCM payload is too large")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be an object")

    shop_id = str(payload.get("shopId") or "").strip()
    shop_name = str(payload.get("shopName") or shop_id).strip()
    collected_at = str(payload.get("collectedAt") or "").strip()
    overview = payload.get("overview")
    source_tree = payload.get("sourceTree")
    period = str(payload.get("period") or "today").strip()
    date_start = str(payload.get("dateStart") or "").strip()
    date_end = str(payload.get("dateEnd") or "").strip()
    device_id = str(payload.get("deviceId") or "").strip()
    if not shop_id or len(shop_id) > 64 or not collected_at:
        raise HTTPException(status_code=422, detail="shopId and collectedAt are required")
    if not isinstance(overview, dict) or not isinstance(source_tree, list):
        raise HTTPException(status_code=422, detail="overview must be an object and sourceTree must be an array")
    if period not in {"today", "yesterday", "recent7", "recent30"}:
        raise HTTPException(status_code=422, detail="Invalid SYCM period")
    if not device_id or len(device_id) > 128:
        raise HTTPException(status_code=422, detail="deviceId is required")
    try:
        datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="collectedAt must be ISO-8601") from exc

    received_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        # 子账号上传时归一到主店铺，避免同店因多个千牛账号重复建行
        account_id = shop_id
        shop_id = resolve_canonical_shop_id(connection, account_id)
        owner = connection.execute(
            "SELECT device_id FROM sycm_shop_owners WHERE shop_id=?", (shop_id,)
        ).fetchone()
        if owner is None or owner[0] != device_id:
            raise HTTPException(status_code=409, detail="Shop is assigned to another collector device")
        if period == "yesterday" and date_end:
            existing = connection.execute(
                "SELECT id, collected_at FROM sycm_snapshots "
                "WHERE shop_id=? AND period='yesterday' AND date_end=? ORDER BY id DESC LIMIT 1",
                (shop_id, date_end),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "DELETE FROM sycm_snapshots WHERE shop_id=? AND period='yesterday' AND date_end=? AND id<>?",
                    (shop_id, date_end, existing[0]),
                )
                collected_at = existing[1]
        connection.execute(
            """
            INSERT INTO sycm_snapshots (
                shop_id, shop_name, collected_at, received_at, uv, pv, cart_byr_cnt,
                pay_byr_cnt, pay_amt, pay_rate, overview_json, source_tree_json,
                period, date_start, date_end
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shop_id, collected_at) DO UPDATE SET
                shop_name=excluded.shop_name,
                received_at=excluded.received_at,
                uv=excluded.uv,
                pv=excluded.pv,
                cart_byr_cnt=excluded.cart_byr_cnt,
                pay_byr_cnt=excluded.pay_byr_cnt,
                pay_amt=excluded.pay_amt,
                pay_rate=excluded.pay_rate,
                overview_json=excluded.overview_json,
                source_tree_json=excluded.source_tree_json
            """,
            (
                shop_id, shop_name[:200], collected_at, received_at,
                sycm_metric(overview, "uv"), sycm_metric(overview, "pv"),
                sycm_metric(overview, "cartByrCnt"), sycm_metric(overview, "payByrCnt"),
                sycm_metric(overview, "payAmt"), sycm_metric(overview, "payRate"),
                json.dumps(overview, ensure_ascii=False, separators=(",", ":")),
                json.dumps(source_tree, ensure_ascii=False, separators=(",", ":")),
                period, date_start, date_end,
            ),
        )
        snapshot_id = connection.execute(
            "SELECT id FROM sycm_snapshots WHERE shop_id=? AND collected_at=?",
            (shop_id, collected_at),
        ).fetchone()[0]
        connection.commit()
    return {"ok": True, "snapshotId": snapshot_id, "receivedAt": received_at}


def serialize_sycm_sync_request(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "status": row["status"],
        "requestedAt": row["requested_at"],
        "claimedAt": row["claimed_at"],
        "completedAt": row["completed_at"],
        "error": row["error"],
        "results": json.loads(row["results_json"] or "[]") if "results_json" in row.keys() else [],
    }


@app.post("/api/sycm/sync-requests", status_code=202)
def create_sycm_sync_request(current_user: AdminUser = Depends(get_current_user)):
    now_dt = datetime.now(ZoneInfo("Asia/Shanghai"))
    now = now_dt.isoformat()
    # A pending request that nobody has claimed for more than 15 minutes means
    # the collector is offline or misconfigured. Returning it forever blocks all
    # future syncs, so expire it and let the user queue a fresh attempt.
    # Running tasks have their own 15-minute reaper in the claim route; only
    # stuck *pending* rows need reclaiming here.
    pending_stale_before = (now_dt - timedelta(minutes=15)).isoformat()
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            "UPDATE sycm_sync_requests SET status='failed', error='采集端未在15分钟内认领，已自动取消' "
            "WHERE status='pending' AND requested_at < ?",
            (pending_stale_before,),
        )
        existing = connection.execute(
            "SELECT * FROM sycm_sync_requests WHERE status IN ('pending', 'running') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if existing is not None:
            connection.commit()
            return serialize_sycm_sync_request(existing)
        cursor = connection.execute(
            "INSERT INTO sycm_sync_requests(status, requested_by, requested_at) VALUES ('pending', ?, ?)",
            (current_user.id, now),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM sycm_sync_requests WHERE id=?", (cursor.lastrowid,)).fetchone()
    return serialize_sycm_sync_request(row)


@app.get("/api/sycm/sync-requests/latest")
def get_latest_sycm_sync_request(_: AdminUser = Depends(get_current_user)):
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM sycm_sync_requests ORDER BY id DESC LIMIT 1").fetchone()
    return serialize_sycm_sync_request(row) if row is not None else None


@app.get("/api/sycm/collector-devices")
def list_sycm_collector_devices(_: AdminUser = Depends(get_current_user)):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT d.device_id, d.device_name, d.first_seen_at, d.last_seen_at, "
            "COUNT(o.shop_id) AS shop_count "
            "FROM sycm_collector_devices d LEFT JOIN sycm_shop_owners o ON o.device_id=d.device_id "
            "GROUP BY d.device_id, d.device_name, d.first_seen_at, d.last_seen_at "
            "ORDER BY d.last_seen_at DESC"
        ).fetchall()
    result = []
    for row in rows:
        try:
            last_seen = datetime.fromisoformat(row["last_seen_at"])
            # Rows written without an offset would raise TypeError on the
            # comparison below, which the old `except ValueError` let escape as
            # a 500. Treat a bare timestamp as already being Shanghai local.
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=now.tzinfo)
            online = last_seen >= now - timedelta(minutes=1)
        except (TypeError, ValueError):
            online = False
        result.append({
            "deviceId": row["device_id"][:8],
            "deviceName": row["device_name"],
            "firstSeenAt": row["first_seen_at"],
            "lastSeenAt": row["last_seen_at"],
            "shopCount": row["shop_count"],
            "online": online,
        })
    return result


@app.post("/api/sycm/sync-requests/claim")
async def claim_sycm_sync_request(request: Request, _: None = Depends(require_sycm_upload_token)):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    device_id = str(payload.get("deviceId") or "").strip() if isinstance(payload, dict) else ""
    device_name = str(payload.get("deviceName") or device_id).strip() if isinstance(payload, dict) else ""
    shop_ids = payload.get("shopIds", []) if isinstance(payload, dict) else []
    shop_ids = list(dict.fromkeys(str(value).strip() for value in shop_ids if str(value).strip())) if isinstance(shop_ids, list) else []
    requested_account_ids = list(shop_ids)
    if not device_id or len(device_id) > 128 or not shop_ids:
        raise HTTPException(status_code=422, detail="deviceId and shopIds are required")
    now_dt = datetime.now(ZoneInfo("Asia/Shanghai"))
    now = now_dt.isoformat()
    owner_stale_before = (now_dt - timedelta(minutes=10)).isoformat()
    stale_before = (now_dt - timedelta(minutes=15)).isoformat()
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        # 认领按规范店铺 ID，主/子账号不会各占一条归属记录
        canonical_map = resolve_canonical_shop_ids(connection, requested_account_ids)
        shop_ids = list(dict.fromkeys(canonical_map.get(value, value) for value in requested_account_ids))
        connection.execute(
            "INSERT INTO sycm_collector_devices(device_id, device_name, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET device_name=excluded.device_name, last_seen_at=excluded.last_seen_at",
            (device_id, device_name[:200], now, now),
        )
        allowed_shop_ids: list[str] = []
        for shop_id in shop_ids:
            owner = connection.execute(
                "SELECT device_id, last_seen_at FROM sycm_shop_owners WHERE shop_id=?", (shop_id,)
            ).fetchone()
            if owner is None:
                connection.execute(
                    "INSERT INTO sycm_shop_owners(shop_id, device_id, assigned_at, last_seen_at) VALUES (?, ?, ?, ?)",
                    (shop_id, device_id, now, now),
                )
                allowed_shop_ids.append(shop_id)
            elif owner["device_id"] == device_id:
                connection.execute("UPDATE sycm_shop_owners SET last_seen_at=? WHERE shop_id=?", (now, shop_id))
                allowed_shop_ids.append(shop_id)
            elif owner["last_seen_at"] < owner_stale_before:
                connection.execute(
                    "UPDATE sycm_shop_owners SET device_id=?, assigned_at=?, last_seen_at=? WHERE shop_id=?",
                    (device_id, now, now, shop_id),
                )
                allowed_shop_ids.append(shop_id)
        connection.execute(
            "UPDATE sycm_sync_requests SET status='pending', claimed_at=NULL "
            "WHERE status='running' AND claimed_at < ?",
            (stale_before,),
        )
        row = connection.execute(
            "SELECT * FROM sycm_sync_requests WHERE status='pending' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None or not allowed_shop_ids:
            connection.commit()
            return None
        connection.execute(
            "UPDATE sycm_sync_requests SET status='running', claimed_at=?, error='' WHERE id=?",
            (now, row["id"]),
        )
        connection.commit()
        claimed = connection.execute("SELECT * FROM sycm_sync_requests WHERE id=?", (row["id"],)).fetchone()
    result = serialize_sycm_sync_request(claimed)
    # 同时回传原始 account_id，兼容仍以 unb 匹配的采集端
    allowed_set = set(allowed_shop_ids)
    allowed_accounts = [
        account_id
        for account_id in requested_account_ids
        if canonical_map.get(account_id, account_id) in allowed_set
    ]
    result["allowedShopIds"] = list(dict.fromkeys(allowed_shop_ids + allowed_accounts))
    result["canonicalShopIds"] = allowed_shop_ids
    result["deviceId"] = device_id
    return result


@app.post("/api/sycm/sync-requests/{request_id}/complete")
async def complete_sycm_sync_request(
    request_id: int,
    request: Request,
    _: None = Depends(require_sycm_upload_token),
):
    payload = await request.json()
    succeeded = bool(payload.get("success", False)) if isinstance(payload, dict) else False
    error = str(payload.get("error") or "")[:500] if isinstance(payload, dict) else ""
    results = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(results, list):
        results = []
    status = "completed" if succeeded else "failed"
    completed_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        cursor = connection.execute(
            "UPDATE sycm_sync_requests SET status=?, completed_at=?, error=?, results_json=? "
            "WHERE id=? AND status='running'",
            (status, completed_at, error, json.dumps(results, ensure_ascii=False), request_id),
        )
        connection.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=409, detail="Sync request is not running")
    return {"ok": True, "status": status, "completedAt": completed_at}


def _serialize_sycm_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "shopId": row["shop_id"], "shopName": row["shop_name"],
        "collectedAt": row["collected_at"], "receivedAt": row["received_at"],
        "uv": row["uv"], "pv": row["pv"], "cartByrCnt": row["cart_byr_cnt"],
        "payByrCnt": row["pay_byr_cnt"], "payAmt": row["pay_amt"], "payRate": row["pay_rate"],
        "period": row["period"], "dateStart": row["date_start"], "dateEnd": row["date_end"],
        "overview": json.loads(row["overview_json"]),
        "sourceTree": json.loads(row["source_tree_json"]),
    }


def _latest_sycm_period(period: str) -> list[dict[str, Any]]:
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT s.* FROM sycm_snapshots s
            INNER JOIN (
                SELECT shop_id, MAX(id) AS id
                FROM sycm_snapshots WHERE period=? GROUP BY shop_id
            ) latest ON latest.id=s.id
            WHERE s.period=?
            ORDER BY s.shop_name COLLATE NOCASE
            """
            , (period, period)
        ).fetchall()
    return [_serialize_sycm_row(row) for row in rows]


def _aggregate_sycm_yesterday(days: int, period: str) -> list[dict[str, Any]]:
    end = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT s.* FROM sycm_snapshots s
            INNER JOIN (
                SELECT shop_id, date_end, MAX(id) AS id
                FROM sycm_snapshots
                WHERE period='yesterday' AND date_end BETWEEN ? AND ?
                GROUP BY shop_id, date_end
            ) latest ON latest.id=s.id
            ORDER BY s.shop_name COLLATE NOCASE, s.date_end
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()

    shops: dict[str, dict[str, Any]] = {}
    derived = {"payRate", "crtRate", "uvValue", "payPct", "avgPv", "itmAvgPv"}
    for row in rows:
        shop = shops.setdefault(row["shop_id"], {
            "id": row["id"], "shopId": row["shop_id"], "shopName": row["shop_name"],
            "collectedAt": row["collected_at"], "receivedAt": row["received_at"],
            "period": period, "dateStart": start.isoformat(), "dateEnd": end.isoformat(),
            "overview": {}, "sourceTree": [], "availableDays": 0,
        })
        shop["availableDays"] += 1
        shop["id"] = max(shop["id"], row["id"])
        shop["collectedAt"] = max(shop["collectedAt"], row["collected_at"])
        for name, metric in json.loads(row["overview_json"]).items():
            value = metric.get("value") if isinstance(metric, dict) else None
            if name not in derived and isinstance(value, (int, float)):
                target = shop["overview"].setdefault(name, {"value": 0, "cycleCrc": None})
                target["value"] += value

    for shop in shops.values():
        overview = shop["overview"]
        value = lambda name: float(overview.get(name, {}).get("value") or 0)
        def set_ratio(name: str, numerator: float, denominator: float) -> None:
            overview[name] = {"value": numerator / denominator if denominator else 0, "cycleCrc": None}
        set_ratio("payRate", value("payByrCnt"), value("uv"))
        set_ratio("crtRate", value("crtByrCnt"), value("uv"))
        set_ratio("uvValue", value("payAmt"), value("uv"))
        set_ratio("payPct", value("payAmt"), value("payByrCnt"))
        set_ratio("avgPv", value("pv"), value("uv"))
        set_ratio("itmAvgPv", value("itmPv"), value("itmUv"))
        shop.update(
            uv=value("uv"), pv=value("pv"), cartByrCnt=value("cartByrCnt"),
            payByrCnt=value("payByrCnt"), payAmt=value("payAmt"),
            payRate=overview["payRate"]["value"],
        )
    return list(shops.values())


@app.get("/api/sycm/latest")
def list_latest_sycm_snapshots(period: str = "today", _: AdminUser = Depends(get_current_user)):
    if period not in {"today", "yesterday", "recent7", "recent30"}:
        raise HTTPException(status_code=422, detail="Invalid SYCM period")
    if period == "recent7":
        return _aggregate_sycm_yesterday(7, period)
    if period == "recent30":
        return _aggregate_sycm_yesterday(30, period)
    return _latest_sycm_period(period)


@app.get("/api/sycm/yesterday")
def list_yesterday_sycm_snapshots(_: AdminUser = Depends(get_current_user)):
    return _latest_sycm_period("yesterday")


@app.get("/api/sycm/shops/{shop_id}/snapshots")
def list_sycm_shop_snapshots(
    shop_id: str,
    limit: int = 100,
    _: AdminUser = Depends(get_current_user),
):
    limit = max(1, min(limit, 500))
    with sqlite3.connect(SYCM_DATA_DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        # 传入子账号 ID 时也能查到合并后的主店铺数据
        shop_id = resolve_canonical_shop_id(connection, shop_id)
        rows = connection.execute(
            """
            SELECT * FROM sycm_snapshots WHERE shop_id=?
            ORDER BY collected_at DESC LIMIT ?
            """,
            (shop_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"], "shopId": row["shop_id"], "shopName": row["shop_name"],
            "collectedAt": row["collected_at"], "receivedAt": row["received_at"],
            "uv": row["uv"], "pv": row["pv"], "cartByrCnt": row["cart_byr_cnt"],
            "payByrCnt": row["pay_byr_cnt"], "payAmt": row["pay_amt"], "payRate": row["pay_rate"],
            "overview": json.loads(row["overview_json"]),
            "sourceTree": json.loads(row["source_tree_json"]),
        }
        for row in rows
    ]


@app.get(
    OPENAPI_ROUTE,
    include_in_schema=False,
)
def secure_openapi_schema(_: AdminUser = Depends(require_role("superadmin"))):
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )


@app.get(
    DOCS_ROUTE,
    include_in_schema=False,
)
def secure_swagger_ui(_: AdminUser = Depends(require_role("superadmin"))):
    return get_swagger_ui_html(
        openapi_url=OPENAPI_ROUTE,
        title=f"{app.title} - Swagger UI",
    )


@app.get(
    REDOC_ROUTE,
    include_in_schema=False,
)
def secure_redoc_ui(_: AdminUser = Depends(require_role("superadmin"))):
    return get_redoc_html(
        openapi_url=OPENAPI_ROUTE,
        title=f"{app.title} - ReDoc",
    )

def frontend_index_response() -> FileResponse:
    return FileResponse(
        FRONTEND_DIST_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def frontend_ui_response(path: str = "") -> FileResponse:
    if not FRONTEND_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")

    requested_path = path.strip("/")
    if not requested_path:
        return frontend_index_response()

    candidate = (FRONTEND_DIST_DIR / requested_path).resolve()
    try:
        candidate.relative_to(FRONTEND_DIST_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if candidate.is_file():
        return FileResponse(candidate)

    return frontend_index_response()


def app_frontend_index_response() -> FileResponse:
    return FileResponse(
        APP_FRONTEND_DIST_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def app_frontend_response(path: str = "") -> FileResponse:
    if not APP_FRONTEND_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="App frontend build not found")

    requested_path = path.strip("/")
    if not requested_path:
        return app_frontend_index_response()

    candidate = (APP_FRONTEND_DIST_DIR / requested_path).resolve()
    try:
        candidate.relative_to(APP_FRONTEND_DIST_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if candidate.is_file():
        return FileResponse(candidate)

    return app_frontend_index_response()


def is_bare_mobile_webview(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "").lower()
    if any(marker in user_agent for marker in ("dingtalk", "micromessenger", "alipayclient")):
        return False
    ios_webview = (
        ("iphone" in user_agent or "ipad" in user_agent)
        and "applewebkit" in user_agent
        and "mobile/" in user_agent
        and "safari/" not in user_agent
    )
    android_webview = "android" in user_agent and ("; wv)" in user_agent or " wv" in user_agent)
    return ios_webview or android_webview


def mobile_app_upgrade_redirect(path: str) -> RedirectResponse:
    target = "/app/login" if path.strip("/").startswith("login") else "/app/tabs/home"
    return RedirectResponse(
        url=f"{target}?app_version=0.7.14-alpha",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def build_login_redirect_url(target_path: str) -> str:
    normalized_target = target_path if target_path.startswith("/") else f"/{target_path}"
    return f"/ui/login?redirect={quote(normalized_target, safe='/%?=&')}"


def tutorials_index_response() -> FileResponse:
    return FileResponse(
        TUTORIALS_DIST_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def tutorials_site_response(path: str = "") -> FileResponse:
    if not TUTORIALS_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="Tutorial site build not found")

    requested_path = path.strip("/")
    if not requested_path:
        return tutorials_index_response()

    direct_candidate = (TUTORIALS_DIST_DIR / requested_path).resolve()
    tutorials_root = TUTORIALS_DIST_DIR.resolve()
    try:
        direct_candidate.relative_to(tutorials_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if direct_candidate.is_file():
        return FileResponse(direct_candidate)

    clean_url_candidate = (TUTORIALS_DIST_DIR / requested_path / "index.html").resolve()
    try:
        clean_url_candidate.relative_to(tutorials_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if clean_url_candidate.is_file():
        return FileResponse(clean_url_candidate)

    html_candidate = (TUTORIALS_DIST_DIR / f"{requested_path}.html").resolve()
    try:
        html_candidate.relative_to(tutorials_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if html_candidate.is_file():
        return FileResponse(html_candidate)

    raise HTTPException(status_code=404, detail="Tutorial page not found")


@app.get("/")
def root(
    current_user: AdminUser | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user is None:
        target = "/ui/login"
        return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/shop-records-admin")
def shop_record_page(current_user: AdminUser | None = Depends(get_current_user_optional)):
    if current_user is None:
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/ui/shop-records", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/licenses")
def license_page(current_user: AdminUser | None = Depends(get_current_user_optional)):
    if current_user is None:
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/ui/licenses", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/ui")
def vue_ui_root(request: Request):
    if is_bare_mobile_webview(request):
        return mobile_app_upgrade_redirect("dashboard")
    return frontend_ui_response()


@app.get("/ui/app")
def legacy_mobile_app_root():
    return RedirectResponse(url="/app/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/ui/app/{path:path}")
def legacy_mobile_app_page(path: str):
    return RedirectResponse(url=f"/app/{path.lstrip('/')}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/ui/{path:path}")
def vue_ui_page(path: str, request: Request):
    embedded_app = request.query_params.get("embedded_app") == "1"
    if is_bare_mobile_webview(request) and not Path(path).suffix and not embedded_app:
        return mobile_app_upgrade_redirect(path)
    return frontend_ui_response(path)


@app.get("/app")
def mobile_app_root():
    return app_frontend_response()


@app.get("/app/{path:path}")
def mobile_app_page(path: str):
    return app_frontend_response(path)


@app.get("/company-expenses-app")
def company_expenses_app_redirect(
    current_user: AdminUser | None = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(
            url=build_login_redirect_url("/company-expenses-app/"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/company-expenses-app/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/company-expenses-app/")
def company_expenses_app(
    current_user: AdminUser | None = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(
            url=build_login_redirect_url("/company-expenses-app/"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    page_file = COMPANY_EXPENSE_APP_DIR / "index.html"
    if not page_file.is_file():
        raise HTTPException(status_code=404, detail="Company expense app not found")
    return FileResponse(
        page_file,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/tutorials")
def tutorials_root(current_user: AdminUser | None = Depends(get_current_user_optional)):
    if current_user is None:
        return RedirectResponse(url=build_login_redirect_url("/tutorials/"), status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/tutorials/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/tutorials/")
def tutorials_index(
    request: Request,
    current_user: AdminUser | None = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(
            url=build_login_redirect_url(request.url.path),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return tutorials_site_response()


@app.get("/tutorials/{path:path}")
def tutorials_page(
    path: str,
    request: Request,
    current_user: AdminUser | None = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(
            url=build_login_redirect_url(request.url.path),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return tutorials_site_response(path)


@app.get(
    "/api/health",
    summary="Public license server health proxy",
    include_in_schema=False,
)
def public_license_health_proxy():
    return proxy_public_license_server_request("GET", "/api/health")


@app.api_route(
    "/api/license/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    summary="Public license server proxy",
    include_in_schema=False,
)
async def public_license_proxy(path: str, request: Request):
    raw_body = await request.body()
    content_type = request.headers.get("content-type")
    normalized_path = "/" + path.lstrip("/")
    return proxy_public_license_server_request(
        request.method,
        f"/api/license{normalized_path}",
        body=raw_body or None,
        content_type=content_type,
    )


@app.get("/login")
def login_page(
    current_user: AdminUser | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user is not None:
        return RedirectResponse(url="/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    if not has_admin_users(db) and settings.public_registration_enabled:
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/register")
def register_page(
    current_user: AdminUser | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if current_user is not None:
        return RedirectResponse(url="/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    if has_admin_users(db) and not settings.public_registration_enabled:
        return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get(
    "/auth/captcha",
    response_model=LoginCaptchaResponse,
    summary="Get a login captcha",
)
def get_login_captcha(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return create_login_captcha()


@app.post(
    "/auth/login",
    response_model=CurrentUserResponse,
    summary="Login with admin username and password",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip_address = get_client_ip(request)
    try:
        ensure_login_not_locked(db, payload.username, ip_address)
    except HTTPException:
        attempt = get_login_attempt(db, payload.username, ip_address)
        write_audit_log(
            db,
            actor=None,
            action="login_locked",
            resource_type="auth_session",
            details=build_auth_audit_details(
                request,
                attempted_username=payload.username,
                failed_count=attempt.failed_count if attempt else None,
                locked_until=attempt.locked_until.isoformat() if attempt and attempt.locked_until else None,
            ),
        )
        commit_session(db, default_detail="Failed to record audit log")
        raise

    if is_login_captcha_required(db, payload.username, ip_address):
        if not payload.captcha_id or not payload.captcha_code:
            raise HTTPException(
                status_code=428,
                detail="登录失败次数较多，请输入验证码",
                headers={"X-Captcha-Required": "true"},
            )
        consume_login_captcha(payload.captcha_id, payload.captcha_code)

    db_user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if db_user is None or not verify_password(payload.password, db_user.password_hash):
        record_login_failure(db, payload.username, ip_address)
        attempt = get_login_attempt(db, payload.username, ip_address)
        write_audit_log(
            db,
            actor=None,
            action="login_failed",
            resource_type="auth_session",
            resource_id=db_user.id if db_user else None,
            details=build_auth_audit_details(
                request,
                attempted_username=payload.username,
                failed_count=attempt.failed_count if attempt else None,
                locked_until=attempt.locked_until.isoformat() if attempt and attempt.locked_until else None,
            ),
        )
        commit_session(db, default_detail="Failed to record audit log")
        captcha_required = bool(attempt and attempt.failed_count >= LOGIN_CAPTCHA_AFTER_FAILURES)
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"X-Captcha-Required": "true"} if captcha_required else None,
        )
    if not db_user.is_active:
        write_audit_log(
            db,
            actor=db_user,
            action="login_rejected_inactive",
            resource_type="admin_user",
            resource_id=db_user.id,
            details=build_auth_audit_details(request),
        )
        commit_session(db, default_detail="Failed to record audit log")
        raise HTTPException(status_code=403, detail="褰撳墠璐﹀彿宸茶绂佺敤")

    if db_user.role == "software":
        write_audit_log(
            db,
            actor=db_user,
            action="login_rejected_software_account",
            resource_type="admin_user",
            resource_id=db_user.id,
            details=build_auth_audit_details(request),
        )
        commit_session(db, default_detail="Failed to record audit log")
        raise HTTPException(status_code=403, detail="软件账号只能登录客户端，不能进入后台")

    if db_user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(
                status_code=428,
                detail="请输入身份验证器中的6位动态验证码",
                headers={"X-TOTP-Required": "true"},
            )
        if not verify_totp_code(decrypt_totp_secret(db_user.totp_secret_encrypted), payload.totp_code):
            record_login_failure(db, payload.username, ip_address)
            write_audit_log(
                db,
                actor=db_user,
                action="login_totp_failed",
                resource_type="auth_session",
                resource_id=db_user.id,
                details=build_auth_audit_details(request),
            )
            commit_session(db, default_detail="Failed to record TOTP login failure")
            raise HTTPException(
                status_code=401,
                detail="动态验证码错误或已过期",
                headers={"X-TOTP-Required": "true"},
            )

    clear_login_failures(db, payload.username, ip_address)
    revoked_session_count = 0
    admin_session = create_session_cookie(db_user, response, db, request=request)
    write_audit_log(
        db,
        actor=db_user,
        action="login_succeeded",
        resource_type="auth_session",
        resource_id=admin_session.id,
        details=build_auth_audit_details(
            request,
            active_session_count=count_active_sessions(db, db_user.id),
            revoked_session_count=revoked_session_count,
            session_expires_at=admin_session.expires_at.isoformat(),
        ),
    )
    commit_session(db, default_detail="Failed to record audit log")
    return serialize_current_user(db_user)


@app.post("/auth/totp/setup", response_model=TotpSetupResponse, summary="Start authenticator setup")
def setup_totp(
    payload: TotpSetupRequest,
    current_user: AdminUser = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    secret = pyotp.random_base32()
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.username,
        issuer_name="内部管理系统",
    )
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "qr_image_data": build_totp_qr_data(provisioning_uri),
    }


@app.post("/auth/totp/confirm", response_model=CurrentUserResponse, summary="Enable authenticator")
def confirm_totp(
    payload: TotpConfirmRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    secret = payload.secret.strip().replace(" ", "").upper()
    if not verify_totp_code(secret, payload.code):
        raise HTTPException(status_code=400, detail="动态验证码错误，请确认手机时间准确后重试")
    current_user.totp_secret_encrypted = encrypt_totp_secret(secret)
    current_user.totp_enabled = True
    write_audit_log(
        db, actor=current_user, action="totp_enabled", resource_type="admin_user", resource_id=current_user.id,
    )
    commit_session(db, default_detail="Failed to enable TOTP")
    return serialize_current_user(current_user)


@app.post("/auth/totp/disable", response_model=CurrentUserResponse, summary="Disable authenticator")
def disable_totp(
    payload: TotpDisableRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    if not current_user.totp_enabled:
        return serialize_current_user(current_user)
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    if not verify_totp_code(decrypt_totp_secret(current_user.totp_secret_encrypted), payload.code):
        raise HTTPException(status_code=400, detail="动态验证码错误或已过期")
    current_user.totp_enabled = False
    current_user.totp_secret_encrypted = None
    write_audit_log(
        db, actor=current_user, action="totp_disabled", resource_type="admin_user", resource_id=current_user.id,
    )
    commit_session(db, default_detail="Failed to disable TOTP")
    return serialize_current_user(current_user)


@app.post(
    "/auth/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register admin account",
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    existing_user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="账号已存在")

    bootstrap_mode = not has_admin_users(db)
    if not bootstrap_mode:
        if not settings.public_registration_enabled:
            raise HTTPException(status_code=403, detail="公开注册已关闭")

    role = "superadmin" if bootstrap_mode else settings.public_registration_role
    db_user = AdminUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )
    db.add(db_user)
    commit_session(
        db,
        default_detail="Failed to register account",
        integrity_detail="账号已存在",
    )
    db.refresh(db_user)

    if bootstrap_mode:
        create_session_cookie(db_user, response, db, request=request)

    return serialize_current_user(db_user)


@app.post(
    "/software/auth/register",
    response_model=SoftwareAuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a software client account",
)
def software_register(
    payload: SoftwareRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    existing_user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="账号已存在")

    db_user = AdminUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role="software",
        is_active=True,
    )
    db.add(db_user)
    commit_session(
        db,
        default_detail="Failed to register software account",
        integrity_detail="账号已存在",
    )
    db.refresh(db_user)
    token, session = create_software_session(
        db_user, db, request=request, device_id=payload.device_id, device_name=payload.device_name,
        platform=payload.platform, app_version=payload.app_version,
    )
    write_audit_log(
        db,
        actor=db_user,
        action="software_register_succeeded",
        resource_type="software_user",
        resource_id=db_user.id,
        details=build_auth_audit_details(request, device_id=payload.device_id, platform=payload.platform),
    )
    commit_session(db, default_detail="Failed to record software register audit log")
    return build_software_auth_response(db_user, token, session, message="账号注册成功，请使用卡密激活。")


@app.post(
    "/software/auth/login",
    response_model=SoftwareAuthResponse,
    summary="Login as a software client account",
)
def software_login(
    payload: SoftwareLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    ip_address = get_client_ip(request)
    try:
        ensure_login_not_locked(db, payload.username, ip_address)
    except HTTPException:
        attempt = get_login_attempt(db, payload.username, ip_address)
        write_audit_log(
            db,
            actor=None,
            action="software_login_locked",
            resource_type="software_user",
            details=build_auth_audit_details(
                request,
                attempted_username=payload.username,
                failed_count=attempt.failed_count if attempt else None,
                locked_until=attempt.locked_until.isoformat() if attempt and attempt.locked_until else None,
            ),
        )
        commit_session(db, default_detail="Failed to record software login lock audit log")
        raise

    db_user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if db_user is None or not verify_password(payload.password, db_user.password_hash):
        record_login_failure(db, payload.username, ip_address)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="当前账号已被禁用")

    refresh_software_license_for_login(db_user, payload, db)

    clear_login_failures(db, payload.username, ip_address)
    token, session = create_software_session(
        db_user, db, request=request, device_id=payload.device_id, device_name=payload.device_name,
        platform=payload.platform, app_version=payload.app_version,
    )
    write_audit_log(
        db,
        actor=db_user,
        action="software_login_succeeded",
        resource_type="software_user",
        resource_id=db_user.id,
        details=build_auth_audit_details(
            request,
            device_id=payload.device_id,
            platform=payload.platform,
            session_expires_at=session.expires_at.isoformat(),
        ),
    )
    commit_session(db, default_detail="Failed to record software login audit log")
    message = "登录成功。" if is_software_user_activated(db_user) else "登录成功，请使用卡密激活。"
    return build_software_auth_response(db_user, token, session, message=message)


@app.post(
    "/software/auth/activate",
    response_model=SoftwareUserResponse,
    summary="Activate current software account with a license key",
)
def software_activate(
    payload: SoftwareActivateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_software_user_allow_inactive),
):
    activate_software_license_for_user(current_user, payload, db)
    write_audit_log(
        db,
        actor=current_user,
        action="software_license_activated",
        resource_type="software_user",
        resource_id=current_user.id,
        details=build_auth_audit_details(
            request,
            license_key=payload.license_key,
            device_id=payload.device_id,
            platform=payload.platform,
        ),
    )
    commit_session(db, default_detail="Failed to record software activation audit log")
    return serialize_software_user(current_user)


@app.post(
    "/software/auth/validate",
    response_model=SoftwareUserResponse,
    summary="Validate current software account and bound license",
)
def software_validate(
    payload: SoftwareAuthDevicePayload,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_software_user_allow_inactive),
):
    if not current_user.software_license_key:
        raise HTTPException(status_code=403, detail="账号未激活")

    response_payload = request_public_license_server(
        "POST",
        "/api/license/validate",
        json_payload={
            "license_key": current_user.software_license_key,
            "device_id": payload.device_id,
            "device_name": payload.device_name or "",
            "platform": payload.platform,
            "app_version": payload.app_version or "",
        },
    )
    license_payload = response_payload.get("license")
    if not isinstance(license_payload, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected license payload")

    sync_software_license_payload(current_user, license_payload)
    commit_session(db, default_detail="Failed to validate software license")
    db.refresh(current_user)
    if not is_software_user_activated(current_user):
        raise HTTPException(status_code=403, detail="账号未激活或授权已过期")
    return serialize_software_user(current_user)


@app.get(
    "/software/auth/me",
    response_model=SoftwareUserResponse,
    summary="Get current software account info",
)
def software_me(current_user: AdminUser = Depends(get_current_software_user_allow_inactive)):
    return serialize_software_user(current_user)


@app.get(
    "/software/rules/catalog",
    summary="Fetch the server publish category rule catalog",
)
def software_get_rule_catalog(
    current_user: AdminUser = Depends(get_current_rule_catalog_maintainer),
):
    return load_category_rule_catalog_payload()


@app.get(
    "/software/rules/category",
    summary="Fetch a single publish category rule",
)
def software_get_category_rule(
    platform: str,
    category_id: str,
    include_snapshot: bool = False,
    current_user: AdminUser = Depends(get_current_rule_api_user),
):
    return load_category_rule_payload(
        platform,
        category_id,
        include_snapshot=include_snapshot and can_view_full_rule_snapshot(current_user),
    )


@app.post(
    "/software/rules/category/package-patch",
    summary="Patch safe auto-learned package flags for one category rule",
)
def software_patch_category_rule_package(
    payload: RuleCategoryPackagePatchRequest,
    current_user: AdminUser = Depends(get_current_rule_api_user),
):
    source_name = str(payload.source or current_user.username or "software-auto-rule-learn").strip()[:120]
    result = patch_category_rule_package(
        payload.platform,
        payload.category_id,
        payload.package_patch,
        source_name=source_name or "software-auto-rule-learn",
        reason=payload.reason,
    )
    return {
        "success": True,
        "result": result,
    }


@app.post(
    "/software/rules/fetch-status",
    summary="Update the fetch status for one category rule",
)
def software_update_category_rule_fetch_status(
    payload: RuleCategoryFetchStatusRequest,
    current_user: AdminUser = Depends(get_current_rule_catalog_maintainer),
):
    source_name = str(payload.source or current_user.username or "software-rule-fetch").strip()[:120]
    result = update_category_rule_fetch_status(
        payload.platform,
        payload.category_id,
        payload.fetch_status,
        payload.last_fetch_error,
        source_name=source_name or "software-rule-fetch",
    )
    return {
        "success": True,
        "result": result,
    }


@app.post(
    "/software/rules/import-page-json",
    summary="Import a publish page JSON into the server rule catalog",
)
def software_import_category_rule_page_json(
    payload: RulePageImportRequest,
    current_user: AdminUser = Depends(get_current_rule_catalog_maintainer),
):
    source_name = str(payload.source or current_user.username or "software-client").strip()[:120]
    try:
        result = save_uploaded_rule_page_json(
            payload.platform,
            payload.category_id,
            payload.root_json,
            source_name=source_name or "software-client",
        )
    except HTTPException as exc:
        mark_rule_page_import_failed(payload.platform, payload.category_id, str(exc.detail))
        raise
    return {
        "success": True,
        "result": result,
    }


@app.post(
    "/software/rules/category-names/import",
    summary="Import category ID/name dictionary into the server rule catalog",
)
def software_import_category_name_dictionary(
    payload: RuleCategoryNameDictionaryImportRequest,
    current_user: AdminUser = Depends(get_current_rule_catalog_maintainer),
):
    source_name = str(payload.source or current_user.username or "software-client").strip()[:120]
    result = import_rule_category_name_dictionary(
        payload.platform,
        payload.items,
        source_name=source_name or "software-client",
    )
    return {
        "success": True,
        "result": result,
    }


@app.get(
    "/software/products/parsed-cache",
    summary="Fetch one parsed product payload by exact item ID",
)
def software_get_product_parse_cache(
    item_id: str,
    platform: str = "taobao",
    current_user: AdminUser = Depends(get_current_product_cache_user),
):
    return load_product_parse_cache(platform, item_id, current_user)


@app.get(
    "/software/products/parsed-cache/list",
    summary="Search shared parsed product cache",
)
def software_list_product_parse_cache(
    platform: str = "taobao",
    keyword: str = "",
    limit: int = 100,
    offset: int = 0,
    current_user: AdminUser = Depends(get_current_product_cache_user),
):
    return list_product_parse_cache(platform, keyword, limit, offset, current_user)


@app.post(
    "/software/products/parsed-cache",
    summary="Upload one parsed product payload into shared cache",
)
def software_upload_product_parse_cache(
    payload: ProductParseCacheUploadRequest,
    current_user: AdminUser = Depends(get_current_product_cache_user),
):
    return save_product_parse_cache(payload, current_user)


@app.delete(
    "/software/products/parsed-cache",
    summary="Delete one parsed product payload from shared cache",
)
def software_delete_product_parse_cache(
    item_id: str,
    platform: str = "taobao",
    current_user: AdminUser = Depends(get_current_product_cache_user),
):
    return delete_product_parse_cache(platform, item_id, current_user)


@app.post(
    "/software/publish-failures",
    summary="Upload one product publish failure report",
)
def software_upload_publish_failure_report(
    payload: PublishFailureReportRequest,
    current_user: AdminUser = Depends(get_current_publish_failure_report_writer),
):
    return save_publish_failure_report(payload, current_user)


@app.get(
    "/software/publish-failures",
    summary="Search product publish failure reports",
)
def software_list_publish_failure_reports(
    platform: str = "all",
    keyword: str = "",
    category_id: str = "",
    item_id: str = "",
    stage: str = "",
    limit: int = 100,
    offset: int = 0,
    current_user: AdminUser = Depends(get_current_publish_failure_report_reader),
):
    return list_publish_failure_reports(
        platform,
        keyword,
        category_id,
        item_id,
        stage,
        limit,
        offset,
        current_user,
    )


@app.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout current admin",
)
def logout(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
    current_user: AdminUser | None = Depends(get_current_user_optional),
):
    session_id: int | None = None
    if session_token:
        db_session = get_admin_session_by_token(db, session_token)
        if db_session is not None:
            session_id = db_session.id
            db.delete(db_session)
            db.commit()

    if current_user is not None:
        write_audit_log(
            db,
            actor=current_user,
            action="logout_succeeded",
            resource_type="auth_session",
            resource_id=session_id,
            details=build_auth_audit_details(
                request,
                active_session_count=count_active_sessions(db, current_user.id),
            ),
        )
        commit_session(db, default_detail="Failed to record audit log")

    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get(
    "/auth/me",
    response_model=CurrentUserResponse,
    summary="Get current admin info",
)
def auth_me(current_user: AdminUser = Depends(get_current_user)):
    return serialize_current_user(current_user)


@app.get(
    "/auth/sessions",
    response_model=list[AdminSessionResponse],
    summary="List active sessions for current admin",
)
def list_auth_sessions(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
    current_session: AdminSession = Depends(get_current_admin_session),
):
    stmt = (
        select(AdminSession)
        .where(
            AdminSession.user_id == current_user.id,
            AdminSession.expires_at > datetime.utcnow(),
        )
        .order_by(AdminSession.created_at.desc(), AdminSession.id.desc())
    )
    return [
        serialize_admin_session(record, current_session_id=current_session.id)
        for record in db.scalars(stmt).all()
    ]


@app.delete(
    "/auth/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one active session for current admin",
)
def revoke_auth_session(
    session_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
    current_session: AdminSession = Depends(get_current_admin_session),
):
    target_session = db.get(AdminSession, session_id)
    if target_session is None or target_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    is_current_session = target_session.id == current_session.id
    write_audit_log(
        db,
        actor=current_user,
        action="session_revoked",
        resource_type="auth_session",
        resource_id=target_session.id,
        details=build_auth_audit_details(
            request,
            target_ip_address=(target_session.ip_address or "unknown").strip() or "unknown",
            target_user_agent=(target_session.user_agent or "unknown").strip() or "unknown",
            target_device_name=summarize_session_device(target_session.user_agent),
            revoked_current_session=is_current_session,
        ),
    )
    db.delete(target_session)
    commit_session(db, default_detail="Failed to revoke session")

    if is_current_session:
        clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.post(
    "/auth/sessions/revoke-others",
    response_model=BatchActionResponse,
    summary="Revoke all other active sessions for current admin",
)
def revoke_other_auth_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
    current_session: AdminSession = Depends(get_current_admin_session),
):
    revoked_count = clear_user_sessions(db, current_user.id, exclude_session_id=current_session.id)
    write_audit_log(
        db,
        actor=current_user,
        action="other_sessions_revoked",
        resource_type="auth_session",
        resource_id=current_session.id,
        details=build_auth_audit_details(
            request,
            revoked_session_count=revoked_count,
        ),
    )
    commit_session(db, default_detail="Failed to record audit log")
    return {"updated_count": revoked_count}


@app.get(
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


@app.get(
    "/license-admin/stats",
    summary="Fetch license key admin statistics",
)
def get_license_admin_stats(
    _: AdminUser = Depends(require_role("superadmin")),
):
    payload = request_license_server("GET", "/api/admin/stats")
    stats_payload = payload.get("stats")
    return stats_payload if isinstance(stats_payload, dict) else {}


@app.get(
    "/license-admin/licenses",
    summary="List managed license keys",
)
def list_license_admin_licenses(
    _: AdminUser = Depends(require_role("superadmin")),
):
    payload = request_license_server("GET", "/api/admin/licenses")
    items = payload.get("items")
    return items if isinstance(items, list) else []


@app.post(
    "/license-admin/licenses",
    status_code=status.HTTP_201_CREATED,
    summary="Create managed license keys",
)
def create_license_admin_licenses(
    payload: dict[str, Any],
    _: AdminUser = Depends(require_role("superadmin")),
):
    normalized_payload = normalize_license_admin_create_payload(payload)
    response_payload = request_license_server(
        "POST",
        "/api/admin/licenses/create",
        json_payload=normalized_payload,
    )
    items = response_payload.get("items")
    return items if isinstance(items, list) else []


@app.post(
    "/license-admin/licenses/{license_key}/status",
    summary="Update managed license key status",
)
def update_license_admin_status(
    license_key: str,
    payload: dict[str, Any],
    _: AdminUser = Depends(require_role("superadmin")),
):
    normalized_payload = normalize_license_admin_status_payload(payload)
    response_payload = request_license_server(
        "POST",
        f"/api/admin/licenses/{license_key}/status",
        json_payload=normalized_payload,
    )
    item = response_payload.get("item")
    if not isinstance(item, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected item payload")
    return item


@app.post(
    "/license-admin/licenses/{license_key}/unbind",
    summary="Unbind devices from a managed license key",
)
def unbind_license_admin_devices(
    license_key: str,
    payload: dict[str, Any] | None = None,
    _: AdminUser = Depends(require_role("superadmin")),
):
    response_payload = request_license_server(
        "POST",
        f"/api/admin/licenses/{license_key}/unbind",
        json_payload=normalize_license_admin_unbind_payload(payload),
    )
    item = response_payload.get("item")
    if not isinstance(item, dict):
        raise HTTPException(status_code=502, detail="License server returned an unexpected item payload")
    return item


@app.get(
    "/software-admin/users",
    summary="List registered software client accounts",
)
def list_software_admin_users(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("superadmin")),
):
    stmt = (
        select(AdminUser)
        .where(AdminUser.role == "software")
        .order_by(AdminUser.created_at.desc(), AdminUser.id.desc())
    )
    return [serialize_software_admin_user(user) for user in db.scalars(stmt).all()]


@app.get(
    "/global-search",
    response_model=GlobalSearchResponse,
    summary="Search across shop records, licenses, accounts, and task records",
)
def global_search(
    q: str = "",
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    query = q.strip()
    normalized_query = query.lower()
    empty_payload = {
        "query": query,
        "total": 0,
        "shop_records": [],
        "license_records": [],
        "account_usage_records": [],
        "task_bookkeeping_records": [],
    }
    if not normalized_query:
        return empty_payload

    limit_per_section = 10
    shop_results: list[dict[str, Any]] = []
    license_results: list[dict[str, Any]] = []
    account_results: list[dict[str, Any]] = []
    task_results: list[dict[str, Any]] = []

    for record in db.scalars(select(ShopRecord).order_by(ShopRecord.id.desc())).all():
        values = parse_record_values(record)
        haystack = normalize_search_text(list(values.values()))
        if normalized_query not in haystack:
            continue

        shop_results.append(
            build_global_search_item(
                item_id=record.id,
                category="shop_record",
                title=str(values.get("shop_name") or f"鍙拌处璁板綍 #{record.id}"),
                subtitle=str(values.get("platform") or "") or None,
                detail=str(values.get("date") or "") or None,
                route="/shop-records",
            ),
        )
        if len(shop_results) >= limit_per_section:
            break

    for record in db.scalars(
        select(LicenseRecord).order_by(LicenseRecord.created_at.desc(), LicenseRecord.id.desc()),
    ).all():
        haystack = normalize_search_text(
            [
                record.subject_name,
                record.credit_code,
                record.legal_representative,
                record.remark,
                record.issue_date,
                record.expiry_date,
                record.image_name,
            ],
        )
        if normalized_query not in haystack:
            continue

        license_results.append(
            build_global_search_item(
                item_id=record.id,
                category="license_record",
                title=record.subject_name,
                subtitle=record.credit_code,
                detail=record.legal_representative or None,
                route="/licenses",
            ),
        )
        if len(license_results) >= limit_per_section:
            break

    for record in db.scalars(select(AccountUsageRecord).order_by(AccountUsageRecord.id.desc())).all():
        try:
            account_name = decrypt_account_usage_secret(record.account_name)
        except AccountPasswordEncryptionError:
            account_name = ""

        haystack = normalize_search_text(
            [
                account_name,
                record.phone_number,
                record.device_name,
                record.usage_notes,
                record.banned_reason,
            ],
        )
        if normalized_query not in haystack:
            continue

        account_results.append(
            build_global_search_item(
                item_id=record.id,
                category="account_usage_record",
                title=account_name or f"璐﹀彿璁板綍 #{record.id}",
                subtitle=record.phone_number or None,
                detail=record.device_name or None,
                route="/account-usage",
            ),
        )
        if len(account_results) >= limit_per_section:
            break

    for record in db.scalars(
        select(TaskBookkeepingRecord).order_by(TaskBookkeepingRecord.task_time.desc(), TaskBookkeepingRecord.id.desc()),
    ).all():
        order_no = build_task_bookkeeping_order_no(record)
        haystack = normalize_search_text(
            [
                order_no,
                record.shop_name,
                record.owner_name,
                record.note,
                record.task_time,
                record.principal_amount,
                record.commission_amount,
                record.gift_amount,
                record.order_count,
            ],
        )
        if normalized_query not in haystack:
            continue

        task_results.append(
            build_global_search_item(
                item_id=record.id,
                category="task_bookkeeping_record",
                title=f"{order_no} {record.shop_name}",
                subtitle=record.owner_name,
                detail=str(record.task_time),
                route="/task-bookkeeping/records",
            ),
        )
        if len(task_results) >= limit_per_section:
            break

    total = len(shop_results) + len(license_results) + len(account_results) + len(task_results)
    return {
        "query": query,
        "total": total,
        "shop_records": shop_results,
        "license_records": license_results,
        "account_usage_records": account_results,
        "task_bookkeeping_records": task_results,
    }


@app.get(
    "/dashboard/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard statistics",
)
def dashboard_stats(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    system_config = get_system_settings(db)
    dashboard_cache_key = f"dashboard:stats:{system_config['license_expiry_days']}"
    cached_payload = cache_get_json(dashboard_cache_key)
    if isinstance(cached_payload, dict):
        return cached_payload

    shop_record_count = db.scalar(select(func.count(ShopRecord.id))) or 0
    license_record_count = db.scalar(select(func.count(LicenseRecord.id))) or 0
    custom_fields = db.scalars(select(CustomField)).all()
    custom_field_count = len(custom_fields)
    admin_user_count = db.scalar(select(func.count(AdminUser.id))) or 0
    active_admin_count = db.scalar(
        select(func.count(AdminUser.id)).where(AdminUser.is_active.is_(True)),
    ) or 0
    revenue_total = db.scalar(select(func.coalesce(func.sum(ShopRecord.daily_revenue), 0.0))) or 0.0
    today = date_type.today()
    expiring_deadline = today + timedelta(days=int(system_config["license_expiry_days"]))
    expired_license_count = db.scalar(
        select(func.count(LicenseRecord.id)).where(
            LicenseRecord.expiry_date.is_not(None),
            LicenseRecord.expiry_date < today,
        ),
    ) or 0
    expiring_license_count = db.scalar(
        select(func.count(LicenseRecord.id)).where(
            LicenseRecord.expiry_date.is_not(None),
            LicenseRecord.expiry_date >= today,
            LicenseRecord.expiry_date <= expiring_deadline,
        ),
    ) or 0
    banned_account_count = db.scalar(
        select(func.count(AccountUsageRecord.id)).where(AccountUsageRecord.is_banned.is_(True)),
    ) or 0
    pending_task_count = db.scalar(
        select(func.count(TaskBookkeepingRecord.id)).where(TaskBookkeepingRecord.signed_status == "pending"),
    ) or 0
    pending_settlement_count = db.scalar(
        select(func.count(TaskBookkeepingRecord.id)).where(TaskBookkeepingRecord.settlement_status == "pending"),
    ) or 0

    recent_shop_records = db.scalars(
        select(ShopRecord).order_by(ShopRecord.id.desc()).limit(5),
    ).all()
    recent_license_records = db.scalars(
        select(LicenseRecord).order_by(LicenseRecord.created_at.desc(), LicenseRecord.id.desc()).limit(5),
    ).all()
    deposit_field_names = [field.field_name for field in custom_fields if is_deposit_field(field)]
    deposit_total = 0.0

    if deposit_field_names:
        all_shop_records = db.scalars(select(ShopRecord)).all()

        for item in all_shop_records:
            record_values = parse_record_values(item)

            for field_name in deposit_field_names:
                numeric_value = normalize_numeric_value(record_values.get(field_name))
                if numeric_value is None:
                    continue

                deposit_total += numeric_value
                break

    payload = {
        "shop_record_count": int(shop_record_count),
        "license_record_count": int(license_record_count),
        "custom_field_count": int(custom_field_count),
        "admin_user_count": int(admin_user_count),
        "active_admin_count": int(active_admin_count),
        "revenue_total": float(revenue_total),
        "deposit_total": float(deposit_total),
        "expired_license_count": int(expired_license_count),
        "expiring_license_count": int(expiring_license_count),
        "banned_account_count": int(banned_account_count),
        "pending_task_count": int(pending_task_count),
        "pending_settlement_count": int(pending_settlement_count),
        "recent_shop_records": [
            {
                "id": item.id,
                "shop_name": item.shop_name or "-",
                "platform": item.platform,
                "date": item.date,
                "daily_revenue": item.daily_revenue,
            }
            for item in recent_shop_records
        ],
        "recent_license_records": [
            {
                "id": item.id,
                "subject_name": item.subject_name,
                "credit_code": item.credit_code,
                "legal_representative": item.legal_representative,
                "expiry_date": item.expiry_date,
            }
            for item in recent_license_records
        ],
    }

    cache_set_json(dashboard_cache_key, payload, ttl_seconds=60)
    return payload


def build_system_alerts(db: Session) -> list[dict[str, Any]]:
    config = get_system_settings(db)
    acknowledgements = read_json_setting(db, SYSTEM_ALERT_ACK_KEY, {})
    if not isinstance(acknowledgements, dict):
        acknowledgements = {}
    alerts: list[dict[str, Any]] = []

    def add_alert(
        key: str,
        category: str,
        severity: str,
        title: str,
        description: str,
        route: str,
        occurred_at: datetime | None = None,
    ) -> None:
        ack = acknowledgements.get(key) if isinstance(acknowledgements.get(key), dict) else {}
        acknowledged_at = None
        if ack.get("at"):
            try:
                acknowledged_at = datetime.fromisoformat(str(ack["at"]))
            except ValueError:
                acknowledged_at = None
        alerts.append({
            "key": key, "category": category, "severity": severity, "title": title,
            "description": description, "route": route, "occurred_at": occurred_at,
            "acknowledged": bool(ack), "acknowledged_at": acknowledged_at,
            "acknowledged_by": ack.get("by") if ack else None,
        })

    if config["low_stock_alert_enabled"]:
        products = {item.id: item for item in db.scalars(select(WarehouseProduct).where(WarehouseProduct.is_active.is_(True))).all()}
        warehouses = {item.id: item for item in db.scalars(select(Warehouse)).all()}
        for stock in db.scalars(select(WarehouseStock)).all():
            product = products.get(stock.product_id)
            if product is None:
                continue
            available = stock.quantity - stock.locked_quantity
            if available <= product.warning_quantity:
                warehouse_name = warehouses.get(stock.warehouse_id).name if warehouses.get(stock.warehouse_id) else "未知仓库"
                add_alert(
                    f"inventory:{stock.warehouse_id}:{stock.product_id}", "inventory",
                    "critical" if available <= 0 else "warning", f"{product.name} 库存不足",
                    f"{warehouse_name} / SKU {product.sku}，可用 {available} {product.unit}，预警值 {product.warning_quantity}。",
                    "/warehouse/stock", stock.updated_at,
                )

    if config["pending_outbound_alert_enabled"]:
        pending_orders = db.scalars(
            select(WarehouseOutboundOrder).where(
                WarehouseOutboundOrder.status.not_in(["shipped", "cancelled"]),
            ).order_by(WarehouseOutboundOrder.created_at.asc()),
        ).all()
        for order in pending_orders:
            age_hours = max(0, int((datetime.utcnow() - order.created_at).total_seconds() // 3600))
            add_alert(
                f"outbound:{order.id}", "outbound", "critical" if age_hours >= 24 else "warning",
                f"出库单 {order.order_no} 待处理", f"当前状态 {order.status}，已等待约 {age_hours} 小时。",
                "/warehouse/outbound", order.created_at,
            )

    today = date_type.today()
    expiry_deadline = today + timedelta(days=int(config["license_expiry_days"]))
    licenses = db.scalars(
        select(LicenseRecord).where(
            LicenseRecord.expiry_date.is_not(None), LicenseRecord.expiry_date <= expiry_deadline,
        ).order_by(LicenseRecord.expiry_date.asc()),
    ).all()
    for record in licenses:
        days_left = (record.expiry_date - today).days
        add_alert(
            f"license:{record.id}", "license", "critical" if days_left < 0 else "warning",
            f"{record.subject_name} {'执照已过期' if days_left < 0 else '执照即将到期'}",
            f"到期日期 {record.expiry_date.isoformat()}，{'已过期 ' + str(abs(days_left)) + ' 天' if days_left < 0 else '剩余 ' + str(days_left) + ' 天'}。",
            "/licenses", datetime.combine(record.expiry_date, datetime.min.time()),
        )

    if config["task_alert_enabled"]:
        cutoff = datetime.utcnow() - timedelta(days=int(config["stale_task_days"]))
        tasks = db.scalars(
            select(TaskBookkeepingRecord).where(
                TaskBookkeepingRecord.task_time <= cutoff,
                (TaskBookkeepingRecord.signed_status == "pending") | (TaskBookkeepingRecord.settlement_status == "pending"),
            ).order_by(TaskBookkeepingRecord.task_time.asc()),
        ).all()
        for task in tasks:
            pending_parts = []
            if task.signed_status == "pending": pending_parts.append("待签收")
            if task.settlement_status == "pending": pending_parts.append("待结算")
            add_alert(
                f"task:{task.id}", "task", "warning", f"{task.shop_name} 任务长时间未完成",
                f"负责人 {task.owner_name}，{'、'.join(pending_parts)}，任务时间 {task.task_time:%Y-%m-%d %H:%M}。",
                "/task-bookkeeping/records", task.task_time,
            )

    if config["security_alert_enabled"]:
        threshold = int(config["login_failure_threshold"])
        attempts = db.scalars(
            select(LoginAttempt).where(LoginAttempt.failed_count >= threshold).order_by(LoginAttempt.last_attempt_at.desc()),
        ).all()
        for attempt in attempts:
            locked = bool(attempt.locked_until and attempt.locked_until > datetime.utcnow())
            add_alert(
                f"security:{attempt.id}", "security", "critical" if locked else "warning",
                f"账号 {attempt.username} {'已被锁定' if locked else '连续登录失败'}",
                f"来源 IP {attempt.ip_address}，累计失败 {attempt.failed_count} 次。",
                "/audit-logs", attempt.last_attempt_at,
            )

    if config["data_alert_enabled"]:
        # SQLite returns Date columns through func.max() as text; normalise before doing date math.
        def as_report_date(value: Any) -> date_type | None:
            if value is None or isinstance(value, date_type):
                return value
            try:
                return date_type.fromisoformat(str(value)[:10])
            except ValueError:
                return None

        profit_stale_days = int(config["profit_stale_days"])
        latest_profit_date = as_report_date(db.scalar(select(func.max(DingTalkProfitRecord.report_date))))

        if latest_profit_date is None:
            add_alert(
                "data:profit-empty", "data", "critical", "钉钉利润数据为空",
                "系统里没有任何钉钉利润记录，请确认机器人是否正常接收群消息并同步。",
                "/dingtalk-profits", None,
            )
        else:
            lag_days = (today - latest_profit_date).days
            if lag_days > profit_stale_days:
                add_alert(
                    "data:profit-stale", "data",
                    "critical" if lag_days > profit_stale_days * 2 else "warning",
                    "钉钉利润数据已停止更新",
                    f"最新记录日期为 {latest_profit_date.isoformat()}，距今 {lag_days} 天没有新数据"
                    f"（预警阈值 {profit_stale_days} 天）。请检查机器人是否正常接收群消息。",
                    "/dingtalk-profits", datetime.combine(latest_profit_date, datetime.min.time()),
                )

            # Per-store silence: a global date check stays blind when one store goes quiet
            # while the others keep reporting.
            store_rows = db.execute(
                select(
                    DingTalkProfitRecord.store_name,
                    func.max(DingTalkProfitRecord.report_date),
                ).group_by(DingTalkProfitRecord.store_name),
            ).all()
            active_since = today - timedelta(days=30)
            for store_name, raw_store_latest in store_rows:
                store_latest = as_report_date(raw_store_latest)
                # Skip stores with no recent history at all - closed, not broken.
                if store_latest is None or store_latest < active_since:
                    continue
                store_lag = (today - store_latest).days
                if store_lag > profit_stale_days:
                    add_alert(
                        f"data:profit-store-stale:{store_name}", "data", "warning",
                        f"{store_name} 已停止上报利润",
                        f"该店铺最新记录为 {store_latest.isoformat()}，距今 {store_lag} 天没有新数据，"
                        f"但其他店铺仍在正常上报。",
                        "/dingtalk-profits", datetime.combine(store_latest, datetime.min.time()),
                    )

        # Stock carrying quantity but no cost price understates 库存成本 on the dashboard.
        cost_products = {item.id: item for item in db.scalars(select(WarehouseProduct)).all()}
        cost_warehouses = {item.id: item for item in db.scalars(select(Warehouse)).all()}
        for stock in db.scalars(select(WarehouseStock).where(WarehouseStock.quantity > 0)).all():
            product = cost_products.get(stock.product_id)
            if product is None or product.cost_price:
                continue
            warehouse = cost_warehouses.get(stock.warehouse_id)
            warehouse_label = warehouse.name if warehouse else "未知仓库"
            add_alert(
                f"data:stock-cost:{stock.warehouse_id}:{stock.product_id}", "data", "warning",
                f"{product.name} 缺少成本价",
                f"{warehouse_label} / SKU {product.sku} 结存 {stock.quantity} "
                f"{product.unit}，但成本价为空或 0，库存成本统计会偏低。",
                "/warehouse/stock", stock.updated_at,
            )

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda item: (item["acknowledged"], severity_order[item["severity"]], item["occurred_at"] or datetime.min))
    return alerts


@app.get("/system-alerts", response_model=SystemAlertListResponse, summary="List current system alerts")
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


@app.patch("/system-alerts/{alert_key:path}", response_model=SystemAlertListResponse, summary="Acknowledge or reopen an alert")
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


def resolve_expense_categories(db: Session) -> tuple[list[str], bool]:
    stored = read_json_setting(db, EXPENSE_CATEGORIES_KEY, None)
    if not isinstance(stored, list):
        return list(DEFAULT_EXPENSE_CATEGORIES), True
    cleaned: list[str] = []
    for item in stored:
        name = str(item or "").strip()
        if name and name not in cleaned:
            cleaned.append(name)
    if not cleaned:
        return list(DEFAULT_EXPENSE_CATEGORIES), True
    return cleaned, False


def build_expense_category_usage(db: Session) -> dict[str, int]:
    usage: dict[str, int] = {}
    for model in (CompanyExpenseRecord, PersonalExpenseRecord):
        rows = db.execute(
            select(model.category, func.count(model.id)).group_by(model.category),
        ).all()
        for name, count in rows:
            key = str(name or "").strip()
            if not key:
                continue
            usage[key] = usage.get(key, 0) + int(count or 0)
    return usage


def build_expense_category_payload(db: Session) -> dict[str, Any]:
    categories, is_default = resolve_expense_categories(db)
    usage = build_expense_category_usage(db)
    return {
        "categories": categories,
        "is_default": is_default,
        "usage": usage,
        "orphan_categories": sorted(name for name in usage if name not in categories),
    }


@app.get(
    "/expense-categories",
    response_model=ExpenseCategoryListResponse,
    summary="List configurable expense categories",
)
def list_expense_categories(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    return build_expense_category_payload(db)


@app.put(
    "/expense-categories",
    response_model=ExpenseCategoryListResponse,
    summary="Replace expense categories (handles rename, reorder, add and remove)",
)
def replace_expense_categories(
    payload: ExpenseCategoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    write_json_setting(db, EXPENSE_CATEGORIES_KEY, payload.categories)
    commit_session(db, default_detail="Failed to save expense categories")
    return build_expense_category_payload(db)


@app.delete(
    "/expense-categories",
    response_model=ExpenseCategoryListResponse,
    summary="Reset expense categories back to the built-in defaults",
)
def reset_expense_categories(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    write_json_setting(db, EXPENSE_CATEGORIES_KEY, list(DEFAULT_EXPENSE_CATEGORIES))
    commit_session(db, default_detail="Failed to reset expense categories")
    return build_expense_category_payload(db)


@app.get(
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


@app.get(
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


@app.get("/system-settings", response_model=SystemSettingsResponse, summary="Read system settings")
def read_system_settings(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("superadmin")),
):
    return get_system_settings(db)


@app.put("/system-settings", response_model=SystemSettingsResponse, summary="Update system settings")
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


@app.post(
    "/auth/change-password",
    response_model=CurrentUserResponse,
    summary="Change current admin password",
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="褰撳墠瀵嗙爜閿欒")

    current_user.password_hash = hash_password(payload.new_password)
    commit_session(db, default_detail="Failed to change password")

    clear_user_sessions(db, current_user.id)
    create_session_cookie(current_user, response, db, request=request)
    return serialize_current_user(current_user)


@app.patch(
    "/auth/profile",
    response_model=CurrentUserResponse,
    summary="Update current admin profile",
)
def update_current_user_profile(
    payload: CurrentUserProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    existing_user = db.scalar(
        select(AdminUser).where(
            AdminUser.username == payload.username,
            AdminUser.id != current_user.id,
        ),
    )
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="账号已存在")

    current_user.username = payload.username
    current_user.display_name = payload.display_name
    author_name = build_admin_user_public_name(current_user)
    authored_links = db.scalars(select(SavedLink).where(SavedLink.author_user_id == current_user.id)).all()
    for link in authored_links:
        link.author_username = author_name

    commit_session(
        db,
        default_detail="Failed to update profile",
        integrity_detail="账号已存在",
    )
    db.refresh(current_user)
    return serialize_current_user(current_user)


@app.get(
    "/auth/me/avatar-file",
    summary="Download current admin avatar",
)
def get_current_user_avatar_file(current_user: AdminUser = Depends(get_current_user)):
    if not current_user.avatar_path:
        raise HTTPException(status_code=404, detail="Avatar not found")

    image_file = (UPLOADS_DIR / current_user.avatar_path).resolve()
    uploads_root = UPLOADS_DIR.resolve()
    try:
        image_file.relative_to(uploads_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Avatar not found") from exc

    if not image_file.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")

    media_type, _ = mimetypes.guess_type(image_file.name)
    return FileResponse(
        image_file,
        media_type=media_type or "application/octet-stream",
        filename=current_user.avatar_name or image_file.name,
        content_disposition_type="inline",
    )


@app.get(
    "/admin-users/{user_id}/avatar-file",
    summary="Download admin avatar",
)
def get_admin_user_avatar_file(
    user_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    user = get_admin_user_or_404(db, user_id)
    if not user.avatar_path:
        raise HTTPException(status_code=404, detail="Avatar not found")

    image_file = (UPLOADS_DIR / user.avatar_path).resolve()
    uploads_root = UPLOADS_DIR.resolve()
    try:
        image_file.relative_to(uploads_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Avatar not found") from exc

    if not image_file.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")

    media_type, _ = mimetypes.guess_type(image_file.name)
    return FileResponse(
        image_file,
        media_type=media_type or "application/octet-stream",
        filename=user.avatar_name or image_file.name,
        content_disposition_type="inline",
    )


@app.post(
    "/auth/avatar",
    response_model=CurrentUserResponse,
    summary="Upload or replace current admin avatar",
)
async def upload_current_user_avatar(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    await save_admin_avatar(current_user, image)
    commit_session(db, default_detail="Failed to upload avatar")
    db.refresh(current_user)
    return serialize_current_user(current_user)


@app.delete(
    "/auth/avatar",
    response_model=CurrentUserResponse,
    summary="Delete current admin avatar",
)
def delete_current_user_avatar(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    if not current_user.avatar_path:
        raise HTTPException(status_code=404, detail="Avatar not found")

    clear_admin_avatar(current_user)
    commit_session(db, default_detail="Failed to delete avatar")
    db.refresh(current_user)
    return serialize_current_user(current_user)


@app.get(
    "/admin-users",
    response_model=list[AdminUserResponse],
    summary="List admin users",
)
def list_admin_users(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("superadmin")),
):
    stmt = (
        select(AdminUser)
        .where(AdminUser.role != "software")
        .order_by(AdminUser.created_at.desc(), AdminUser.id.desc())
    )
    return [serialize_admin_user(user) for user in db.scalars(stmt).all()]


@app.post(
    "/admin-users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create admin user",
)
def create_admin_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("superadmin")),
):
    existing_user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="账号已存在")

    db_user = AdminUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        permissions_json=normalize_admin_permissions(payload.role, payload.permissions),
        is_active=True,
    )
    db.add(db_user)
    commit_session(
        db,
        default_detail="Failed to create admin user",
        integrity_detail="账号已存在",
    )
    db.refresh(db_user)
    return serialize_admin_user(db_user)


@app.patch(
    "/admin-users/{user_id}",
    response_model=AdminUserResponse,
    summary="Update admin role and module permissions",
)
def update_admin_user_access(
    user_id: int,
    payload: AdminUserAccessUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("superadmin")),
):
    db_user = get_admin_user_or_404(db, user_id)

    if db_user.id == current_user.id and payload.role != "superadmin":
        raise HTTPException(status_code=400, detail="不能降低当前登录账号的超级管理员角色")

    if db_user.role == "superadmin" and payload.role != "superadmin":
        superadmin_count = db.scalar(
            select(func.count(AdminUser.id)).where(AdminUser.role == "superadmin"),
        ) or 0
        if superadmin_count <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个超级管理员")

    previous_role = db_user.role
    previous_permissions = resolve_admin_permissions(db_user)
    db_user.role = payload.role
    db_user.permissions_json = normalize_admin_permissions(payload.role, payload.permissions)
    write_audit_log(
        db,
        actor=current_user,
        action="admin_access_updated",
        resource_type="admin_user",
        resource_id=db_user.id,
        details={
            "target_username": db_user.username,
            "previous_role": previous_role,
            "role": payload.role,
            "previous_permissions": previous_permissions,
            "permissions": resolve_admin_permissions(db_user),
        },
    )
    commit_session(db, default_detail="Failed to update admin access")

    if db_user.id != current_user.id:
        clear_user_sessions(db, db_user.id)
    db.refresh(db_user)
    return serialize_admin_user(db_user)


@app.patch(
    "/admin-users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Enable or disable admin user",
)
def update_admin_user_status(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("superadmin")),
):
    db_user = get_admin_user_or_404(db, user_id)

    if db_user.id == current_user.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="涓嶈兘绂佺敤褰撳墠鐧诲綍璐﹀彿")

    if db_user.role == "superadmin" and not payload.is_active:
        active_superadmin_count = db.scalar(
            select(func.count(AdminUser.id)).where(
                AdminUser.role == "superadmin",
                AdminUser.is_active.is_(True),
            ),
        ) or 0
        if db_user.is_active and active_superadmin_count <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个启用的超级管理员")

    db_user.is_active = payload.is_active
    write_audit_log(
        db,
        actor=current_user,
        action="admin_status_updated",
        resource_type="admin_user",
        resource_id=db_user.id,
        details={
            "target_username": db_user.username,
            "is_active": payload.is_active,
        },
    )
    commit_session(db, default_detail="Failed to update admin status")

    if not payload.is_active:
        clear_user_sessions(db, db_user.id)

    db.refresh(db_user)
    return serialize_admin_user(db_user)


@app.patch(
    "/admin-users/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset an admin user's password",
)
def reset_admin_user_password(
    user_id: int,
    payload: AdminUserPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("superadmin")),
):
    db_user = get_admin_user_or_404(db, user_id)
    if db_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="请通过个人菜单中的修改密码功能修改当前账号密码")

    db_user.password_hash = hash_password(payload.new_password)
    write_audit_log(
        db,
        actor=current_user,
        action="admin_password_reset",
        resource_type="admin_user",
        resource_id=db_user.id,
        details={"target_username": db_user.username},
    )
    commit_session(db, default_detail="Failed to reset admin password")
    clear_user_sessions(db, db_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


UI_TABLE_SETTING_KEYS = {
    "shop-records-columns",
    "license-records-columns",
    "peer-shop-columns",
    "account-usage-columns",
    "mobile-device-columns",
    # Shared 常用功能 layout for the mobile home tab. Stored once for everyone so
    # every account sees the same grid; only superadmin may PUT it.
    "home-modules",
}


@app.get("/ui-settings/{setting_key}", summary="Read shared table settings")
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


@app.put("/ui-settings/{setting_key}", summary="Save shared table settings")
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


@app.get(
    "/custom-fields",
    response_model=list[FieldDefinitionResponse],
    summary="List table headers",
)
def list_fields(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    return list_field_definitions(db)


@app.post(
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


@app.patch(
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


@app.post(
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


@app.delete(
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


@app.post(
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


@app.post(
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


@app.get(
    "/dingtalk-profits/summary",
    response_model=DingTalkProfitSummaryResponse,
    summary="Get DingTalk profit sync summary",
)
def get_dingtalk_profit_summary(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    return build_dingtalk_profit_summary(db)


@app.get(
    "/dingtalk-profits/monthly-summary",
    response_model=list[DingTalkProfitMonthlySummaryResponse],
    summary="Get DingTalk profit monthly summary",
)
def get_dingtalk_profit_monthly_summary(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    return build_dingtalk_profit_monthly_summary(db)


@app.get(
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


@app.post(
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


@app.get(
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


@app.get(
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


@app.put(
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


@app.delete(
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


@app.post(
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


@app.post(
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


@app.get("/expense-shortcut/token", summary="Get Apple Shortcut bookkeeping token status")
def get_expense_shortcut_token_status(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    stored = read_expense_shortcut_setting(db, current_user.id)
    return {
        "enabled": bool(stored.get("token_hash")),
        "created_at": stored.get("created_at"),
        "endpoint": "/expense-shortcut/record",
    }


@app.post("/expense-shortcut/token", summary="Create or rotate Apple Shortcut bookkeeping token")
def create_expense_shortcut_token(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    raw_token = f"xse_{secrets.token_urlsafe(32)}"
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    write_expense_shortcut_setting(
        db,
        current_user.id,
        {"token_hash": hash_expense_shortcut_token(raw_token), "created_at": created_at},
    )
    write_audit_log(
        db,
        actor=current_user,
        action="expense_shortcut_token_rotated",
        resource_type="expense_shortcut_token",
        resource_id=current_user.id,
        details={"created_at": created_at},
    )
    commit_session(db, default_detail="Failed to create expense shortcut token")
    return {
        "enabled": True,
        "created_at": created_at,
        "endpoint": "/expense-shortcut/record",
        "token": raw_token,
    }


@app.delete("/expense-shortcut/token", summary="Revoke Apple Shortcut bookkeeping token")
def revoke_expense_shortcut_token(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    setting = get_expense_shortcut_setting(db, current_user.id)
    if setting is not None:
        db.delete(setting)
    write_audit_log(
        db,
        actor=current_user,
        action="expense_shortcut_token_revoked",
        resource_type="expense_shortcut_token",
        resource_id=current_user.id,
        details={},
    )
    commit_session(db, default_detail="Failed to revoke expense shortcut token")
    return {"enabled": False}


@app.post("/expense-shortcut/record", status_code=status.HTTP_201_CREATED, summary="Create expense from Apple Shortcuts")
def create_expense_from_shortcut(
    payload: ExpenseShortcutRecordRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_expense_shortcut_user),
):
    book = payload.book.strip().lower()
    record_date = payload.date or date_type.today()
    category = payload.category.strip()
    note = payload.note.strip()
    payment_account = payload.payment_account.strip() or "\u5feb\u6377\u6307\u4ee4"

    if book == "personal":
        transaction_type = payload.transaction_type.strip().lower()
        if transaction_type not in {"expense", "income"}:
            raise HTTPException(status_code=400, detail="\u4e2a\u4eba\u8d26\u672c\u7c7b\u578b\u53ea\u80fd\u662f expense \u6216 income")
        category = category or ("\u5176\u4ed6\u6536\u5165" if transaction_type == "income" else "\u65e5\u5e38\u6d88\u8d39")
        record = PersonalExpenseRecord(
            record_date=record_date,
            amount=payload.amount,
            transaction_type=transaction_type,
            category=category,
            payment_account=payment_account,
            description=note or category,
            owner_user_id=current_user.id,
            owner_name=build_admin_user_public_name(current_user),
        )
        db.add(record)
        commit_session(db, default_detail="Failed to create personal expense from shortcut")
        db.refresh(record)
        serialized_record = serialize_personal_expense(record)
        action = "personal_expense_created_from_shortcut"
        resource_type = "personal_expense"
        message = "\u4e2a\u4eba\u8bb0\u8d26\u6210\u529f"
    elif book == "company":
        if ROLE_LEVELS.get(current_user.role, 0) < ROLE_LEVELS["editor"]:
            raise HTTPException(status_code=403, detail="\u5f53\u524d\u8d26\u53f7\u6ca1\u6709\u516c\u53f8\u8bb0\u8d26\u6743\u9650")
        payment_type = payload.payment_type.strip().lower()
        if payment_type not in {"company", "employee"}:
            raise HTTPException(status_code=400, detail="\u516c\u53f8\u652f\u4ed8\u7c7b\u578b\u53ea\u80fd\u662f company \u6216 employee")
        category = category or "\u5176\u4ed6\u6d88\u8d39"
        record = CompanyExpenseRecord(
            expense_date=record_date,
            amount=payload.amount,
            category=category,
            payment_type=payment_type,
            payment_account=payment_account,
            expense_scope=payload.expense_scope.strip() or "\u516c\u5171\u8d39\u7528",
            description=note or category,
            approval_status="approved",
            reimbursement_status="not_required",
            submitter_user_id=current_user.id,
            submitter_name=build_admin_user_public_name(current_user),
        )
        db.add(record)
        commit_session(db, default_detail="Failed to create company expense from shortcut")
        db.refresh(record)
        serialized_record = serialize_company_expense(record)
        action = "company_expense_created_from_shortcut"
        resource_type = "company_expense"
        message = "\u516c\u53f8\u8bb0\u8d26\u6210\u529f"
    else:
        raise HTTPException(status_code=400, detail="\u8d26\u672c\u7c7b\u578b\u53ea\u80fd\u662f personal \u6216 company")

    write_audit_log(
        db,
        actor=current_user,
        action=action,
        resource_type=resource_type,
        resource_id=record.id,
        details=serialized_record,
    )
    commit_session(db, default_detail="Failed to record expense shortcut audit log")
    return {"success": True, "message": message, "book": book, "record": serialized_record}


@app.get(
    "/company-expenses/summary",
    response_model=CompanyExpenseSummaryResponse,
    summary="Get current-month company expense summary",
)
def get_company_expense_summary(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    today = date_type.today()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    records = db.scalars(
        select(CompanyExpenseRecord).where(
            CompanyExpenseRecord.expense_date >= month_start,
            CompanyExpenseRecord.expense_date < next_month,
        )
    ).all()
    return {
        "month_total": sum(float(record.amount or 0) for record in records if record.approval_status != "rejected"),
        "pending_approval_total": sum(float(record.amount or 0) for record in records if record.approval_status == "pending"),
        "pending_reimbursement_total": sum(float(record.amount or 0) for record in records if record.reimbursement_status == "pending"),
        "month_record_count": len(records),
    }


@app.get(
    "/company-expenses",
    response_model=list[CompanyExpenseResponse],
    summary="List company expenses",
)
def list_company_expenses(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    records = db.scalars(
        select(CompanyExpenseRecord).order_by(
            CompanyExpenseRecord.expense_date.desc(),
            CompanyExpenseRecord.id.desc(),
        )
    ).all()
    return [serialize_company_expense(record) for record in records]


@app.post(
    "/company-expenses",
    response_model=CompanyExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a company expense",
)
def create_company_expense(
    payload: CompanyExpenseCreate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    submitter_name = build_admin_user_public_name(current_user)
    record = CompanyExpenseRecord(
        expense_date=payload.expense_date,
        amount=payload.amount,
        category=payload.category,
        payment_type=payload.payment_type,
        payment_account=payload.payment_account,
        expense_scope=payload.expense_scope,
        description=payload.description,
        approval_status="approved",
        reimbursement_status="not_required",
        submitter_user_id=current_user.id,
        submitter_name=submitter_name,
    )
    db.add(record)
    commit_session(db, default_detail="Failed to create company expense")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="company_expense_created",
        resource_type="company_expense",
        resource_id=record.id,
        details=serialize_company_expense(record),
    )
    commit_session(db, default_detail="Failed to record company expense audit log")
    return serialize_company_expense(record)


@app.get(
    "/company-expenses/{record_id}",
    response_model=CompanyExpenseResponse,
    summary="Get a company expense",
)
def get_company_expense(
    record_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    return serialize_company_expense(get_company_expense_or_404(db, record_id))


@app.put(
    "/company-expenses/{record_id}",
    response_model=CompanyExpenseResponse,
    summary="Update a company expense",
)
def update_company_expense(
    record_id: int,
    payload: CompanyExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    record = get_company_expense_or_404(db, record_id)
    record.expense_date = payload.expense_date
    record.amount = payload.amount
    record.category = payload.category
    record.payment_type = payload.payment_type
    record.payment_account = payload.payment_account
    record.expense_scope = payload.expense_scope
    record.description = payload.description
    if payload.payment_type == "company":
        record.reimbursement_status = "not_required"
    elif record.reimbursement_status == "not_required":
        record.reimbursement_status = "pending"
    commit_session(db, default_detail="Failed to update company expense")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="company_expense_updated",
        resource_type="company_expense",
        resource_id=record.id,
        details=serialize_company_expense(record),
    )
    commit_session(db, default_detail="Failed to record company expense audit log")
    return serialize_company_expense(record)


@app.patch(
    "/company-expenses/{record_id}/status",
    response_model=CompanyExpenseResponse,
    summary="Review or reimburse a company expense",
)
def update_company_expense_status(
    record_id: int,
    payload: CompanyExpenseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    record = get_company_expense_or_404(db, record_id)
    record.approval_status = payload.approval_status
    if payload.reimbursement_status is not None:
        record.reimbursement_status = payload.reimbursement_status
    if record.payment_type == "company":
        record.reimbursement_status = "not_required"
    record.reviewer_name = build_admin_user_public_name(current_user)
    record.reviewed_at = datetime.utcnow()
    commit_session(db, default_detail="Failed to update company expense status")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="company_expense_status_updated",
        resource_type="company_expense",
        resource_id=record.id,
        details=serialize_company_expense(record),
    )
    commit_session(db, default_detail="Failed to record company expense audit log")
    return serialize_company_expense(record)


@app.post(
    "/company-expenses/{record_id}/attachment",
    response_model=CompanyExpenseResponse,
    summary="Upload or replace a company expense proof",
)
async def upload_company_expense_attachment(
    record_id: int,
    attachment: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    record = get_company_expense_or_404(db, record_id)
    await save_company_expense_attachment(record, attachment)
    commit_session(db, default_detail="Failed to upload company expense attachment")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="company_expense_attachment_uploaded",
        resource_type="company_expense",
        resource_id=record.id,
        details={"attachment_name": record.attachment_name},
    )
    commit_session(db, default_detail="Failed to record company expense attachment audit log")
    return serialize_company_expense(record)


@app.get(
    "/company-expenses/{record_id}/attachment-file",
    summary="Download a protected company expense proof",
)
def get_company_expense_attachment_file(
    record_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    record = get_company_expense_or_404(db, record_id)
    if not record.attachment_path:
        raise HTTPException(status_code=404, detail="该消费记录没有凭证")
    file_path = Path(record.attachment_path).resolve()
    upload_dir = COMPANY_EXPENSE_UPLOAD_DIR.resolve()
    if file_path.parent != upload_dir or not file_path.is_file():
        raise HTTPException(status_code=404, detail="消费凭证文件不存在")
    return FileResponse(
        file_path,
        filename=record.attachment_name or file_path.name,
        media_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
    )


@app.delete(
    "/company-expenses/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company expense",
)
def delete_company_expense(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    record = get_company_expense_or_404(db, record_id)
    backup_path = create_sqlite_backup("company-expense-delete")
    write_audit_log(
        db,
        actor=current_user,
        action="company_expense_deleted",
        resource_type="company_expense",
        resource_id=record.id,
        details={**serialize_company_expense(record), "backup_path": backup_path},
    )
    db.delete(record)
    commit_session(db, default_detail="Failed to delete company expense")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/personal-expenses/summary",
    response_model=PersonalExpenseSummaryResponse,
    summary="Get current user's personal expense summary",
)
def get_personal_expense_summary(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    today = date_type.today()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    records = db.scalars(
        select(PersonalExpenseRecord).where(
            PersonalExpenseRecord.owner_user_id == current_user.id,
            PersonalExpenseRecord.record_date >= month_start,
            PersonalExpenseRecord.record_date < next_month,
        )
    ).all()
    month_expense = sum(float(record.amount or 0) for record in records if record.transaction_type == "expense")
    month_income = sum(float(record.amount or 0) for record in records if record.transaction_type == "income")
    return {
        "month_expense": month_expense,
        "month_income": month_income,
        "month_balance": month_income - month_expense,
        "month_record_count": len(records),
    }


@app.get(
    "/personal-expenses",
    response_model=list[PersonalExpenseResponse],
    summary="List current user's personal expenses",
)
def list_personal_expenses(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    records = db.scalars(
        select(PersonalExpenseRecord)
        .where(PersonalExpenseRecord.owner_user_id == current_user.id)
        .order_by(PersonalExpenseRecord.record_date.desc(), PersonalExpenseRecord.id.desc())
    ).all()
    return [serialize_personal_expense(record) for record in records]


@app.post(
    "/personal-expenses",
    response_model=PersonalExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a personal expense entry",
)
def create_personal_expense(
    payload: PersonalExpenseCreate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    record = PersonalExpenseRecord(
        record_date=payload.record_date,
        amount=payload.amount,
        transaction_type=payload.transaction_type,
        category=payload.category,
        payment_account=payload.payment_account,
        description=payload.description,
        owner_user_id=current_user.id,
        owner_name=build_admin_user_public_name(current_user),
    )
    db.add(record)
    commit_session(db, default_detail="Failed to create personal expense")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="personal_expense_created",
        resource_type="personal_expense",
        resource_id=record.id,
        details=serialize_personal_expense(record),
    )
    commit_session(db, default_detail="Failed to record personal expense audit log")
    return serialize_personal_expense(record)


@app.get(
    "/personal-expenses/{record_id}",
    response_model=PersonalExpenseResponse,
    summary="Get a personal expense entry",
)
def get_personal_expense(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    return serialize_personal_expense(get_personal_expense_or_404(db, record_id, current_user))


@app.put(
    "/personal-expenses/{record_id}",
    response_model=PersonalExpenseResponse,
    summary="Update a personal expense entry",
)
def update_personal_expense(
    record_id: int,
    payload: PersonalExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    record = get_personal_expense_or_404(db, record_id, current_user)
    record.record_date = payload.record_date
    record.amount = payload.amount
    record.transaction_type = payload.transaction_type
    record.category = payload.category
    record.payment_account = payload.payment_account
    record.description = payload.description
    commit_session(db, default_detail="Failed to update personal expense")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="personal_expense_updated",
        resource_type="personal_expense",
        resource_id=record.id,
        details=serialize_personal_expense(record),
    )
    commit_session(db, default_detail="Failed to record personal expense audit log")
    return serialize_personal_expense(record)


@app.post(
    "/personal-expenses/{record_id}/attachment",
    response_model=PersonalExpenseResponse,
    summary="Upload a personal expense proof",
)
async def upload_personal_expense_attachment(
    record_id: int,
    attachment: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    record = get_personal_expense_or_404(db, record_id, current_user)
    await save_personal_expense_attachment(record, attachment)
    commit_session(db, default_detail="Failed to upload personal expense attachment")
    db.refresh(record)
    write_audit_log(
        db,
        actor=current_user,
        action="personal_expense_attachment_uploaded",
        resource_type="personal_expense",
        resource_id=record.id,
        details={"attachment_name": record.attachment_name},
    )
    commit_session(db, default_detail="Failed to record personal expense attachment audit log")
    return serialize_personal_expense(record)


@app.get(
    "/personal-expenses/{record_id}/attachment-file",
    summary="Download current user's personal expense proof",
)
def get_personal_expense_attachment_file(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    record = get_personal_expense_or_404(db, record_id, current_user)
    if not record.attachment_path:
        raise HTTPException(status_code=404, detail="???????????")
    file_path = Path(record.attachment_path).resolve()
    upload_dir = PERSONAL_EXPENSE_UPLOAD_DIR.resolve()
    if file_path.parent != upload_dir or not file_path.is_file():
        raise HTTPException(status_code=404, detail="???????????")
    return FileResponse(
        file_path,
        filename=record.attachment_name or file_path.name,
        media_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
    )


@app.delete(
    "/personal-expenses/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a personal expense entry",
)
def delete_personal_expense(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("viewer")),
):
    record = get_personal_expense_or_404(db, record_id, current_user)
    backup_path = create_sqlite_backup("personal-expense-delete")
    write_audit_log(
        db,
        actor=current_user,
        action="personal_expense_deleted",
        resource_type="personal_expense",
        resource_id=record.id,
        details={**serialize_personal_expense(record), "backup_path": backup_path},
    )
    db.delete(record)
    commit_session(db, default_detail="Failed to delete personal expense")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
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


@app.delete(
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


@app.post(
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


@app.get(
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


@app.delete(
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


@app.post(
    "/saved-links",
    response_model=SavedLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved link",
)
def create_saved_link(
    payload: SavedLinkCreate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    payload_data = payload.model_dump()
    payload_data["url"] = resolve_saved_link_primary_url(payload_data.get("url"), payload_data.get("description"))
    db_record = SavedLink(
        **payload_data,
        author_user_id=current_user.id,
        author_username=build_admin_user_public_name(current_user),
    )
    db.add(db_record)
    commit_session(db, default_detail="Failed to create saved link")
    db.refresh(db_record)
    write_audit_log(
        db,
        actor=current_user,
        action="saved_link_created",
        resource_type="saved_link",
        resource_id=db_record.id,
        details=serialize_saved_link(db_record, db),
    )
    commit_session(db, default_detail="Failed to record audit log")
    return serialize_saved_link(db_record, db)


@app.get(
    "/saved-links",
    response_model=list[SavedLinkResponse],
    summary="List all saved links",
)
def list_saved_links(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    stmt = select(SavedLink).order_by(
        SavedLink.is_pinned.desc(),
        SavedLink.sort_order.asc(),
        SavedLink.updated_at.desc(),
        SavedLink.id.desc(),
    )
    return [serialize_saved_link(record, db) for record in db.scalars(stmt).all()]


@app.put(
    "/saved-links/{link_id}",
    response_model=SavedLinkResponse,
    summary="Update a saved link",
)
def update_saved_link(
    link_id: int,
    payload: SavedLinkUpdate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    payload_data = payload.model_dump(exclude_unset=True)
    if "url" in payload_data or "description" in payload_data:
        payload_data["url"] = resolve_saved_link_primary_url(payload_data.get("url"), payload_data.get("description"))
    for key, value in payload_data.items():
        setattr(db_record, key, value)

    commit_session(db, default_detail="Failed to update saved link")
    db.refresh(db_record)
    write_audit_log(
        db,
        actor=current_user,
        action="saved_link_updated",
        resource_type="saved_link",
        resource_id=db_record.id,
        details=serialize_saved_link(db_record, db),
    )
    commit_session(db, default_detail="Failed to record audit log")
    return serialize_saved_link(db_record, db)


@app.post(
    "/saved-links/{link_id}/pin",
    response_model=SavedLinkResponse,
    summary="Pin a saved link",
)
def pin_saved_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    db_record.is_pinned = True
    commit_session(db, default_detail="Failed to pin saved link")
    db.refresh(db_record)
    write_audit_log(
        db,
        actor=current_user,
        action="saved_link_pinned",
        resource_type="saved_link",
        resource_id=db_record.id,
        details=serialize_saved_link(db_record, db),
    )
    commit_session(db, default_detail="Failed to record saved-link pin audit log")
    return serialize_saved_link(db_record, db)


@app.delete(
    "/saved-links/{link_id}/pin",
    response_model=SavedLinkResponse,
    summary="Unpin a saved link",
)
def unpin_saved_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    db_record.is_pinned = False
    commit_session(db, default_detail="Failed to unpin saved link")
    db.refresh(db_record)
    write_audit_log(
        db,
        actor=current_user,
        action="saved_link_unpinned",
        resource_type="saved_link",
        resource_id=db_record.id,
        details=serialize_saved_link(db_record, db),
    )
    commit_session(db, default_detail="Failed to record saved-link unpin audit log")
    return serialize_saved_link(db_record, db)


@app.post(
    "/saved-links/{link_id}/push",
    response_model=SavedLinkResponse,
    summary="Push a saved link to DingTalk or schedule it",
)
def push_saved_link(
    link_id: int,
    payload: SavedLinkPushRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)

    scheduled_at = normalize_saved_link_schedule_datetime(payload.scheduled_at)
    now = get_saved_link_local_now()

    # Validate the robot configuration before accepting either immediate or scheduled pushes.
    get_dingtalk_robot_request_url()

    if scheduled_at is not None and scheduled_at > now:
        set_saved_link_push_state(
            db_record,
            status=SAVED_LINK_PUSH_STATUS_SCHEDULED,
            scheduled_at=scheduled_at,
            sent_at=None,
            error_text=None,
        )
        commit_session(db, default_detail="Failed to schedule saved-link push")
        db.refresh(db_record)
        write_audit_log(
            db,
            actor=current_user,
            action="saved_link_push_scheduled",
            resource_type="saved_link",
            resource_id=db_record.id,
            details=serialize_saved_link(db_record, db),
        )
        commit_session(db, default_detail="Failed to record saved-link scheduling audit log")
        return serialize_saved_link(db_record, db)

    trigger_time = scheduled_at or now
    set_saved_link_push_state(
        db_record,
        status=SAVED_LINK_PUSH_STATUS_SENDING,
        scheduled_at=trigger_time,
        sent_at=None,
        error_text=None,
    )
    commit_session(db, default_detail="Failed to prepare saved-link push")

    try:
        push_saved_link_to_dingtalk(db_record)
    except HTTPException as exc:
        set_saved_link_push_state(
            db_record,
            status=SAVED_LINK_PUSH_STATUS_FAILED,
            scheduled_at=trigger_time,
            sent_at=None,
            error_text=str(exc.detail),
        )
        commit_session(db, default_detail="Failed to persist saved-link push failure state")
        write_audit_log(
            db,
            actor=current_user,
            action="saved_link_push_failed",
            resource_type="saved_link",
            resource_id=db_record.id,
            details=serialize_saved_link(db_record, db),
        )
        commit_session(db, default_detail="Failed to record saved-link push failure audit log")
        raise

    set_saved_link_push_state(
        db_record,
        status=SAVED_LINK_PUSH_STATUS_SENT,
        scheduled_at=trigger_time,
        sent_at=get_saved_link_local_now(),
        error_text=None,
    )
    commit_session(db, default_detail="Failed to persist saved-link push success state")
    db.refresh(db_record)
    write_audit_log(
        db,
        actor=current_user,
        action="saved_link_pushed",
        resource_type="saved_link",
        resource_id=db_record.id,
        details=serialize_saved_link(db_record, db),
    )
    commit_session(db, default_detail="Failed to record saved-link push audit log")
    return serialize_saved_link(db_record, db)


@app.get(
    "/saved-links/{link_id}/images/{image_name}",
    summary="Download a protected saved-link image",
)
def get_saved_link_image_file(
    link_id: int,
    image_name: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    db_record = get_saved_link_or_404(db, link_id)
    image_entry = next(
        (item for item in get_saved_link_images(db_record) if Path(str(item.get("path") or "")).name == image_name),
        None,
    )
    if image_entry is None:
        raise HTTPException(status_code=404, detail="Saved-link image not found")

    image_file = (UPLOADS_DIR / str(image_entry["path"])).resolve()
    uploads_root = UPLOADS_DIR.resolve()
    try:
        image_file.relative_to(uploads_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Saved-link image not found") from exc

    if not image_file.is_file():
        raise HTTPException(status_code=404, detail="Saved-link image not found")

    media_type, _ = mimetypes.guess_type(image_file.name)
    return FileResponse(
        image_file,
        media_type=media_type or "application/octet-stream",
        filename=str(image_entry.get("name") or image_file.name),
        content_disposition_type="inline",
    )


@app.post(
    "/saved-links/{link_id}/images",
    response_model=SavedLinkResponse,
    summary="Upload or replace saved-link images",
)
async def upload_saved_link_images(
    link_id: int,
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    await save_saved_link_images(db_record, images)
    commit_session(db, default_detail="Failed to upload saved-link images")
    db.refresh(db_record)
    return serialize_saved_link(db_record, db)


@app.post(
    "/saved-links/{link_id}/images/append",
    response_model=SavedLinkResponse,
    summary="Append saved-link images",
)
async def append_saved_link_images_endpoint(
    link_id: int,
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    await append_saved_link_images(db_record, images)
    commit_session(db, default_detail="Failed to append saved-link images")
    db.refresh(db_record)
    return serialize_saved_link(db_record, db)


@app.post(
    "/saved-links/{link_id}/image",
    response_model=SavedLinkResponse,
    summary="Upload or replace a saved-link image",
)
async def upload_saved_link_image(
    link_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    await save_saved_link_images(db_record, [image])
    commit_session(db, default_detail="Failed to upload saved-link image")
    db.refresh(db_record)
    return serialize_saved_link(db_record, db)


@app.put(
    "/saved-links/{link_id}/images/{image_name}",
    response_model=SavedLinkResponse,
    summary="Replace a saved-link image",
)
async def replace_saved_link_image_endpoint(
    link_id: int,
    image_name: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    await replace_saved_link_image(db_record, image_name, image)
    commit_session(db, default_detail="Failed to replace saved-link image")
    db.refresh(db_record)
    return serialize_saved_link(db_record, db)


@app.delete(
    "/saved-links/{link_id}/images/{image_name}",
    response_model=SavedLinkResponse,
    summary="Delete a saved-link image",
)
def delete_saved_link_image_endpoint(
    link_id: int,
    image_name: str,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    remove_saved_link_image(db_record, image_name)
    commit_session(db, default_detail="Failed to delete saved-link image")
    db.refresh(db_record)
    return serialize_saved_link(db_record, db)


@app.delete(
    "/saved-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved link",
)
def delete_saved_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    db_record = get_saved_link_or_404(db, link_id)
    ensure_saved_link_write_access(db_record, current_user)
    write_audit_log(
        db,
        actor=current_user,
        action="saved_link_deleted",
        resource_type="saved_link",
        resource_id=db_record.id,
        details=serialize_saved_link(db_record, db),
    )
    delete_saved_link_image_file(db_record)
    db.delete(db_record)
    commit_session(db, default_detail="Failed to delete saved link")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
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


@app.post(
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


@app.get(
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


@app.get(
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


@app.put(
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


@app.delete(
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


@app.patch(
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


@app.post(
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


@app.post(
    "/account-usage-records",
    response_model=AccountUsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account usage record",
)
def create_account_usage_record(
    payload: AccountUsageRecordCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("editor")),
):
    values = payload.model_dump()
    values["extra_fields"] = dump_json_object(values.get("extra_fields") or {})
    values["account_name"] = encrypt_account_usage_secret(values.get("account_name")) or ""
    values["password"] = encrypt_account_password(values.get("password"))
    db_record = AccountUsageRecord(**values)
    db.add(db_record)
    commit_session(db, default_detail="Failed to create account usage record")
    db.refresh(db_record)
    return serialize_account_usage_record(db_record)


@app.get(
    "/account-usage-records",
    response_model=list[AccountUsageRecordResponse],
    summary="List all account usage records",
)
def list_account_usage_records(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    stmt = select(AccountUsageRecord).order_by(AccountUsageRecord.id.desc())
    records = db.scalars(stmt).all()
    return [serialize_account_usage_record(record) for record in records]


@app.get(
    "/account-usage-records/{record_id}",
    response_model=AccountUsageRecordResponse,
    summary="Get an account usage record by ID",
)
def get_account_usage_record(
    record_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("viewer")),
):
    return serialize_account_usage_record(get_account_usage_record_or_404(db, record_id))


@app.get(
    "/account-usage-records/{record_id}/edit-detail",
    response_model=AccountUsageRecordResponse,
    summary="Get full account usage record for editing",
)
def get_account_usage_record_edit_detail(
    record_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("superadmin")),
):
    return serialize_account_usage_record(
        get_account_usage_record_or_404(db, record_id),
        mask_account_name_value=False,
    )


@app.put(
    "/account-usage-records/{record_id}",
    response_model=AccountUsageRecordResponse,
    summary="Update an account usage record",
)
def update_account_usage_record(
    record_id: int,
    payload: AccountUsageRecordUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_role("editor")),
):
    db_record = get_account_usage_record_or_404(db, record_id)
    for key, value in payload.model_dump().items():
        if key == "account_name" and value is None:
            continue
        if key == "password" and value is None:
            continue
        if key == "account_name":
            value = encrypt_account_usage_secret(value) or db_record.account_name
        if key == "password":
            value = encrypt_account_password(value)
        if key == "extra_fields":
            value = dump_json_object(value or {})
        setattr(db_record, key, value)

    commit_session(db, default_detail="Failed to update account usage record")
    db.refresh(db_record)
    return serialize_account_usage_record(db_record)


@app.delete(
    "/account-usage-records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account usage record",
)
def delete_account_usage_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    db_record = get_account_usage_record_or_404(db, record_id)
    write_audit_log(
        db,
        actor=current_user,
        action="account_usage_record_deleted",
        resource_type="account_usage_record",
        resource_id=db_record.id,
        details={
            "phone_number": db_record.phone_number,
            "device_name": db_record.device_name,
            "is_banned": db_record.is_banned,
        },
    )
    db.delete(db_record)
    commit_session(db, default_detail="Failed to delete account usage record")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.patch(
    "/account-usage-records/batch-status",
    response_model=BatchActionResponse,
    summary="Batch update account usage record banned status",
)
def batch_update_account_usage_status(
    payload: AccountUsageBatchStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    stmt = select(AccountUsageRecord).where(AccountUsageRecord.id.in_(payload.record_ids))
    records = db.scalars(stmt).all()
    if len(records) != len(set(payload.record_ids)):
        raise HTTPException(status_code=404, detail="One or more account usage records were not found")

    for record in records:
        record.is_banned = payload.is_banned

    write_audit_log(
        db,
        actor=current_user,
        action="account_usage_status_batch_updated",
        resource_type="account_usage_record",
        details={
            "record_ids": [record.id for record in records],
            "is_banned": payload.is_banned,
        },
    )
    commit_session(db, default_detail="Failed to batch update account usage records")
    return {"updated_count": len(records)}


@app.post(
    "/account-usage-records/batch-delete",
    response_model=BatchActionResponse,
    summary="Batch delete account usage records",
)
def batch_delete_account_usage_records(
    payload: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("editor")),
):
    stmt = select(AccountUsageRecord).where(AccountUsageRecord.id.in_(payload.record_ids))
    records = db.scalars(stmt).all()
    if len(records) != len(set(payload.record_ids)):
        raise HTTPException(status_code=404, detail="One or more account usage records were not found")

    backup_path = create_sqlite_backup("account-usage-batch-delete")
    write_audit_log(
        db,
        actor=current_user,
        action="account_usage_records_batch_deleted",
        resource_type="account_usage_record",
        details={
            "record_ids": [record.id for record in records],
            "backup_path": backup_path,
        },
    )

    for record in records:
        db.delete(record)

    commit_session(db, default_detail="Failed to batch delete account usage records")
    return {"updated_count": len(records)}


@app.post(
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


@app.get(
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


@app.get(
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


@app.put(
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


@app.delete(
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


@app.post(
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


@app.post(
    "/account-usage-records/{record_id}/reveal-account-name",
    response_model=AccountUsageAccountNameRevealResponse,
    summary="Reveal account name after admin password verification",
)
def reveal_account_usage_account_name(
    record_id: int,
    payload: AccountUsagePasswordRevealRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("superadmin")),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前登录密码错误")

    db_record = get_account_usage_record_or_404(db, record_id)
    try:
        account_name = decrypt_account_usage_secret(db_record.account_name)
    except AccountPasswordEncryptionError as exc:
        raise HTTPException(status_code=500, detail="Failed to decrypt account name") from exc

    write_audit_log(
        db,
        actor=current_user,
        action="account_name_revealed",
        resource_type="account_usage_record",
        resource_id=db_record.id,
    )
    commit_session(db, default_detail="Failed to record audit log")
    return {"account_name": account_name}


@app.post(
    "/account-usage-records/{record_id}/reveal-password",
    response_model=AccountUsagePasswordRevealResponse,
    summary="Reveal account password after admin password verification",
)
def reveal_account_usage_password(
    record_id: int,
    payload: AccountUsagePasswordRevealRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_role("superadmin")),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前登录密码错误")

    db_record = get_account_usage_record_or_404(db, record_id)
    try:
        password = decrypt_account_password(db_record.password)
    except AccountPasswordEncryptionError as exc:
        raise HTTPException(status_code=500, detail="Failed to decrypt account password") from exc

    write_audit_log(
        db,
        actor=current_user,
        action="account_password_revealed",
        resource_type="account_usage_record",
        resource_id=db_record.id,
    )
    commit_session(db, default_detail="Failed to record audit log")
    return {"password": password}


@app.post(
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


@app.get(
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


@app.get(
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


@app.get(
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


@app.put(
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


@app.delete(
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


@app.post(
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


@app.post(
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


@app.delete(
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
