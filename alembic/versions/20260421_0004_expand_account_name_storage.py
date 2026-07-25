"""expand account name storage for encrypted values

Revision ID: 20260421_0004
Revises: 20260421_0003
Create Date: 2026-04-21 03:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260421_0004"
down_revision = "20260421_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("AccountUsageRecord") as batch_op:
        batch_op.alter_column(
            "account_name",
            existing_type=sa.String(length=100),
            type_=sa.String(length=512),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("AccountUsageRecord") as batch_op:
        batch_op.alter_column(
            "account_name",
            existing_type=sa.String(length=512),
            type_=sa.String(length=100),
            existing_nullable=False,
        )
