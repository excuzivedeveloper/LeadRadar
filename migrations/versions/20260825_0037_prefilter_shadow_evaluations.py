"""Add V2 legacy prefilter shadow telemetry.

Revision ID: 20260825_0037
Revises: 20260818_0036
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260825_0037"
down_revision: str | None = "20260818_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_prefilter_shadow_evaluations",
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("filter_config_sha256", sa.String(64), nullable=False),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("matched_keywords", postgresql.JSONB(), nullable=False),
        sa.Column("rejected_by", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["raw_message_id"],
            ["raw_messages.id"],
            name=op.f(
                "fk_message_prefilter_shadow_evaluations_raw_message_id_raw_messages"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "raw_message_id",
            name=op.f("pk_message_prefilter_shadow_evaluations"),
        ),
        sa.CheckConstraint(
            "schema_version ~ '^[a-z][a-z0-9_.-]{0,31}$'",
            name=op.f("ck_message_prefilter_shadow_evaluations_schema_version_safe"),
        ),
        sa.CheckConstraint(
            "length(filter_config_sha256) = 64 "
            "AND filter_config_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f(
                "ck_message_prefilter_shadow_evaluations_filter_config_sha256_valid"
            ),
        ),
        sa.CheckConstraint(
            "min_score > 0",
            name=op.f("ck_message_prefilter_shadow_evaluations_min_score_positive"),
        ),
        sa.CheckConstraint(
            "score >= 0",
            name=op.f("ck_message_prefilter_shadow_evaluations_score_nonnegative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(matched_keywords) = 'array' "
            "AND jsonb_array_length(matched_keywords) <= 64",
            name=op.f(
                "ck_message_prefilter_shadow_evaluations_matched_keywords_array_bounded"
            ),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(rejected_by) = 'array' "
            "AND jsonb_array_length(rejected_by) <= 64",
            name=op.f("ck_message_prefilter_shadow_evaluations_rejected_by_array_bounded"),
        ),
    )


def downgrade() -> None:
    op.drop_table("message_prefilter_shadow_evaluations")
