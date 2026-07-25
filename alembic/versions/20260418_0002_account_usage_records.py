"""add account usage record table

Revision ID: 20260418_0002
Revises: 20260418_0001
Create Date: 2026-04-18 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_0002"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "AccountUsageRecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=100), nullable=False),
        sa.Column("password", sa.String(length=100), nullable=True),
        sa.Column("phone_number", sa.String(length=30), nullable=True),
        sa.Column("device_name", sa.String(length=50), nullable=True),
        sa.Column("usage_notes", sa.Text(), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False),
        sa.Column("banned_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_AccountUsageRecord_account_name"), "AccountUsageRecord", ["account_name"], unique=False)
    op.create_index(op.f("ix_AccountUsageRecord_id"), "AccountUsageRecord", ["id"], unique=False)
    op.create_index(op.f("ix_AccountUsageRecord_phone_number"), "AccountUsageRecord", ["phone_number"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_AccountUsageRecord_phone_number"), table_name="AccountUsageRecord")
    op.drop_index(op.f("ix_AccountUsageRecord_id"), table_name="AccountUsageRecord")
    op.drop_index(op.f("ix_AccountUsageRecord_account_name"), table_name="AccountUsageRecord")
    op.drop_table("AccountUsageRecord")
