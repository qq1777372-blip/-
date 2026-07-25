import re
from datetime import date as date_type, datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


FieldType = Literal["text", "number", "date"]
RoleType = Literal["software", "viewer", "editor", "superadmin"]
AdminRoleType = Literal["viewer", "editor", "superadmin"]
AccountType = Literal["staff", "developer", "admin", "viewer"]
TaskStatusType = Literal["pending", "completed"]
SavedLinkPushStatusType = Literal["idle", "scheduled", "sending", "sent", "failed"]


class ShopRecordPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict, description="Field values keyed by field_name")

    @field_validator("values", mode="before")
    @classmethod
    def validate_values(cls, value: Any) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if isinstance(value, dict):
            return value
        raise ValueError("values must be an object")


class ShopRecordCreate(ShopRecordPayload):
    pass


class ShopRecordUpdate(ShopRecordPayload):
    pass


class ShopRecordResponse(ShopRecordPayload):
    id: int


class DingTalkProfitSyncRecord(BaseModel):
    source_record_id: int = Field(..., ge=1)
    report_date: date_type
    store_name: str = Field(..., min_length=1, max_length=100)
    profit: float
    reporter_name: str = Field(..., min_length=1, max_length=50)
    reporter_id: str | None = Field(default=None, max_length=100)
    batch_id: str | None = Field(default=None, max_length=64)
    source_message_id: str | None = Field(default=None, max_length=100)
    source_create_time: datetime | None = None
    source_update_time: datetime | None = None

    @field_validator(
        "store_name",
        "reporter_name",
        "reporter_id",
        "batch_id",
        "source_message_id",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("store_name", "reporter_name")
    @classmethod
    def ensure_required_text(cls, value: str | None) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized


class DingTalkProfitSyncBatchRequest(BaseModel):
    records: list[DingTalkProfitSyncRecord] = Field(default_factory=list, min_length=1)


class DingTalkProfitDeleteBatchRequest(BaseModel):
    source_record_ids: list[int] = Field(default_factory=list, min_length=1)


class DingTalkProfitSyncBatchResponse(BaseModel):
    inserted_count: int
    updated_count: int
    total_count: int


class DingTalkProfitDeleteBatchResponse(BaseModel):
    deleted_count: int


class DingTalkProfitRecordResponse(BaseModel):
    id: int
    source_record_id: int
    report_date: date_type
    store_name: str
    profit: float
    reporter_name: str
    reporter_id: str | None = None
    batch_id: str | None = None
    source_message_id: str | None = None
    source_create_time: datetime | None = None
    source_update_time: datetime | None = None
    synced_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DingTalkProfitSummaryResponse(BaseModel):
    total_records: int
    total_profit: float
    unique_store_count: int
    unique_reporter_count: int
    latest_report_date: date_type | None = None
    latest_sync_time: datetime | None = None


class DingTalkProfitMonthlySummaryResponse(BaseModel):
    month: str
    total_profit: float
    record_count: int
    store_count: int
    reporter_count: int
    latest_report_date: date_type | None = None


class BatchDeleteRequest(BaseModel):
    record_ids: list[int] = Field(default_factory=list, min_length=1)


class BatchActionResponse(BaseModel):
    updated_count: int


class AuditLogResponse(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_username: str | None = None
    action: str
    resource_type: str
    resource_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class LicenseRecordBase(BaseModel):
    subject_name: str = Field(..., min_length=1, max_length=120)
    credit_code: str = Field(..., min_length=1, max_length=50)
    legal_representative: str | None = Field(default=None, max_length=50)
    issue_date: date_type | None = Field(default=None)
    expiry_date: date_type | None = Field(default=None)
    remark: str | None = Field(default=None)
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("subject_name", "credit_code", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("legal_representative", "remark", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip()
        return normalized or None


class LicenseRecordCreate(LicenseRecordBase):
    pass


class LicenseRecordUpdate(LicenseRecordBase):
    pass


class LicenseRecordResponse(LicenseRecordBase):
    id: int
    created_at: datetime
    image_url: str | None = None
    image_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PeerShopBase(BaseModel):
    shop_name: str = Field(..., min_length=1, max_length=120)
    shop_url: str | None = Field(default=None, max_length=1000)
    remark: str | None = Field(default=None)

    @field_validator("shop_name", mode="before")
    @classmethod
    def normalize_required_shop_name(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("shop_url", "remark", mode="before")
    @classmethod
    def normalize_optional_peer_shop_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None

    @field_validator("shop_url")
    @classmethod
    def validate_shop_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must start with http:// or https://")
        return value


class PeerShopCreate(PeerShopBase):
    pass


class PeerShopUpdate(PeerShopBase):
    pass


class PeerShopResponse(PeerShopBase):
    id: int
    created_at: datetime
    image_url: str | None = None
    image_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AccountUsageRecordBase(BaseModel):
    account_name: str = Field(..., min_length=1, max_length=100)
    password: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    device_name: str | None = Field(default=None, max_length=50)
    usage_notes: str | None = Field(default=None)
    is_banned: bool = Field(default=False)
    banned_reason: str | None = Field(default=None, max_length=255)

    @field_validator("account_name", mode="before")
    @classmethod
    def normalize_account_name(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("account_name cannot be empty")
        return normalized

    @field_validator("password", "phone_number", "device_name", "usage_notes", "banned_reason", mode="before")
    @classmethod
    def normalize_optional_account_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None


class AccountUsageRecordCreate(AccountUsageRecordBase):
    pass


class AccountUsageRecordUpdate(BaseModel):
    account_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    device_name: str | None = Field(default=None, max_length=50)
    usage_notes: str | None = Field(default=None)
    is_banned: bool = Field(default=False)
    banned_reason: str | None = Field(default=None, max_length=255)

    @field_validator("account_name", mode="before")
    @classmethod
    def normalize_optional_account_name(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None

    @field_validator("password", "phone_number", "device_name", "usage_notes", "banned_reason", mode="before")
    @classmethod
    def normalize_optional_update_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None


class AccountUsageRecordResponse(BaseModel):
    account_name: str
    phone_number: str | None = None
    device_name: str | None = None
    usage_notes: str | None = None
    is_banned: bool
    banned_reason: str | None = None
    id: int
    has_password: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountUsagePasswordRevealRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)


class AccountUsagePasswordRevealResponse(BaseModel):
    password: str | None


class AccountUsageAccountNameRevealResponse(BaseModel):
    account_name: str | None


class AccountUsageBatchStatusUpdateRequest(BaseModel):
    record_ids: list[int] = Field(default_factory=list, min_length=1)
    is_banned: bool


class MobileDeviceRecordBase(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=100)
    primary_card: str | None = Field(default=None, max_length=50)
    secondary_card: str | None = Field(default=None, max_length=50)
    remark: str | None = Field(default=None)

    @field_validator("device_name", mode="before")
    @classmethod
    def normalize_device_name(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("device_name cannot be empty")
        return normalized

    @field_validator("primary_card", "secondary_card", "remark", mode="before")
    @classmethod
    def normalize_optional_mobile_device_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None


class MobileDeviceRecordCreate(MobileDeviceRecordBase):
    pass


class MobileDeviceRecordUpdate(MobileDeviceRecordBase):
    pass


class MobileDeviceRecordResponse(BaseModel):
    id: int
    device_name: str
    primary_card: str | None = None
    secondary_card: str | None = None
    remark: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBookkeepingNamedEntityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class TaskBookkeepingShopCreate(TaskBookkeepingNamedEntityBase):
    pass


class TaskBookkeepingShopResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBookkeepingOwnerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class TaskBookkeepingOwnerResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBookkeepingRecordBase(BaseModel):
    task_time: datetime | None = Field(default=None)
    shop_name: str = Field(..., min_length=1, max_length=100)
    owner_name: str = Field(..., min_length=1, max_length=50)
    principal_amount: float = Field(default=0, ge=0)
    order_count: int = Field(default=1, ge=1)
    commission_amount: float = Field(default=0, ge=0)
    gift_amount: float = Field(default=0, ge=0)
    signed_status: TaskStatusType = Field(default="pending")
    settlement_status: TaskStatusType = Field(default="pending")
    note: str | None = Field(default=None)

    @field_validator("shop_name", "owner_name", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("note", mode="before")
    @classmethod
    def normalize_optional_note(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None


class TaskBookkeepingRecordCreate(TaskBookkeepingRecordBase):
    pass


class TaskBookkeepingRecordUpdate(TaskBookkeepingRecordBase):
    pass


class TaskBookkeepingRecordResponse(TaskBookkeepingRecordBase):
    id: int
    order_no: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBookkeepingBatchStatusUpdateRequest(BaseModel):
    record_ids: list[int] = Field(default_factory=list, min_length=1)
    field: Literal["signed_status", "settlement_status"]
    value: TaskStatusType


class TaskBookkeepingBatchDeleteRequest(BaseModel):
    record_ids: list[int] = Field(default_factory=list, min_length=1)


class TaskBookkeepingBatchActionResponse(BaseModel):
    updated_count: int


class TaskBookkeepingSummaryResponse(BaseModel):
    total_records: int
    unsettled_principal_total: float
    commission_total: float
    gift_total: float
    principal_total: float
    pending_signed_count: int
    pending_settlement_count: int
    recent_records: list[TaskBookkeepingRecordResponse]


class SavedLinkBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    url: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=100000)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_pinned: bool = Field(default=False)

    @field_validator("title", "category", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("title")
    @classmethod
    def ensure_title_not_empty(cls, value: str | None) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("title cannot be empty")
        return normalized

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must start with http:// or https://")
        return value


class SavedLinkCreate(SavedLinkBase):
    pass


class SavedLinkUpdate(SavedLinkBase):
    pass


class SavedLinkPushRequest(BaseModel):
    scheduled_at: datetime | None = None

    @field_validator("scheduled_at", mode="before")
    @classmethod
    def normalize_scheduled_at(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        return value


class SavedLinkImageResponse(BaseModel):
    name: str | None = None
    url: str
    storage_name: str


class SavedLinkResponse(SavedLinkBase):
    id: int
    images: list[SavedLinkImageResponse] = Field(default_factory=list)
    image_url: str | None = None
    image_name: str | None = None
    author_user_id: int
    author_username: str
    author_avatar_url: str | None = None
    push_status: SavedLinkPushStatusType = "idle"
    push_scheduled_at: datetime | None = None
    push_sent_at: datetime | None = None
    push_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FieldDefinitionCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=50, description="Column label")
    field_name: str | None = Field(default=None, max_length=50, description="Optional field key")
    field_type: FieldType = Field(default="text", description="Field type")
    required: bool = Field(default=False, description="Whether the field is required")

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("label cannot be empty")
        return normalized

    @field_validator("field_name")
    @classmethod
    def normalize_field_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().lower()
        if not normalized:
            return None

        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", normalized):
            raise ValueError("field_name must start with a letter and contain only letters, numbers, and underscores")
        return normalized


class FieldDefinitionUpdate(BaseModel):
    required: bool | None = None
    is_visible: bool | None = None


class FieldDefinitionReorderRequest(BaseModel):
    field_ids: list[int] = Field(default_factory=list, min_length=1)


class FieldDefinitionResponse(BaseModel):
    id: int
    field_name: str
    label: str
    field_type: FieldType
    required: bool
    sort_order: int
    is_visible: bool
    is_builtin: bool

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    captcha_id: str = Field(..., min_length=1, max_length=128)
    captcha_code: str = Field(..., min_length=1, max_length=16)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty")
        return normalized

    @field_validator("captcha_id")
    @classmethod
    def normalize_captcha_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("captcha_id cannot be empty")
        return normalized

    @field_validator("captcha_code")
    @classmethod
    def normalize_captcha_code(cls, value: str) -> str:
        normalized = re.sub(r"\s+", "", value).strip().upper()
        if not normalized:
            raise ValueError("captcha_code cannot be empty")
        return normalized


class LoginCaptchaResponse(BaseModel):
    captcha_id: str
    image_data: str
    expires_in_seconds: int


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    role: RoleType = Field(default="editor")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty")
        return normalized


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class CurrentUserProfileUpdateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    display_name: str | None = Field(default=None, max_length=50)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty")
        return normalized

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip()
        return normalized or None


class AdminUserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    role: RoleType = Field(default="editor")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty")
        return normalized


class AdminUserStatusUpdateRequest(BaseModel):
    is_active: bool


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: AdminRoleType
    account_type: AccountType
    is_active: bool
    avatar_url: str | None = None
    avatar_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminSessionResponse(BaseModel):
    id: int
    ip_address: str
    user_agent: str
    device_name: str
    created_at: datetime
    expires_at: datetime
    is_current: bool = False


class AdminUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: RoleType
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SoftwareAuthDevicePayload(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=128)
    device_name: str | None = Field(default=None, max_length=128)
    platform: str = Field(default="windows", max_length=32)
    app_version: str | None = Field(default=None, max_length=50)

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("device_id cannot be empty")
        return normalized

    @field_validator("device_name", "app_version", mode="before")
    @classmethod
    def normalize_optional_device_text(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: Any) -> str:
        normalized = str(value or "windows").strip().lower()
        return normalized or "windows"


class SoftwareRegisterRequest(SoftwareAuthDevicePayload):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty")
        return normalized


class SoftwareLoginRequest(SoftwareAuthDevicePayload):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty")
        return normalized


class SoftwareActivateRequest(SoftwareAuthDevicePayload):
    license_key: str = Field(..., min_length=1, max_length=80)

    @field_validator("license_key")
    @classmethod
    def normalize_license_key(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("license_key cannot be empty")
        return normalized


class SoftwareUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: RoleType
    account_type: AccountType
    is_active: bool
    is_activated: bool
    license_key: str | None = None
    plan_name: str | None = None
    license_status: str | None = None
    activated_at: datetime | None = None
    expire_at: datetime | None = None
    last_validated_at: datetime | None = None


class SoftwareAuthResponse(BaseModel):
    token: str
    token_expires_at: datetime
    user: SoftwareUserResponse
    message: str = ""


class DashboardRecentShopRecord(BaseModel):
    id: int
    shop_name: str
    platform: str | None = None
    date: date_type | None = None
    daily_revenue: float | None = None


class DashboardRecentLicenseRecord(BaseModel):
    id: int
    subject_name: str
    credit_code: str
    legal_representative: str | None = None
    expiry_date: date_type | None = None


class GlobalSearchResultItem(BaseModel):
    id: int
    category: Literal["shop_record", "license_record", "account_usage_record", "task_bookkeeping_record"]
    title: str
    subtitle: str | None = None
    detail: str | None = None
    route: str


class GlobalSearchResponse(BaseModel):
    query: str
    total: int
    shop_records: list[GlobalSearchResultItem]
    license_records: list[GlobalSearchResultItem]
    account_usage_records: list[GlobalSearchResultItem]
    task_bookkeeping_records: list[GlobalSearchResultItem]


class DashboardStatsResponse(BaseModel):
    shop_record_count: int
    license_record_count: int
    custom_field_count: int
    admin_user_count: int
    active_admin_count: int
    revenue_total: float
    deposit_total: float
    expired_license_count: int
    expiring_license_count: int
    banned_account_count: int
    pending_task_count: int
    pending_settlement_count: int
    recent_shop_records: list[DashboardRecentShopRecord]
    recent_license_records: list[DashboardRecentLicenseRecord]


class ServerServiceStatusResponse(BaseModel):
    name: str
    display_name: str
    active_state: str
    sub_state: str
    description: str
    is_active: bool


class ServerDatabaseStatusResponse(BaseModel):
    name: str
    source: str
    relative_path: str
    category: str
    status: str
    error_message: str | None
    main_size_bytes: int
    sidecar_size_bytes: int
    size_bytes: int
    modified_at: datetime


class ServerStatusResponse(BaseModel):
    generated_at: datetime
    health: str
    hostname: str
    operating_system: str
    architecture: str
    cpu_count: int
    cpu_percent: float | None
    load_1m: float | None
    load_5m: float | None
    load_15m: float | None
    memory_total_bytes: int
    memory_used_bytes: int
    memory_available_bytes: int
    memory_percent: float
    disk_total_bytes: int
    disk_used_bytes: int
    disk_free_bytes: int
    disk_percent: float
    system_uptime_seconds: int | None
    process_uptime_seconds: int
    process_id: int
    database_engine: str
    database_connection_status: str
    database_latency_ms: float | None
    database_error: str | None
    database_count: int
    database_total_size_bytes: int
    active_database_total_size_bytes: int
    backup_database_total_size_bytes: int
    services: list[ServerServiceStatusResponse]
    databases: list[ServerDatabaseStatusResponse]
