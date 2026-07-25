from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint

from app.core.database import Base


APP_LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def local_now() -> datetime:
    return datetime.now(APP_LOCAL_TIMEZONE).replace(tzinfo=None)


class ShopRecord(Base):
    __tablename__ = "ShopRecord"

    id = Column(Integer, primary_key=True, index=True)
    shop_name = Column(String(100), nullable=True, index=True)
    platform = Column(String(50), nullable=True, index=True)
    daily_revenue = Column(Float, nullable=True)
    remark = Column(Text, nullable=True)
    date = Column(Date, nullable=True, index=True)
    extra_fields = Column(Text, nullable=False, default="{}")
    record_data = Column(Text, nullable=False, default="{}")


class DingTalkProfitRecord(Base):
    __tablename__ = "DingTalkProfitRecord"
    __table_args__ = (
        UniqueConstraint("source_record_id", name="uq_dingtalk_profit_source_record_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_record_id = Column(Integer, nullable=False, index=True)
    report_date = Column(Date, nullable=False, index=True)
    store_name = Column(String(100), nullable=False, index=True)
    profit = Column(Float, nullable=False, default=0)
    reporter_name = Column(String(50), nullable=False, index=True)
    reporter_id = Column(String(100), nullable=True, index=True)
    batch_id = Column(String(64), nullable=True, index=True)
    source_message_id = Column(String(100), nullable=True, index=True)
    source_create_time = Column(DateTime, nullable=True)
    source_update_time = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LicenseRecord(Base):
    __tablename__ = "LicenseRecord"

    id = Column(Integer, primary_key=True, index=True)
    subject_name = Column(String(120), nullable=False, index=True)
    credit_code = Column(String(50), nullable=False, unique=True, index=True)
    legal_representative = Column(String(50), nullable=True)
    issue_date = Column(Date, nullable=True, index=True)
    expiry_date = Column(Date, nullable=True, index=True)
    remark = Column(Text, nullable=True)
    extra_fields = Column(Text, nullable=False, default="{}")
    image_path = Column(String(255), nullable=True)
    image_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PeerShop(Base):
    __tablename__ = "PeerShop"

    id = Column(Integer, primary_key=True, index=True)
    shop_name = Column(String(120), nullable=False, index=True)
    shop_url = Column(String(1000), nullable=True)
    remark = Column(Text, nullable=True)
    image_path = Column(String(255), nullable=True)
    image_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AccountUsageRecord(Base):
    __tablename__ = "AccountUsageRecord"

    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String(512), nullable=False, index=True)
    password = Column(Text, nullable=True)
    phone_number = Column(String(30), nullable=True, index=True)
    device_name = Column(String(50), nullable=True)
    usage_notes = Column(Text, nullable=True)
    is_banned = Column(Boolean, nullable=False, default=False)
    banned_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MobileDeviceRecord(Base):
    __tablename__ = "MobileDeviceRecord"

    id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(100), nullable=False, index=True)
    primary_card = Column(String(50), nullable=True)
    secondary_card = Column(String(50), nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TaskBookkeepingShop(Base):
    __tablename__ = "TaskBookkeepingShop"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TaskBookkeepingOwner(Base):
    __tablename__ = "TaskBookkeepingOwner"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TaskBookkeepingRecord(Base):
    __tablename__ = "TaskBookkeepingRecord"

    id = Column(Integer, primary_key=True, index=True)
    task_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    shop_name = Column(String(100), nullable=False, index=True)
    owner_name = Column(String(50), nullable=False, index=True)
    principal_amount = Column(Float, nullable=False, default=0)
    order_count = Column(Integer, nullable=False, default=1)
    commission_amount = Column(Float, nullable=False, default=0)
    gift_amount = Column(Float, nullable=False, default=0)
    signed_status = Column(String(20), nullable=False, default="pending", index=True)
    settlement_status = Column(String(20), nullable=False, default="pending", index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavedLink(Base):
    __tablename__ = "SavedLink"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False, index=True)
    url = Column(String(1000), nullable=False, default="")
    category = Column(String(50), nullable=True, index=True)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    is_pinned = Column(Boolean, nullable=False, default=False, index=True)
    images_json = Column(Text, nullable=False, default="[]")
    image_path = Column(String(255), nullable=True)
    image_name = Column(String(255), nullable=True)
    author_user_id = Column(Integer, nullable=False, index=True)
    author_username = Column(String(50), nullable=False, index=True)
    push_status = Column(String(20), nullable=False, default="idle", index=True)
    push_scheduled_at = Column(DateTime, nullable=True, index=True)
    push_sent_at = Column(DateTime, nullable=True)
    push_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=local_now)
    updated_at = Column(DateTime, nullable=False, default=local_now, onupdate=local_now)


class CustomField(Base):
    __tablename__ = "CustomField"

    id = Column(Integer, primary_key=True, index=True)
    field_name = Column(String(50), nullable=False, unique=True, index=True)
    label = Column(String(50), nullable=False, unique=True)
    field_type = Column(String(20), nullable=False, default="text")
    required = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_visible = Column(Boolean, nullable=False, default=True)
    is_builtin = Column(Boolean, nullable=False, default=False)


class AppSetting(Base):
    __tablename__ = "AppSetting"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")


class AdminUser(Base):
    __tablename__ = "AdminUser"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="superadmin")
    is_active = Column(Boolean, nullable=False, default=True)
    avatar_path = Column(String(255), nullable=True)
    avatar_name = Column(String(255), nullable=True)
    software_license_key = Column(String(80), nullable=True, index=True)
    software_plan_name = Column(String(100), nullable=True)
    software_license_status = Column(String(20), nullable=True)
    software_activated_at = Column(DateTime, nullable=True)
    software_expire_at = Column(DateTime, nullable=True, index=True)
    software_last_validated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AdminSession(Base):
    __tablename__ = "AdminSession"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    ip_address = Column(String(64), nullable=False, default="unknown")
    user_agent = Column(String(255), nullable=False, default="unknown")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)


class LoginAttempt(Base):
    __tablename__ = "LoginAttempt"
    __table_args__ = (
        UniqueConstraint("username", "ip_address", name="uq_login_attempt_username_ip"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    ip_address = Column(String(64), nullable=False, index=True)
    failed_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True, index=True)
    last_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_username = Column(String(50), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, index=True)
    resource_id = Column(Integer, nullable=True, index=True)
    details_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
