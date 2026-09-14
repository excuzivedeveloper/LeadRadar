"""Add durable owner candidate probe cooldown state.

Revision ID: 20260914_0043
Revises: 20260908_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260914_0043"
down_revision: str | None = "20260908_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_source_candidate_probe_state",
        sa.Column("recipient_chat_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "search_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("search_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "discovery_intent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("profile_discovery_intents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("profile_revision", sa.Integer(), nullable=False),
        sa.Column("last_outcome", sa.String(32), nullable=False),
        sa.Column("consecutive_outcomes", sa.Integer(), nullable=False),
        sa.Column("last_probed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_probe_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("ck_owner_source_candidate_probe_state_recipient_chat_id_nonzero"),
        ),
        sa.CheckConstraint(
            "profile_revision >= 1",
            name=op.f("ck_owner_source_candidate_probe_state_profile_revision_positive"),
        ),
        sa.CheckConstraint(
            "consecutive_outcomes >= 1",
            name=op.f("ck_owner_source_candidate_probe_state_consecutive_outcomes_positive"),
        ),
        sa.CheckConstraint(
            "last_outcome IN ('stale_or_empty', 'unresolvable')",
            name=op.f("ck_owner_source_candidate_probe_state_last_outcome_valid"),
        ),
        sa.CheckConstraint(
            "next_probe_at > last_probed_at",
            name=op.f("ck_owner_source_candidate_probe_state_next_after_last"),
        ),
    )
    op.create_index(
        "ix_owner_source_candidate_probe_state_recipient_next_probe",
        "owner_source_candidate_probe_state",
        ["recipient_chat_id", "next_probe_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_owner_source_candidate_probe_state_recipient_next_probe",
        table_name="owner_source_candidate_probe_state",
    )
    op.drop_table("owner_source_candidate_probe_state")
