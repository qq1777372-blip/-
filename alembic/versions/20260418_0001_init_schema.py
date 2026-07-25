"""initial schema

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "AdminSession",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_AdminSession_expires_at"), "AdminSession", ["expires_at"], unique=False)
    op.create_index(op.f("ix_AdminSession_id"), "AdminSession", ["id"], unique=False)
    op.create_index(op.f("ix_AdminSession_token_hash"), "AdminSession", ["token_hash"], unique=True)
    op.create_index(op.f("ix_AdminSession_user_id"), "AdminSession", ["user_id"], unique=False)

    op.create_table(
        "AdminUser",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_AdminUser_id"), "AdminUser", ["id"], unique=False)
    op.create_index(op.f("ix_AdminUser_username"), "AdminUser", ["username"], unique=True)

    op.create_table(
        "AppSetting",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "CustomField",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("field_type", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_name"),
        sa.UniqueConstraint("label"),
    )
    op.create_index(op.f("ix_CustomField_field_name"), "CustomField", ["field_name"], unique=True)
    op.create_index(op.f("ix_CustomField_id"), "CustomField", ["id"], unique=False)

    op.create_table(
        "LicenseRecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_name", sa.String(length=120), nullable=False),
        sa.Column("credit_code", sa.String(length=50), nullable=False),
        sa.Column("legal_representative", sa.String(length=50), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("image_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credit_code"),
    )
    op.create_index(op.f("ix_LicenseRecord_credit_code"), "LicenseRecord", ["credit_code"], unique=True)
    op.create_index(op.f("ix_LicenseRecord_expiry_date"), "LicenseRecord", ["expiry_date"], unique=False)
    op.create_index(op.f("ix_LicenseRecord_id"), "LicenseRecord", ["id"], unique=False)
    op.create_index(op.f("ix_LicenseRecord_issue_date"), "LicenseRecord", ["issue_date"], unique=False)
    op.create_index(op.f("ix_LicenseRecord_subject_name"), "LicenseRecord", ["subject_name"], unique=False)

    op.create_table(
        "LoginAttempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", "ip_address", name="uq_login_attempt_username_ip"),
    )
    op.create_index(op.f("ix_LoginAttempt_id"), "LoginAttempt", ["id"], unique=False)
    op.create_index(op.f("ix_LoginAttempt_ip_address"), "LoginAttempt", ["ip_address"], unique=False)
    op.create_index(op.f("ix_LoginAttempt_locked_until"), "LoginAttempt", ["locked_until"], unique=False)
    op.create_index(op.f("ix_LoginAttempt_username"), "LoginAttempt", ["username"], unique=False)

    op.create_table(
        "ShopRecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_name", sa.String(length=100), nullable=True),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("daily_revenue", sa.Float(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("extra_fields", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("record_data", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ShopRecord_date"), "ShopRecord", ["date"], unique=False)
    op.create_index(op.f("ix_ShopRecord_id"), "ShopRecord", ["id"], unique=False)
    op.create_index(op.f("ix_ShopRecord_platform"), "ShopRecord", ["platform"], unique=False)
    op.create_index(op.f("ix_ShopRecord_shop_name"), "ShopRecord", ["shop_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ShopRecord_shop_name"), table_name="ShopRecord")
    op.drop_index(op.f("ix_ShopRecord_platform"), table_name="ShopRecord")
    op.drop_index(op.f("ix_ShopRecord_id"), table_name="ShopRecord")
    op.drop_index(op.f("ix_ShopRecord_date"), table_name="ShopRecord")
    op.drop_table("ShopRecord")

    op.drop_index(op.f("ix_LoginAttempt_username"), table_name="LoginAttempt")
    op.drop_index(op.f("ix_LoginAttempt_locked_until"), table_name="LoginAttempt")
    op.drop_index(op.f("ix_LoginAttempt_ip_address"), table_name="LoginAttempt")
    op.drop_index(op.f("ix_LoginAttempt_id"), table_name="LoginAttempt")
    op.drop_table("LoginAttempt")

    op.drop_index(op.f("ix_LicenseRecord_subject_name"), table_name="LicenseRecord")
    op.drop_index(op.f("ix_LicenseRecord_issue_date"), table_name="LicenseRecord")
    op.drop_index(op.f("ix_LicenseRecord_id"), table_name="LicenseRecord")
    op.drop_index(op.f("ix_LicenseRecord_expiry_date"), table_name="LicenseRecord")
    op.drop_index(op.f("ix_LicenseRecord_credit_code"), table_name="LicenseRecord")
    op.drop_table("LicenseRecord")

    op.drop_index(op.f("ix_CustomField_id"), table_name="CustomField")
    op.drop_index(op.f("ix_CustomField_field_name"), table_name="CustomField")
    op.drop_table("CustomField")

    op.drop_table("AppSetting")

    op.drop_index(op.f("ix_AdminUser_username"), table_name="AdminUser")
    op.drop_index(op.f("ix_AdminUser_id"), table_name="AdminUser")
    op.drop_table("AdminUser")

    op.drop_index(op.f("ix_AdminSession_user_id"), table_name="AdminSession")
    op.drop_index(op.f("ix_AdminSession_token_hash"), table_name="AdminSession")
    op.drop_index(op.f("ix_AdminSession_id"), table_name="AdminSession")
    op.drop_index(op.f("ix_AdminSession_expires_at"), table_name="AdminSession")
    op.drop_table("AdminSession")

