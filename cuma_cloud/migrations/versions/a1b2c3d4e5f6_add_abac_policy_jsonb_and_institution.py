"""add_abac_policy_jsonb_and_institution

Revision ID: a1b2c3d4e5f6
Revises: f26419c854dc
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f26419c854dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add institution_id to cloud_accounts
    op.add_column("cloud_accounts", sa.Column("institution_id", sa.String(255), nullable=True))
    op.create_index("ix_cloud_accounts_institution_id", "cloud_accounts", ["institution_id"], unique=False)

    # Drop old abac_policies indexes and columns, add new schema
    op.drop_index("idx_abac_account_subject", table_name="abac_policies")
    op.drop_index("idx_abac_account_resource", table_name="abac_policies")

    op.add_column("abac_policies", sa.Column("institution_id", sa.String(255), nullable=True))
    op.add_column("abac_policies", sa.Column("policy_name", sa.String(255), nullable=True))
    op.add_column("abac_policies", sa.Column("resource_type", sa.String(255), nullable=True))
    op.add_column("abac_policies", sa.Column("rules", JSONB, nullable=True))
    op.add_column("abac_policies", sa.Column("version", sa.Integer(), nullable=True))

    # Migrate: set defaults for new columns from old data (for existing rows)
    # conditions was Text; we wrap action as allowed_actions and use {} for conditions
    op.execute(
        """
        UPDATE abac_policies SET
            policy_name = COALESCE(subject, 'legacy'),
            resource_type = COALESCE(resource, 'legacy'),
            rules = jsonb_build_object(
                'allowed_actions', jsonb_build_array(action),
                'conditions', '{}'::jsonb
            ),
            version = 1
        WHERE policy_name IS NULL
        """
    )

    op.drop_column("abac_policies", "subject")
    op.drop_column("abac_policies", "resource")
    op.drop_column("abac_policies", "action")
    op.drop_column("abac_policies", "conditions")

    op.alter_column(
        "abac_policies",
        "policy_name",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.alter_column(
        "abac_policies",
        "resource_type",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.alter_column(
        "abac_policies",
        "rules",
        existing_type=JSONB,
        nullable=False,
    )
    op.alter_column(
        "abac_policies",
        "version",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("1"),
    )

    op.create_index("idx_abac_institution", "abac_policies", ["institution_id"], unique=False)
    op.create_index("idx_abac_account_resource", "abac_policies", ["account_id", "resource_type"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_abac_account_resource", table_name="abac_policies")
    op.drop_index("idx_abac_institution", table_name="abac_policies")

    op.add_column("abac_policies", sa.Column("subject", sa.String(255), nullable=True))
    op.add_column("abac_policies", sa.Column("resource", sa.String(255), nullable=True))
    op.add_column("abac_policies", sa.Column("action", sa.String(64), nullable=True))
    op.add_column("abac_policies", sa.Column("conditions", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE abac_policies SET
            subject = policy_name,
            resource = resource_type,
            action = COALESCE(rules->'allowed_actions'->>0, 'read'),
            conditions = (rules->'conditions')::text
        """
    )

    op.drop_column("abac_policies", "institution_id")
    op.drop_column("abac_policies", "policy_name")
    op.drop_column("abac_policies", "resource_type")
    op.drop_column("abac_policies", "rules")
    op.drop_column("abac_policies", "version")

    op.alter_column("abac_policies", "subject", nullable=False)
    op.alter_column("abac_policies", "resource", nullable=False)
    op.alter_column("abac_policies", "action", nullable=False)

    op.create_index("idx_abac_account_resource", "abac_policies", ["account_id", "resource"], unique=False)
    op.create_index("idx_abac_account_subject", "abac_policies", ["account_id", "subject"], unique=False)

    op.drop_index("ix_cloud_accounts_institution_id", table_name="cloud_accounts")
    op.drop_column("cloud_accounts", "institution_id")
