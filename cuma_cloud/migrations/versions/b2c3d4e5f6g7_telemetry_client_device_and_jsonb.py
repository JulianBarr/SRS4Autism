"""telemetry_client_device_and_jsonb

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16

Add client_device_id and convert payload to JSONB for Phase 4 telemetry sync.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_device_id (required for new syncs; default for existing rows)
    op.add_column(
        "telemetry_sync_logs",
        sa.Column("client_device_id", sa.String(255), nullable=True),
    )
    op.execute(
        "UPDATE telemetry_sync_logs SET client_device_id = 'legacy' WHERE client_device_id IS NULL"
    )
    op.alter_column(
        "telemetry_sync_logs",
        "client_device_id",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.create_index(
        "idx_telemetry_client_device",
        "telemetry_sync_logs",
        ["client_device_id"],
        unique=False,
    )

    # Convert payload from Text to JSONB (null/empty -> null; valid JSON -> jsonb)
    op.alter_column(
        "telemetry_sync_logs",
        "payload",
        existing_type=sa.Text(),
        type_=JSONB(),
        postgresql_using="CASE WHEN payload IS NULL OR trim(payload) = '' THEN NULL ELSE payload::jsonb END",
    )


def downgrade() -> None:
    op.drop_index("idx_telemetry_client_device", table_name="telemetry_sync_logs")
    op.drop_column("telemetry_sync_logs", "client_device_id")

    op.alter_column(
        "telemetry_sync_logs",
        "payload",
        existing_type=JSONB,
        type_=sa.Text(),
        postgresql_using="payload::text",
    )
