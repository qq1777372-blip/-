"""expand account password storage for encrypted values

Revision ID: 20260421_0003
Revises: 20260418_0002
Create Date: 2026-04-21 02:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260421_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("AccountUsageRecord") as batch_op:
        batch_op.alter_column(
            "password",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("AccountUsageRecord") as batch_op:
        batch_op.alter_column(
            "password",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
