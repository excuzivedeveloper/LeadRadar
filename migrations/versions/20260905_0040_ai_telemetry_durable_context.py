"""Add durable job context to AI telemetry.

Revision ID: 20260905_0040
Revises: 20260904_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260905_0040"
down_revision: str | None = "20260904_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_call_telemetry",
        sa.Column("durable_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "ai_call_telemetry",
        sa.Column("durable_attempt", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_ai_call_telemetry_durable_job_id_durable_jobs"),
        "ai_call_telemetry",
        "durable_jobs",
        ["durable_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_ai_call_telemetry_durable_attempt_bounded"),
        "ai_call_telemetry",
        "durable_attempt IS NULL OR durable_attempt BETWEEN 1 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_ai_call_telemetry_durable_attempt_bounded"),
        "ai_call_telemetry",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_ai_call_telemetry_durable_job_id_durable_jobs"),
        "ai_call_telemetry",
        type_="foreignkey",
    )
    op.drop_column("ai_call_telemetry", "durable_attempt")
    op.drop_column("ai_call_telemetry", "durable_job_id")
