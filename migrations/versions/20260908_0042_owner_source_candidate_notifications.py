"""Add owner source candidate notification attempts.

Revision ID: 20260908_0042
Revises: 20260906_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "20260908_0042"
down_revision: str | None = "20260906_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_source_candidate_notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recipient_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_identity_snapshot", JSONB(), nullable=False),
        sa.Column("source_url_snapshot", sa.Text(), nullable=False),
        sa.Column("latest_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger()),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "recipient_chat_id <> 0",
            name=op.f(
                "ck_owner_source_candidate_notifications_recipient_chat_id_nonzero"
            ),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_identity_snapshot) = 'object'",
            name=op.f(
                "ck_owner_source_candidate_notifications_source_identity_snapshot_object"
            ),
        ),
        sa.CheckConstraint(
            "source_url_snapshot = btrim(source_url_snapshot) "
            "AND source_url_snapshot <> ''",
            name=op.f(
                "ck_owner_source_candidate_notifications_source_url_snapshot_nonempty"
            ),
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'sent', 'failed')",
            name=op.f("ck_owner_source_candidate_notifications_status_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'reserved' AND sent_at IS NULL "
            "AND telegram_message_id IS NULL AND failure_code IS NULL) OR "
            "(status = 'sent' AND sent_at IS NOT NULL "
            "AND telegram_message_id IS NOT NULL AND failure_code IS NULL) OR "
            "(status = 'failed' AND sent_at IS NULL "
            "AND telegram_message_id IS NULL AND failure_code IS NOT NULL)",
            name=op.f(
                "ck_owner_source_candidate_notifications_status_payload_consistent"
            ),
        ),
        sa.CheckConstraint(
            "sent_at IS NULL OR sent_at >= attempted_at",
            name=op.f("ck_owner_source_candidate_notifications_sent_after_attempt"),
        ),
        sa.UniqueConstraint(
            "recipient_chat_id",
            "source_id",
            name=op.f("uq_owner_source_candidate_notifications_recipient_source"),
        ),
    )
    op.create_index(
        "ix_owner_source_candidate_notifications_source",
        "owner_source_candidate_notifications",
        ["source_id"],
    )
    op.create_index(
        "ix_owner_source_candidate_notifications_status_attempted",
        "owner_source_candidate_notifications",
        ["status", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_owner_source_candidate_notifications_status_attempted",
        table_name="owner_source_candidate_notifications",
    )
    op.drop_index(
        "ix_owner_source_candidate_notifications_source",
        table_name="owner_source_candidate_notifications",
    )
    op.drop_table("owner_source_candidate_notifications")
